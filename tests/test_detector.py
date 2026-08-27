"""
Headcount detection test — runs detector on a single test image
and prints results. No hardware required; set TEST_IMAGE to any
JPEG/PNG of a classroom scene.

Usage:
    python test_detector.py [--image path/to/image.jpg]
"""

import argparse
import sys
import cv2

# Add src/pi to path
sys.path.insert(0, "src/pi")
from detection.detector import Detector
from config import Config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", default="tests/assets/test_classroom.jpg")
    parser.add_argument("--model", default="models/mobilenet_v2_ssd_classcan.tflite")
    args = parser.parse_args()

    # Stub: use a saved image instead of live camera
    frame = cv2.imread(args.image)
    if frame is None:
        print(f"[TEST] Image not found: {args.image}")
        sys.exit(1)

    cfg      = Config()
    detector = Detector.__new__(Detector)  # Bypass camera init
    detector.conf_threshold = cfg.CONF_THRESHOLD

    from tflite_runtime.interpreter import Interpreter
    detector.interpreter = Interpreter(model_path=args.model)
    detector.interpreter.allocate_tensors()
    input_details  = detector.interpreter.get_input_details()
    output_details = detector.interpreter.get_output_details()
    detector.input_idx  = input_details[0]["index"]
    detector.input_h    = input_details[0]["shape"][1]
    detector.input_w    = input_details[0]["shape"][2]
    detector.out_boxes  = output_details[0]["index"]
    detector.out_classes= output_details[1]["index"]
    detector.out_scores = output_details[2]["index"]
    detector.out_num    = output_details[3]["index"]

    detections = detector.detect(frame)
    print(f"[TEST] Detected {len(detections)} person(s):")
    for i, d in enumerate(detections):
        print(f"  [{i}] score={d['score']:.2f}  box={d['box']}")


if __name__ == "__main__":
    main()
