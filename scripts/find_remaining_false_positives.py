"""
Round 2 hard-negative hunting: runs the FINE-TUNED model across ALL 117
real-footage frames (not just a spot-check), saves a heatmap overlay for
every frame PLUS a cropped patch of every confident density peak.

Unlike the earlier heuristic (which tried to auto-guess false positives by
rank vs true_count, and was wrong ~50% of the time), this script makes NO
guess about which peaks are real heads vs objects. It just extracts every
confident peak as a candidate crop, sorted into per-frame folders, so you
can flip through them fast and manually pull out the new offenders --
faster than opening 117 full heatmap images one at a time, but still 100%
your judgment on what's actually a false positive.

USAGE (on the Pi, same venv, from ~/CLASSCAN):
  python3 scripts/find_remaining_false_positives.py \
      --frames-dir extracted_frames \
      --model classcan_density_hardneg_ft4_float32.tflite \
      --out-dir round2_candidates \
      --min-confidence-rel 0.25

Output:
  round2_candidates/
    heatmaps/              <- full-frame heatmap overlay per frame (117 images)
    crops/                 <- individual cropped peak patches, named by frame+rank
    peaks_summary.csv      <- one row per crop: which frame, confidence, crop filename

WORKFLOW AFTER RUNNING:
  1. Pull round2_candidates/ to your laptop (scp -r)
  2. Skim the heatmaps/ folder FIRST (117 images, but quick to flip through) --
     for each frame, does anything OTHER than a real head look lit up?
  3. For any frame where you spot a suspicious hit, find its matching crops in
     crops/ (same frame name prefix) and confirm which specific peak is the
     offending object
  4. Manually crop/save those specific new offenders into your existing
     manual_clutter_crops/ folder, same as round 1 -- then re-run
     build_manual_hardneg_manifest.py to fold them into the training set
"""

import argparse
import csv
import os

import cv2
import numpy as np
from scipy import ndimage

try:
    from ai_edge_litert.interpreter import Interpreter
except ImportError:
    from tflite_runtime.interpreter import Interpreter


def load_interpreter(model_path):
    interpreter = Interpreter(model_path=model_path)
    interpreter.allocate_tensors()
    return interpreter, interpreter.get_input_details(), interpreter.get_output_details()


def get_density_map(frame_bgr, interpreter, input_details, output_details):
    target_h = input_details[0]["shape"][1]
    target_w = input_details[0]["shape"][2]
    img = cv2.resize(frame_bgr, (target_w, target_h))
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    x = np.expand_dims(img, axis=0)

    interpreter.set_tensor(input_details[0]["index"], x)
    interpreter.invoke()
    out = interpreter.get_tensor(output_details[0]["index"])
    dmap = np.squeeze(out)
    if dmap.ndim == 3:
        dmap = dmap[..., 0]
    return dmap


def find_peaks(dmap, min_distance=5, threshold_rel=0.15):
    """Returns list of (y, x, raw_confidence, relative_confidence), sorted by
    relative confidence descending. NO assumption made about which are real
    heads -- that's left entirely to manual review."""
    max_val = dmap.max()
    if max_val <= 0:
        return []
    thresh = threshold_rel * max_val

    local_max = ndimage.maximum_filter(dmap, size=min_distance) == dmap
    above_thresh = dmap > thresh
    peak_mask = local_max & above_thresh

    ys, xs = np.where(peak_mask)
    peaks = [(int(y), int(x), float(dmap[y, x]), float(dmap[y, x]) / max_val) for y, x in zip(ys, xs)]
    peaks.sort(key=lambda p: -p[3])
    return peaks


def make_heatmap_overlay(frame, dmap):
    heat = dmap - dmap.min()
    if heat.max() > 0:
        heat = heat / heat.max()
    heat_u8 = (heat * 255).astype(np.uint8)
    heat_color = cv2.applyColorMap(heat_u8, cv2.COLORMAP_JET)
    heat_color = cv2.resize(heat_color, (frame.shape[1], frame.shape[0]))
    return cv2.addWeighted(frame, 0.5, heat_color, 0.5, 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames-dir", default="extracted_frames")
    ap.add_argument("--model", required=True)
    ap.add_argument("--out-dir", default="round2_candidates")
    ap.add_argument("--min-confidence-rel", type=float, default=0.25,
                     help="Only crop/list peaks at or above this fraction of the frame's own max density (0-1 scale). Lower = more candidates, higher = fewer/stronger-only.")
    ap.add_argument("--crop-size", type=int, default=120)
    ap.add_argument("--max-peaks-per-frame", type=int, default=8,
                     help="Cap crops per frame so a single noisy frame doesn't dominate output")
    args = ap.parse_args()

    heatmaps_dir = os.path.join(args.out_dir, "heatmaps")
    crops_dir = os.path.join(args.out_dir, "crops")
    os.makedirs(heatmaps_dir, exist_ok=True)
    os.makedirs(crops_dir, exist_ok=True)

    interpreter, input_details, output_details = load_interpreter(args.model)
    print(f"[model] loaded {args.model}")

    frame_files = sorted(
        f for f in os.listdir(args.frames_dir)
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    )
    print(f"[info] found {len(frame_files)} frames to process")

    manifest_rows = []

    for idx, fname in enumerate(frame_files, start=1):
        fpath = os.path.join(args.frames_dir, fname)
        frame = cv2.imread(fpath)
        if frame is None:
            continue
        oh, ow = frame.shape[:2]

        dmap = get_density_map(frame, interpreter, input_details, output_details)
        mh, mw = dmap.shape

        # save the full-frame heatmap for quick visual skimming
        overlay = make_heatmap_overlay(frame, dmap)
        base_name = os.path.splitext(fname)[0]
        cv2.imwrite(os.path.join(heatmaps_dir, f"{base_name}_heatmap.jpg"), overlay)

        # crop individual peaks above the confidence floor
        peaks = find_peaks(dmap)
        peaks_to_crop = [p for p in peaks if p[3] >= args.min_confidence_rel][:args.max_peaks_per_frame]

        for rank, (py, px, raw_conf, rel_conf) in enumerate(peaks_to_crop, start=1):
            oy = int(py / mh * oh)
            ox = int(px / mw * ow)
            half = args.crop_size // 2
            y0, y1 = max(0, oy - half), min(oh, oy + half)
            x0, x1 = max(0, ox - half), min(ow, ox + half)
            crop = frame[y0:y1, x0:x1]
            if crop.size == 0:
                continue

            crop_name = f"{base_name}_peak{rank:02d}_conf{rel_conf:.2f}.jpg"
            cv2.imwrite(os.path.join(crops_dir, crop_name), crop)

            manifest_rows.append({
                "source_frame": fname,
                "crop_file": crop_name,
                "peak_confidence": round(rel_conf, 3),
                "rank_in_frame": rank,
            })

        if idx % 20 == 0 or idx == len(frame_files):
            print(f"[progress] {idx}/{len(frame_files)} frames processed")

    manifest_path = os.path.join(args.out_dir, "peaks_summary.csv")
    with open(manifest_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["source_frame", "crop_file", "peak_confidence", "rank_in_frame"])
        writer.writeheader()
        writer.writerows(manifest_rows)

    print(f"\n[done] processed {len(frame_files)} frames")
    print(f"[done] saved {len(frame_files)} full-frame heatmaps -> {heatmaps_dir}/")
    print(f"[done] saved {len(manifest_rows)} individual peak crops -> {crops_dir}/")
    print(f"[done] summary CSV -> {manifest_path}")
    print()
    print("NEXT: pull this whole folder to your laptop, skim heatmaps/ first to find")
    print("frames with suspicious non-head hits, then check crops/ for that frame to")
    print("isolate the exact offending object. Manually save real offenders into your")
    print("manual_clutter_crops/ folder (round 2), then re-run")
    print("build_manual_hardneg_manifest.py before the next fine-tune.")


if __name__ == "__main__":
    main()