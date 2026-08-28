"""
TFLite person-detector wrapper.

Handles:
  - Camera capture (OpenCV / UVC)
  - Frame preprocessing for MobileNetV2-SSD input
  - Inference and bounding-box post-processing
  - Zone-targeted detection (for ZONE_CHECK mode)
"""

import cv2
import numpy as np

try:
    from tflite_runtime.interpreter import Interpreter
except ImportError:
    from tensorflow.lite.python.interpreter import Interpreter  # fallback for dev machines


class Detector:
    def __init__(self, model_path: str, conf_threshold: float = 0.5, camera_index: int = 0):
        self.conf_threshold = conf_threshold

        # ── Load TFLite model ──────────────────────────────────────────────
        self.interpreter = Interpreter(model_path=model_path)
        self.interpreter.allocate_tensors()

        input_details  = self.interpreter.get_input_details()
        self.input_idx = input_details[0]["index"]
        self.input_h   = input_details[0]["shape"][1]
        self.input_w   = input_details[0]["shape"][2]

        output_details     = self.interpreter.get_output_details()
        # Standard SSD output order: boxes, classes, scores, num_detections
        self.out_boxes     = output_details[0]["index"]
        self.out_classes   = output_details[1]["index"]
        self.out_scores    = output_details[2]["index"]
        self.out_num       = output_details[3]["index"]

        # ── Camera ────────────────────────────────────────────────────────
        self.cap = cv2.VideoCapture(camera_index, cv2.CAP_V4L2)
        if not self.cap.isOpened():
            raise RuntimeError(f"Cannot open camera index {camera_index}")

        print(f"[Detector] Model loaded: {model_path}")
        print(f"[Detector] Input size: {self.input_w}×{self.input_h}")

    def capture_frame(self) -> np.ndarray:
        """Grab latest frame from camera. Returns BGR ndarray."""
        ret, frame = self.cap.read()
        if not ret:
            raise RuntimeError("[Detector] Failed to capture frame")
        return frame

    def _preprocess(self, frame: np.ndarray) -> np.ndarray:
        """Resize + normalise frame to model input tensor."""
        resized = cv2.resize(frame, (self.input_w, self.input_h))
        rgb     = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        return np.expand_dims(rgb.astype(np.uint8), axis=0)

    def detect(self, frame: np.ndarray) -> list[dict]:
        """
        Run full-frame inference.
        Returns list of detections: [{"box": [y1,x1,y2,x2], "score": float}]
        Only person class (class 0 in COCO) above conf_threshold.
        """
        tensor = self._preprocess(frame)
        self.interpreter.set_tensor(self.input_idx, tensor)
        self.interpreter.invoke()

        scores  = self.interpreter.get_tensor(self.out_scores)[0]
        classes = self.interpreter.get_tensor(self.out_classes)[0]
        boxes   = self.interpreter.get_tensor(self.out_boxes)[0]
        count   = int(self.interpreter.get_tensor(self.out_num)[0])

        detections = []
        for i in range(count):
            if int(classes[i]) == 0 and scores[i] >= self.conf_threshold:
                detections.append({
                    "box":   boxes[i].tolist(),  # [y1, x1, y2, x2] normalised 0..1
                    "score": float(scores[i]),
                })
        return detections

    def detect_zones(self, frame: np.ndarray, zone_positions: dict) -> dict[str, int]:
        """
        Run inference once on full frame, then bucket detections into
        named zones by bounding-box centre proximity.
        (Zone positions are servo angles, not pixel coords — zone_bbox_map
        must be populated after calibration for pixel-level assignment.)

        For now returns a flat count per zone label based on horizontal
        thirds/quadrants of the frame — replace with calibrated pixel
        zone boundaries once mounted.
        """
        detections = self.detect(frame)
        h, w = frame.shape[:2]

        zone_names = list(zone_positions.keys())
        counts = {z: 0 for z in zone_names}
        n = len(zone_names)

        for det in detections:
            y1, x1, y2, x2 = det["box"]
            cx = (x1 + x2) / 2  # normalised 0..1 horizontal centre
            # Bucket into equal horizontal strips as a placeholder
            idx = min(int(cx * n), n - 1)
            counts[zone_names[idx]] += 1

        return counts

    def release(self):
        self.cap.release()

    def __del__(self):
        self.release()
