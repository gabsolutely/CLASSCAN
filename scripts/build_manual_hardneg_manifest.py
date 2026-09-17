"""
Converts MANUALLY cropped clutter images (chairs, bags, fans, tables --
things you personally identified and cropped, no guessing) into the
zero-density training format the fine-tune script expects.

No peak-detection, no confidence heuristics, no guessing which crops are
real heads. You already know these are clutter because you cropped them
yourself while looking at the frame. This script just packages them.

USAGE:
  1. Manually crop clutter objects (chairs, bags, fans, tables, etc.) from
     your extracted_frames/ images using any tool -- Paint, Preview, GIMP,
     or even just running this with --interactive to crop via OpenCV.
  2. Put all your crops in one folder, e.g. manual_clutter_crops/
  3. Run this script to build the manifest CSV automatically -- since YOU
     already confirmed these are clutter by cropping them, every row is
     pre-marked confirmed_not_a_head=yes. No sorting needed.

     python3 build_manual_hardneg_manifest.py \
         --crops-dir manual_clutter_crops \
         --out-dir manual_clutter_crops

This produces manual_clutter_crops/candidates_manifest.csv, ready to
upload to Drive alongside the crops for colab_hardneg_finetune.py.
"""

import argparse
import csv
import os


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--crops-dir", required=True, help="Folder containing your manually cropped clutter images")
    ap.add_argument("--out-dir", default=None, help="Where to write the manifest CSV (defaults to --crops-dir)")
    args = ap.parse_args()

    out_dir = args.out_dir or args.crops_dir
    os.makedirs(out_dir, exist_ok=True)

    valid_exts = (".jpg", ".jpeg", ".png")
    crop_files = sorted(
        f for f in os.listdir(args.crops_dir)
        if f.lower().endswith(valid_exts)
    )

    if not crop_files:
        print(f"[warn] no image files found in {args.crops_dir}")
        print("Make sure your manually cropped images are directly inside this folder.")
        return

    manifest_path = os.path.join(out_dir, "candidates_manifest.csv")
    with open(manifest_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "source_frame", "crop_file", "peak_confidence",
            "frame_true_count", "frame_model_peak_count", "confirmed_not_a_head",
        ])
        writer.writeheader()
        for crop_file in crop_files:
            writer.writerow({
                "source_frame": "manual",       # not tracked -- these were hand-picked, not extracted from a specific known frame/GT pair
                "crop_file": crop_file,
                "peak_confidence": "",           # not applicable, no heuristic was used
                "frame_true_count": "",          # not applicable
                "frame_model_peak_count": "",    # not applicable
                "confirmed_not_a_head": "yes",   # pre-confirmed: you cropped it yourself, you already know
            })

    print(f"[done] wrote manifest for {len(crop_files)} manually-cropped clutter images")
    print(f"[done] {manifest_path}")
    print()
    print("Every row is pre-marked confirmed_not_a_head=yes since you cropped")
    print("these yourself while looking directly at the frame -- no review needed.")
    print()
    print("Next: upload this whole folder to Google Drive at the path")
    print("expected by colab_hardneg_finetune.py (HARD_NEG_DIR), then run that")
    print("script whenever you have Colab GPU time.")


if __name__ == "__main__":
    main()