"""
Frame-diff change trigger unit test — no hardware required.

Patches cv2 inside the change_trigger module directly so the
real numpy pixel math is exercised with controlled inputs.
No opencv install needed.

Usage:
    python -m pytest tests/test_change_trigger.py -v
"""

import sys
import unittest
from unittest.mock import patch, MagicMock
import numpy as np

sys.path.insert(0, "src/pi")

# Pre-stub cv2 so the module-level import inside change_trigger doesn't fail
if "cv2" not in sys.modules:
    sys.modules["cv2"] = MagicMock()

from detection.change_trigger import ChangeTrigger  # noqa: E402


def make_frame(brightness: int) -> np.ndarray:
    """3-channel (H, W, 3) frame of uniform brightness."""
    return np.full((480, 640, 3), brightness, dtype=np.uint8)


def _real_cv2_side_effects(mock_cv2):
    """
    Wire the cv2 stub to do real numpy operations so ChangeTrigger's
    pixel-diff logic actually runs on our synthetic frames.
    """
    mock_cv2.COLOR_BGR2GRAY = 6
    # cvtColor: take the first channel as "gray" (uniform frames → same result)
    mock_cv2.cvtColor.side_effect = (
        lambda img, code, **kw: img[:, :, 0].astype(np.uint8)
    )
    # GaussianBlur: pass-through (uniform frames are already "blurred")
    mock_cv2.GaussianBlur.side_effect = (
        lambda img, ksize, sigma, **kw: img
    )
    # absdiff: real absolute difference
    mock_cv2.absdiff.side_effect = (
        lambda a, b: np.abs(
            a.astype(np.int32) - b.astype(np.int32)
        ).astype(np.uint8)
    )


class TestChangeTrigger(unittest.TestCase):

    def _patch(self):
        """Context manager: patch cv2 inside change_trigger with real numpy ops."""
        patcher = patch("detection.change_trigger.cv2")
        mock_cv2 = patcher.start()
        _real_cv2_side_effects(mock_cv2)
        self.addCleanup(patcher.stop)

    def test_no_change(self):
        """Identical frames must not trigger."""
        self._patch()
        t = ChangeTrigger(threshold=0.15)
        f = make_frame(100)
        t.check(f)                   # seed reference
        result = t.check(f)          # identical frame
        self.assertFalse(bool(result), "Identical frames should not trigger")

    def test_big_change(self):
        """Large brightness delta (100 → 230) must trigger."""
        self._patch()
        t = ChangeTrigger(threshold=0.15)
        t.check(make_frame(100))
        result = t.check(make_frame(230))
        # diff = 130/255 ≈ 0.51 > 0.15 threshold
        self.assertTrue(bool(result), "Large brightness delta should trigger")

    def test_threshold_boundary(self):
        """Below-threshold delta must not trigger (100/255 ≈ 0.39 < 0.50)."""
        self._patch()
        t = ChangeTrigger(threshold=0.50)
        t.check(make_frame(0))
        result = t.check(make_frame(100))
        self.assertFalse(bool(result), "Below-threshold delta should not trigger")

    def test_first_check_always_returns_false(self):
        """First call seeds the reference — no prior frame to diff against."""
        self._patch()
        t = ChangeTrigger(threshold=0.0)  # threshold=0 → any diff triggers
        result = t.check(make_frame(255))
        self.assertFalse(bool(result), "First call must never trigger")


if __name__ == "__main__":
    unittest.main(verbosity=2)
