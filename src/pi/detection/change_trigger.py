"""
Frame-diff change trigger.

Computes a simple mean-absolute-difference between the current
frame and the last checked frame. If the ratio exceeds the
threshold, a re-detection is triggered immediately.
"""

import cv2
import numpy as np


class ChangeTrigger:
    def __init__(self, threshold: float = 0.15):
        """
        threshold: fraction of maximum possible pixel diff
                   that must be exceeded to flag a significant change.
                   0.15 ≈ 15% mean normalised pixel change.
        """
        self.threshold  = threshold
        self._last_gray: np.ndarray | None = None

    def check(self, frame: np.ndarray) -> bool:
        """
        Compare current frame against the last stored frame.
        Returns True if change is significant, False otherwise.
        Updates the stored reference frame on every call.
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (9, 9), 0)

        if self._last_gray is None:
            self._last_gray = gray
            return False  # No reference yet

        diff  = cv2.absdiff(gray, self._last_gray).astype(np.float32)
        ratio = diff.mean() / 255.0

        self._last_gray = gray
        return ratio >= self.threshold
