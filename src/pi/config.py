"""
CLASSCAN — Pi 3B Configuration
All tuneable constants in one place. Override per-deployment.
"""

class Config:
    # ── Serial (Pi 3B ↔ ESP32) ─────────────────────────────────────────────
    SERIAL_PORT   = "/dev/ttyUSB0"   # Adjust to actual device path
    SERIAL_BAUD   = 115200

    # ── Wi-Fi Dashboard ────────────────────────────────────────────────────
    DASHBOARD_HOST = "0.0.0.0"
    DASHBOARD_PORT = 8080

    # ── TFLite Model ───────────────────────────────────────────────────────
    MODEL_PATH      = "models/mobilenet_v2_ssd_classcan.tflite"
    CONF_THRESHOLD  = 0.50            # Person-class confidence cutoff

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

