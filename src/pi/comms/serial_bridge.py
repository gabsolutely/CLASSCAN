"""
Serial bridge — Pi 3B ↔ ESP32 over USB serial.

Protocol (newline-delimited JSON):
  Pi → ESP32:
    {"type": "count",   "value": <int>}
    {"type": "command", "value": "<cmd>"}

  ESP32 → Pi:
    {"type": "state",   "value": "idle" | "moving"}
"""

import json
import threading
import serial


class SerialBridge:
    def __init__(self, port: str, baud: int):
        self._ser = serial.Serial(port, baud, timeout=0.1)
        self._state = "idle"
        self._lock  = threading.Lock()

        # Background reader thread keeps state up-to-date
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()
        print(f"[SerialBridge] Connected on {port} @ {baud}")

    def _read_loop(self):
        while True:
            try:
                line = self._ser.readline().decode("utf-8", errors="ignore").strip()
                if not line:
                    continue
                msg = json.loads(line)
                if msg.get("type") == "state":
                    with self._lock:
                        self._state = msg["value"]
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass
            except Exception as e:
                print(f"[SerialBridge] Read error: {e}")

    def get_state(self) -> str:
        with self._lock:
            return self._state

    def send_count(self, count: int):
        msg = json.dumps({"type": "count", "value": count}) + "\n"
        self._ser.write(msg.encode("utf-8"))

    def send_command(self, cmd: str):
        msg = json.dumps({"type": "command", "value": cmd}) + "\n"
        self._ser.write(msg.encode("utf-8"))

    def close(self):
        if self._ser.is_open:
            self._ser.close()
