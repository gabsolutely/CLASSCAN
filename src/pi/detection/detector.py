"""
CLASSCAN — TFLite Detector Wrapper
====================================
Handles model loading, camera capture, inference, and post-processing for
both the primary density-map regression model and the box detector / COCO fallback.

Model Support
-------------
Four model classes are provided:

1. EnsembleDensityDetector — FINAL ADOPTED HEADCOUNT ENGINE  ← use this
   Two-model weighted ensemble (MAE=2.77, r=0.586 on genuine v2 held-out data):
     • classcan_density_round4_ep8.tflite   (weight 0.6) — evaluated with LETTERBOX
     • classcan_density_style_aug_ep8.tflite (weight 0.4) — evaluated with STRETCH
   Preprocessing asymmetry is deliberate: letterbox eval on stretch-trained round4
   weights lifts correlation 0.506→0.602 with no retraining.
   Drop both .tflite files into models/ and config.py picks them up automatically.
   Falls back gracefully to DensityDetector if only one file is present.

2. DensityDetector — SINGLE-MODEL HEADCOUNT ENGINE (fallback)
   Model: classcan_density_v4.tflite (float32 or int8 quantized)
   Architecture: MobileNetV3-Large backbone + progressive upsampling decoder
   → 104×104 single-channel spatial density map (Softplus activation, 3.6M params).
   Input:  [1, 416, 416, 3]  float32  normalized [0, 1] RGB
   Output: [1, 104, 104]     float32  density surface (or [1, 104, 104, 1])
   Count:  output.sum()  (integral of density map ≈ head count)
   Validated on 407 images: MAE=2.13 overall, MAE=0.93 in 0-20 quadrant regime.

3. Detector — BOX DETECTOR (HUD overlay / visual bounding boxes)
   Supports two sub-formats auto-detected by output tensor count:

   3a. CLASSCAN Head Detector (classcan_head_v1.tflite)
       MobileNetV3-Large @ 416×416, 3-head FPN, NMS baked into export wrapper.
       Output: boxes [1,MAX,4] / scores [1,MAX] / count [1]
       Best config: 2×2 tiled inference, full_obj=0.35, tile_obj=0.65, Soft-NMS.
       F1=31.8%, MAE=3.84, r=0.986 (Pi 3B: 0.557 s/frame).

   3b. COCO MobileNetV2-SSD fallback (mobilenet_v2_ssd_classcan.tflite)
       Stock COCO model. 4-tensor output: boxes/classes/scores/num_detections.
       NOTE: undercounts desk-occluded students — smoke-test only.

Import chain (ai-edge-litert is the production Pi 3B package):
  1. ai_edge_litert.interpreter  (official Google Pi wheel — preferred on device)
  2. tensorflow.lite.python.interpreter  (dev-machine fallback via full TF install)

Camera Frame Acquisition — Stale-Buffer Fix (Sept 24, 2026)
-------------------------------------------------------------
OpenCV / V4L2 maintains an internal ring buffer (typically 3–4 frames deep).
The camera hardware continuously fills this buffer at the configured frame rate
regardless of what the Python process is doing.

Problem: TFLite inference on the Pi 3B takes ~700 ms (density model) to ~1+ s
(ensemble).  During that time many new camera frames pile up in the buffer.
A naive cap.read() after inference returns the *oldest* buffered frame — potentially
several seconds stale — handing the AI an image that no longer represents the
live scene.  This was the root cause of the "AI operates on late frames / inference
lags live video" symptom reported Sept 24, 2026.

Fix: _grab_fresh_frame(cap) drains the buffer before every real-hardware capture:
  1. Call cap.grab() in a tight loop (up to 8×) — advances the V4L2 DMA pointer
     and discards each queued frame without decoding pixels (nearly free).
  2. Call cap.retrieve() once to decode only the final, freshest frame.
All three detector classes (DensityDetector, EnsembleDensityDetector, Detector)
use _grab_fresh_frame() in their capture_frame() methods when not in mock mode.
_MockCapture bypasses it (plain read — no buffer concept in simulation).

Training & Model Evolution (summary)
-------------------------------------
  V2+300 baseline → MobileNetV3-Large 416×416 (F1=30.1%) → count calibration
  (obj=0.35, MAE=3.57) → tiled inference (F1=31.8%, MAE=3.84) → QA review →
  density-map regression v4 (MAE=2.13, r=0.9951, quadrant MAE=0.93) →
  9 rounds hard-neg fine-tuning + ensemble search → final 2-model weighted ensemble
  (MAE=2.77, r=0.586 on genuine v2 held-out, best real-footage result across all rounds).
"""

import cv2
import numpy as np

try:
    from ai_edge_litert.interpreter import Interpreter  # production package (Pi 3B aarch64 wheel)
except ImportError:
    from tensorflow.lite.python.interpreter import Interpreter  # dev fallback (full TF install)


# ─── NMS & Soft-NMS ──────────────────────────────────────────────────────────

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


def soft_non_max_suppression(
    boxes: np.ndarray,
    scores: np.ndarray,
    sigma: float = 0.5,
    score_threshold: float = 0.3,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Gaussian Soft-NMS (decay scores continuously rather than hard suppression).
    Prevents aggressive suppression of closely seated, partially overlapping heads.

    Tuned best parameters for CLASSCAN:
        sigma=0.5, score_threshold=0.3

    Args:
        boxes:           (N, 4) float32 [ymin, xmin, ymax, xmax] normalized 0..1
        scores:          (N,) float32 objectness scores
        sigma:           Gaussian decay parameter
        score_threshold: minimum decayed score to retain a detection

    Returns:
        kept_boxes:  (K, 4) float32 array
        kept_scores: (K,) float32 array
    """
    if len(boxes) == 0:
        return np.zeros((0, 4), dtype=np.float32), np.zeros(0, dtype=np.float32)

    boxes = boxes.copy()
    scores = scores.copy()
    n = len(boxes)

    kept_boxes = []
    kept_scores = []

    for i in range(n):
        # Pick box with max score in the remaining set
        max_idx = i + np.argmax(scores[i:])
        # Swap current box i with max_idx
        boxes[[i, max_idx]] = boxes[[max_idx, i]]
        scores[[i, max_idx]] = scores[[max_idx, i]]

        box_i = boxes[i]
        score_i = scores[i]

        if score_i < score_threshold:
            break

        kept_boxes.append(box_i)
        kept_scores.append(score_i)

        if i + 1 >= n:
            break

        # Compute IoU between box i and remaining boxes [i+1:]
        iy1 = np.maximum(box_i[0], boxes[i + 1:, 0])
        ix1 = np.maximum(box_i[1], boxes[i + 1:, 1])
        iy2 = np.minimum(box_i[2], boxes[i + 1:, 2])
        ix2 = np.minimum(box_i[3], boxes[i + 1:, 3])

        inter_h = np.maximum(0.0, iy2 - iy1)
        inter_w = np.maximum(0.0, ix2 - ix1)
        inter   = inter_h * inter_w

        area_i = (box_i[2] - box_i[0]) * (box_i[3] - box_i[1])
        area_rem = (boxes[i + 1:, 2] - boxes[i + 1:, 0]) * (boxes[i + 1:, 3] - boxes[i + 1:, 1])
        iou = inter / np.maximum(area_i + area_rem - inter, 1e-6)

        # Gaussian weight decay
        decay = np.exp(-(iou ** 2) / sigma)
        scores[i + 1:] *= decay

    if len(kept_boxes) == 0:
        return np.zeros((0, 4), dtype=np.float32), np.zeros(0, dtype=np.float32)

    return np.array(kept_boxes, dtype=np.float32), np.array(kept_scores, dtype=np.float32)


# ─── Mock camera for pipeline testing without hardware ───────────────────────

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


def _open_camera(camera_index: int) -> object:
    """Open camera with V4L2 on Linux, fallback for dev machines."""
    cap = cv2.VideoCapture(camera_index, cv2.CAP_V4L2)
    if not cap.isOpened():
        cap = cv2.VideoCapture(camera_index)
    return cap


def _grab_fresh_frame(cap) -> np.ndarray:
    """
    Drain OpenCV's internal frame buffer and return only the freshest frame.

    OpenCV (especially with V4L2) queues several frames internally.  After a
    slow AI inference pass those buffered frames go stale.  Calling cap.read()
    without draining would hand the AI an old frame.

    Strategy:
      - Call cap.grab() (cheap — no pixel decode, just advances the DMA pointer)
        in a tight loop until it returns False or no new frame arrives within a
        tiny timeout window.
      - cap.retrieve() decodes only the single final frame we kept.

    Falls back to cap.read() if retrieve fails for any reason.
    """
    grabbed = False
    # Drain up to 8 buffered frames; stop early when grabs stop succeeding
    for _ in range(8):
        ok = cap.grab()
        if not ok:
            break
        grabbed = True

    if grabbed:
        ret, frame = cap.retrieve()
        if ret and frame is not None:
            return frame

    # Fallback: plain read (works for mock capture and edge cases)
    ret, frame = cap.read()
    if not ret or frame is None:
        raise RuntimeError("[CLASSCAN] Failed to capture frame from camera")
    return frame


# ─── DensityDetector — primary headcount engine ───────────────────────────────

class DensityDetector:
    """
    CLASSCAN primary headcount engine — density-map regression model.

    Wraps classcan_density_v4.tflite (float32 or int8 quantized):
      - Input:  [1, 416, 416, 3]  float32  normalized [0, 1] RGB
      - Output: [1, 104, 104]     float32  spatial density map (Softplus)
                (also handles [1, 104, 104, 1] — trailing channel dim squeezed out)
      - Count:  round(output.sum())   (integral of density surface)

    Achieves MAE = 2.13 overall, MAE = 0.93 in 0–20 quadrant regime.
    No bounding boxes — use Detector alongside for optional HUD box overlay.

    Parameters
    ----------
    model_path    : str   — path to classcan_density_v4.tflite
    camera_index  : int   — OpenCV camera device index
    force_mock    : bool  — skip camera open, return synthetic result
    mock_count    : int   — simulated head count in mock mode
    """

    def __init__(
        self,
        model_path: str,
        camera_index: int = 0,
        force_mock: bool = False,
        mock_count: int = 4,
    ):
        self.is_mock = force_mock

        # ── Load TFLite model ──────────────────────────────────────────────
        self.interpreter = Interpreter(model_path=model_path)
        self.interpreter.allocate_tensors()

        input_details      = self.interpreter.get_input_details()
        self.input_idx     = input_details[0]["index"]
        self.input_h       = input_details[0]["shape"][1]
        self.input_w       = input_details[0]["shape"][2]

        output_details         = self.interpreter.get_output_details()
        self._out_density_idx  = output_details[0]["index"]

        # ── Camera ────────────────────────────────────────────────────────
        if force_mock:
            self.cap         = _MockCapture(mock_count=mock_count)
            self._mock_count = mock_count
            print(f"[DensityDetector] Mock mode — simulating count={mock_count}")
        else:
            self.cap = _open_camera(camera_index)
            if not self.cap.isOpened():
                raise RuntimeError(
                    f"[DensityDetector] Cannot open camera device {camera_index}. "
                    "Check: camera connected? correct device index? V4L2 driver loaded?"
                )

        print(f"[DensityDetector] Model loaded: {model_path}")
        print(f"[DensityDetector] Input size:   {self.input_w}×{self.input_h}")

    # ── Frame capture ──────────────────────────────────────────────────────

    def capture_frame(self) -> np.ndarray:
        """Grab the freshest frame from camera (drains stale buffer). Returns BGR ndarray."""
        if self.is_mock:
            _, frame = self.cap.read()
            return frame
        return _grab_fresh_frame(self.cap)

    # ── Preprocessing ──────────────────────────────────────────────────────

    def _preprocess(self, frame: np.ndarray) -> np.ndarray:
        """Resize + normalize to [1, H, W, 3] float32 in [0, 1]."""
        resized = cv2.resize(frame, (self.input_w, self.input_h))
        rgb     = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        return np.expand_dims(rgb.astype(np.float32) / 255.0, axis=0)

    # ── Inference ──────────────────────────────────────────────────────────

    def predict(self, frame: np.ndarray) -> dict:
        """
        Run density-map inference on a BGR frame.

        Returns
        -------
        dict with keys:
            "count"       : int    — rounded headcount estimate
            "raw_sum"     : float  — unrounded integral of density map
            "density_map" : ndarray(104, 104) float32 — raw density surface

        In mock mode returns synthetic result without touching the model.
        """
        if self.is_mock:
            fake_map = np.zeros((104, 104), dtype=np.float32)
            return {
                "count":       self._mock_count,
                "raw_sum":     float(self._mock_count),
                "density_map": fake_map,
            }

        tensor = self._preprocess(frame)
        self.interpreter.set_tensor(self.input_idx, tensor)
        self.interpreter.invoke()

        raw = self.interpreter.get_tensor(self._out_density_idx)  # (1,104,104) or (1,104,104,1)
        density_map = np.squeeze(raw).astype(np.float32)          # → (104, 104)
        raw_sum     = float(density_map.sum())
        count       = max(0, round(raw_sum))

        return {
            "count":       count,
            "raw_sum":     raw_sum,
            "density_map": density_map,
        }

    # ── Cleanup ────────────────────────────────────────────────────────────

    def release(self):
        if hasattr(self, "cap"):
            self.cap.release()

    def __del__(self):
        self.release()


# ─── EnsembleDensityDetector — final adopted headcount engine ─────────────────

class EnsembleDensityDetector:
    """
    CLASSCAN final adopted headcount engine — weighted 2-model density-map ensemble.

    Implements the ensemble found via 3-way grid search across 9 fine-tuning rounds:

        count = max(0, round(
            0.6 × round4_ep8_letterbox_sum  +
            0.4 × style_aug_ep8_stretch_sum
        ))

    Preprocessing asymmetry is deliberate (not a mistake):
      - round4_ep8    trained on STRETCH, evaluated with LETTERBOX  → r=0.602
      - style_aug_ep8 trained on STRETCH, evaluated with STRETCH    → r=0.531
      Ensemble: MAE=2.77, r=0.586  (genuine v2 held-out, 350 frames)

    Integration:
        Drop classcan_density_round4_ep8.tflite and
             classcan_density_style_aug_ep8.tflite into models/.
        Config auto-detects them; main.py prefers this class over DensityDetector.

    Interface is identical to DensityDetector — .predict(), .capture_frame(),
    .release() — so main.py requires no structural changes.

    Parameters
    ----------
    round4_ep8_path    : str   — path to classcan_density_round4_ep8.tflite
    style_aug_ep8_path : str   — path to classcan_density_style_aug_ep8.tflite
    w_round4           : float — ensemble weight for round4_ep8 (default 0.6)
    w_style_aug        : float — ensemble weight for style_aug_ep8 (default 0.4)
    camera_index       : int   — OpenCV camera device index
    force_mock         : bool  — skip camera open, return synthetic result
    mock_count         : int   — simulated head count in mock mode
    """

    def __init__(
        self,
        round4_ep8_path: str,
        style_aug_ep8_path: str,
        w_round4: float = 0.6,
        w_style_aug: float = 0.4,
        camera_index: int = 0,
        force_mock: bool = False,
        mock_count: int = 4,
    ):
        self.w_round4    = w_round4
        self.w_style_aug = w_style_aug
        self.is_mock     = force_mock

        # ── Load both TFLite interpreters ─────────────────────────────────
        self._interp_r4 = Interpreter(model_path=round4_ep8_path)
        self._interp_r4.allocate_tensors()
        r4_in  = self._interp_r4.get_input_details()[0]
        self._r4_in_idx  = r4_in["index"]
        self._r4_h       = r4_in["shape"][1]   # expected 416
        self._r4_w       = r4_in["shape"][2]   # expected 416
        self._r4_out_idx = self._interp_r4.get_output_details()[0]["index"]

        self._interp_sa = Interpreter(model_path=style_aug_ep8_path)
        self._interp_sa.allocate_tensors()
        sa_in  = self._interp_sa.get_input_details()[0]
        self._sa_in_idx  = sa_in["index"]
        self._sa_h       = sa_in["shape"][1]   # expected 416
        self._sa_w       = sa_in["shape"][2]   # expected 416
        self._sa_out_idx = self._interp_sa.get_output_details()[0]["index"]

        # ── Camera (one shared capture, same frame fed to both models) ────
        if force_mock:
            self.cap         = _MockCapture(mock_count=mock_count)
            self._mock_count = mock_count
            print(f"[EnsembleDensityDetector] Mock mode — simulating count={mock_count}")
        else:
            self.cap = _open_camera(camera_index)
            if not self.cap.isOpened():
                raise RuntimeError(
                    f"[EnsembleDensityDetector] Cannot open camera device {camera_index}."
                )

        print(f"[EnsembleDensityDetector] Ensemble loaded:")
        print(f"  round4_ep8    (w={w_round4}) letterbox → {round4_ep8_path}")
        print(f"  style_aug_ep8 (w={w_style_aug}) stretch  → {style_aug_ep8_path}")
        print(f"  Target: MAE=2.77, r=0.586 (v2 held-out, 350 frames)")

    # ── Frame capture ──────────────────────────────────────────────────────

    def capture_frame(self) -> np.ndarray:
        """Grab the freshest frame from camera (drains stale buffer). Returns BGR ndarray."""
        if self.is_mock:
            _, frame = self.cap.read()
            return frame
        return _grab_fresh_frame(self.cap)

    # ── Preprocessing ─────────────────────────────────────────────────────

    def _letterbox(self, frame: np.ndarray) -> np.ndarray:
        """
        Letterbox-resize to (target × target): preserve aspect ratio, pad black.
        Used for round4_ep8 — this preprocessing geometry is what lifted
        correlation from 0.506 → 0.602 (no retraining needed).
        """
        target = self._r4_h
        h, w   = frame.shape[:2]
        scale  = target / max(h, w)
        nh, nw = int(h * scale), int(w * scale)
        canvas = np.zeros((target, target, 3), dtype=np.float32)
        resized = cv2.resize(frame, (nw, nh))
        rgb     = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        canvas[:nh, :nw] = rgb.astype(np.float32) / 255.0
        return np.expand_dims(canvas, axis=0)  # → [1, 416, 416, 3]

    def _stretch(self, frame: np.ndarray) -> np.ndarray:
        """
        Stretch-resize to (target × target): simple cv2.resize, no aspect preservation.
        Used for style_aug_ep8 — matches its training-time preprocessing.
        """
        resized = cv2.resize(frame, (self._sa_w, self._sa_h))
        rgb     = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        return np.expand_dims(rgb.astype(np.float32) / 255.0, axis=0)  # → [1, 416, 416, 3]

    # ── Inference ──────────────────────────────────────────────────────────

    def predict(self, frame: np.ndarray) -> dict:
        """
        Run ensemble density-map inference on a BGR frame.

        Returns
        -------
        dict with keys:
            "count"            : int    — weighted ensemble headcount (rounded)
            "raw_sum"          : float  — unrounded weighted sum
            "density_map"      : ndarray(104, 104) float32 — weighted combined density surface
            "raw_sum_round4"   : float  — component sum from round4_ep8 (letterbox)
            "raw_sum_style_aug": float  — component sum from style_aug_ep8 (stretch)

        In mock mode returns synthetic result without running either model.
        """
        if self.is_mock:
            fake_map = np.zeros((104, 104), dtype=np.float32)
            return {
                "count":             self._mock_count,
                "raw_sum":           float(self._mock_count),
                "density_map":       fake_map,
                "raw_sum_round4":    float(self._mock_count),
                "raw_sum_style_aug": float(self._mock_count),
            }

        # round4_ep8 — letterbox input
        inp_lb = self._letterbox(frame)
        self._interp_r4.set_tensor(self._r4_in_idx, inp_lb)
        self._interp_r4.invoke()
        dm_r4     = np.squeeze(
            self._interp_r4.get_tensor(self._r4_out_idx)
        ).astype(np.float32)                                    # (104, 104)
        sum_r4    = float(dm_r4.sum())

        # style_aug_ep8 — stretch input
        inp_st = self._stretch(frame)
        self._interp_sa.set_tensor(self._sa_in_idx, inp_st)
        self._interp_sa.invoke()
        dm_sa     = np.squeeze(
            self._interp_sa.get_tensor(self._sa_out_idx)
        ).astype(np.float32)                                    # (104, 104)
        sum_sa    = float(dm_sa.sum())

        # Weighted combination
        raw_sum     = self.w_round4 * sum_r4 + self.w_style_aug * sum_sa
        count       = max(0, round(raw_sum))
        density_map = self.w_round4 * dm_r4 + self.w_style_aug * dm_sa

        return {
            "count":             count,
            "raw_sum":           raw_sum,
            "density_map":       density_map,
            "raw_sum_round4":    sum_r4,
            "raw_sum_style_aug": sum_sa,
        }

    # ── Cleanup ────────────────────────────────────────────────────────────

    def release(self):
        if hasattr(self, "cap"):
            self.cap.release()

    def __del__(self):
        self.release()


# ─── Detector — box detector for HUD bounding boxes ──────────────────────────

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
            self.cap         = _MockCapture(mock_count=mock_count)
            self._mock_count = mock_count
            print(f"[Detector] Mock mode — simulating {mock_count} detections")
        else:
            self.cap = _open_camera(camera_index)
            if not self.cap.isOpened():
                raise RuntimeError(
                    f"[Detector] Cannot open camera device {camera_index}. "
                    "Check: camera connected? correct device index? V4L2 driver loaded?"
                )

        print(f"[Detector] Model loaded: {model_path}")
        print(f"[Detector] Input size:   {self.input_w}×{self.input_h}  dtype={self.input_dtype.__name__}")
        print(f"[Detector] Conf threshold: {self.conf_threshold}")

    # ── Frame capture ──────────────────────────────────────────────────────

    def capture_frame(self) -> np.ndarray:
        """Grab the freshest frame from camera (drains stale buffer). Returns BGR ndarray."""
        if self.is_mock:
            _, frame = self.cap.read()
            return frame
        return _grab_fresh_frame(self.cap)

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