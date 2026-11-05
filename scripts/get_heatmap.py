#!/usr/bin/env python3
"""
CLASSCAN — Generate Density Heatmap Overlay
==========================================
Generates a colored heatmap overlay from an input image or live camera frame
using the primary v5 density regression model (classcan_v5_final.tflite).

Usage (on the Pi or machine with ai-edge-litert):
    # From an image:
    python scripts/get_heatmap.py --image scripts/extracted_frames/line1_0001.jpg

    # Live from camera:
    python scripts/get_heatmap.py --camera

    # Custom output filename:
    python scripts/get_heatmap.py --image my_frame.jpg --out my_heatmap.jpg
"""

import argparse
import os
import sys
from pathlib import Path

# Add src/pi to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "src" / "pi"))

import cv2
import numpy as np
from detection.detector import DensityDetector
from config import Config as cfg


def generate_heatmap(image_path=None, model_path=None, output_path="heatmap_output.jpg", use_camera=False):
    model = model_path or cfg.DENSITY_V5_PATH or str(BASE_DIR / "models" / "classcan_v5_final.tflite")
    if not os.path.exists(model):
        print(f"[Error] Model not found: {model}")
        return

    print(f"[Heatmap] Loading model: {model}")
    detector = DensityDetector(
        model_path=model,
        force_mock=False,
        density_threshold=0.0,  # v5 uses raw unthresholded density integral
    )

    if use_camera:
        print("[Heatmap] Capturing frame from camera...")
        frame = detector.capture_frame()
    else:
        if not image_path or not os.path.exists(image_path):
            print(f"[Error] Image not found: {image_path}")
            return
        frame = cv2.imread(image_path)
        if frame is None:
            print(f"[Error] Failed to read image: {image_path}")
            return

    # Run inference
    result = detector.predict(frame)
    density_map = result["density_map"]
    count = result["count"]
    raw_sum = result["raw_sum"]

    print(f"[Heatmap] Inferred Raw Sum: {raw_sum:.2f} -> Headcount: {count}")
    print(f"[Heatmap] Density Range:   min={density_map.min():.4f}, max={density_map.max():.4f}")

    # Generate colored heatmap overlay
    norm_map = density_map - density_map.min()
    if norm_map.max() > 0:
        norm_map = norm_map / norm_map.max()
    heat_u8 = (norm_map * 255).astype(np.uint8)
    colored_heat = cv2.applyColorMap(heat_u8, cv2.COLORMAP_JET)

    # Upscale heatmap to match input frame resolution
    h, w = frame.shape[:2]
    colored_heat = cv2.resize(colored_heat, (w, h), interpolation=cv2.INTER_CUBIC)

    # Blend with original frame (60% original image + 40% heatmap)
    overlay = cv2.addWeighted(frame, 0.6, colored_heat, 0.4, 0)

    # Annotate headcount on image
    cv2.putText(
        overlay,
        f"CLASSCAN v5 Count: {count} (raw: {raw_sum:.2f})",
        (20, 45),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )

    cv2.imwrite(output_path, overlay)
    print(f"[Heatmap] Saved heatmap overlay -> {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate CLASSCAN density heatmap")
    parser.add_argument("--image", "-i", default="scripts/extracted_frames/line1_0001.jpg", help="Path to input image")
    parser.add_argument("--model", "-m", default=None, help="Path to .tflite model")
    parser.add_argument("--out", "-o", default="heatmap_output.jpg", help="Output file path")
    parser.add_argument("--camera", action="store_true", help="Capture live from camera device")
    args = parser.parse_args()

    generate_heatmap(
        image_path=args.image,
        model_path=args.model,
        output_path=args.out,
        use_camera=args.camera,
    )

