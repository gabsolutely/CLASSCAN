"""
Hard-negative training-data prep for CLASSCAN density-map retraining.

WHAT THIS DOES:
Your model is confidently predicting head-level density on bags, chairs,
and clutter. The real fix is retraining with explicit examples showing
"this region has zero heads" -- not thresholding the output after the
fact. This script builds those training examples from footage you
ALREADY have and have ALREADY eyeballed.

APPROACH:
For each of your 117 frames (known ground truth count already collected),
this script:
  1. Runs the current model to get the predicted density map
  2. Finds "hot" regions (localized density peaks) in the map
  3. Since you know the true head count for the frame, if the model
     predicts more localized peaks than the true count, the EXTRA peaks
     are very likely false positives on background objects
  4. Crops those extra-peak regions from the original image as candidate
     hard-negative training examples --  patches that LOOK confident to
     the model but are NOT heads

This does NOT auto-label anything as certain -- it flags candidates for
YOU to quickly visually confirm (yes-this-is-a-bag / no-actually-a-head)
before they go into a retraining set. That confirmation step matters:
a wrongly-labeled "hard negative" that's actually a real head would
poison training in the opposite direction.

OUTPUT:
  hard_negative_candidates/
    <frame>_peak01_conf0.82.jpg   <- cropped candidate patch
    <frame>_peak02_conf0.65.jpg
    ...
    candidates_manifest.csv        <- for you to fill in a confirm column

USAGE (on the Pi, same venv, from ~/CLASSCAN):
  python3 scripts/extract_hard_negatives.py \
      --frames-dir extracted_frames \
      --model classcan_density_float32.tflite \
      --out-dir hard_negative_candidates
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


def mid(s):
    s = s.strip()
    if "/" in s:
        a, b = s.split("/")
        return (float(a) + float(b)) / 2
    return float(s)


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
    """Find local density peaks (candidate 'head' detections) in the map."""
    max_val = dmap.max()
    if max_val <= 0:
        return []
    thresh = threshold_rel * max_val

    # local maxima via maximum filter
    local_max = ndimage.maximum_filter(dmap, size=min_distance) == dmap
    above_thresh = dmap > thresh
    peak_mask = local_max & above_thresh

    ys, xs = np.where(peak_mask)
    peaks = [(int(y), int(x), float(dmap[y, x])) for y, x in zip(ys, xs)]
    # sort by confidence descending
    peaks.sort(key=lambda p: -p[2])
    return peaks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames-dir", default="extracted_frames")
    ap.add_argument("--model", required=True)
    ap.add_argument("--out-dir", default="hard_negative_candidates")
    ap.add_argument("--crop-size", type=int, default=120, help="Size of the cropped patch around each candidate peak (in original image pixels)")
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    interpreter, input_details, output_details = load_interpreter(args.model)
    target_h = input_details[0]["shape"][1]
    target_w = input_details[0]["shape"][2]

    manifest_rows = []

    for clip, gts in GT.items():
        for i, gt in enumerate(gts, start=1):
            fname = f"{clip}_{i:04d}.jpg"
            fpath = os.path.join(args.frames_dir, fname)
            if not os.path.exists(fpath):
                continue

            frame = cv2.imread(fpath)
            oh, ow = frame.shape[:2]
            dmap = get_density_map(frame, interpreter, input_details, output_details)
            mh, mw = dmap.shape

            peaks = find_peaks(dmap)
            true_count = int(round(gt))

            # only the peaks BEYOND the true count are candidate false positives
            # (since peaks are sorted by confidence descending, the top `true_count`
            # are the most likely to be real heads; anything past that is suspect)
            extra_peaks = peaks[true_count:]

            for j, (py, px, conf) in enumerate(extra_peaks):
                # map peak coords from density-map space back to original image space
                oy = int(py / mh * oh)
                ox = int(px / mw * ow)

                half = args.crop_size // 2
                y0, y1 = max(0, oy - half), min(oh, oy + half)
                x0, x1 = max(0, ox - half), min(ow, ox + half)
                crop = frame[y0:y1, x0:x1]

                if crop.size == 0:
                    continue

                crop_name = f"{clip}_{i:04d}_peak{j+1:02d}_conf{conf:.2f}.jpg"
                cv2.imwrite(os.path.join(args.out_dir, crop_name), crop)

                manifest_rows.append({
                    "source_frame": fname,
                    "crop_file": crop_name,
                    "peak_confidence": round(conf, 3),
                    "frame_true_count": true_count,
                    "frame_model_peak_count": len(peaks),
                    "confirmed_not_a_head": "",  # fill in: yes/no after visual check
                })

    manifest_path = os.path.join(args.out_dir, "candidates_manifest.csv")
    with open(manifest_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "source_frame", "crop_file", "peak_confidence",
            "frame_true_count", "frame_model_peak_count", "confirmed_not_a_head",
        ])
        writer.writeheader()
        writer.writerows(manifest_rows)

    print(f"\n[done] extracted {len(manifest_rows)} candidate hard-negative crops")
    print(f"[done] saved to {args.out_dir}/")
    print(f"[done] manifest: {manifest_path}")
    print()
    print("NEXT STEPS:")
    print("1. scp the whole folder to your laptop:")
    print(f"   scp -r gabsolutely@<pi-ip>:~/CLASSCAN/{args.out_dir} .")
    print("2. Open each crop image, check if it's genuinely NOT a head (bag/chair/clutter)")
    print("   vs. actually a real head the peak-counting heuristic mislabeled.")
    print("3. Fill in confirmed_not_a_head = yes/no per row in the manifest CSV.")
    print("4. Only the 'yes' (confirmed non-head) crops become real hard-negative")
    print("   training examples -- pair each with a zero-density training target")
    print("   the next time you have Colab GPU time for a retrain.")


if __name__ == "__main__":
    main()