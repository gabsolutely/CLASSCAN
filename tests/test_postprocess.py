"""
Tests for NMS and post-processing functions in detector.py.
"""

import numpy as np
import pytest
import sys
from pathlib import Path

# Add src/pi to path so detector.py can be imported without a full install
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "pi"))

from detection.detector import non_max_suppression


# ─── NMS unit tests ───────────────────────────────────────────────────────────

class TestNonMaxSuppression:

    def test_empty_input(self):
        """NMS on empty arrays returns empty list."""
        boxes  = np.zeros((0, 4), dtype=np.float32)
        scores = np.zeros(0, dtype=np.float32)
        result = non_max_suppression(boxes, scores)
        assert result == []

    def test_single_detection(self):
        """Single box always kept."""
        boxes  = np.array([[0.1, 0.1, 0.5, 0.5]], dtype=np.float32)
        scores = np.array([0.9], dtype=np.float32)
        result = non_max_suppression(boxes, scores)
        assert result == [0]

    def test_verified_synthetic_case(self):
        """
        Reproduced from the Colab verification session:
        4 detections → 2 after NMS.
          - Boxes 0,1,2 all overlap heavily (same head, 3 duplicate predictions)
          - Box 3 is a separate non-overlapping head
        Expected: keep box 0 (highest score among cluster) + box 3.
        """
        boxes = np.array([
            [0.10, 0.10, 0.30, 0.30],  # head A, highest score → kept
            [0.11, 0.11, 0.31, 0.31],  # head A duplicate → suppressed
            [0.12, 0.09, 0.32, 0.29],  # head A duplicate → suppressed
            [0.60, 0.60, 0.80, 0.80],  # head B, separate → kept
        ], dtype=np.float32)

        scores = np.array([0.92, 0.75, 0.68, 0.85], dtype=np.float32)

        result = non_max_suppression(boxes, scores, iou_threshold=0.45)

        assert len(result) == 2, f"Expected 2 detections after NMS, got {len(result)}"
        # Highest-confidence duplicate kept (box 0, score 0.92)
        assert 0 in result, "Box 0 (highest confidence in cluster) should be kept"
        # Non-overlapping box kept
        assert 3 in result, "Box 3 (separate head, score 0.85) should be kept"
        # Duplicates suppressed
        assert 1 not in result, "Box 1 (overlap duplicate) should be suppressed"
        assert 2 not in result, "Box 2 (overlap duplicate) should be suppressed"

    def test_no_overlap_all_kept(self):
        """Non-overlapping boxes — all should be kept."""
        boxes = np.array([
            [0.00, 0.00, 0.10, 0.10],
            [0.20, 0.20, 0.30, 0.30],
            [0.50, 0.50, 0.65, 0.65],
            [0.80, 0.80, 0.95, 0.95],
        ], dtype=np.float32)
        scores = np.array([0.9, 0.8, 0.7, 0.6], dtype=np.float32)

        result = non_max_suppression(boxes, scores, iou_threshold=0.45)

        assert len(result) == 4, f"All 4 non-overlapping boxes should be kept, got {len(result)}"

    def test_complete_overlap_one_kept(self):
        """Identical boxes → only the highest-confidence one kept."""
        box = [0.10, 0.10, 0.40, 0.40]
        boxes  = np.array([box, box, box], dtype=np.float32)
        scores = np.array([0.5, 0.9, 0.7], dtype=np.float32)

        result = non_max_suppression(boxes, scores, iou_threshold=0.45)

        assert len(result) == 1
        # Box 1 has highest score (0.9) — should be kept
        assert result[0] == 1

    def test_iou_threshold_sensitivity(self):
        """
        Tests that IoU threshold controls suppression correctly.
        With a higher (permissive) IoU threshold (e.g. 0.50), moderate overlap is tolerated,
        so both boxes are kept.
        With a lower (aggressive) IoU threshold (e.g. 0.10), even slight overlap triggers
        suppression, so only the highest-scoring box is kept.
        """
        # Two boxes with moderate overlap (intersection 0.2x0.2=0.04, union=0.14 -> IoU ≈ 0.286)
        boxes = np.array([
            [0.10, 0.10, 0.40, 0.40],
            [0.20, 0.20, 0.50, 0.50],
        ], dtype=np.float32)
        scores = np.array([0.9, 0.7], dtype=np.float32)

        # Permissive threshold (0.50 >= 0.286): both kept
        result_permissive = non_max_suppression(boxes, scores, iou_threshold=0.50)
        assert len(result_permissive) == 2, "Permissive threshold (0.50) should keep both boxes"

        # Aggressive threshold (0.10 < 0.286): lower-confidence box suppressed
        result_aggressive = non_max_suppression(boxes, scores, iou_threshold=0.10)
        assert len(result_aggressive) == 1, "Aggressive threshold (0.10) should suppress overlapping box"
        assert result_aggressive[0] == 0, "Highest-score box should be kept"

    def test_output_order_descending_confidence(self):
        """Returned indices should be in descending confidence order."""
        boxes = np.array([
            [0.0, 0.0, 0.1, 0.1],
            [0.2, 0.2, 0.3, 0.3],
            [0.5, 0.5, 0.6, 0.6],
        ], dtype=np.float32)
        scores = np.array([0.5, 0.9, 0.7], dtype=np.float32)

        result = non_max_suppression(boxes, scores)
        # All non-overlapping; order should be 1 (0.9), 2 (0.7), 0 (0.5)
        assert result == [1, 2, 0], f"Expected [1, 2, 0], got {result}"


# ─── Exact count match regression test ───────────────────────────────────────

class TestCountMatch:

    def test_13_box_count_match_scenario(self):
        """
        Regression: epoch-55 inference on val image produced 13 raw predictions,
        13 after NMS, matching 13 ground-truth boxes exactly.

        This synthetic test verifies that our NMS doesn't drop or add detections
        when no duplicates exist (all non-overlapping clusters of size 1).
        """
        rng = np.random.default_rng(seed=42)
        n = 13
        # Generate 13 well-separated boxes (grid layout → no overlaps)
        boxes = []
        for i in range(n):
            row = i // 4
            col = i % 4
            y1 = row * 0.22 + 0.01
            x1 = col * 0.22 + 0.01
            boxes.append([y1, x1, y1 + 0.12, x1 + 0.12])

        boxes  = np.array(boxes, dtype=np.float32)
        scores = rng.uniform(0.35, 0.75, size=n).astype(np.float32)

        result = non_max_suppression(boxes, scores, iou_threshold=0.45)
        assert len(result) == 13, (
            f"All 13 non-overlapping boxes should survive NMS, got {len(result)}"
        )
