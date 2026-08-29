"""
CLASSCAN — TFLite Model Downloader
==================================
Downloads a pre-trained COCO MobileNet SSD TFLite model for immediate bench testing.

Usage:
    python models/download_model.py
"""

import os
import sys
import urllib.request
from pathlib import Path

MODELS_DIR = Path(__file__).resolve().parent
TARGET_FILE = MODELS_DIR / "mobilenet_v2_ssd_classcan.tflite"

# Google's official pre-trained MobileNet SSD quantized TFLite model (COCO dataset)
MODEL_URL = "https://raw.githubusercontent.com/google-coral/test_data/master/ssd_mobilenet_v2_coco_quant_postprocess.tflite"


def download_model():
    print(f"[Model Downloader] Target: {TARGET_FILE}")
    if TARGET_FILE.is_file():
        print(f"[Model Downloader] Model already exists at {TARGET_FILE.name} ({TARGET_FILE.stat().st_size} bytes).")
        return

    print(f"[Model Downloader] Downloading MobileNetV2-SSD model from:\n  {MODEL_URL}\n")
    try:
        def reporthook(blocknum, blocksize, totalsize):
            read = blocknum * blocksize
            if totalsize > 0:
                percent = min(100.0, read * 100.0 / totalsize)
                sys.stdout.write(f"\r  Progress: {percent:5.1f}% ({read // 1024} KB / {totalsize // 1024} KB)")
                sys.stdout.flush()

        urllib.request.urlretrieve(MODEL_URL, TARGET_FILE, reporthook)
        print("\n[Model Downloader] Download complete!")
        print(f"[Model Downloader] Saved to: {TARGET_FILE}")
    except Exception as e:
        print(f"\n[Model Downloader] Download error: {e}")
        print("You can also manually download the .tflite model and place it in the models/ folder.")


if __name__ == "__main__":
    download_model()
