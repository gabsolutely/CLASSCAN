"""
TFLite person-detector and camera capture wrapper.

Handles:
  - Camera capture (Real OpenCV UVC/CSI with MockCamera fallback)
  - Preprocessing & inference for MobileNetV2-SSD
  - Simulated detection for camera-less testing
  - HUD overlay rendering (bounding boxes, telemetry cards, scanlines)
  - Zone-targeted detection
"""

import math
import os
import random
import sys
import time
from pathlib import Path

import cv2
import numpy as np


# ── Annotation / HUD Drawing ───────────────────────────────────────────────────
_ACCENT     = (180, 230, 0)     # cyan-green (BGR)
_WARN       = (71, 179, 255)    # amber-orange
_WHITE      = (220, 220, 220)
_DIM        = (80, 80, 80)
_GRID_COLOR = (35, 45, 40)
_CORNER_LEN = 16


def _draw_corner_bracket(img: np.ndarray, x1: int, y1: int, x2: int, y2: int, color: tuple, thick: int = 2):
    """Draw corner brackets for detection bounding boxes."""
    length = min(_CORNER_LEN, max(4, (x2 - x1) // 4), max(4, (y2 - y1) // 4))
    cv2.line(img, (x1, y1), (x1 + length, y1), color, thick)
    cv2.line(img, (x1, y1), (x1, y1 + length), color, thick)
    cv2.line(img, (x2, y1), (x2 - length, y1), color, thick)
    cv2.line(img, (x2, y1), (x2, y1 + length), color, thick)
    cv2.line(img, (x1, y2), (x1 + length, y2), color, thick)
    cv2.line(img, (x1, y2), (x1, y2 - length), color, thick)
    cv2.line(img, (x2, y2), (x2 - length, y2), color, thick)
    cv2.line(img, (x2, y2), (x2, y2 - length), color, thick)


def draw_hud_overlay(frame: np.ndarray, detections: list, fps: float = 0.0,
                     mode_str: str = "SWEEP", source_tag: str = "LIVE") -> np.ndarray:
    """Annotate frame with bounding boxes, HUD cards, scanlines, and status badges."""
    h, w = frame.shape[:2]
    out = frame.copy()

    # Per-detection bounding boxes
    for det in detections:
        y1n, x1n, y2n, x2n = det["box"]
        x1 = max(0, min(w - 1, int(x1n * w)))
        y1 = max(0, min(h - 1, int(y1n * h)))
        x2 = max(0, min(w - 1, int(x2n * w)))
        y2 = max(0, min(h - 1, int(y2n * h)))
        score = det.get("score", 0.85)

        color = _ACCENT if score >= 0.70 else _WARN

        # Dim filled rectangle simulation
        dim_color = (color[0] // 5, color[1] // 5, color[2] // 5)
        cv2.rectangle(out, (x1, y1), (x2, y2), dim_color, 1)
        _draw_corner_bracket(out, x1, y1, x2, y2, color, thick=2)

        # Confidence label
        label = f"PERSON {score:.0%}"
        font_scale = 0.40
        (lw, lh), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 1)
        label_y = max(y1 - 6, lh + 4)
        cv2.rectangle(out, (x1, label_y - lh - 4), (x1 + lw + 6, label_y + 2), (0, 0, 0), -1)
        cv2.putText(out, label, (x1 + 3, label_y - 1), cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, 1, cv2.LINE_AA)

    # Top-left HUD card
    count = len(detections)
    panel_lines = [
        ("CLASSCAN // " + source_tag, _DIM, 0.36),
        (f"OCCUPANCY  {count:>3d}", _ACCENT if count > 0 else _WHITE, 0.58),
        (f"FPS  {fps:>5.1f} | MODE: {mode_str}", _WHITE, 0.36),
    ]

    py = 16
    for text, color, fs in panel_lines:
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, fs, 1)
        cv2.rectangle(out, (8, py - th - 3), (16 + tw, py + 4), (0, 0, 0), -1)
        cv2.putText(out, text, (11, py), cv2.FONT_HERSHEY_SIMPLEX, fs, color, 1, cv2.LINE_AA)
        py += th + 9

    # Bottom timestamp
    ts = time.strftime("%H:%M:%S")
    (tw, th), _ = cv2.getTextSize(ts, cv2.FONT_HERSHEY_SIMPLEX, 0.36, 1)
    cv2.putText(out, ts, (w - tw - 10, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.36, _DIM, 1, cv2.LINE_AA)

    # Moving scan-line effect
    scan_y = int((time.time() % 2.5) / 2.5 * h)
    cv2.line(out, (0, scan_y), (w, scan_y), (0, 70, 55), 1)

    return out


# ── Camera Abstraction ─────────────────────────────────────────────────────────

class CameraCapture:
    """Manages real UVC/CSI camera with automatic fallback to synthetic generator."""
    def __init__(self, camera_index: int = 0, force_mock: bool = False, width: int = 640, height: int = 480):
        self.width = width
        self.height = height
        self.is_mock = force_mock
        self.cap = None
        self._start_time = time.time()

        if not force_mock:
            backend = cv2.CAP_V4L2 if hasattr(cv2, "CAP_V4L2") and sys.platform.startswith("linux") else cv2.CAP_ANY
            try:
                self.cap = cv2.VideoCapture(camera_index, backend)
                if self.cap.isOpened():
                    print(f"[Camera] Opened hardware camera index {camera_index}")
                else:
                    print(f"[Camera] Camera index {camera_index} not opened. Using simulated camera.")
                    self.is_mock = True
            except Exception as e:
                print(f"[Camera] Failed to open camera ({e}). Using simulated camera.")
                self.is_mock = True
        else:
            print("[Camera] Mock mode active (simulated classroom camera).")

    def capture_frame(self) -> np.ndarray:
        if not self.is_mock and self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret and frame is not None:
                return frame

        # Simulated frame generation
        img = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        img[:] = (12, 16, 20)

        for x in range(0, self.width, 60):
            cv2.line(img, (x, 0), (x, self.height), _GRID_COLOR, 1)
        for y in range(0, self.height, 45):
            cv2.line(img, (0, y), (self.width, y), _GRID_COLOR, 1)

        mid_x = self.width // 2
        mid_y = self.height // 2
        cv2.line(img, (mid_x, 0), (mid_x, self.height), (20, 70, 60), 1)
        cv2.line(img, (0, mid_y), (self.width, mid_y), (20, 70, 60), 1)

        cv2.putText(img, "ZONE Q1", (15, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (40, 90, 80), 1)
        cv2.putText(img, "ZONE Q2", (mid_x + 15, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (40, 90, 80), 1)
        cv2.putText(img, "ZONE Q3", (15, mid_y + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (40, 90, 80), 1)
        cv2.putText(img, "ZONE Q4", (mid_x + 15, mid_y + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (40, 90, 80), 1)

        cv2.putText(img, "[SIMULATED CAMERA STREAM]", (mid_x - 110, self.height - 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, (50, 100, 90), 1)

        time.sleep(0.035)  # Simulate frame interval
        return img

    def release(self):
        if self.cap and self.cap.isOpened():
            self.cap.release()


# ── Detector Abstraction ───────────────────────────────────────────────────────

class Detector:
    def __init__(self, model_path: str = "models/mobilenet_v2_ssd_classcan.tflite",
                 conf_threshold: float = 0.5, camera_index: int = 0,
                 force_mock: bool = False, mock_count: int = 4):
        self.conf_threshold = conf_threshold
        self.is_mock = force_mock
        self.interpreter = None
        self.camera = CameraCapture(camera_index=camera_index, force_mock=force_mock)

        # Simulation slots
        self._current_mock_count = mock_count
        self._last_mock_shift = time.time()
        self._mock_slots = [
            {"box": [0.18, 0.08, 0.42, 0.22], "base_score": 0.88},
            {"box": [0.22, 0.25, 0.45, 0.38], "base_score": 0.92},
            {"box": [0.16, 0.55, 0.40, 0.68], "base_score": 0.85},
            {"box": [0.20, 0.72, 0.44, 0.86], "base_score": 0.91},
            {"box": [0.55, 0.10, 0.80, 0.24], "base_score": 0.79},
            {"box": [0.58, 0.28, 0.82, 0.42], "base_score": 0.84},
            {"box": [0.54, 0.58, 0.78, 0.72], "base_score": 0.89},
            {"box": [0.60, 0.75, 0.84, 0.90], "base_score": 0.82},
        ]

        if not force_mock:
            # Check model file exists
            resolved_model = Path(model_path)
            if not resolved_model.is_file():
                alt = Path(__file__).resolve().parent.parent.parent / model_path
                if alt.is_file():
                    resolved_model = alt

            if resolved_model.is_file():
                try:
                    try:
                        from tflite_runtime.interpreter import Interpreter
                    except ImportError:
                        from tensorflow.lite.python.interpreter import Interpreter

                    self.interpreter = Interpreter(model_path=str(resolved_model))
                    self.interpreter.allocate_tensors()

                    inp = self.interpreter.get_input_details()[0]
                    self.input_idx   = inp["index"]
                    self.input_h     = inp["shape"][1]
                    self.input_w     = inp["shape"][2]
                    self.input_dtype = inp["dtype"]

                    outs = self.interpreter.get_output_details()
                    # Auto-detect tensor roles by shape/order
                    self.out_boxes = outs[0]["index"]
                    self.out_classes = outs[1]["index"]
                    self.out_scores = outs[2]["index"]
                    self.out_num = outs[3]["index"]

                    for o in outs:
                        shape = list(o["shape"])
                        if len(shape) == 3 and shape[-1] == 4:
                            self.out_boxes = o["index"]
                        elif len(shape) == 2 and (o["dtype"] == np.float32 or o["dtype"] == np.float64):
                            # Usually scores or classes
                            if "score" in o.get("name", "").lower():
                                self.out_scores = o["index"]
                            elif "class" in o.get("name", "").lower():
                                self.out_classes = o["index"]
                        elif len(shape) == 1:
                            self.out_num = o["index"]

                    print(f"[Detector] Model loaded successfully: {resolved_model} ({self.input_w}x{self.input_h}, dtype={self.input_dtype.__name__})")
                except Exception as e:
                    print(f"[Detector] Model initialization error ({e}). Using simulated detector.")
                    self.is_mock = True
            else:
                print(f"[Detector] Model '{model_path}' not found. Using simulated detector.")
                self.is_mock = True
        else:
            print("[Detector] Simulated detector active.")

    def capture_frame(self) -> np.ndarray:
        return self.camera.capture_frame()

    def detect(self, frame: np.ndarray) -> list[dict]:
        if self.is_mock or self.interpreter is None:
            now = time.time()
            if now - self._last_mock_shift > 8.0:
                delta = random.choice([-1, 0, 1])
                self._current_mock_count = max(0, min(len(self._mock_slots), self._current_mock_count + delta))
                self._last_mock_shift = now

            active = self._mock_slots[:self._current_mock_count]
            detections = []
            for s in active:
                jitter = math.sin(now * 2 + s["base_score"]) * 0.02
                score = max(0.51, min(0.99, s["base_score"] + jitter))
                detections.append({"box": s["box"], "score": round(score, 3)})
            return detections

        # Real TFLite inference
        resized = cv2.resize(frame, (self.input_w, self.input_h))
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)

        if self.input_dtype == np.float32:
            input_data = (np.float32(rgb) - 127.5) / 127.5
        else:
            input_data = rgb.astype(np.uint8)

        tensor = np.expand_dims(input_data, axis=0)

        self.interpreter.set_tensor(self.input_idx, tensor)
        self.interpreter.invoke()

        scores  = self.interpreter.get_tensor(self.out_scores)[0]
        classes = self.interpreter.get_tensor(self.out_classes)[0]
        boxes   = self.interpreter.get_tensor(self.out_boxes)[0]
        count_tensor = self.interpreter.get_tensor(self.out_num)
        count   = int(count_tensor[0]) if count_tensor.size > 0 else len(scores)

        detections = []
        for i in range(count):
            cls_id = int(classes[i])
            score_val = float(scores[i])
            # COCO Person class is index 0
            if cls_id == 0 and score_val >= self.conf_threshold:
                detections.append({
                    "box": boxes[i].tolist(),
                    "score": score_val,
                })
        return detections

    def detect_zones(self, frame: np.ndarray, zone_positions: dict) -> dict[str, int]:
        detections = self.detect(frame)
        zone_names = list(zone_positions.keys())
        counts = {z: 0 for z in zone_names}
        n = len(zone_names)

        for det in detections:
            y1, x1, y2, x2 = det["box"]
            cx = (x1 + x2) / 2
            idx = min(int(cx * n), n - 1)
            counts[zone_names[idx]] += 1

        return counts

    def release(self):
        self.camera.release()

    def __del__(self):
        self.release()
