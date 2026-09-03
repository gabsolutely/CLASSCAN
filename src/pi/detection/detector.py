"""
CLASSCAN — TFLite Head Detector Wrapper
========================================
Handles model loading, camera capture, inference, and post-processing for
both the custom CLASSCAN head detector and the stock COCO SSD fallback.

Model Support
-------------
Two model formats are handled automatically (detected by output tensor count):

1. CLASSCAN Head Detector (classcan_head_v1.tflite) — PRIMARY
   Exported from Keras multi-scale MobileNetV2 via scripts/export_to_tflite.py.
   Architecture: 3-head FPN (P3 38×38 / P4 19×19 / P5 10×10), occupancy-based
   target encoding, focal loss + smooth-L1, trained on SCUT-HEAD + local classroom.
   The export wrapper bakes sigmoid + NMS into the TFLite graph, so output is:
     • boxes  [1, MAX_DETECTIONS, 4]  float32  [ymin,xmin,ymax,xmax] normalized, padded
     • scores [1, MAX_DETECTIONS]     float32  objectness scores, padded
     • count  [1]                     int32    valid detection count
   NMS is already applied — detector.py uses :count to slice valid detections only.
   Class filter: ALL detections are 'head' (single-class model).

2. COCO MobileNetV2-SSD fallback (mobilenet_v2_ssd_classcan.tflite)
   Stock COCO model, used when classcan_head_v1.tflite is not present.
   4-tensor output: boxes [1,N,4], classes [1,N], scores [1,N], num_detections [1].
   Filters class 0 ('person') above conf_threshold.
   NOTE: This fallback will undercount in real classroom conditions (fails on
   desk-occluded distant rows). Only suitable for PoC pipeline smoke-testing.

Training History (summary)
--------------------------
  - 50-epoch run (brother's laptop): val plateau ~ep47-50. 13/13 count match on val.
  - +10 epochs with box_loss_weight=2.0: val bottomed ep55, started rising ep60.
  - Best checkpoint: epoch 55 (Drive-verified, 18922768 bytes).
  - Export: scripts/export_to_tflite.py --weights ckpt_ep55.weights.h5 --quant float32
"""

import cv2
import numpy as np

try:
    from ai_edge_litert.interpreter import Interpreter  # current, maintained package
except ImportError:
    try:
        from tflite_runtime.interpreter import Interpreter  # legacy package
    except ImportError:
        from tensorflow.lite.python.interpreter import Interpreter  # dev fallback


# ─── NMS ─────────────────────────────────────────────────────────────────────

def non_max_suppression(boxes: np.ndarray, scores: np.ndarray,
                        iou_threshold: float = 0.45) -> list[int]:
    """
    Greedy IoU-based NMS. Returns indices of kept boxes (highest-confidence first).

    Used as a fallback if the export wrapper's built-in NMS is bypassed
    (e.g. when using raw multi-scale output for debugging), or for future
    inference paths that output pre-NMS candidates.

    Verified on synthetic test: 4 detections → 2.
    3 overlapping boxes collapsed to 1 (highest confidence), separate box kept.

    Args:
        boxes:         (N, 4) float32 [ymin, xmin, ymax, xmax] normalized 0..1
        scores:        (N,) float32 objectness scores
        iou_threshold: suppress boxes with IoU > threshold vs. a kept box

    Returns:
        List of integer indices into boxes/scores of kept detections.
    """
    if len(boxes) == 0:
        return []

    order = np.argsort(scores)[::-1]
    kept = []

    while len(order) > 0:
        i = order[0]
        kept.append(int(i))
        order = order[1:]

        if len(order) == 0:
            break

        iy1 = np.maximum(boxes[i, 0], boxes[order, 0])
        ix1 = np.maximum(boxes[i, 1], boxes[order, 1])
        iy2 = np.minimum(boxes[i, 2], boxes[order, 2])
        ix2 = np.minimum(boxes[i, 3], boxes[order, 3])

        inter_h = np.maximum(0.0, iy2 - iy1)
        inter_w = np.maximum(0.0, ix2 - ix1)
        inter   = inter_h * inter_w

        area_i = (boxes[i, 2] - boxes[i, 0]) * (boxes[i, 3] - boxes[i, 1])
        area_r = (boxes[order, 2] - boxes[order, 0]) * (boxes[order, 3] - boxes[order, 1])
        iou = inter / np.maximum(area_i + area_r - inter, 1e-6)

        order = order[iou <= iou_threshold]

    return kept


# ─── Mock camera / detector for pipeline testing without hardware ─────────────

class _MockCapture:
    """Simulates camera frames when no physical camera is available."""
    def __init__(self, mock_count: int = 4):
        self.mock_count = mock_count
        self._frame_w = 640
        self._frame_h = 480

    def read(self):
        frame = np.zeros((self._frame_h, self._frame_w, 3), dtype=np.uint8)
        frame[:] = (30, 30, 30)
        return True, frame

    def release(self):
        pass

    def isOpened(self):
        return True


# ─── Detector ─────────────────────────────────────────────────────────────────

class Detector:
    """
    CLASSCAN TFLite head detector.

    Supports two model output formats (auto-detected on load):
      - CLASSCAN head model: 3-tensor output [boxes, scores, count]
      - COCO SSD fallback:   4-tensor output [boxes, classes, scores, num_det]

    Parameters
    ----------
    model_path    : str   — path to .tflite model file
    conf_threshold: float — objectness / score confidence cutoff (default 0.35 for
                            CLASSCAN model; recommended 0.50 for COCO fallback)
    camera_index  : int   — OpenCV camera device index
    force_mock    : bool  — skip camera open, return synthetic frames
    mock_count    : int   — number of simulated detections in mock mode
    """

    def __init__(
        self,
        model_path: str,
        conf_threshold: float = 0.35,
        camera_index: int = 0,
        force_mock: bool = False,
        mock_count: int = 4,
    ):
        self.conf_threshold = conf_threshold
        self.is_mock = force_mock

        # ── Load TFLite model ──────────────────────────────────────────────
        self.interpreter = Interpreter(model_path=model_path)
        self.interpreter.allocate_tensors()

        input_details     = self.interpreter.get_input_details()
        self.input_idx    = input_details[0]["index"]
        self.input_h      = input_details[0]["shape"][1]
        self.input_w      = input_details[0]["shape"][2]
        self.input_dtype  = input_details[0].get("dtype", np.float32)  # fallback for mock interpreters

        output_details    = self.interpreter.get_output_details()
        self._num_outputs = len(output_details)

        # ── Detect model format ───────────────────────────────────────────
        # CLASSCAN export wrapper: 3 outputs named 'boxes', 'scores', 'count'
        # COCO SSD: 4 outputs (boxes, classes, scores, num_detections)
        out_names = [d.get("name", "") for d in output_details]
        self._is_classcan_model = (
            self._num_outputs == 3 and
            any("count" in n for n in out_names)
        )

        if self._is_classcan_model:
            # Map by name (robust to index ordering differences)
            out_map = {
                d["name"].split("/")[-1].split(":")[0]: d
                for d in output_details
                if "name" in d
            }
            # Fallback to positional if names don't match expected pattern
            self._out_boxes_idx  = out_map.get("boxes",  output_details[0])["index"]
            self._out_scores_idx = out_map.get("scores", output_details[1])["index"]
            self._out_count_idx  = out_map.get("count",  output_details[2])["index"]
            print(f"[Detector] Model type: CLASSCAN head detector (3-tensor NMS output)")
        else:
            # COCO SSD 4-tensor format
            self._out_boxes_idx  = output_details[0]["index"]
            self._out_classes_idx = output_details[1]["index"] if self._num_outputs > 1 else None
            self._out_scores_idx  = output_details[2]["index"] if self._num_outputs > 2 else None
            self._out_num_idx     = output_details[3]["index"] if self._num_outputs > 3 else None
            print(f"[Detector] Model type: COCO SSD fallback ({self._num_outputs}-tensor output)")
            print(f"           NOTE: COCO model will undercount desk-occluded students.")

        # ── Camera ────────────────────────────────────────────────────────
        if force_mock:
            self.cap = _MockCapture(mock_count=mock_count)
            self._mock_count = mock_count
            print(f"[Detector] Mock mode — simulating {mock_count} detections")
        else:
            self.cap = cv2.VideoCapture(camera_index, cv2.CAP_V4L2)
            if not self.cap.isOpened():
                self.cap = cv2.VideoCapture(camera_index)  # Fallback (non-Linux dev)
            if not self.cap.isOpened():
                raise RuntimeError(
                    f"[Detector] Cannot open camera device {camera_index}. "
                    f"Check: camera connected? correct device index? V4L2 driver loaded?"
                )

        print(f"[Detector] Model loaded: {model_path}")
        print(f"[Detector] Input size:   {self.input_w}×{self.input_h}  dtype={self.input_dtype.__name__}")
        print(f"[Detector] Conf threshold: {self.conf_threshold}")

    # ── Frame capture ──────────────────────────────────────────────────────

    def capture_frame(self) -> np.ndarray:
        """Grab latest frame from camera. Returns BGR ndarray."""
        ret, frame = self.cap.read()
        if not ret:
            raise RuntimeError("[Detector] Failed to capture frame from camera")
        return frame

    # ── Preprocessing ──────────────────────────────────────────────────────

    def _preprocess(self, frame: np.ndarray) -> np.ndarray:
        """
        Resize + normalize frame to match model input tensor.

        CLASSCAN model: expects float32 [0, 1] (normalized in export wrapper).
        COCO SSD fallback: expects uint8 [0, 255].
        """
        resized = cv2.resize(frame, (self.input_w, self.input_h))
        rgb     = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)

        if self._is_classcan_model:
            return np.expand_dims(rgb.astype(np.float32) / 255.0, axis=0)
        else:
            return np.expand_dims(rgb.astype(np.uint8), axis=0)

    # ── Inference ─────────────────────────────────────────────────────────

    def detect(self, frame: np.ndarray) -> list[dict]:
        """
        Run full-frame inference on the given BGR frame.

        Returns list of detections:
            [{"box": [y1, x1, y2, x2], "score": float}, ...]
        where box coordinates are normalized 0..1.

        In mock mode: returns synthetic detections without touching the model.
        """
        if self.is_mock:
            return self._mock_detections()

        tensor = self._preprocess(frame)
        self.interpreter.set_tensor(self.input_idx, tensor)
        self.interpreter.invoke()

        if self._is_classcan_model:
            return self._parse_classcan_output()
        else:
            return self._parse_coco_ssd_output()

    def _parse_classcan_output(self) -> list[dict]:
        """
        Parse CLASSCAN head detector output (3-tensor, NMS already applied).

        Tensors:
            boxes  [1, MAX, 4]  float32  [ymin,xmin,ymax,xmax] normalized, zero-padded
            scores [1, MAX]     float32  scores, zero-padded
            count  [1]          int32    valid detection count
        """
        boxes  = self.interpreter.get_tensor(self._out_boxes_idx)[0]   # (MAX, 4)
        scores = self.interpreter.get_tensor(self._out_scores_idx)[0]  # (MAX,)
        count  = int(self.interpreter.get_tensor(self._out_count_idx)[0])

        detections = []
        for i in range(count):
            if scores[i] >= self.conf_threshold:
                detections.append({
                    "box":   boxes[i].tolist(),  # [y1, x1, y2, x2] normalized
                    "score": float(scores[i]),
                })
        return detections

    def _parse_coco_ssd_output(self) -> list[dict]:
        """
        Parse COCO MobileNetV2-SSD output (4-tensor format).
        Filters class 0 ('person') above conf_threshold.
        """
        scores  = self.interpreter.get_tensor(self._out_scores_idx)[0]
        classes = self.interpreter.get_tensor(self._out_classes_idx)[0]
        boxes   = self.interpreter.get_tensor(self._out_boxes_idx)[0]
        count   = int(self.interpreter.get_tensor(self._out_num_idx)[0])

        detections = []
        for i in range(count):
            if int(classes[i]) == 0 and scores[i] >= self.conf_threshold:
                detections.append({
                    "box":   boxes[i].tolist(),
                    "score": float(scores[i]),
                })
        return detections

    def _mock_detections(self) -> list[dict]:
        """Return synthetic detections for mock/simulation mode."""
        count = self._mock_count
        detections = []
        for k in range(count):
            y_base = 0.1 + (k / max(count, 1)) * 0.6
            detections.append({
                "box": [y_base, 0.1 + k * 0.15, y_base + 0.15, 0.25 + k * 0.15],
                "score": 0.80,
            })
        return detections

    # ── Zone detection ────────────────────────────────────────────────────

    def detect_zones(self, frame: np.ndarray,
                     zone_positions: dict) -> dict[str, int]:
        """
        Run inference once on full frame, then bucket detections into
        named zones by bounding-box centre position.

        zone_positions: dict of zone_name → (pan_deg, tilt_deg) servo angles.
        Zones are currently assigned by horizontal thirds/quadrants of the frame.
        Replace with calibrated pixel zone boundaries post-deployment.

        Returns dict: {zone_name: count}
        """
        detections = self.detect(frame)
        zone_names = list(zone_positions.keys())
        counts = {z: 0 for z in zone_names}
        n = len(zone_names)

        for det in detections:
            y1, x1, y2, x2 = det["box"]
            cx = (x1 + x2) / 2.0   # Normalized 0..1 horizontal centre
            idx = min(int(cx * n), n - 1)
            counts[zone_names[idx]] += 1

        return counts

    # ── Cleanup ───────────────────────────────────────────────────────────

    def release(self):
        if hasattr(self, "cap"):
            self.cap.release()

    def __del__(self):
        self.release()


# ─── HUD Overlay ─────────────────────────────────────────────────────────────

def draw_hud_overlay(
    frame: np.ndarray,
    detections: list[dict],
    fps: float = 0.0,
    mode_str: str = "SWEEP",
    source_tag: str = "HARDWARE",
) -> np.ndarray:
    """
    Draw bounding boxes and HUD info bar on a BGR frame for the dashboard stream.

    Returns a new BGR ndarray with annotations.
    """
    out = frame.copy()
    h, w = out.shape[:2]
    count = len(detections)

    # Draw detection boxes
    for det in detections:
        y1, x1, y2, x2 = det["box"]
        px1 = int(x1 * w)
        py1 = int(y1 * h)
        px2 = int(x2 * w)
        py2 = int(y2 * h)
        cv2.rectangle(out, (px1, py1), (px2, py2), (0, 255, 80), 2)
        label = f"{det['score']:.2f}"
        cv2.putText(out, label, (px1, max(py1 - 5, 0)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 80), 1)

    # HUD bar
    cv2.rectangle(out, (0, 0), (w, 50), (0, 0, 0), -1)  # Black bar
    cv2.putText(
        out,
        f"CLASSCAN  Count: {count}  |  {mode_str}  |  {fps:.1f} FPS  |  [{source_tag}]",
        (10, 33),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (255, 255, 255),
        1,
    )
    return out