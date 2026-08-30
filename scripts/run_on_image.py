"""
Manual inference smoke-test script.

Runs the real Detector against a real .tflite model and a real image file.
NOT part of the automated pytest suite (which uses fully mocked cv2/interpreter) —
this is for manually sanity-checking actual detection output on real hardware.

Usage:
    python scripts/run_on_image.py [path/to/image.jpg]
    (defaults to tests/assets/Mohakirk.jpg if no path given)
"""

import sys
sys.path.insert(0, "src/pi")

import cv2
from detection.detector import Detector

image_path = sys.argv[1] if len(sys.argv) > 1 else "tests/assets/Mohakirk.jpg"
model_path = "models/mobilenet_v2_ssd_classcan.tflite"

frame = cv2.imread(image_path)
if frame is None:
    print(f"Could not load image: {image_path}")
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
det.out_boxes   = output_details[0]["index"]
det.out_classes = output_details[1]["index"]
det.out_scores  = output_details[2]["index"]
det.out_num     = output_details[3]["index"]

results = det.detect(frame)
print(f"Detected {len(results)} person(s):")
for i, r in enumerate(results):
    print(f"  [{i}] score={r['score']:.2f}  box={r['box']}")