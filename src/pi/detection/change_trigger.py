"""
Frame-diff change trigger.

Computes a simple mean-absolute-difference between the current
frame and the last checked frame. If the normalised ratio exceeds
the threshold, a re-detection is triggered immediately.

Typical usage::

    trigger = ChangeTrigger(threshold=0.015)
    # In loop:
    if trigger.check(frame):
        run_inference(frame)
"""

import cv2
import numpy as np


class ChangeTrigger:
    def __init__(self, threshold: float = 0.15):
        """
        Args:
            threshold: fraction of maximum possible pixel diff
                       that must be exceeded to flag a significant change.
                       0.015 ≈ 1.5% mean normalised pixel change (camera motion)
                       0.15  ≈ 15% (large scene shift; used in unit tests only)
        """
        self.threshold  = threshold
        self._last_gray: np.ndarray | None = None

    def check(self, frame: np.ndarray) -> bool:
        """
        Compare *frame* against the last stored reference frame.

        Returns:
            True  if the mean pixel change ratio exceeds ``self.threshold``.
            False on the very first call (no reference yet) or below threshold.

        Side effect: always updates the stored reference to *frame*.
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (9, 9), 0)

        if self._last_gray is None:
            self._last_gray = gray
            return False  # No reference yet — seed only

        diff  = cv2.absdiff(gray, self._last_gray).astype(np.float32)
        ratio = diff.mean() / 255.0

        self._last_gray = gray
        return ratio >= self.threshold

    def reset(self) -> None:
        """Clear the stored reference frame.

        Call this after a deliberate scene change (e.g. servo move) so the
        next ``check()`` call seeds a fresh reference without triggering.
        """
        self._last_gray = None
