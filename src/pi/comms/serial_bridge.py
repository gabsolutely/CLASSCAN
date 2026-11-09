"""
Serial bridge — Pi 3B ↔ ESP32 over USB serial.

Protocol (newline-delimited JSON):
  Pi → ESP32:
    {"type": "count",   "value": <int>}
    {"type": "command", "value": "<cmd>"}
    {"type": "servo",   "pan": <0-180>, "tilt": <0-180>, "duration_ms": <optional>}
    {"type": "servo",   "pan_angle": <0-180>, "tilt_angle": <0-180>, "speed": <91-180>}

  ESP32 → Pi:
    {"type": "state",   "value": "idle" | "moving"}
    {"type": "ldr",     "value": <adc 0-4095>, "illumination": true | false}
    {"type": "pan_pos", "pct": <0-100>, "moving": <bool>}

Notes:
  - In mock mode (serial port unavailable) all sends are silent no-ops and
    state/illumination accessors return their default values.
  - Opening the serial port on Linux triggers a DTR reset on the ESP32.
    __init__ waits 2 s for the ESP32 bootloader to finish before returning,
    so the first command is never sent while the chip is still booting.
  - _send() is guarded by _lock so the reader thread and writer thread
    can never interleave bytes on the same UART connection.
  - The background reader thread exits cleanly when the port disconnects
    (OSError / SerialException); it does not restart automatically.
"""


import json
import time
import threading
import serial

# Seconds to wait after opening the serial port for the ESP32 DTR-reset
# bootloader sequence to finish before sending the first command.
_BOOT_SETTLE_S = 2.0


class SerialBridge:
    def __init__(self, port: str, baud: int):
        self.port = port
        self.baud = baud
        self._state       = "idle"
        self._illumination = False   # True when ESP32 has turned its LEDs on
        self._ldr_value   = None     # Last raw ADC reading (0-4095), None before first report
        self._pan_pct     = 50       # Estimated pan position 0-100 (dead-reckoned by ESP32)
        self._pan_moving  = False    # True while ESP32 pan servo is in motion
        self._lock        = threading.Lock()
        self._ser         = None
        self._is_mock     = False

        try:
            self._ser = serial.Serial(port, baud, timeout=0.1)
            # Opening the port pulses DTR which resets the ESP32 — wait for
            # the bootloader to settle before the caller sends any commands.
            print(f"[SerialBridge] Port opened ({port} @ {baud}). "
                  f"Waiting {_BOOT_SETTLE_S:.0f} s for ESP32 boot…")
            time.sleep(_BOOT_SETTLE_S)
            self._ser.reset_input_buffer()   # discard bootloader noise
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

                elif msg_type == "pan_pos":
                    with self._lock:
                        self._pan_pct = int(msg.get("pct", 50))
                        self._pan_moving = bool(msg.get("moving", False))

                elif msg_type == "debug":
                    # Boot diagnostic from ESP32 — log but don't block
                    lcd_addr = msg.get("lcd")
                    pan_pin  = msg.get("pan")
                    tilt_pin = msg.get("tilt")
                    print(f"[SerialBridge][ESP32 boot] LCD I2C=0x{lcd_addr:02X}  "
                          f"pan=GPIO{pan_pin}  tilt=GPIO{tilt_pin}")

            except (json.JSONDecodeError, UnicodeDecodeError):
                pass  # Malformed line — ignore and continue
            except (OSError, serial.SerialException) as e:
                # Port disconnected or closed — exit reader cleanly
                print(f"[SerialBridge] Port disconnected, reader stopping: {e}")
                return
            except Exception as e:
                print(f"[SerialBridge] Read error: {e}")


    # ── State accessors ──────────────────────────────────────────────────────

    @property
    def is_connected(self) -> bool:
        """True when the serial port opened successfully (not in mock mode)."""
        return not self._is_mock

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

    def get_pan_pct(self) -> int:
        """Returns the estimated pan servo sweep position (0-100%)."""
        with self._lock:
            return self._pan_pct

    def get_pan_moving(self) -> bool:
        """Returns True if the ESP32 reports the pan servo is actively sweeping."""
        with self._lock:
            return self._pan_moving


    # ── Senders ──────────────────────────────────────────────────────────────

    def _send(self, obj: dict):
        """Serialize obj as JSON and write it to serial (no-op in mock mode).

        Acquires _lock so the writer thread and reader thread never interleave
        bytes on the shared UART connection.
        """
        with self._lock:
            if self._ser and self._ser.is_open:
                self._ser.write((json.dumps(obj) + "\n").encode("utf-8"))
                self._ser.flush()

    def send_count(self, count: int):
        """Push the latest headcount to the ESP32 for display on the LCD display."""
        self._send({"type": "count", "value": count})

    def send_zones(self, zone_counts: dict, total: int):
        """Send per-zone counts to ESP32 for zone-mode LCD display."""
        msg = {"type": "zones", "total": int(total)}
        for k, v in zone_counts.items():
            msg[k] = int(v)
        self._send(msg)

    def send_command(self, cmd: str):
        """Send a named command string (MODE_SWEEP, STOP_SERVOS, ZONE_Q1, etc.)."""
        self._send({"type": "command", "value": cmd})

    def send_servo_speed(self, pan: int, tilt: int = 30, duration_ms: int = 0):
        """
        Send Pan speed (MG90S 360 deg continuous) and Tilt angle (MG90S 180 deg positional).

        pan: 0-180 speed value (90 = stop, >90 = forward/CW, <90 = reverse/CCW)
        tilt: 0-180 target tilt angle in degrees (default 30 deg downward pitch)
        duration_ms: if >0, ESP32 will auto-stop pan rotation after this many ms.
        """
        msg = {"type": "servo", "pan": pan, "tilt": tilt}
        if duration_ms > 0:
            msg["duration_ms"] = duration_ms
        self._send(msg)

    def send_servo_angle(self, pan_angle: int, tilt_angle: int = 30, speed: int = 155):
        """
        Send a timed Pan angle move (MG90S 360 deg) and absolute Tilt angle (MG90S 180 deg).

        pan_angle: target pan angle 0-180 degrees (timed rotation via SERVO_MS_PER_DEGREE)
        tilt_angle: target tilt angle 0-180 degrees (direct positional hold, default 30 deg)
        speed: pan continuous-servo speed (default 155)
        """
        self._send({
            "type": "servo",
            "pan_angle": pan_angle,
            "tilt_angle": tilt_angle,
            "speed": speed,
        })

    # ── Helpers ──────────────────────────────────────────────────────────────

    def flush_input(self) -> None:
        """Drain any stale bytes sitting in the receive buffer.

        Useful to call after a reconnect or mode-change where queued old
        messages could otherwise confuse the reader.
        """
        if self._ser and self._ser.is_open:
            self._ser.reset_input_buffer()

    # ── Cleanup ───────────────────────────────────────────────────────────────

    def close(self) -> None:
        """Close the serial port (no-op in mock mode)."""
        if self._ser and self._ser.is_open:
            self._ser.close()
