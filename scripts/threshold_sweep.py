"""
Full-dataset threshold sweep: validates whether a density-map confidence
threshold generalizes across ALL 117 real-classroom frames, not just the
10 line1 frames from the earlier quick test.

Ground truth is hardcoded below from the eyeballed counts already collected.

USAGE (on the Pi, same venv, from ~/CLASSCAN):
  python3 scripts/threshold_sweep_full.py \
      --frames-dir extracted_frames \
      --model classcan_density_float32.tflite
"""

import argparse
import os

import cv2
import numpy as np

try:
    from ai_edge_litert.interpreter import Interpreter
except ImportError:
    from tflite_runtime.interpreter import Interpreter


def mid(s):
    s = s.strip()
    if "/" in s:
        a, b = s.split("/")
        return (float(a) + float(b)) / 2
    return float(s)


# ground truth, same data used in the earlier MAE computation
GT_RAW = {
    "line1": "11/12,10/11,9/10,7,5,5,3,3,3,3",
    "line2": "14/15,11/13,12/13,9/10,10/11,9,7,5/6,3/4,3,1,2,4,3/4,6/7,10/11,14,14,12/13,15/16,13/14,12,12",
    "line3": "12/13,13,12/13,10/11,10/11,8,8,7,4,3,3,3,5,4/5,6,11/12,11/13,10/11,10/11,12/13,13/14,11",
    "sit1": "6,6/8,10,8/9,8,7/8,4/5,6/7,7,9,10,9,9,6,4/5,3/5,5,5/6,9/10,10,8,5/6,4,6/7,7,9,10/11,7/8,6,3",
    "sit2": "6,6,6,8,9/10,10/11,9,7,6,5,8,8,10/11,10,11/12,10/12,10,7/9,8/10,6,11,11,10,9,6,6,7,8,12,13/14,11,7",
}
GT = {k: [mid(x) for x in v.split(",")] for k, v in GT_RAW.items()}


def load_interpreter(model_path):
    interpreter = Interpreter(model_path=model_path)
    interpreter.allocate_tensors()
    return interpreter, interpreter.get_input_details(), interpreter.get_output_details()


def get_density_map(frame_path, interpreter, input_details, output_details):
    target_h = input_details[0]["shape"][1]
    target_w = input_details[0]["shape"][2]
    img = cv2.imread(frame_path)
    img = cv2.resize(img, (target_w, target_h))
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    x = np.expand_dims(img, axis=0)

    interpreter.set_tensor(input_details[0]["index"], x)
    interpreter.invoke()
    out = interpreter.get_tensor(output_details[0]["index"])
    dmap = np.squeeze(out)
    if dmap.ndim == 3:
        dmap = dmap[..., 0]
    return dmap


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames-dir", default="extracted_frames")
    ap.add_argument("--model", required=True)
    args = ap.parse_args()

    interpreter, input_details, output_details = load_interpreter(args.model)

    # build ordered (frame_path, gt) pairs matching how class_footage_test.py
    # numbered frames: <clip>_0001.jpg, <clip>_0002.jpg, ... in order
    pairs = []
    missing = []
    for clip, gts in GT.items():
        for i, gt in enumerate(gts, start=1):
            fname = f"{clip}_{i:04d}.jpg"
            fpath = os.path.join(args.frames_dir, fname)
            if os.path.exists(fpath):
                pairs.append((fpath, gt, clip))
            else:
                missing.append(fname)

    if missing:
        print(f"[warn] {len(missing)} expected frames not found, skipping them:")
        for m in missing[:10]:
            print(f"    {m}")
        if len(missing) > 10:
            print(f"    ... and {len(missing)-10} more")

    print(f"[info] loaded {len(pairs)} frame/ground-truth pairs")

    print("[info] computing density maps for all frames (this takes a bit)...")
    dmaps = []
    gts = []
    clips = []
    for fpath, gt, clip in pairs:
        dmaps.append(get_density_map(fpath, interpreter, input_details, output_details))
        gts.append(gt)
        clips.append(clip)
    gts = np.array(gts)

    thresholds = [0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40]

    print(f"\n{'thresh':>8} {'MAE':>8} {'bias':>8} {'corr':>8}  (n={len(dmaps)} frames)")
    best = None
    for t in thresholds:
        preds = []
        for dmap in dmaps:
            cutoff = t * dmap.max()
            filtered = np.where(dmap >= cutoff, dmap, 0.0)
            preds.append(float(filtered.sum()))
        preds = np.array(preds)
        errs = preds - gts
        mae = np.mean(np.abs(errs))
        bias = np.mean(errs)
        corr = np.corrcoef(preds, gts)[0, 1]
        print(f"{t:8.2f} {mae:8.2f} {bias:+8.2f} {corr:8.3f}")
        if best is None or mae < best[1]:
            best = (t, mae, bias, corr)

    print(f"\n[best by MAE] threshold={best[0]:.2f}  MAE={best[1]:.2f}  bias={best[2]:+.2f}  corr={best[3]:.3f}")

    # per-clip breakdown at the best threshold
    print(f"\n=== per-clip breakdown at threshold={best[0]:.2f} ===")
    preds_best = []
    for dmap in dmaps:
        cutoff = best[0] * dmap.max()
        filtered = np.where(dmap >= cutoff, dmap, 0.0)
        preds_best.append(float(filtered.sum()))
    preds_best = np.array(preds_best)
    clips_arr = np.array(clips)
    for clip in GT.keys():
        mask = clips_arr == clip
        if mask.sum() == 0:
            continue
        p = preds_best[mask]
        g = gts[mask]
        mae_c = np.mean(np.abs(p - g))
        bias_c = np.mean(p - g)
        corr_c = np.corrcoef(p, g)[0, 1] if mask.sum() > 1 else float("nan")
        print(f"{clip:8} n={mask.sum():3} MAE={mae_c:6.2f} bias={bias_c:+6.2f} corr={corr_c:6.3f}")


if __name__ == "__main__":
    main()