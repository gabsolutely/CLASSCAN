"""
Unit tests for scripts/hardware_verify.py.
Verifies the commissioning script and ESP32 JSON protocol formatting in mock mode.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from hardware_verify import (
    Esp32HardwareInterface,
    verify_lcd_display,
    verify_pan_tilt_servos,
    verify_ldr_illumination,
)


def test_esp32_interface_mock_mode():
    hw = Esp32HardwareInterface(mock=True)
    assert hw.mock is True
    assert hw.last_state == "idle"

    # Test count command
    assert hw.set_headcount(14) is True

    # Test command string
    assert hw.send_command("MODE_SWEEP") is True
    assert hw.stop_servos() is True
    assert hw.center_servos() is True

    # Test quadrant moves
    assert hw.move_to_zone("Q1") is True
    assert hw.move_to_zone("Q4") is True

    # Test raw servo speeds
    assert hw.set_servo_speed(pan=155, tilt=90, duration_ms=500) is True

    # Test servo angle move
    assert hw.set_servo_angle(pan_angle=45, tilt_angle=30, speed=155) is True

    hw.close()


def test_hardware_verify_routines_mock():
    hw = Esp32HardwareInterface(mock=True)

    # All three routine functions should succeed without exceptions
    assert verify_lcd_display(hw) is True
    assert verify_pan_tilt_servos(hw) is True
    assert verify_ldr_illumination(hw) is True

    hw.close()
