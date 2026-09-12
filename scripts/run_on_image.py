"""
Manual inference smoke-test script.

Runs inference against a real .tflite model and a real image file.
NOT part of the automated pytest suite (which uses fully mocked cv2/interpreter) —
this is for manually sanity-checking actual detection output on real hardware.

Supports both model types:
  • classcan_density_v4 (float32 / int8) — density-map regression, returns headcount
  • classcan_head_v1 / mobilenet_v2_ssd_classcan — box detector, returns bounding boxes

Usage:
    python scripts/run_on_image.py [path/to/image.jpg] [path/to/model.tflite]
"""

import sys
import os
from pathlib import Path
sys.path.insert(0, "src/pi")

import cv2
import numpy as np
from ai_edge_litert.interpreter import Interpreter

# ── Resolve defaults ──────────────────────────────────────────────────────────
# Density model (primary headcount engine) — float32 preferred for smoke-testing
_MODEL_DIR = Path("models")
_DENSITY_CANDIDATES = [
    str(_MODEL_DIR / "classcan_density_float32.tflite"),
    str(_MODEL_DIR / "classcan_density_int8.tflite"),
]
_BOX_CANDIDATES = [
    str(_MODEL_DIR / "classcan_head_v1.tflite"),
    str(_MODEL_DIR / "mobilenet_v2_ssd_classcan.tflite"),
]

image_path = sys.argv[1] if len(sys.argv) > 1 else "tests/assets/test_scene.jpg"
if len(sys.argv) > 2:
    model_path = sys.argv[2]
else:
    model_path = next(
        (p for p in _DENSITY_CANDIDATES + _BOX_CANDIDATES if os.path.isfile(p)),
        None,
    )

frame = cv2.imread(image_path)
if frame is None:
    print(f"Could not load image: {image_path}")
    sys.exit(1)

if not model_path or not os.path.isfile(model_path):
    print(f"Model file not found: {model_path or '(none)'}")
    print("Checked:", _DENSITY_CANDIDATES + _BOX_CANDIDATES)
    print("Run `python models/download_model.py` for the COCO fallback, or")
    print("run `python scripts/export_to_tflite.py` to export from a checkpoint.")
    sys.exit(1)

# ── Load interpreter ──────────────────────────────────────────────────────────
print(f"\n[Smoke Test] Model:  {model_path}")
print(f"[Smoke Test] Image:  {image_path}")

interp = Interpreter(model_path=model_path)
interp.allocate_tensors()

input_details  = interp.get_input_details()
output_details = interp.get_output_details()
model_name     = os.path.basename(model_path)

print(f"[Smoke Test] Input tensor:  shape={input_details[0]['shape']}  dtype={input_details[0]['dtype'].__name__}")
print(f"[Smoke Test] Output tensors ({len(output_details)}):")
for i, out in enumerate(output_details):
    print(f"  [{i}] name={out.get('name', 'N/A')}  shape={out['shape']}  dtype={out['dtype'].__name__}")

# ── Preprocess ────────────────────────────────────────────────────────────────
h = input_details[0]["shape"][1]
w = input_details[0]["shape"][2]
rgb    = cv2.cvtColor(cv2.resize(frame, (w, h)), cv2.COLOR_BGR2RGB)
tensor = np.expand_dims(rgb.astype(np.float32) / 255.0, axis=0)

interp.set_tensor(input_details[0]["index"], tensor)
interp.invoke()

# ── Post-process by model type ────────────────────────────────────────────────
is_density_model = "density" in model_name.lower()

if is_density_model:
    # classcan_density_v4: sum the density map for headcount
    raw         = interp.get_tensor(output_details[0]["index"])   # (1,104,104) or (1,104,104,1)
    density_map = np.squeeze(raw).astype(np.float32)              # → (104,104)
    raw_sum     = float(density_map.sum())
    count       = max(0, round(raw_sum))

    print(f"\n[Density Model] Raw sum: {raw_sum:.2f}  →  Headcount: {count}")
    print(f"[Density Model] Density map: min={density_map.min():.4f}  max={density_map.max():.4f}  mean={density_map.mean():.4f}")
else:
    # Box detector: threshold detections
    conf = 0.35
    print(f"\n[Box Detector] Confidence threshold: {conf}")

    if len(output_details) == 3:
        # CLASSCAN head model (3-tensor, NMS already applied)
        out_map    = {d["name"].split("/")[-1].split(":")[0]: d for d in output_details}
        boxes_idx  = out_map.get("boxes",  output_details[0])["index"]
        scores_idx = out_map.get("scores", output_details[1])["index"]
        count_idx  = out_map.get("count",  output_details[2])["index"]

        boxes  = interp.get_tensor(boxes_idx)[0]
        scores = interp.get_tensor(scores_idx)[0]
        count  = int(interp.get_tensor(count_idx)[0])

        results = [
            {"box": boxes[i].tolist(), "score": float(scores[i])}
            for i in range(count)
            if scores[i] >= conf
        ]
    else:
        # COCO SSD fallback (4-tensor)
        boxes   = interp.get_tensor(output_details[0]["index"])[0]
        classes = interp.get_tensor(output_details[1]["index"])[0] if len(output_details) > 1 else None
        scores  = interp.get_tensor(output_details[2]["index"])[0] if len(output_details) > 2 else None
        count   = int(interp.get_tensor(output_details[3]["index"])[0]) if len(output_details) > 3 else len(boxes)

        results = [
            {"box": boxes[i].tolist(), "score": float(scores[i])}
            for i in range(count)
            if scores is not None and int(classes[i]) == 0 and scores[i] >= conf
        ]

    print(f"Detected {len(results)} target(s):")
    for i, r in enumerate(results):
        print(f"  [{i}] score={r['score']:.2f}  box={r['box']}")