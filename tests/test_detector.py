"""
Detector unit tests — no hardware, no real model required.

cv2 and tflite_runtime are stubbed in sys.modules before any import,
so these run cleanly on any machine without opencv or a model file.

Usage:
    python -m pytest tests/test_detector.py -v
"""

import sys
import unittest
from unittest.mock import MagicMock, patch
import numpy as np

sys.path.insert(0, "src/pi")

# ── Stub heavy deps before any detection import ────────────────────────────────

# cv2 stub — only the calls Detector actually makes
_cv2_stub = MagicMock()
_cv2_stub.CAP_V4L2 = 800
_cv2_stub.COLOR_BGR2RGB = 4
_cv2_stub.resize.return_value = np.zeros((300, 300, 3), dtype=np.uint8)
_cv2_stub.cvtColor.return_value = np.zeros((300, 300, 3), dtype=np.uint8)
sys.modules["cv2"] = _cv2_stub

# tflite_runtime stub so the try/except in detector.py resolves cleanly
_tflite_stub = MagicMock()
sys.modules.setdefault("tflite_runtime", _tflite_stub)
sys.modules.setdefault("tflite_runtime.interpreter", _tflite_stub)

# Now safe to import Detector
from detection.detector import Detector  # noqa: E402


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_mock_interpreter(input_h=300, input_w=300, n_det=2,
                            scores=None, classes=None, boxes=None):
    """
    Build a fully-stubbed TFLite Interpreter returning synthetic outputs.
    Default: 2 person detections at 80% and 60% confidence.
    """
    if scores  is None: scores  = np.array([[0.80, 0.60, 0.10]], dtype=np.float32)
    if classes is None: classes = np.array([[0.0,  0.0,  1.0]],  dtype=np.float32)
    if boxes   is None: boxes   = np.array(
        [[[0.1, 0.1, 0.8, 0.4], [0.5, 0.5, 0.9, 0.9], [0.0, 0.0, 0.3, 0.3]]],
        dtype=np.float32,
    )
    num_det = np.array([float(n_det)], dtype=np.float32)

    interp = MagicMock()
    interp.get_input_details.return_value = [
        {"index": 0, "shape": [1, input_h, input_w, 3]}
    ]
    interp.get_output_details.return_value = [
        {"index": 1},  # boxes
        {"index": 2},  # classes
        {"index": 3},  # scores
        {"index": 4},  # num_detections
    ]

    tensor_map = {1: boxes, 2: classes, 3: scores, 4: num_det}
    interp.get_tensor.side_effect = lambda idx: tensor_map[idx]
    return interp


def _make_detector(interp_mock, conf=0.5):
    """Instantiate Detector with a stubbed interpreter + camera."""
    # Patch the Interpreter class inside the already-loaded detector module
    with patch("detection.detector.Interpreter", return_value=interp_mock):
        cap_mock = _cv2_stub.VideoCapture.return_value
        cap_mock.isOpened.return_value = True
        det = Detector("fake.tflite", conf_threshold=conf)
    return det


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestDetectorInit(unittest.TestCase):

    def test_init_success(self):
        interp = _make_mock_interpreter()
        det = _make_detector(interp)
        self.assertEqual(det.input_h, 300)
        self.assertEqual(det.input_w, 300)

    def test_init_camera_failure_raises(self):
        interp = _make_mock_interpreter()
        with patch("detection.detector.Interpreter", return_value=interp):
            cap_mock = _cv2_stub.VideoCapture.return_value
            cap_mock.isOpened.return_value = False
            with self.assertRaises(RuntimeError):
                Detector("fake.tflite", camera_index=99)


class TestDetectorDetect(unittest.TestCase):

    def test_detect_two_persons(self):
        det     = _make_detector(_make_mock_interpreter())
        frame   = np.zeros((480, 640, 3), dtype=np.uint8)
        results = det.detect(frame)
        # Default mock: scores 0.80, 0.60 → both above 0.50 threshold
        self.assertEqual(len(results), 2)
        self.assertIn("score", results[0])
        self.assertIn("box",   results[0])

    def test_detect_filters_by_confidence(self):
        det     = _make_detector(_make_mock_interpreter(), conf=0.75)
        frame   = np.zeros((480, 640, 3), dtype=np.uint8)
        results = det.detect(frame)
        # Only 0.80 survives a 0.75 threshold
        self.assertEqual(len(results), 1)
        self.assertGreaterEqual(results[0]["score"], 0.75)

    def test_detect_filters_non_person_class(self):
        classes = np.array([[1.0, 1.0, 1.0]], dtype=np.float32)
        det     = _make_detector(_make_mock_interpreter(classes=classes))
        frame   = np.zeros((480, 640, 3), dtype=np.uint8)
        results = det.detect(frame)
        self.assertEqual(len(results), 0, "Non-person classes must be excluded")

    def test_detect_empty_frame(self):
        det     = _make_detector(_make_mock_interpreter(n_det=0))
        frame   = np.zeros((480, 640, 3), dtype=np.uint8)
        results = det.detect(frame)
        self.assertEqual(len(results), 0)


class TestDetectorZones(unittest.TestCase):

    def test_zone_counts_sum_to_total(self):
        det            = _make_detector(_make_mock_interpreter(n_det=2))
        frame          = np.zeros((480, 640, 3), dtype=np.uint8)
        zone_positions = {"Q1": (0, 30), "Q2": (90, 30), "Q3": (180, 30), "Q4": (270, 30)}
        zone_counts    = det.detect_zones(frame, zone_positions)
        self.assertEqual(set(zone_counts.keys()), {"Q1", "Q2", "Q3", "Q4"})
        self.assertEqual(sum(zone_counts.values()), 2)


class TestCaptureFrame(unittest.TestCase):

    def test_capture_frame_failure_raises(self):
        det = _make_detector(_make_mock_interpreter())
        det.cap = MagicMock()
        det.cap.read.return_value = (False, None)
        with self.assertRaises(RuntimeError):
            det.capture_frame()


if __name__ == "__main__":
    unittest.main(verbosity=2)
