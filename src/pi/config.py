"""
CLASSCAN — Pi 3B Configuration
All tuneable constants in one place. Override per-deployment.
"""

import os
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent
MODELS_DIR = BASE_DIR / "models"

class Config:
    # ── Serial (Pi 3B ↔ ESP32) ─────────────────────────────────────────────
    SERIAL_PORT   = "/dev/ttyUSB0"   # Adjust to actual device path
    SERIAL_BAUD   = 115200

    # ── Wi-Fi Dashboard ────────────────────────────────────────────────────
    DASHBOARD_HOST = "0.0.0.0"
    DASHBOARD_PORT = 8080

    # ── TFLite Models ──────────────────────────────────────────────────────
    # Primary headcount engine: classcan_density_v4_hardneg_ft_epoch4 (ADOPTED model).
    #   Fine-tuned on 176 hard-negative real-footage crops (bags, chairs, tables, etc.)
    #   from classcan_density_v4_best. Real-footage: MAE=3.87 (↓59%), r=0.448 (↑).
    #   SCUT-HEAD 407-image check held: MAE=2.35, r=0.9908.
    #   ⚠️  models/classcan_density_float32.tflite must be regenerated from epoch4 checkpoint.
    #   Export: python scripts/export_to_tflite.py --mode density --weights classcan_density_v4_hardneg_ft_epoch4.weights.h5
    _DENSITY_FLOAT32 = str(MODELS_DIR / "classcan_density_float32.tflite")
    _DENSITY_INT8    = str(MODELS_DIR / "classcan_density_int8.tflite")


    # Secondary box detector: MobileNetV3-Large @ 416x416 (HUD bounding boxes).
    #   Export: python scripts/export_to_tflite.py --weights ckpt_ep60.weights.h5
    # Fallback: COCO MobileNetV2-SSD (smoke-test only — undercounts occluded students)
    _HEAD_MODEL      = str(MODELS_DIR / "classcan_head_v1.tflite")
    _FALLBACK_MODEL  = str(MODELS_DIR / "mobilenet_v2_ssd_classcan.tflite")

    # Resolved at startup — float32 first, int8 second, None if neither present
    DENSITY_MODEL_PATH: str | None = (
        _DENSITY_FLOAT32 if os.path.isfile(_DENSITY_FLOAT32) else
        _DENSITY_INT8    if os.path.isfile(_DENSITY_INT8)    else
        None
    )

    # Box detector path (classcan_head_v1 if exported, else COCO SSD fallback)
    HEAD_MODEL_PATH = _HEAD_MODEL if os.path.isfile(_HEAD_MODEL) else _FALLBACK_MODEL

    # Legacy alias used by Detector() and --model CLI flag
    MODEL_PATH = HEAD_MODEL_PATH

    CONF_THRESHOLD  = 0.35            # Objectness threshold — calibrated for count accuracy (MAE 3.57, r=0.987)
                                      # (use 0.50 if falling back to COCO SSD model)

    # Per-frame relative density threshold: zero out density_map values below this
    # fraction of the frame's own max before summing for headcount.
    # Adopted alongside classcan_density_v4_hardneg_ft_epoch4 (real-footage MAE 3.87→3.08).
    # Set to 0.0 to use raw unthresholded sum (matches original v4 SCUT-HEAD eval).
    DENSITY_THRESHOLD = 0.15

    # ── Detection Timing ───────────────────────────────────────────────────
    HEARTBEAT_INTERVAL = 10.0         # Seconds between periodic scans
    LOOP_SLEEP         = 0.05         # Seconds between loop iterations (~20 Hz frame poll)
    CHANGE_THRESHOLD   = 0.15         # Frame-diff ratio to trigger immediate re-detect

    # ── Mode ("SWEEP" | "ZONE_CHECK") ──────────────────────────────────────
    MODE = "SWEEP"

    # ── Zone/Quadrant Config ───────────────────────────────────────────────
    # Named zones with (pan_deg, tilt_deg) servo positions.
    # Calibrate physical servo angles per deployment.
    # Note: Headcount per zone is counted dynamically by the detector,
    # not configured or pre-set.
    ZONE_POSITIONS = {
        "Q1": (0,   30),
        "Q2": (90,  30),
        "Q3": (180, 30),
        "Q4": (270, 30),
    }
