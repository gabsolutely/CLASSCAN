"""
CLASSCAN — Unified Pi 3B Main Server & Detection Loop
======================================================
Consolidated system runner supporting both live hardware deployments and
camera-less prototype testing.

Features:
  - Automatic hardware detection with seamless simulation/mock fallback
  - Serves the unified web dashboard UI (HTML/CSS/JS)
  - Live MJPEG video stream with HUD overlays
  - Periodic and motion-triggered person detection
  - Multi-zone reconciliation & ESP32 serial relay

Usage:
    # Auto mode (uses hardware if present, falls back to simulation if no camera/model):
    python main.py

    # Force simulation / mock mode:
    python main.py --mock --mock-count 5

    # Run with specific hardware settings:
    python main.py --camera 0 --model models/mobilenet_v2_ssd_classcan.tflite --port 8080

Open http://localhost:8080 or http://<pi-ip>:8080 in your browser.
"""

import argparse
import sys
import time

from config import Config
from comms.dashboard_server import DashboardServer
from comms.serial_bridge import SerialBridge
from detection.change_trigger import ChangeTrigger
from detection.detector import Detector, draw_hud_overlay
from detection.zone_reconciler import ZoneReconciler


def parse_args():
    cfg = Config()
    parser = argparse.ArgumentParser(description="CLASSCAN Pi 3B Main System & Server")
    parser.add_argument("--mock", action="store_true",
                        help="Force mock camera and detector simulation (no hardware required)")
    parser.add_argument("--camera", type=int, default=0,
                        help="OpenCV camera device index (default: 0)")
    parser.add_argument("--model", default=cfg.MODEL_PATH,
                        help=f"Path to TFLite model file (default: {cfg.MODEL_PATH})")
    parser.add_argument("--port", type=int, default=cfg.DASHBOARD_PORT,
                        help=f"HTTP port for the dashboard (default: {cfg.DASHBOARD_PORT})")
    parser.add_argument("--host", default=cfg.DASHBOARD_HOST,
                        help=f"HTTP bind host (default: {cfg.DASHBOARD_HOST})")
    parser.add_argument("--conf", type=float, default=cfg.CONF_THRESHOLD,
                        help=f"Confidence threshold (default: {cfg.CONF_THRESHOLD})")
    parser.add_argument("--serial-port", default=cfg.SERIAL_PORT,
                        help=f"Serial port for ESP32 (default: {cfg.SERIAL_PORT})")
    parser.add_argument("--serial-baud", type=int, default=cfg.SERIAL_BAUD,
                        help=f"Serial baud rate (default: {cfg.SERIAL_BAUD})")
    parser.add_argument("--mock-count", type=int, default=4,
                        help="Initial student count in mock simulation (default: 4)")
    return parser.parse_args()


def main():
    args = parse_args()
    cfg = Config()

    # Override config with CLI options if provided
    cfg.MODEL_PATH = args.model
    cfg.CONF_THRESHOLD = args.conf
    cfg.DASHBOARD_HOST = args.host
    cfg.DASHBOARD_PORT = args.port
    cfg.SERIAL_PORT = args.serial_port
    cfg.SERIAL_BAUD = args.serial_baud

    print("=" * 60)
    print("  CLASSCAN — Pi 3B System Active")
    print("=" * 60)

    # 1. Initialize Subsystems
    detector = Detector(
        model_path=cfg.MODEL_PATH,
        conf_threshold=cfg.CONF_THRESHOLD,
        camera_index=args.camera,
        force_mock=args.mock,
        mock_count=args.mock_count,
    )
    trigger = ChangeTrigger(threshold=cfg.CHANGE_THRESHOLD)
    reconciler = ZoneReconciler(zone_names=list(cfg.ZONE_POSITIONS.keys()))

    serial_bridge = SerialBridge(port=cfg.SERIAL_PORT, baud=cfg.SERIAL_BAUD)
    dashboard = DashboardServer(host=cfg.DASHBOARD_HOST, port=cfg.DASHBOARD_PORT)

    last_count = 0
    last_check_time = time.time()
    last_fps_time = time.time()
    fps_counter = 0
    current_fps = 0.0
    detections = []
    zone_counts = None

    source_tag = "SIMULATED" if detector.is_mock else "HARDWARE"

    print("-" * 60)
    print(f"[CLASSCAN] Dashboard live: http://{cfg.DASHBOARD_HOST}:{cfg.DASHBOARD_PORT}")
    print(f"[CLASSCAN] Video stream:   http://{cfg.DASHBOARD_HOST}:{cfg.DASHBOARD_PORT}/stream")
    print("-" * 60)
    print("Press Ctrl-C to stop.\n")

    try:
        while True:
            # 2. Grab Frame
            frame = detector.capture_frame()
            esp_state = serial_bridge.get_state()  # "idle" | "moving"

            # 3. FPS calculation
            fps_counter += 1
            elapsed_fps = time.time() - last_fps_time
            if elapsed_fps >= 1.0:
                current_fps = fps_counter / elapsed_fps
                fps_counter = 0
                last_fps_time = time.time()

            # 4. Check if detection is due
            significant_change = trigger.check(frame)
            heartbeat_due = (time.time() - last_check_time) >= cfg.HEARTBEAT_INTERVAL

            if (esp_state == "idle" and significant_change) or heartbeat_due or len(detections) == 0:
                last_check_time = time.time()

                if cfg.MODE == "SWEEP":
                    detections = detector.detect(frame)
                    count = len(detections)
                    zone_counts = None
                elif cfg.MODE == "ZONE_CHECK":
                    zone_counts = detector.detect_zones(frame, cfg.ZONE_POSITIONS)
                    count, needs_rescan = reconciler.reconcile(zone_counts, last_count)
                    if needs_rescan:
                        print("[CLASSCAN] Reconciliation mismatch — re-scanning...")
                        zone_counts = detector.detect_zones(frame, cfg.ZONE_POSITIONS)
                        count, _ = reconciler.reconcile(zone_counts, last_count)
                    detections = detector.detect(frame)

                if count != last_count:
                    last_count = count
                    serial_bridge.send_count(count)
                    print(f"[CLASSCAN] Headcount updated -> {count}")

            # 5. Annotate & Push Frame to Dashboard
            top_conf = max((d["score"] for d in detections), default=0.0)
            annotated_frame = draw_hud_overlay(
                frame, detections, fps=current_fps, mode_str=cfg.MODE, source_tag=source_tag
            )
            dashboard.push(
                count=last_count,
                frame=annotated_frame,
                fps=current_fps,
                top_conf=top_conf,
                zones=zone_counts,
                mode=cfg.MODE,
            )

            # 6. Handle Inbound Dashboard Commands
            cmd = dashboard.poll_command()
            if cmd:
                print(f"[CLASSCAN] Command received from dashboard: {cmd}")
                serial_bridge.send_command(cmd)
                if cmd == "MODE_SWEEP":
                    cfg.MODE = "SWEEP"
                elif cmd == "MODE_ZONE":
                    cfg.MODE = "ZONE_CHECK"

            time.sleep(cfg.LOOP_SLEEP)

    except KeyboardInterrupt:
        print("\n[CLASSCAN] Shutting down gracefully...")
    finally:
        serial_bridge.close()
        dashboard.close()
        detector.release()
        print("[CLASSCAN] Stopped.")


if __name__ == "__main__":
    main()
