"""
CLASSCAN — Pi 3B Configuration
All tuneable constants in one place. Override per-deployment.
"""

import os
from pathlib import Path

# Paths
BASE_DIR   = Path(__file__).resolve().parent.parent.parent
MODELS_DIR = BASE_DIR / "models"

class Config:
    # ── Serial (Pi 3B ↔ ESP32) ─────────────────────────────────────────────
    SERIAL_PORT = "/dev/ttyUSB0"   # Adjust to actual device path
    SERIAL_BAUD = 115200

    # ── Wi-Fi Dashboard ────────────────────────────────────────────────────
    DASHBOARD_HOST = "0.0.0.0"
    DASHBOARD_PORT = 8080

    # ── TFLite Models ──────────────────────────────────────────────────────

    # ── Priority 1: v5 FINAL ADOPTED headcount engine ──────────────────────
    # classcan_v5_final.tflite — MobileNetV3-Large Density-Map Regression.
    # 5-clip leave-one-out holdout: MAE = 1.47, Pearson r = 0.86, within ±2 = 72%.
    # Single-model runtime ~702 ms on Pi 3B (2x faster than 2-model ensemble).
    # Preprocessing: PIL bilinear gray-114 letterbox to 416x416, 0-255 float32 RGB,
    # unthresholded density map sum (Count L1 training — do NOT apply DENSITY_THRESHOLD).
    _DENSITY_V5     = str(MODELS_DIR / "classcan_v5_final.tflite")
    DENSITY_V5_PATH: str | None = _DENSITY_V5 if os.path.isfile(_DENSITY_V5) else None

    # ── Priority 2: Ensemble fallback (v4 2-model weighted, superseded by v5) ─
    # round4_ep8 (w=0.6, letterbox) + style_aug_ep8 (w=0.4, stretch).
    # MAE = 2.77, r = 0.586, ~1400 ms/frame runtime.
    # Export from Colab Drive checkpoints (see models/README.md):
    #   round4_ep8:    classcan_density_v4_round4_ft_epoch8.weights.h5
    #   style_aug_ep8: classcan_density_style_aug_ft_lowLR_epoch8.weights.h5
    _ENSEMBLE_ROUND4_EP8    = str(MODELS_DIR / "classcan_density_round4_ep8.tflite")
    _ENSEMBLE_STYLE_AUG_EP8 = str(MODELS_DIR / "classcan_density_style_aug_ep8.tflite")

    ENSEMBLE_ROUND4_EP8_PATH: str | None = (
        _ENSEMBLE_ROUND4_EP8 if os.path.isfile(_ENSEMBLE_ROUND4_EP8) else None
    )
    ENSEMBLE_STYLE_AUG_EP8_PATH: str | None = (
        _ENSEMBLE_STYLE_AUG_EP8 if os.path.isfile(_ENSEMBLE_STYLE_AUG_EP8) else None
    )

    # ── Priority 3: Single density-model fallbacks (legacy v4) ─────────────
    # classcan_density_v4_hardneg_ft_epoch4 — used when v5 and ensemble absent.
    # Real-footage: MAE = 3.87, r = 0.448. Regenerate from epoch4 checkpoint.
    # Export: python scripts/export_to_tflite.py --mode density --weights <ckpt>
    _DENSITY_FLOAT32 = str(MODELS_DIR / "classcan_density_float32.tflite")
    _DENSITY_INT8    = str(MODELS_DIR / "classcan_density_int8.tflite")

    # Legacy alias: resolves to v5 path when present, then float32, then int8.
    # Used by DensityDetector() when instantiated directly (not via v5 path).
    DENSITY_MODEL_PATH: str | None = (
        _DENSITY_V5      if os.path.isfile(_DENSITY_V5)      else
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

    # Density thresholds:
    # v5 was trained with Count L1 loss on raw sum — use 0.0 (no threshold).
    # Legacy v4 threshold suppresses background density-map noise.
    DENSITY_V5_THRESHOLD = 0.0
    DENSITY_THRESHOLD    = 0.15  # used by v4 single-model and ensemble fallbacks

    # ── Detection Timing ───────────────────────────────────────────────────
    HEARTBEAT_INTERVAL = 3.0          # Seconds between periodic scans when scene is static
    LOOP_SLEEP         = 0.033        # Seconds between loop iterations (~30 Hz frame poll)
    CHANGE_THRESHOLD   = 0.015        # Frame-diff ratio to trigger immediate re-detect (calibrated for human motion)

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

    # ── Free Wins: Deployment Constraints & Filtering (No Retraining) ──────
    # 1. Physical Capacity Clipping: clamp hallucinations to actual room seats
    MAX_ROOM_CAPACITY = 45
    MAX_ZONE_CAPACITY = {"Q1": 15, "Q2": 15, "Q3": 15, "Q4": 15}

    # 2. Multi-Capture Smoothing: number of frames per quadrant/scan to take median
    MULTI_CAPTURE_COUNT = 3

    # 3. Count Hysteresis: dead-band to prevent 1-count flickering at rounding borders
    COUNT_HYSTERESIS_DELTA = 0.6  # Change must exceed 0.6 float difference to flip int count

    # 4. Zone Exclusion Masks: zero out windows, doors, whiteboard, ceiling before summing
    # Format per zone: list of normalized boxes [ymin, xmin, ymax, xmax] (0.0 - 1.0)
    ZONE_EXCLUSION_MASKS: dict[str, list[list[float]]] = {
        "Q1": [[0.0, 0.0, 0.25, 1.0]],  # example: top 25% ceiling/whiteboard
        "Q2": [[0.0, 0.0, 0.20, 1.0]],
        "Q3": [[0.0, 0.0, 0.20, 1.0]],
        "Q4": [[0.0, 0.0, 0.25, 1.0]],
    }

    # 5. Linear Calibration: (a, b) scaling where calibrated = a * pred + b per pose
    # Default (1.0, 0.0) is uncalibrated identity
    LINEAR_CALIBRATION: dict[str, tuple[float, float]] = {
        "default": (1.0, 0.0),
        "Q1": (1.0, 0.0),
        "Q2": (1.0, 0.0),
        "Q3": (1.0, 0.0),
        "Q4": (1.0, 0.0),
    }

    # 6. Native Resolution ROI Crop: [ymin, xmin, ymax, xmax] normalized
    # When enabled, crops floor area from 2688x1520 native frame before downscaling
    NATIVE_ROI_CROP: list[float] | None = None

    # ── Camera Orientation ─────────────────────────────────────────────────
    # Set True when the camera is mounted upside-down (ceiling-down deployment).
    # The display frame shown in the dashboard is rotated 180° for readability;
    # AI inference always uses the original unflipped frame.
    CAMERA_FLIP: bool = True
