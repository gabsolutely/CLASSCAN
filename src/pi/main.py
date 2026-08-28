"""
CLASSCAN — Pi 3B Main Loop
Runs TFLite person-detection, manages Wi-Fi dashboard comms,
and relays commands/headcount to ESP32 over USB serial.
"""

import time
from detection.detector import Detector
from detection.change_trigger import ChangeTrigger
from detection.zone_reconciler import ZoneReconciler
from comms.serial_bridge import SerialBridge
from comms.dashboard_server import DashboardServer
from config import Config


def main():
    cfg = Config()

    detector = Detector(model_path=cfg.MODEL_PATH, conf_threshold=cfg.CONF_THRESHOLD)
    trigger = ChangeTrigger(threshold=cfg.CHANGE_THRESHOLD)
    reconciler = ZoneReconciler(zones=cfg.ZONES)

    serial_bridge = SerialBridge(port=cfg.SERIAL_PORT, baud=cfg.SERIAL_BAUD)
    dashboard = DashboardServer(host=cfg.DASHBOARD_HOST, port=cfg.DASHBOARD_PORT)

    last_count = 0
    last_check_time = time.time()

    print("[CLASSCAN] Pi 3B main loop starting...")

    try:
        while True:
            frame = detector.capture_frame()
            esp_state = serial_bridge.get_state()  # "idle" | "moving"

            # Run detection if:
            #   (a) ESP32 is idle AND significant change detected, OR
            #   (b) heartbeat interval elapsed
            significant_change = trigger.check(frame)
            heartbeat_due = (time.time() - last_check_time) >= cfg.HEARTBEAT_INTERVAL

            if (esp_state == "idle" and significant_change) or heartbeat_due:
                last_check_time = time.time()

                if cfg.MODE == "SWEEP":
                    detections = detector.detect(frame)
                    count = len(detections)
                elif cfg.MODE == "ZONE_CHECK":
                    zone_counts = detector.detect_zones(frame, cfg.ZONE_POSITIONS)
                    count, needs_rescan = reconciler.reconcile(zone_counts, last_count)
                    if needs_rescan:
                        print("[CLASSCAN] Reconciliation mismatch — re-scanning...")
                        zone_counts = detector.detect_zones(frame, cfg.ZONE_POSITIONS)
                        count, _ = reconciler.reconcile(zone_counts, last_count)

                if count != last_count:
                    last_count = count
                    serial_bridge.send_count(count)
                    print(f"[CLASSCAN] Headcount updated → {count}")

                dashboard.push(count=count, snapshot=frame)

            # Handle inbound dashboard commands (non-blocking)
            cmd = dashboard.poll_command()
            if cmd:
                print(f"[CLASSCAN] Command from dashboard: {cmd}")
                serial_bridge.send_command(cmd)

            time.sleep(cfg.LOOP_SLEEP)

    except KeyboardInterrupt:
        print("[CLASSCAN] Shutting down.")
    finally:
        serial_bridge.close()
        dashboard.close()


if __name__ == "__main__":
    main()
