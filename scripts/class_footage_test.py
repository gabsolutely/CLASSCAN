"""
Real-classroom-footage domain-gap test for CLASSCAN density-map model.

Run this ON THE PI. Assumes:
  - ffmpeg is installed (sudo apt install ffmpeg if not)
  - your TFLite model file (float32 export, e.g. classcan_density_v4.tflite)
  - two video clips already copied onto the Pi (see step 0 below)

USAGE:
  python3 classroom_footage_test.py \
      --video clip_line.mp4 \
      --video clip_sitting.mp4 \
      --model classcan_density_v4.tflite \
      --fps 1 \
      --out results.csv

STEP 0 — get the files onto the Pi from Drive:
  On your laptop (with the Drive folder synced, or after downloading manually):
    scp clip_line.mp4 clip_sitting.mp4 classcan_density_v4.tflite \
        gabsolutely@<pi-ip>:~/footage_test/

  Or, if you'd rather pull straight from Drive to the Pi without going through
  the laptop: install gdown on the Pi (`pip install gdown`) and use
  `gdown --id <file_id>` for each file (get the file_id from the Drive share link).
"""

import argparse
import csv
import os
import subprocess
import sys

import numpy as np

try:
    from ai_edge_litert.interpreter import Interpreter
except ImportError:
    from tflite_runtime.interpreter import Interpreter  # fallback name

import cv2


def extract_frames(video_path: str, out_dir: str, fps: int) -> list:
    """Extract frames at the given fps using ffmpeg. Returns sorted list of frame paths."""
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(video_path))[0]
    pattern = os.path.join(out_dir, f"{base}_%04d.jpg")

    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vf", f"fps={fps}",
        "-q:v", "2",
        pattern,
    ]
    print(f"[extract] {video_path} -> {out_dir} @ {fps}fps")
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    frames = sorted(
        os.path.join(out_dir, f) for f in os.listdir(out_dir)
        if f.startswith(base) and f.endswith(".jpg")
    )
    print(f"[extract] got {len(frames)} frames")
    return frames


def load_interpreter(model_path: str):
    interpreter = Interpreter(model_path=model_path)
    interpreter.allocate_tensors()
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()
    return interpreter, input_details, output_details


def preprocess(frame_path: str, target_hw):
    h, w = target_hw
    img = cv2.imread(frame_path)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img = cv2.resize(img, (w, h))
    img = img.astype(np.float32) / 255.0
    img = np.expand_dims(img, axis=0)
    return img


def run_inference(interpreter, input_details, output_details, frame_path: str):
    target_h = input_details[0]["shape"][1]
    target_w = input_details[0]["shape"][2]
    x = preprocess(frame_path, (target_h, target_w))

    interpreter.set_tensor(input_details[0]["index"], x)
    interpreter.invoke()
    out = interpreter.get_tensor(output_details[0]["index"])

    # Density-map output: sum the map to get the predicted count.
    # If your model's output head is already a scalar count, this just
    # collapses trivially — adjust here if your output shape differs.
    predicted_count = float(np.sum(out))
    return predicted_count


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", action="append", required=True,
                     help="Path to a video clip. Repeat --video for multiple clips.")
    ap.add_argument("--model", required=True, help="Path to .tflite model file")
    ap.add_argument("--fps", type=int, default=1, help="Frame extraction rate (default 1fps)")
    ap.add_argument("--out", default="results.csv", help="Output CSV path")
    ap.add_argument("--frames-dir", default="extracted_frames", help="Where to save extracted frames")
    args = ap.parse_args()

    interpreter, input_details, output_details = load_interpreter(args.model)
    print(f"[model] loaded {args.model}")
    print(f"[model] input shape: {input_details[0]['shape']}")

    rows = []
    for video_path in args.video:
        frames = extract_frames(video_path, args.frames_dir, args.fps)
        for i, frame_path in enumerate(frames):
            pred = run_inference(interpreter, input_details, output_details, frame_path)
            print(f"  {os.path.basename(frame_path)}: predicted={pred:.2f}")
            rows.append({
                "clip": os.path.basename(video_path),
                "frame": os.path.basename(frame_path),
                "frame_index": i,
                "predicted_count": round(pred, 2),
                "eyeballed_count": "",  # fill in by hand after watching the clip
            })

    with open(args.out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["clip", "frame", "frame_index", "predicted_count", "eyeballed_count"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n[done] wrote {len(rows)} rows to {args.out}")
    print("Open the extracted frames, eyeball the actual headcount per frame,")
    print("fill in the eyeballed_count column, then compare vs predicted_count.")


if __name__ == "__main__":
    main()