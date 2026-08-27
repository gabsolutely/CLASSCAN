"""
Frame-diff change trigger unit test — no hardware required.
"""

import sys, numpy as np
sys.path.insert(0, "src/pi")
from detection.change_trigger import ChangeTrigger


def make_frame(brightness: int) -> np.ndarray:
    return np.full((480, 640, 3), brightness, dtype=np.uint8)


def test_no_change():
    t = ChangeTrigger(threshold=0.15)
    f = make_frame(100)
    t.check(f)          # seed reference
    result = t.check(f) # identical — no change
    assert result is False, "Identical frames should not trigger"

def test_big_change():
    t = ChangeTrigger(threshold=0.15)
    t.check(make_frame(100))
    result = t.check(make_frame(230))
    assert result is True, "Large brightness delta should trigger"

def test_threshold_boundary():
    t = ChangeTrigger(threshold=0.50)
    t.check(make_frame(0))
    result = t.check(make_frame(100))
    # 100/255 ≈ 0.39 < 0.50 threshold → should NOT trigger
    assert result is False, "Below-threshold delta should not trigger"


if __name__ == "__main__":
    test_no_change();       print("✓ test_no_change")
    test_big_change();      print("✓ test_big_change")
    test_threshold_boundary(); print("✓ test_threshold_boundary")
    print("All tests passed.")
