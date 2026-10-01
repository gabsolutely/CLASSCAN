"""
Serial bridge — Pi 3B ↔ ESP32 over USB serial.

Protocol (newline-delimited JSON):
  Pi → ESP32:
    {"type": "count",   "value": <int>}
    {"type": "command", "value": "<cmd>"}
    {"type": "servo",   "pan": <0-180>, "tilt": <0-180>, "duration_ms": <optional>}
    {"type": "servo",   "pan_angle": <0-180>, "tilt_angle": <0-180>, "speed": <91-180>}

  ESP32 → Pi:
    {"type": "state",  "value": "idle" | "moving"}
    {"type": "ldr",    "value": <adc 0-4095>, "illumination": true | false}
"""

import json
import threading
import serial


class SerialBridge:
    def __init__(self, port: str, baud: int):
        self.port = port
        self.baud = baud
        self._state       = "idle"
        self._illumination = False   # True when ESP32 has turned its LEDs on
        self._ldr_value   = None     # Last raw ADC reading (0-4095), None before first report
        self._lock        = threading.Lock()
        self._ser         = None
        self._is_mock     = False

        try:
            self._ser = serial.Serial(port, baud, timeout=0.1)
            # Background reader thread keeps _state and _illumination up-to-date
            self._reader = threading.Thread(target=self._read_loop, daemon=True)
            self._reader.start()
            print(f"[SerialBridge] Connected on {port} @ {baud}")
        except Exception as e:
            self._is_mock = True
            print(f"[SerialBridge] Port {port} unavailable ({e}). Running in simulated serial mode.")

    # ── Background reader ────────────────────────────────────────────────────

    def _read_loop(self):
        while True:
            try:
                line = self._ser.readline().decode("utf-8", errors="ignore").strip()
                if not line:
                    continue
                msg = json.loads(line)
                msg_type = msg.get("type")

                if msg_type == "state":
                    with self._lock:
                        self._state = msg["value"]

                elif msg_type == "ldr":
                    with self._lock:
                        if "value" in msg:
                            self._ldr_value = int(msg["value"])
                        if "illumination" in msg:
                            self._illumination = bool(msg["illumination"])

            except (json.JSONDecodeError, UnicodeDecodeError):
                pass
            except Exception as e:
                print(f"[SerialBridge] Read error: {e}")

    # ── State accessors ──────────────────────────────────────────────────────

    def get_state(self) -> str:
        """Returns ESP32 servo state: 'idle' or 'moving'."""
        with self._lock:
            return self._state

    def get_illumination(self) -> bool:
        """Returns True when the ESP32's illumination LEDs are currently on."""
        with self._lock:
            return self._illumination

    def get_ldr_value(self) -> int | None:
        """Returns the last raw ADC reading from the LDR (0-4095), or None if not yet received."""
        with self._lock:
            return self._ldr_value

    # ── Senders ──────────────────────────────────────────────────────────────

    def _send(self, obj: dict):
        """Serialize obj as JSON and write it to serial (no-op in mock mode)."""
        if self._ser and self._ser.is_open:
            self._ser.write((json.dumps(obj) + "\n").encode("utf-8"))

    def send_count(self, count: int):
        """Push the latest headcount to the ESP32 for display on the LED matrix."""
        self._send({"type": "count", "value": count})

    def send_command(self, cmd: str):
        """Send a named command string (MODE_SWEEP, STOP_SERVOS, ZONE_Q1, etc.)."""
        self._send({"type": "command", "value": cmd})

    def send_servo_speed(self, pan: int, tilt: int, duration_ms: int = 0):
        """
        Send a raw continuous-servo speed command.

        pan / tilt: 0-180 speed value (90 = stop, >90 = forward, <90 = reverse)
        duration_ms: if >0, ESP32 will auto-stop after this many ms.
        """
        msg = {"type": "servo", "pan": pan, "tilt": tilt}
        if duration_ms > 0:
            msg["duration_ms"] = duration_ms
        self._send(msg)

    def send_servo_angle(self, pan_angle: int, tilt_angle: int, speed: int = 155):
        """
        Send a timed angle-move command (open-loop, calibrated by SERVO_MS_PER_DEGREE).

        pan_angle / tilt_angle: target angle 0-180 degrees (relative to last SET_CENTER)
        speed: continuous-servo run command (91-180, default SERVO_ANGLE_SPEED=155)
        """
        self._send({
            "type": "servo",
            "pan_angle": pan_angle,
            "tilt_angle": tilt_angle,
            "speed": speed,
        })

    # ── Cleanup ───────────────────────────────────────────────────────────────

    def close(self):
        if self._ser and self._ser.is_open:
            self._ser.close()
