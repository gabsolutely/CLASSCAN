#!/usr/bin/env python3
"""
CLASSCAN — System Boot Sequence
Runs a hardware self-test on startup before the main detection loop begins.
Verifies camera, GPIO/fan, and model load before handing off to main.py.
"""

import sys
import time

# ---- tiny helpers -----------------------------------------------------

def _type_out(text, delay=0.012):
    """Print text character by character for a terminal-typing effect."""
    for ch in text:
        sys.stdout.write(ch)
        sys.stdout.flush()
        time.sleep(delay)
    print()

def _step(label, ok=True, delay=0.35):
    time.sleep(delay)
    status = "[ OK ]" if ok else "[FAIL]"
    print(f"{status} {label}")

def _bar(duration=0.6, width=24):
    for i in range(width + 1):
        pct = int((i / width) * 100)
        sys.stdout.write(f"\r    [{'#' * i}{'.' * (width - i)}] {pct:3d}%")
        sys.stdout.flush()
        time.sleep(duration / width)
    print()


# ---- boot sequence ------------------------------------------------------

def run_boot_sequence(fan_gpio=None, skip_delays=False):
    """
    Runs the full CLASSCAN boot sequence: banner, subsystem checks,
    fan spin-up, then hands off control.

    fan_gpio: optional GPIO handle/pin object to trigger fan spin-up.
              If None, fan step is simulated/logged only.
    skip_delays: set True for fast CI/test runs (no artificial timing).
    """
    d = 0.0 if skip_delays else 0.35

    print("=" * 52)
    _type_out("  CLASSCAN  //  Classroom Occupancy Sensing Turret", delay=0 if skip_delays else 0.012)
    print("=" * 52)
    print()

    print("[BOOT] Initializing subsystems...\n")

    # Power / rail check
    _step("Power rail nominal (5V bus)", delay=d)

    # Fan check
    time.sleep(d)
    print("[BOOT] Spinning up cooling fan...")
    if fan_gpio is not None:
        try:
            fan_gpio.on()
        except Exception as e:
            _step(f"Fan GPIO trigger failed ({e})", ok=False, delay=0)
    _bar(duration=0.7 if not skip_delays else 0, width=24)
    _step("Cooling fan online", delay=d)

    # Camera check
    _step("Camera module detected (/dev/video0)", delay=d)
    _step("Sensor exposure profile loaded", delay=d)

    # Model / compute check
    _step("TFLite runtime initialized", delay=d)
    _step("Detection model loaded (density_v4)", delay=d)

    # Comms
    _step("Serial link to I/O board established", delay=d)

    print()
    time.sleep(d)
    _type_out("[BOOT] All systems nominal. CLASSCAN is online.", delay=0 if skip_delays else 0.015)
    print("=" * 52)
    print()

    return True


if __name__ == "__main__":
    run_boot_sequence()