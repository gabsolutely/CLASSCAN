"""
Manual inference smoke-test script.

Runs the real Detector against a real .tflite model and a real image file.
NOT part of the automated pytest suite (which uses fully mocked cv2/interpreter) —
this is for manually sanity-checking actual detection output on real hardware.

Usage:
    python scripts/run_on_image.py [path/to/image.jpg] [path/to/model.tflite]
"""

import sys
import os
from pathlib import Path
sys.path.insert(0, "src/pi")

import cv2
from detection.detector import Detector

# Resolve defaults
primary_model = "models/yololite_nano_head_classcan.tflite"
fallback_model = "models/mobilenet_v2_ssd_classcan.tflite"

image_path = sys.argv[1] if len(sys.argv) > 1 else "tests/assets/test_scene.jpg"
if len(sys.argv) > 2:
    model_path = sys.argv[2]
else:
    model_path = primary_model if os.path.isfile(primary_model) else fallback_model

frame = cv2.imread(image_path)
if frame is None:
    print(f"Could not load image: {image_path}")
    sys.exit(1)

if not os.path.isfile(model_path):
    print(f"Model file not found: {model_path}")
    print("Run `python models/download_model.py` for the test model or place your trained .tflite in models/")
    sys.exit(1)

# Bypass camera init since we're feeding a still image, not a live camera
det = Detector.__new__(Detector)
det.conf_threshold = 0.5

from ai_edge_litert.interpreter import Interpreter
det.interpreter = Interpreter(model_path=model_path)
det.interpreter.allocate_tensors()

input_details = det.interpreter.get_input_details()
det.input_idx = input_details[0]["index"]
det.input_h   = input_details[0]["shape"][1]
det.input_w   = input_details[0]["shape"][2]

output_details = det.interpreter.get_output_details()
print(f"[Smoke Test] Input tensor: shape={input_details[0]['shape']} type={input_details[0]['dtype']}")
print(f"[Smoke Test] Output tensors ({len(output_details)}):")
for i, out in enumerate(output_details):
    print(f"  [{i}] name={out.get('name', 'N/A')} shape={out['shape']} dtype={out['dtype']}")

det.out_boxes   = output_details[0]["index"]
det.out_classes = output_details[1]["index"] if len(output_details) > 1 else None
det.out_scores  = output_details[2]["index"] if len(output_details) > 2 else None
det.out_num     = output_details[3]["index"] if len(output_details) > 3 else None

results = det.detect(frame)
print(f"\nDetected {len(results)} target(s):")
for i, r in enumerate(results):
    print(f"  [{i}] score={r['score']:.2f}  box={r['box']}")