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

    # ── Ensemble (FINAL ADOPTED — drop these two files into models/) ───────
    # Export from Colab Drive checkpoints (see models/README.md):
    #   round4_ep8:    classcan_density_v4_round4_ft_epoch8.weights.h5
    #   style_aug_ep8: classcan_density_style_aug_ft_lowLR_epoch8.weights.h5
    # When both are present, main.py uses EnsembleDensityDetector (MAE=2.77, r=0.586).
    _ENSEMBLE_ROUND4_EP8    = str(MODELS_DIR / "classcan_density_round4_ep8.tflite")
    _ENSEMBLE_STYLE_AUG_EP8 = str(MODELS_DIR / "classcan_density_style_aug_ep8.tflite")

    ENSEMBLE_ROUND4_EP8_PATH: str | None = (
        _ENSEMBLE_ROUND4_EP8 if os.path.isfile(_ENSEMBLE_ROUND4_EP8) else None
    )
    ENSEMBLE_STYLE_AUG_EP8_PATH: str | None = (
        _ENSEMBLE_STYLE_AUG_EP8 if os.path.isfile(_ENSEMBLE_STYLE_AUG_EP8) else None
    )

    # ── Single density-model fallbacks (legacy / partial deploy) ───────────
    # classcan_density_v4_hardneg_ft_epoch4 — used when ensemble files are absent.
    #   Fine-tuned on 176 hard-negative crops. Real-footage: MAE=3.87 (↓59%), r=0.448.
    #   ⚠️  Regenerate from epoch4 checkpoint before use.
    #   Export: python scripts/export_to_tflite.py --mode density --weights classcan_density_v4_hardneg_ft_epoch4.weights.h5
    _DENSITY_FLOAT32 = str(MODELS_DIR / "classcan_density_float32.tflite")
    _DENSITY_INT8    = str(MODELS_DIR / "classcan_density_int8.tflite")

    # Resolved at startup — float32 first, int8 second, None if neither present
    DENSITY_MODEL_PATH: str | None = (
        _DENSITY_FLOAT32 if os.path.isfile(_DENSITY_FLOAT32) else
        _DENSITY_INT8    if os.path.isfile(_DENSITY_INT8)    else
        None
    )

    # ── Box detector (HUD bounding-box overlay) ────────────────────────────
    # classcan_head_v1 if exported, else COCO SSD fallback (smoke-test only)
    _HEAD_MODEL     = str(MODELS_DIR / "classcan_head_v1.tflite")
    _FALLBACK_MODEL = str(MODELS_DIR / "mobilenet_v2_ssd_classcan.tflite")

    HEAD_MODEL_PATH = _HEAD_MODEL if os.path.isfile(_HEAD_MODEL) else _FALLBACK_MODEL
    MODEL_PATH      = HEAD_MODEL_PATH  # legacy alias used by Detector() and --model CLI

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
