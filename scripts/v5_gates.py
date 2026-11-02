#!/usr/bin/env python3
"""
v5_gates.py - test harness for the CLASSCAN v5 model on the Pi.
Put it next to v5_counter.py (CLASSCAN/scripts/) and run from ~/CLASSCAN with the venv active.

  Gate 1 (Pi vs reference counts, or vs your hand counts):
      python scripts/v5_gates.py folder test_frames --ref ref.csv
      ref.csv lines:  line1_0001,12.0   (name without extension, then the reference count)

  Gate 2 (empty room false positives, from a video):
      python scripts/v5_gates.py video empty_room.mp4 --every 2

  Gate 3 (speed + heat):
      python scripts/v5_gates.py bench test_frames/line1_0001.jpg -n 50

  Gate 4 (live accuracy with a human counting):
      python scripts/v5_gates.py live --out gate4.csv

Add --flip to any command to test flip averaging. Default model: models/classcan_v5_final.tflite
"""
import argparse
import csv
import glob
import os
import statistics
import subprocess
import sys
import time

import cv2

from v5_counter import V5Counter


def cpu_temp():
    try:
        out = subprocess.check_output(["vcgencmd", "measure_temp"], text=True)
        return out.strip().replace("temp=", "")
    except Exception:
        return "n/a"


def make_counter(args):
    return V5Counter(args.model, flip_avg=args.flip)


def load_ref(path):
    ref = {}
    with open(path, newline="") as f:
        for row in csv.reader(f):
            if len(row) >= 2 and row[0].strip() and not row[0].startswith("#"):
                try:
                    ref[os.path.splitext(row[0].strip())[0]] = float(row[1])
                except ValueError:
                    pass
    return ref


# ---------------- Gate 1 ----------------
def cmd_folder(args):
    c = make_counter(args)
    files = sorted(
        p for ext in ("jpg", "jpeg", "png") for p in glob.glob(os.path.join(args.folder, f"*.{ext}"))
    )
    if not files:
        sys.exit(f"no images found in {args.folder}")
    ref = load_ref(args.ref) if args.ref else {}
    diffs = []
    print(f"{'frame':<28}{'pi_count':>10}{'ref':>8}{'diff':>8}")
    for p in files:
        name = os.path.splitext(os.path.basename(p))[0]
        img = cv2.imread(p)
        if img is None:
            print(f"{name:<28}  could not read")
            continue
        n = c.count(img)
        if name in ref:
            d = n - ref[name]
            diffs.append(d)
            flag = "" if abs(d) <= args.tol else "  <-- off"
            print(f"{name:<28}{n:>10.2f}{ref[name]:>8.2f}{d:>+8.2f}{flag}")
        else:
            print(f"{name:<28}{n:>10.2f}{'-':>8}{'-':>8}")
    if diffs:
        mae = sum(abs(d) for d in diffs) / len(diffs)
        bias = sum(diffs) / len(diffs)
        ok = sum(abs(d) <= args.tol for d in diffs)
        print(f"\n{len(diffs)} frames with a reference | MAE {mae:.2f} | bias {bias:+.2f} | "
              f"within +-{args.tol}: {ok}/{len(diffs)}")


# ---------------- Gate 2 ----------------
def cmd_video(args):
    c = make_counter(args)
    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        sys.exit(f"cannot open {args.video}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    step = max(1, int(round(fps * args.every)))
    counts, i = [], 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if i % step == 0:
            n = c.count(frame)
            counts.append(n)
            print(f"t={i / fps:6.1f}s  count={n:.2f}")
        i += 1
    cap.release()
    if not counts:
        sys.exit("no frames counted")
    hits = sum(n >= 2 for n in counts)
    print(f"\n{len(counts)} samples | mean {statistics.mean(counts):.2f} | max {max(counts):.2f} | "
          f"samples >= 2: {hits} ({100 * hits / len(counts):.0f}%)")
    print("For an empty room you want the mean near 0 and almost no samples >= 2.")


# ---------------- Gate 3 ----------------
def cmd_bench(args):
    c = make_counter(args)
    img = cv2.imread(args.image)
    if img is None:
        sys.exit(f"cannot read {args.image}")
    for _ in range(2):  # warm-up, not timed
        c.count(img)
    t0 = cpu_temp()
    times = []
    for _ in range(args.n):
        s = time.perf_counter()
        c.count(img)
        times.append((time.perf_counter() - s) * 1000)
    t1 = cpu_temp()
    times.sort()
    print(f"{args.n} runs (preprocess + inference), flip_avg={args.flip}")
    print(f"mean {statistics.mean(times):.0f} ms | median {statistics.median(times):.0f} ms | "
          f"p95 {times[int(0.95 * (len(times) - 1))]:.0f} ms | max {times[-1]:.0f} ms")
    print(f"temp before {t0} | after {t1}  (keep under 80 C)")
    print(f"one 4-quadrant scan = about {4 * statistics.mean(times) / 1000:.1f} s of inference")


# ---------------- Gate 4 ----------------
def cmd_live(args):
    c = make_counter(args)
    cap = cv2.VideoCapture(args.cam)
    if not cap.isOpened():
        sys.exit(f"cannot open camera {args.cam}")
    if args.width:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    os.makedirs(args.frames_dir, exist_ok=True)
    rows = []
    print("Run your camera settings script first (set_camera_config.sh).")
    print("For each trial: arrange the room, count by hand, type the true number.\n")
    while True:
        s = input("True count (blank to finish): ").strip()
        if not s:
            break
        try:
            truth = float(s)
        except ValueError:
            print("  enter a number")
            continue
        for _ in range(10):  # let exposure settle, discard stale buffered frames
            cap.read()
        ok, frame = cap.read()
        if not ok:
            print("  camera read failed, try again")
            continue
        n = c.count(frame)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        cv2.imwrite(os.path.join(args.frames_dir, f"live_{stamp}_true{s}.jpg"), frame)
        rows.append((stamp, truth, n, n - truth))
        print(f"  CLASSCAN {n:.2f} | truth {truth:g} | error {n - truth:+.2f}")
    cap.release()
    if not rows:
        return
    with open(args.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["time", "true", "pred", "error"])
        w.writerows(rows)
    errs = [r[3] for r in rows]
    mae = sum(abs(e) for e in errs) / len(errs)
    within2 = sum(abs(e) <= 2 for e in errs)
    print(f"\n{len(rows)} trials | MAE {mae:.2f} | bias {sum(errs) / len(errs):+.2f} | "
          f"within +-2: {within2}/{len(rows)} | saved to {args.out}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--model", default="models/classcan_v5_final.tflite")
    ap.add_argument("--flip", action="store_true", help="flip averaging (2x time)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("folder")
    p.add_argument("folder")
    p.add_argument("--ref", help="csv: name,count")
    p.add_argument("--tol", type=float, default=0.2, help="pass tolerance (default 0.2)")
    p.set_defaults(fn=cmd_folder)

    p = sub.add_parser("video")
    p.add_argument("video")
    p.add_argument("--every", type=float, default=2.0, help="seconds between samples")
    p.set_defaults(fn=cmd_video)

    p = sub.add_parser("bench")
    p.add_argument("image")
    p.add_argument("-n", type=int, default=50)
    p.set_defaults(fn=cmd_bench)

    p = sub.add_parser("live")
    p.add_argument("--cam", type=int, default=0)
    p.add_argument("--width", type=int, default=0)
    p.add_argument("--height", type=int, default=0)
    p.add_argument("--out", default="gate4.csv")
    p.add_argument("--frames-dir", default="gate4_frames")
    p.set_defaults(fn=cmd_live)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()