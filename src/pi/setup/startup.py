#!/usr/bin/env python3
"""
CLASSCAN — System Boot Sequence
Runs a real hardware self-test on startup before the main detection loop
begins. Each check actually probes the corresponding subsystem — camera,
TFLite runtime, model file, serial port — rather than assuming success.

Critical checks (camera, model files, serial) prompt interactively on
failure: [R]etry the check, [C]ontinue anyway, or [A]bort the boot.
Non-critical checks (TFLite runtime import) just print [FAIL] and move on,
since retrying an import failure without changing the environment first
(e.g. installing a package) can't succeed anyway.
"""

import os
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


def _step(label, ok=True, delay=0.0):
    time.sleep(delay)
    status = "[ OK ]" if ok else "[FAIL]"
    print(f"{status} {label}")
    return ok


def _prompt_on_fail(check_fn, *args, **kwargs):
    """
    Runs check_fn(*args, **kwargs) repeatedly. check_fn must return True/False.
    On failure, prompts the user: [R]etry / [C]ontinue / [A]bort.
      - Retry: runs the check again from scratch.
      - Continue: treats this check as skipped, boot proceeds.
      - Abort: raises SystemExit, boot stops here.
    Returns True if the check ultimately passed, False if continued past a failure.
    """
    while True:
        result = check_fn(*args, **kwargs)
        if result:
            return True

        while True:
            choice = input("        [R]etry / [C]ontinue anyway / [A]bort boot? ").strip().lower()
            if choice in ("r", "retry"):
                break  # breaks inner loop, re-runs check_fn
            elif choice in ("c", "continue"):
                return False
            elif choice in ("a", "abort"):
                print("[BOOT] Aborted by user.")
                raise SystemExit(1)
            else:
                print("        Please enter R, C, or A.")
        # loop back and retry check_fn


# ---- individual checks --------------------------------------------

def _check_power():
    """
    The Pi doesn't expose a way to read rail voltage without extra sensor
    hardware (e.g. INA219), so this isn't a true voltage check. What we can
    say for certain is: if this code is executing, the board is powered.
    The fan (2-pin, no PWM/control line) is wired straight to the same
    rail, so if the Pi is up, the fan rail is live too.
    """
    return _step("Pi powered — fan rail live (2-pin fan, no separate control)")


def _check_camera(camera_index=0):
    """Actually try to open the camera device with OpenCV."""
    try:
        import cv2
    except ImportError as e:
        _step(f"OpenCV not available ({e})", ok=False)
        return False

    dev_path = f"/dev/video{camera_index}"
    if not os.path.exists(dev_path):
        _step(f"Camera device not found ({dev_path})", ok=False)
        return False

    cap = cv2.VideoCapture(camera_index)
    is_open = cap.isOpened()
    if is_open:
        cap.release()
        _step(f"Camera opened ({dev_path})")
        return True
    else:
        _step(f"Camera device exists but could not be opened ({dev_path})", ok=False)
        return False


def _check_tflite_runtime():
    """Actually import the TFLite runtime this project depends on."""
    try:
        import ai_edge_litert  # noqa: F401
        _step("TFLite runtime available (ai_edge_litert)")
        return True
    except ImportError:
        try:
            import tflite_runtime  # noqa: F401
            _step("TFLite runtime available (tflite_runtime)")
            return True
        except ImportError as e:
            _step(f"No TFLite runtime importable ({e})", ok=False)
            return False


def _check_model_file(model_path):
    """Actually check the configured model file exists on disk."""
    if model_path and os.path.exists(model_path):
        _step(f"Model file found ({model_path})")
        return True
    else:
        _step(f"Model file missing ({model_path})", ok=False)
        return False


def _check_serial(serial_port, baud):
    """open the configured serial port."""
    try:
        import serial
    except ImportError as e:
        _step(f"pyserial not available ({e})", ok=False)
        return False

    try:
        ser = serial.Serial(serial_port, baud, timeout=0.5)
        ser.close()
        _step(f"Serial port opened ({serial_port} @ {baud})")
        return True
    except Exception as e:
        _step(f"Serial port unavailable ({serial_port}): {e}", ok=False)
        return False


# ---- boot sequence ------------------------------------------------------

def run_boot_sequence(
    camera_index=0,
    model_path=None,
    density_model_path=None,
    serial_port=None,
    serial_baud=115200,
    skip_delays=False,
):
    """
    Runs the CLASSCAN boot sequence with real subsystem checks.

    Critical checks (camera, model files, serial) prompt interactively on
    failure via _prompt_on_fail: Retry / Continue / Abort. Non-critical
    checks (TFLite runtime import) just print [FAIL] and move on.
    """
    print("=" * 52)
    _type_out("  CLASSCAN  //  Classroom Occupancy Sensing Turret",
              delay=0 if skip_delays else 0.012)
    print("=" * 52)
    print()

    _type_out("[BOOT] Initializing subsystems...\n")

    _check_power()

    # Critical: camera
    _prompt_on_fail(_check_camera, camera_index)

    # Non-critical: runtime import (retrying without fixing the env won't help)
    _check_tflite_runtime()

    # Critical: model files
    if model_path:
        _prompt_on_fail(_check_model_file, model_path)
    if density_model_path:
        _prompt_on_fail(_check_model_file, density_model_path)

    # Critical: serial link
    if serial_port:
        _prompt_on_fail(_check_serial, serial_port, serial_baud)
    else:
        _step("Serial port not configured — skipping", ok=False)

    print()
    _type_out("[BOOT] Subsystem checks complete.", delay=0 if skip_delays else 0.015)
    print("=" * 52)
    print()

    return True


if __name__ == "__main__":
    run_boot_sequence()