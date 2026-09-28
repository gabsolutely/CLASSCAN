"""
CLASSCAN - Unified Pi 3B Main Server and Detection Loop
======================================================
Consolidated system runner supporting both live hardware deployments and
camera-less prototype testing.

Features:
  - Automatic hardware detection with seamless simulation/mock fallback
  - Serves the unified web dashboard UI (HTML/CSS/JS)
  - Live MJPEG video stream with HUD overlays
  - Periodic and motion-triggered person detection
  - Multi-zone reconciliation and ESP32 serial relay

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
import threading
import time

from config import Config
from comms.dashboard_server import DashboardServer
from comms.serial_bridge import SerialBridge
from detection.change_trigger import ChangeTrigger
from detection.detector import Detector, DensityDetector, EnsembleDensityDetector, draw_hud_overlay
from detection.zone_reconciler import ZoneReconciler
from setup.startup import run_boot_sequence


def parse_args():
    cfg = Config()
    parser = argparse.ArgumentParser(description="CLASSCAN Pi 3B Main System and Server")
    parser.add_argument("--mock", action="store_true",
                        help="Force mock camera and detector simulation (no hardware required)")
    parser.add_argument("--camera", type=int, default=0,
                        help="OpenCV camera device index (default: 0)")
    parser.add_argument("--model", default=cfg.MODEL_PATH,
                        help=f"Path to box detector .tflite (default: {cfg.MODEL_PATH})")
    parser.add_argument("--density-model", default=cfg.DENSITY_MODEL_PATH,
                        help="Path to density-map .tflite (default: auto-detect float32/int8)")
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
    parser.add_argument("--skip-boot-check", action="store_true",
                        help="Skip the hardware self-test boot sequence entirely")
    return parser.parse_args()


def main():
    args = parse_args()
    cfg = Config()

    # Override config with CLI options if provided
    cfg.MODEL_PATH         = args.model
    cfg.DENSITY_MODEL_PATH = args.density_model
    cfg.CONF_THRESHOLD     = args.conf
    cfg.DASHBOARD_HOST     = args.host
    cfg.DASHBOARD_PORT     = args.port
    cfg.SERIAL_PORT        = args.serial_port
    cfg.SERIAL_BAUD        = args.serial_baud

    # Hardware self-test
    if not args.mock and not args.skip_boot_check:
        if cfg.ENSEMBLE_ROUND4_EP8_PATH and cfg.ENSEMBLE_STYLE_AUG_EP8_PATH:
            boot_density_path  = cfg.ENSEMBLE_ROUND4_EP8_PATH
            boot_density_path2 = cfg.ENSEMBLE_STYLE_AUG_EP8_PATH
        else:
            boot_density_path  = cfg.DENSITY_MODEL_PATH
            boot_density_path2 = None

        run_boot_sequence(
            camera_index=args.camera,
            model_path=cfg.MODEL_PATH,
            density_model_path=boot_density_path,
            density_model_path2=boot_density_path2,
            serial_port=cfg.SERIAL_PORT,
            serial_baud=cfg.SERIAL_BAUD,
        )

    print("=" * 60)
    print("  CLASSCAN - Pi 3B System Active")
    print("=" * 60)

    # 1. Initialize Subsystems

    # Primary headcount engine: ensemble (final adopted) or single-model fallback
    density_detector = None
    if cfg.ENSEMBLE_ROUND4_EP8_PATH and cfg.ENSEMBLE_STYLE_AUG_EP8_PATH:
        density_detector = EnsembleDensityDetector(
            round4_ep8_path=cfg.ENSEMBLE_ROUND4_EP8_PATH,
            style_aug_ep8_path=cfg.ENSEMBLE_STYLE_AUG_EP8_PATH,
            camera_index=args.camera,
            force_mock=args.mock,
            mock_count=args.mock_count,
        )
    elif cfg.DENSITY_MODEL_PATH:
        print("[CLASSCAN] Ensemble files not found - falling back to single density model.")
        print(f"           To enable ensemble: export classcan_density_round4_ep8.tflite and")
        print(f"           classcan_density_style_aug_ep8.tflite into models/ (see models/README.md)")
        density_detector = DensityDetector(
            model_path=cfg.DENSITY_MODEL_PATH,
            camera_index=args.camera,
            force_mock=args.mock,
            mock_count=args.mock_count,
        )
    else:
        print("[CLASSCAN] WARNING: No density model found. Headcount will use box detector count.")
        print("           Expected: models/classcan_density_round4_ep8.tflite +")
        print("                     models/classcan_density_style_aug_ep8.tflite")
        print("           (or legacy fallback: models/classcan_density_float32.tflite)")

    # Secondary box detector: bounding boxes for HUD overlay
    detector = Detector(
        model_path=cfg.MODEL_PATH,
        conf_threshold=cfg.CONF_THRESHOLD,
        camera_index=args.camera,
        force_mock=args.mock,
        mock_count=args.mock_count,
    )
    trigger    = ChangeTrigger(threshold=cfg.CHANGE_THRESHOLD)
    reconciler = ZoneReconciler(zone_names=list(cfg.ZONE_POSITIONS.keys()))

    serial_bridge = SerialBridge(port=cfg.SERIAL_PORT, baud=cfg.SERIAL_BAUD)
    dashboard     = DashboardServer(host=cfg.DASHBOARD_HOST, port=cfg.DASHBOARD_PORT)

    last_count      = 0
    last_check_time = time.time()
    last_fps_time   = time.time()
    fps_counter     = 0
    current_fps     = 0.0

    source_tag = "SIMULATED" if detector.is_mock else "HARDWARE"

    print("-" * 60)
    print(f"[CLASSCAN] Dashboard live: http://{cfg.DASHBOARD_HOST}:{cfg.DASHBOARD_PORT}")
    print(f"[CLASSCAN] Video stream:   http://{cfg.DASHBOARD_HOST}:{cfg.DASHBOARD_PORT}/stream")
    print("-" * 60)
    print("Press Ctrl-C to stop.\n")

    # ---- Inference background thread ----------------------------------------
    #
    # ROOT CAUSE OF SYNC LAG (fixed here):
    #   TFLite ensemble inference takes ~700 ms - 1 s+ on the Pi 3B.
    #   Running it synchronously in the main loop blocked frame capture for
    #   that entire duration. The MJPEG stream thread was re-sending the same
    #   stale annotated frame during that window, making video appear frozen
    #   and detection boxes look "late" relative to live motion.
    #
    # FIX - producer/consumer split:
    #   Main loop         : grabs fresh frame -> annotates with last inference
    #                       boxes -> pushes to stream. Runs at full camera rate
    #                       (~20 Hz, limited by LOOP_SLEEP=0.05 s). Never
    #                       blocks on AI inference.
    #   InferenceWorker   : waits for a frame, runs detector.detect() and
    #                       density_detector.predict(), writes results atomically.
    #
    # Synchronisation:
    #   _infer_trigger (Event) - main sets to hand a frame to the worker
    #   _infer_busy    (Event) - worker sets while inference is running
    #   _stop_flag     (Event) - main sets on shutdown
    #   _infer_lock    (Lock)  - guards _result dict reads/writes
    #   _pending_frame (list)  - [frame] passed from main to worker

    _infer_lock         = threading.Lock()
    _infer_trigger      = threading.Event()
    _infer_busy         = threading.Event()
    _stop_flag          = threading.Event()
    _pending_frame_lock = threading.Lock()
    _pending_frame      = [None]  # list wrapper avoids closure rebind issues

    # Shared inference results - worker writes, main loop reads
    _result = {
        "detections":  [],
        "count":       0,
        "zone_counts": None,
    }

    def _inference_worker():
        """
        Daemon thread: sits idle between detection cycles.
        When the main loop posts a frame (_infer_trigger), runs full TFLite
        inference and writes results to _result under _infer_lock.
        """
        while not _stop_flag.is_set():
            # Block until main loop signals (1-second timeout to re-check _stop_flag)
            triggered = _infer_trigger.wait(timeout=1.0)
            if not triggered:
                continue

            _infer_trigger.clear()
            _infer_busy.set()

            with _pending_frame_lock:
                frame = _pending_frame[0]

            if frame is None:
                _infer_busy.clear()
                continue

            try:
                if cfg.MODE == "SWEEP":
                    new_detections = detector.detect(frame)
                    if density_detector:
                        result    = density_detector.predict(frame)
                        new_count = result["count"]
                    else:
                        new_count = len(new_detections)
                    new_zone_counts = None

                elif cfg.MODE == "ZONE_CHECK":
                    new_zone_counts = detector.detect_zones(frame, cfg.ZONE_POSITIONS)
                    if density_detector:
                        result    = density_detector.predict(frame)
                        new_count = result["count"]
                    else:
                        with _infer_lock:
                            prev_count = _result["count"]
                        new_count, needs_rescan = reconciler.reconcile(
                            new_zone_counts, prev_count)
                        if needs_rescan:
                            print("[CLASSCAN] Reconciliation mismatch - re-scanning...")
                            new_zone_counts = detector.detect_zones(
                                frame, cfg.ZONE_POSITIONS)
                            new_count, _ = reconciler.reconcile(
                                new_zone_counts, prev_count)
                    new_detections = detector.detect(frame)

                else:
                    new_detections  = []
                    new_count       = 0
                    new_zone_counts = None

                with _infer_lock:
                    _result["detections"]  = new_detections
                    _result["count"]       = new_count
                    _result["zone_counts"] = new_zone_counts

            except Exception as exc:
                print(f"[CLASSCAN][InferenceWorker] Error: {exc}")
            finally:
                _infer_busy.clear()

    worker_thread = threading.Thread(
        target=_inference_worker, daemon=True, name="InferenceWorker")
    worker_thread.start()

    motion_active_until   = 0.0
    initial_infer_queued = False

    try:
        while True:
            # 2. Grab Frame - always get the freshest available camera frame
            frame     = detector.capture_frame()
            esp_state = serial_bridge.get_state()  # "idle" | "moving"

            # 3. FPS calculation
            fps_counter += 1
            elapsed_fps = time.time() - last_fps_time
            if elapsed_fps >= 1.0:
                current_fps   = fps_counter / elapsed_fps
                fps_counter   = 0
                last_fps_time = time.time()

            # 4. Schedule next inference pass when worker is idle and one is due.
            #    Motion detection extends the active inference window (2s) so AI
            #    stays locked onto moving targets with minimal latency.
            significant_change = trigger.check(frame)
            if significant_change:
                motion_active_until = time.time() + 2.0

            motion_active = time.time() < motion_active_until
            heartbeat_due = (time.time() - last_check_time) >= cfg.HEARTBEAT_INTERVAL

            worker_idle = not _infer_busy.is_set() and not _infer_trigger.is_set()
            if worker_idle and (not initial_infer_queued or motion_active or heartbeat_due):
                initial_infer_queued = True
                last_check_time      = time.time()
                # Copy the frame so inference operates on a stable snapshot
                with _pending_frame_lock:
                    _pending_frame[0] = frame.copy()
                _infer_trigger.set()

            # 5. Read the most recently completed inference results (non-blocking)
            with _infer_lock:
                detections  = _result["detections"]
                new_count   = _result["count"]
                zone_counts = _result["zone_counts"]

            if new_count != last_count:
                last_count = new_count
                serial_bridge.send_count(last_count)
                print(f"[CLASSCAN] Headcount updated -> {last_count}")

            # 6. Annotate and Push Frame to Dashboard.
            #    Boxes from the latest completed inference are overlaid on the
            #    current live frame - stream is always smooth, no inference wait.
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

            # 7. Handle Inbound Dashboard Commands
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
        _stop_flag.set()
        _infer_trigger.set()            # unblock the worker if it is waiting
        worker_thread.join(timeout=3.0)
        serial_bridge.close()
        dashboard.close()
        detector.release()
        if density_detector:
            density_detector.release()
        print("[CLASSCAN] Stopped.")


if __name__ == "__main__":
    main()
