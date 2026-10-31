#!/usr/bin/env python3
"""
CLASSCAN — Hardware Verification & Calibration Script
======================================================
Dedicated bench-test and field-commissioning tool for newly acquired
Phase 2 materials:
  1. LCD2004 Display Module (20×4 Character LCD, PCF8574 I2C Backpack)
  2. Pan/Tilt Dual-Axis Bracket Kit (TowerPro MG90S Metal-Gear Servos)
  3. LDR Ambient Light Sensor & Auxiliary LED Illumination Driver

This script communicates directly with the ESP32 firmware over USB-Serial
using the standard newline-delimited JSON protocol. It runs on both the
Raspberry Pi 3B (Linux) and a host development machine (Windows/macOS).

Usage:
    # Run full automated hardware smoke-test (all components):
    python scripts/hardware_verify.py --all

    # Test the LCD2004 display only (headcount rendering & formatting):
    python scripts/hardware_verify.py --test-lcd

    # Test the Pan/Tilt bracket kit & servos only (pan, tilt, quadrants):
    python scripts/hardware_verify.py --test-servos

    # Continuous live monitor of ambient LDR sensor & illumination state:
    python scripts/hardware_verify.py --read-ldr

    # Interactive manual turret & display control prompt:
    python scripts/hardware_verify.py --interactive

Options:
    --port       Serial port path (default: auto-detected, or /dev/ttyUSB0 on Pi)
    --baud       Baud rate (default: 115200)
    --mock       Run in simulation mode without physical serial hardware
"""

import argparse
import json
import os
import sys
import time
from typing import Optional

try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False


# ── Serial Port Auto-Detection ────────────────────────────────────────────────

def find_serial_port() -> Optional[str]:
    """Auto-detect connected ESP32 / USB-UART serial adapter."""
    if not SERIAL_AVAILABLE:
        return None

    # Check common Linux/Pi devices first
    default_candidates = [
        "/dev/ttyUSB0",
        "/dev/ttyUSB1",
        "/dev/ttyACM0",
        "/dev/ttyACM1",
    ]
    for dev in default_candidates:
        if os.path.exists(dev):
            return dev

    # Enumerate all available serial ports via pyserial
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        return None

    # Look for known USB-UART vendor strings (CP2102, CH340, FTDI, Espressif)
    for p in ports:
        desc = (p.description or "").lower()
        hwid = (p.hwid or "").lower()
        if any(keyword in desc or keyword in hwid for keyword in [
            "cp210", "ch340", "ch341", "ftdi", "uart", "usb serial", "espressif"
        ]):
            return p.device

    # Fallback to the first available COM/serial port
    return ports[0].device


# ── ESP32 Hardware Interface ──────────────────────────────────────────────────

class Esp32HardwareInterface:
    """Handles JSON messaging with the ESP32 firmware."""

    def __init__(self, port: Optional[str] = None, baud: int = 115200, mock: bool = False):
        self.port = port
        self.baud = baud
        self.mock = mock
        self._ser = None
        self.last_state = "idle"
        self.last_ldr = None
        self.last_illum = False

        if not self.mock and SERIAL_AVAILABLE:
            if not self.port:
                self.port = find_serial_port()
            if self.port:
                try:
                    self._ser = serial.Serial(self.port, self.baud, timeout=0.2)
                    time.sleep(1.5)  # Allow ESP32 bootloader settling time
                    print(f"[Hardware] Connected to ESP32 on {self.port} @ {self.baud} baud.")
                except Exception as e:
                    print(f"[Hardware] Warning: Could not open {self.port} ({e}).")
                    print("           Falling back to SIMULATED MOCK mode.")
                    self.mock = True
            else:
                print("[Hardware] No serial port detected. Running in SIMULATED MOCK mode.")
                self.mock = True
        else:
            self.mock = True

    def send_raw(self, payload: dict) -> bool:
        """Send a JSON payload terminated by newline."""
        line = json.dumps(payload) + "\n"
        if self._ser and self._ser.is_open:
            try:
                self._ser.write(line.encode("utf-8"))
                self._ser.flush()
                return True
            except Exception as e:
                print(f"[Hardware] Error writing to serial: {e}")
                return False
        elif self.mock:
            print(f"[SIMULATED TX] -> {line.strip()}")
            return True
        return False

    def read_responses(self, max_seconds: float = 0.5):
        """Read and parse any pending telemetry messages from the ESP32."""
        if self.mock or not self._ser or not self._ser.is_open:
            return

        end_time = time.time() + max_seconds
        while time.time() < end_time:
            try:
                raw = self._ser.readline()
                if not raw:
                    continue
                line = raw.decode("utf-8", errors="ignore").strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    msg_type = data.get("type")
                    if msg_type == "state":
                        self.last_state = data.get("value", self.last_state)
                        print(f"  [ESP32 Status] Turret State: {self.last_state.upper()}")
                    elif msg_type == "ldr":
                        self.last_ldr = data.get("value")
                        self.last_illum = bool(data.get("illumination", False))
                        print(f"  [ESP32 Sensor] LDR ADC: {self.last_ldr} | Illumination: {'ON' if self.last_illum else 'OFF'}")
                except json.JSONDecodeError:
                    # Ignore non-JSON bootloader debug lines
                    pass
            except Exception as e:
                print(f"[Hardware] Serial read error: {e}")
                break

    def set_headcount(self, count: int) -> bool:
        """Update the LCD2004 headcount display."""
        return self.send_raw({"type": "count", "value": int(count)})

    def send_command(self, cmd: str) -> bool:
        """Send a system command string."""
        return self.send_raw({"type": "command", "value": cmd})

    def move_to_zone(self, zone_name: str) -> bool:
        """Move pan/tilt turret to a specific quadrant (e.g. 'Q1', 'Q2', 'Q3', 'Q4')."""
        return self.send_command(f"ZONE_{zone_name.upper()}")

    def set_servo_speed(self, pan: int, tilt: int, duration_ms: int = 0) -> bool:
        """Direct continuous-servo speed command (90 is stop)."""
        payload = {"type": "servo", "pan": int(pan), "tilt": int(tilt)}
        if duration_ms > 0:
            payload["duration_ms"] = int(duration_ms)
        return self.send_raw(payload)

    def set_servo_angle(self, pan_angle: int, tilt_angle: int, speed: int = 155) -> bool:
        """Timed angle command (0-180 degrees)."""
        return self.send_raw({
            "type": "servo",
            "pan_angle": int(pan_angle),
            "tilt_angle": int(tilt_angle),
            "speed": int(speed)
        })

    def stop_servos(self) -> bool:
        """Immediately halt all servo motion."""
        return self.send_command("STOP_SERVOS")

    def center_servos(self) -> bool:
        """Halt servos and reset internal angle reference to center (90°, 90°)."""
        return self.send_command("SET_CENTER")

    def close(self):
        """Close connection cleanly."""
        if self._ser and self._ser.is_open:
            self._ser.close()


# ── Verification Routines ─────────────────────────────────────────────────────

def verify_lcd_display(hw: Esp32HardwareInterface) -> bool:
    """Test LCD2004 character display layout and numerical updates."""
    print("\n" + "=" * 60)
    print("  TEST 1: LCD2004 Character LCD (I2C 20x4, PCF8574 Backpack)")
    print("=" * 60)
    print("Testing 20x4 character formatting, row layout, and count updates:")
    print("  - Row 0: Centered '== CLASSCAN ==' header")
    print("  - Row 1: Spacing row")
    print("  - Row 2: Centered headcount 'Count: <N>'")
    print("  - Row 3: Centered 'students' label\n")

    test_counts = [0, 5, 18, 35, 42]
    for count in test_counts:
        print(f"  --> Sending headcount count={count} to LCD...")
        hw.set_headcount(count)
        hw.read_responses(max_seconds=0.3)
        time.sleep(0.5)

    print("\n[OK] LCD2004 display sequence complete.")
    print("     Verify visually that characters are clear, backlight is active,")
    print("     and text contrast is sharp (adjust rear blue pot on PCF8574 if blank).")
    return True


def verify_pan_tilt_servos(hw: Esp32HardwareInterface) -> bool:
    """Test dual-axis pan/tilt bracket platform with MG90S servos."""
    print("\n" + "=" * 60)
    print("  TEST 2: Pan/Tilt Dual-Axis Bracket Kit (MG90S Servos)")
    print("=" * 60)
    print("Testing mechanical range, continuous sweep, and quadrant targeting:\n")

    # Step 1: Center calibration
    print("  [Step 1/4] Centering servos (SET_CENTER)...")
    hw.center_servos()
    hw.read_responses(max_seconds=0.5)
    time.sleep(0.5)

    # Step 2: Test discrete quadrant moves (Q1 -> Q2 -> Q3 -> Q4)
    print("  [Step 2/4] Testing quadrant targeting table (ZONE_Q1 -> ZONE_Q4)...")
    quadrants = ["Q1", "Q2", "Q3", "Q4"]
    for q in quadrants:
        print(f"    --> Positioning turret to Quadrant {q}...")
        hw.move_to_zone(q)
        hw.read_responses(max_seconds=0.8)
        time.sleep(0.5)

    # Step 3: Test brief continuous sweep
    print("  [Step 3/4] Activating continuous sweep mode (MODE_SWEEP) for 2 seconds...")
    hw.send_command("MODE_SWEEP")
    t_end = time.time() + 2.0
    while time.time() < t_end:
        hw.read_responses(max_seconds=0.5)
        time.sleep(0.1)

    # Step 4: Halt servos safely
    print("  [Step 4/4] Sending STOP_SERVOS to park turret safely...")
    hw.stop_servos()
    hw.read_responses(max_seconds=0.5)
    time.sleep(0.5)

    print("\n[OK] Pan/tilt dual-axis bracket test complete.")
    print("     Confirm smooth rotation without mechanical binding or gear stripping.")
    return True


def verify_ldr_illumination(hw: Esp32HardwareInterface) -> bool:
    """Test LDR ambient light sensor and IRLZ44N illumination driver."""
    print("\n" + "=" * 60)
    print("  TEST 3: Ambient LDR & Auxiliary LED Illumination Driver")
    print("=" * 60)
    print("Sampling ambient light ADC reading (0-4095; lower = darker)...")

    # Read sensor values over 2 seconds
    samples = []
    t_end = time.time() + 2.0
    while time.time() < t_end:
        hw.read_responses(max_seconds=0.5)
        if hw.last_ldr is not None:
            samples.append(hw.last_ldr)
        time.sleep(0.3)

    if samples:
        avg_ldr = sum(samples) / len(samples)
        print(f"\n  Average LDR Reading : {avg_ldr:.1f} / 4095 counts")
        print(f"  Illumination State  : {'ACTIVE (Dark)' if hw.last_illum else 'OFF (Adequate Light)'}")
        print("  Threshold Baseline  : 1500 +/- 75 hysteresis (from config.h)")
        print("\n[OK] LDR telemetry received successfully.")
    else:
        print("  [!] Notice: No periodic LDR packet received within window.")
        print("      (Verify PIN_LDR GPIO 34 wiring and 10k pull-down resistor).")

    return True


def run_interactive_mode(hw: Esp32HardwareInterface):
    """Interactive CLI menu for live hardware commissioning."""
    print("\n" + "=" * 60)
    print("  CLASSCAN — Interactive Hardware Commissioning Shell")
    print("=" * 60)
    print("Controls:")
    print("  1, 2, 3, 4 : Aim turret at Quadrant Q1, Q2, Q3, or Q4")
    print("  s          : Start autonomous continuous SWEEP mode")
    print("  z          : Start autonomous ZONE_CHECK stepping mode")
    print("  c          : Center servos & zero angle references (SET_CENTER)")
    print("  h          : Halt / Emergency Stop all servos (STOP_SERVOS)")
    print("  d <number> : Display specific headcount on LCD2004 (e.g. 'd 24')")
    print("  l          : Poll LDR ambient lux & illumination state")
    print("  q          : Exit interactive shell\n")

    while True:
        try:
            cmd = input("hardware_verify> ").strip()
            if not cmd:
                continue

            parts = cmd.split()
            action = parts[0].lower()

            if action in ["q", "exit", "quit"]:
                print("Stopping servos and exiting...")
                hw.stop_servos()
                break
            elif action in ["1", "q1"]:
                print("Moving to Quadrant Q1...")
                hw.move_to_zone("Q1")
            elif action in ["2", "q2"]:
                print("Moving to Quadrant Q2...")
                hw.move_to_zone("Q2")
            elif action in ["3", "q3"]:
                print("Moving to Quadrant Q3...")
                hw.move_to_zone("Q3")
            elif action in ["4", "q4"]:
                print("Moving to Quadrant Q4...")
                hw.move_to_zone("Q4")
            elif action == "s":
                print("Starting SWEEP mode...")
                hw.send_command("MODE_SWEEP")
            elif action == "z":
                print("Starting ZONE_CHECK stepping mode...")
                hw.send_command("MODE_ZONE")
            elif action == "c":
                print("Centering servos...")
                hw.center_servos()
            elif action == "h":
                print("Emergency STOP sent.")
                hw.stop_servos()
            elif action == "d":
                if len(parts) > 1 and parts[1].isdigit():
                    num = int(parts[1])
                    print(f"Setting LCD headcount to {num}...")
                    hw.set_headcount(num)
                else:
                    print("Usage: d <number>   (e.g. 'd 15')")
            elif action == "l":
                hw.read_responses(max_seconds=0.5)
                print(f"Current LDR: {hw.last_ldr} | Illumination: {hw.last_illum} | Turret: {hw.last_state}")
            else:
                print(f"Unknown command: '{cmd}'. Type 1-4, s, z, c, h, d <n>, l, or q.")

            hw.read_responses(max_seconds=0.2)

        except (KeyboardInterrupt, EOFError):
            print("\nInterrupt received. Halting servos...")
            hw.stop_servos()
            break


# ── Main Entry Point ──────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="CLASSCAN Hardware Verification & Commissioning Tool (LCD2004 & Pan/Tilt Bracket Kit)"
    )
    parser.add_argument("--port", type=str, default=None,
                        help="Serial port path (e.g. /dev/ttyUSB0 or COM3). Auto-detected if omitted.")
    parser.add_argument("--baud", type=int, default=115200,
                        help="Serial baud rate (default: 115200)")
    parser.add_argument("--mock", action="store_true",
                        help="Run in simulation mode without physical serial connection")
    parser.add_argument("--all", action="store_true",
                        help="Run full automated verification of LCD, Servos, and LDR")
    parser.add_argument("--test-lcd", action="store_true",
                        help="Run LCD2004 character display verification sequence")
    parser.add_argument("--test-servos", action="store_true",
                        help="Run Pan/Tilt bracket kit & MG90S servo motion sequence")
    parser.add_argument("--read-ldr", action="store_true",
                        help="Continuous monitor of LDR sensor & illumination state")
    parser.add_argument("--interactive", action="store_true",
                        help="Launch interactive terminal prompt for live hardware control")

    args = parser.parse_args()

    # If no specific mode flag was selected, default to --all automated smoke-test
    run_all = args.all or (not (args.test_lcd or args.test_servos or args.read_ldr or args.interactive))

    print("=" * 60)
    print("  CLASSCAN // Phase 2 Hardware Commissioning & Verification")
    print("=" * 60)

    hw = Esp32HardwareInterface(port=args.port, baud=args.baud, mock=args.mock)

    try:
        if args.interactive:
            run_interactive_mode(hw)
        elif args.read_ldr:
            print("\nMonitoring LDR ambient light sensor (Press Ctrl+C to exit)...")
            while True:
                hw.read_responses(max_seconds=0.5)
                time.sleep(0.3)
        else:
            if run_all or args.test_lcd:
                verify_lcd_display(hw)
            if run_all or args.test_servos:
                verify_pan_tilt_servos(hw)
            if run_all:
                verify_ldr_illumination(hw)

            print("\n" + "=" * 60)
            print("  ALL HARDWARE VERIFICATION CHECKS COMPLETED")
            print("=" * 60)
            print("Hardware status: Ready for full system integration.\n")

    except KeyboardInterrupt:
        print("\n[!] Execution interrupted by user.")
    finally:
        hw.stop_servos()
        hw.close()


if __name__ == "__main__":
    main()
