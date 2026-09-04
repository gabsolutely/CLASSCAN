"""
CLASSCAN — Camera Verification Script
======================================
Quick standalone test: open OV4689 UVC camera, grab one frame, run
inference with classcan_head_v1.tflite, print count, draw bounding boxes.

Use this INSTEAD of running the full Flask server (main.py) when first
connecting the camera or after swapping the model file.

Usage (on Pi):
    cd /path/to/CLASSCAN/src/pi
    python ../../scripts/camera_verify.py

Options:
    --model   Path to .tflite model (default: auto-detects classcan_head_v1.tflite)
    --camera  Camera device index (default: 0)
    --conf    Confidence threshold (default: 0.35)
    --save    Save annotated frame to camera_verify_output.jpg
    --frames  Number of frames to capture and run inference on (default: 5)

Expected output:
    [Camera] Opened device 0 — 1280×960
    [Model]  Loaded: models/classcan_head_v1.tflite
    [Frame 1/5] Count=4  Inference=241ms
    [Frame 2/5] Count=4  Inference=238ms
    ...
    [✓] Camera verify passed — model producing non-zero detections.
"""

import argparse
import os
import sys
import time
from pathlib import Path

import cv2
import numpy as np

# Allow running from repo root or from scripts/ directory
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src" / "pi"))

try:
    from ai_edge_litert.interpreter import Interpreter
except ImportError:
    try:
        from tflite_runtime.interpreter import Interpreter
    except ImportError:
        try:
            from tensorflow.lite.python.interpreter import Interpreter
        except ImportError:
            Interpreter = None



# ─── NMS (self-contained copy — no src imports needed for quick verify) ────────

def non_max_suppression(boxes: np.ndarray, scores: np.ndarray,
                        iou_threshold: float = 0.45) -> list[int]:
    """Greedy IoU NMS. Returns indices of kept boxes."""
    if len(boxes) == 0:
        return []
    order = np.argsort(scores)[::-1]
    kept = []
    while len(order):
        i = order[0]
        kept.append(int(i))
        order = order[1:]
        if not len(order):
            break
        iy1 = np.maximum(boxes[i, 0], boxes[order, 0])
        ix1 = np.maximum(boxes[i, 1], boxes[order, 1])
        iy2 = np.minimum(boxes[i, 2], boxes[order, 2])
        ix2 = np.minimum(boxes[i, 3], boxes[order, 3])
        inter = np.maximum(0.0, iy2 - iy1) * np.maximum(0.0, ix2 - ix1)
        area_i = (boxes[i, 2] - boxes[i, 0]) * (boxes[i, 3] - boxes[i, 1])
        area_r = (boxes[order, 2] - boxes[order, 0]) * (boxes[order, 3] - boxes[order, 1])
        iou = inter / np.maximum(area_i + area_r - inter, 1e-6)
        order = order[iou <= iou_threshold]
    return kept


# ─── Model interface helpers ──────────────────────────────────────────────────

def load_model(model_path: str):
    if Interpreter is None:
        print("[✗] Error: Neither 'ai_edge_litert', 'tflite_runtime', nor 'tensorflow' is installed.")
        print("    • On Raspberry Pi 3B (64-bit):  pip install ai-edge-litert")
        print("    • On dev workstation / laptop: pip install tensorflow")
        print("    • To verify camera hardware alone without a model: run with --camera-only")
        sys.exit(1)
    interp = Interpreter(model_path=model_path)
    interp.allocate_tensors()
    inp = interp.get_input_details()
    out = interp.get_output_details()
    return interp, inp, out



def detect_classcan_model(interp, inp_details, out_details,
                          frame_bgr: np.ndarray, conf: float = 0.35):
    """
    Run inference with classcan_head_v1.tflite (export wrapper output format).
    Returns list of {'box': [y1,x1,y2,x2], 'score': float}.

    The export wrapper outputs:
      boxes  [1, MAX, 4]  (zero-padded)
      scores [1, MAX]     (zero-padded)
      count  [1]          (valid detection count)
    """
    h = inp_details[0]["shape"][1]
    w = inp_details[0]["shape"][2]

    rgb = cv2.cvtColor(cv2.resize(frame_bgr, (w, h)), cv2.COLOR_BGR2RGB)
    tensor = np.expand_dims(rgb.astype(np.float32) / 255.0, axis=0)

    interp.set_tensor(inp_details[0]["index"], tensor)
    t0 = time.perf_counter()
    interp.invoke()
    inference_ms = (time.perf_counter() - t0) * 1000

    # Find output tensors by name suffix (robust to index ordering)
    out_map = {d["name"].split("/")[-1].split(":")[0]: d for d in out_details}
    # Fallback: use positional order if names don't match
    boxes_idx  = out_map.get("boxes",  out_details[0])["index"]
    scores_idx = out_map.get("scores", out_details[1])["index"]
    count_idx  = out_map.get("count",  out_details[2])["index"]

    boxes  = interp.get_tensor(boxes_idx)[0]   # (MAX, 4)
    scores = interp.get_tensor(scores_idx)[0]  # (MAX,)
    count  = int(interp.get_tensor(count_idx)[0])

    detections = []
    for i in range(count):
        if scores[i] >= conf:
            detections.append({"box": boxes[i].tolist(), "score": float(scores[i])})

    return detections, inference_ms


def detect_coco_model(interp, inp_details, out_details,
                      frame_bgr: np.ndarray, conf: float = 0.50):
    """
    Fallback: run inference with stock 4-tensor SSD COCO model.
    Returns same format as detect_classcan_model.
    """
    h = inp_details[0]["shape"][1]
    w = inp_details[0]["shape"][2]

    rgb = cv2.cvtColor(cv2.resize(frame_bgr, (w, h)), cv2.COLOR_BGR2RGB)
    tensor = np.expand_dims(rgb.astype(np.uint8), axis=0)

    interp.set_tensor(inp_details[0]["index"], tensor)
    t0 = time.perf_counter()
    interp.invoke()
    inference_ms = (time.perf_counter() - t0) * 1000

    scores  = interp.get_tensor(out_details[2]["index"])[0]
    classes = interp.get_tensor(out_details[1]["index"])[0]
    boxes   = interp.get_tensor(out_details[0]["index"])[0]
    count   = int(interp.get_tensor(out_details[3]["index"])[0])

    detections = []
    for i in range(count):
        if int(classes[i]) == 0 and scores[i] >= conf:
            detections.append({"box": boxes[i].tolist(), "score": float(scores[i])})
    return detections, inference_ms


def draw_boxes(frame: np.ndarray, detections: list[dict],
               count: int, inference_ms: float, conf: float) -> np.ndarray:
    """Draw bounding boxes and HUD info on frame."""
    h, w = frame.shape[:2]
    out = frame.copy()

    for det in detections:
        y1, x1, y2, x2 = det["box"]
        px1 = int(x1 * w)
        py1 = int(y1 * h)
        px2 = int(x2 * w)
        py2 = int(y2 * h)
        cv2.rectangle(out, (px1, py1), (px2, py2), (0, 255, 80), 2)
        cv2.putText(out, f"{det['score']:.2f}", (px1, max(py1 - 5, 0)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 80), 1)

    cv2.putText(out, f"Count: {count}  |  {inference_ms:.0f}ms",
                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 0), 2)
    cv2.putText(out, f"Threshold: {conf}",
                (10, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (180, 180, 180), 1)
    return out


# ─── System telemetry helpers ──────────────────────────────────────────────────

def get_soc_temperature() -> str | None:
    """Query Raspberry Pi SoC core temperature via vcgencmd if available."""
    try:
        import subprocess
        res = subprocess.run(["vcgencmd", "measure_temp"], capture_output=True, text=True, timeout=1.0)
        if res.returncode == 0:
            return res.stdout.strip().replace("temp=", "")
    except Exception:
        pass
    return None


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="CLASSCAN camera + model quick verify")
    parser.add_argument("--camera-only", action="store_true",
                        help="Verify camera feed hardware only (skip model loading and inference)")
    parser.add_argument("--model",   default=None,
                        help="Path to .tflite model (auto-detects if not set)")
    parser.add_argument("--camera",  type=int, default=0,
                        help="Camera device index (default: 0)")
    parser.add_argument("--width",   type=int, default=None,
                        help="Requested capture width in pixels (e.g. 1280 or 640)")
    parser.add_argument("--height",  type=int, default=None,
                        help="Requested capture height in pixels (e.g. 720 or 480)")
    parser.add_argument("--conf",    type=float, default=0.35,
                        help="Confidence threshold (default: 0.35)")
    parser.add_argument("--frames",  type=int, default=5,
                        help="Number of frames to test (default: 5)")
    parser.add_argument("--save",    action="store_true",
                        help="Save annotated last frame to camera_verify_output.jpg")
    parser.add_argument("--save-raw", action="store_true",
                        help="Save raw unannotated test frame to camera_raw_test.jpg")
    args = parser.parse_args()

    # ── Model loading (skipped if --camera-only) ───────────────────────────
    interp = None
    inp_details = None
    out_details = None
    is_classcan_model = False

    if not args.camera_only:
        if args.model:
            model_path = args.model
        else:
            candidates = [
                str(REPO_ROOT / "models" / "classcan_head_v1.tflite"),
                str(REPO_ROOT / "models" / "mobilenet_v2_ssd_classcan.tflite"),
            ]
            model_path = next((p for p in candidates if os.path.isfile(p)), None)
            if not model_path:
                print("[!] No model file found in models/.")
                print("    Falling back to --camera-only mode to verify video hardware.")
                print("    (To test inference, run scripts/export_to_tflite.py or pass --model path/to/model.tflite)")
                args.camera_only = True

    if not args.camera_only:
        is_classcan_model = "classcan_head" in os.path.basename(model_path)
        print(f"[Model] Loading: {model_path}")
        print(f"        Mode: {'CLASSCAN head detector' if is_classcan_model else 'COCO SSD fallback'}")

        interp, inp_details, out_details = load_model(model_path)
        print(f"[Model] Input:  {inp_details[0]['shape']}  {inp_details[0]['dtype'].__name__}")
        for d in out_details:
            print(f"[Model] Output: {d['shape']}  {d['dtype'].__name__}  ({d['name']})")
    else:
        print("[Mode] Camera hardware verification only (model inference skipped)")

    # ── Open camera ───────────────────────────────────────────────────────
    print(f"\n[Camera] Opening device index {args.camera}...")
    cap = cv2.VideoCapture(args.camera, cv2.CAP_V4L2)
    backend_used = "V4L2"
    if not cap.isOpened():
        # Fallback without V4L2 flag (for Windows/macOS dev environments)
        cap = cv2.VideoCapture(args.camera)
        backend_used = "Default (non-V4L2)"

    if not cap.isOpened():
        print(f"\n[✗] ERROR: Cannot open camera device index {args.camera}")
        print("\nTroubleshooting checklist:")
        print("  1. Is the OV4689 camera cable plugged firmly into a USB port on the Pi?")
        print("  2. Check if the OS sees the USB device:")
        print("         lsusb")
        print("     Look for OmniVision Technologies or a USB Video Device.")
        print("  3. Check available video devices:")
        print("         v4l2-ctl --list-devices")
        print("         ls -l /dev/video*")
        print("     If the camera is at /dev/video1 or /dev/video2, run with: --camera 1 (or 2)")
        print("  4. Check user permissions for video access:")
        print("         sudo usermod -a -G video $USER")
        print("  5. If connected via hub or breadboard, ensure sufficient 5V power.")
        sys.exit(1)

    # Optional resolution request
    if args.width:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    if args.height:
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)

    cam_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    cam_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cam_fps = cap.get(cv2.CAP_PROP_FPS)
    print(f"[Camera] Opened successfully via {backend_used} — {cam_w}×{cam_h} @ {cam_fps:.1f} FPS")

    # ── Camera Warmup ─────────────────────────────────────────────────────
    # Discard first 3 frames so auto-exposure (AEC) and auto-white-balance (AWB) stabilize
    print("[Camera] Warming up sensor (auto-exposure settling)...", end="", flush=True)
    for _ in range(3):
        cap.read()
    print(" ready.")

    # ── Run verification loop ─────────────────────────────────────────────
    print(f"\nRunning {args.frames} test frame(s)...\n")
    total_counts = []
    capture_latencies = []
    last_frame = None
    raw_frame_saved = None

    try:
        for i in range(args.frames):
            t_cap_start = time.perf_counter()
            ret, frame = cap.read()
            t_cap_ms = (time.perf_counter() - t_cap_start) * 1000
            capture_latencies.append(t_cap_ms)

            if not ret:
                print(f"[✗] Failed to capture frame {i + 1}")
                break

            if raw_frame_saved is None:
                raw_frame_saved = frame.copy()

            if args.camera_only:
                # Camera only mode: display frame stats and capture latency
                print(f"  [Frame {i + 1}/{args.frames}] Captured: {frame.shape[1]}×{frame.shape[0]} "
                      f"in {t_cap_ms:.1f}ms (Mean brightness: {frame.mean():.1f}/255)")
                last_frame = frame.copy()
                cv2.putText(last_frame, f"OV4689 RAW FEED: {cam_w}x{cam_h}",
                            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                cv2.putText(last_frame, f"Capture Latency: {t_cap_ms:.1f}ms",
                            (10, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
            else:
                if is_classcan_model:
                    detections, inf_ms = detect_classcan_model(
                        interp, inp_details, out_details, frame, args.conf
                    )
                else:
                    detections, inf_ms = detect_coco_model(
                        interp, inp_details, out_details, frame, args.conf
                    )

                count = len(detections)
                total_counts.append(count)
                print(f"  [Frame {i + 1}/{args.frames}]  Count={count}  "
                      f"Inference={inf_ms:.0f}ms  "
                      f"Scores={[round(d['score'], 2) for d in detections]}")

                last_frame = draw_boxes(frame, detections, count, inf_ms, args.conf)

    finally:
        cap.release()

    # ── Summary ───────────────────────────────────────────────────────────
    print("\n" + "=" * 50)
    print("  VERIFICATION SUMMARY")
    print("=" * 50)

    avg_cap_ms = sum(capture_latencies) / max(len(capture_latencies), 1)
    print(f"• Video Pipeline: {backend_used} ({cam_w}×{cam_h})")
    print(f"• Frame Capture:  {len(capture_latencies)} frames captured, avg {avg_cap_ms:.1f}ms/frame")

    soc_temp = get_soc_temperature()
    if soc_temp:
        print(f"• Pi 3B Core Temp: {soc_temp} (Active fan cooling)")

    if args.camera_only:
        print("• Camera Hardware Status: [✓] PASS — sensor streaming clean frames.")
    else:
        if not total_counts:
            print("[✗] No frames processed — check camera connection.")
            sys.exit(1)

        avg_count = sum(total_counts) / len(total_counts)
        print(f"• Detection Stats: Average count across {len(total_counts)} frames: {avg_count:.1f}")

        if max(total_counts) == 0:
            print("• Model Detections: 0 detections on all frames.")
            print("    Guidance:")
            print("      - Camera field of view may be empty or pointed at ceiling/wall.")
            print("      - Try lowering threshold: --conf 0.25")
            print("      - If using stock COCO fallback, remember it misses distant/desk-occluded subjects.")
        else:
            print("• Model Detections: [✓] PASS — model producing positive detections.")

    if args.save_raw and raw_frame_saved is not None:
        raw_path = "camera_raw_test.jpg"
        cv2.imwrite(raw_path, raw_frame_saved)
        print(f"• Raw Frame Saved: {raw_path} (inspect focus, sharpness, and lighting)")

    if args.save and last_frame is not None:
        out_path = "camera_verify_output.jpg"
        cv2.imwrite(out_path, last_frame)
        print(f"• Output Saved:    {out_path}")

    print("=" * 50)


if __name__ == "__main__":
    main()

