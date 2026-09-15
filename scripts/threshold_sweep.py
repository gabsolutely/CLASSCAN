"""
Quick fix attempt: threshold the density map to suppress low-confidence
background noise (bags, chairs, edge artifacts) before summing to a count.

Sweeps a few threshold values against your existing eyeballed ground truth
to see if a simple cutoff meaningfully reduces the overcount bias, without
touching the model itself.

USAGE (on the Pi, same venv):
  python3 threshold_sweep.py \
      --frame extracted_frames/line1_0010.jpg --gt 3 \
      --frame extracted_frames/line1_0001.jpg --gt 11.5 \
      --frame extracted_frames/line2_0011.jpg --gt 2 \
      --model classcan_density_float32.tflite

Add more --frame/--gt pairs (in matching order) to test on more of your
117 frames. Order matters: nth --frame goes with nth --gt.
"""

import argparse

import cv2
import numpy as np

try:
    from ai_edge_litert.interpreter import Interpreter
except ImportError:
    from tflite_runtime.interpreter import Interpreter


def load_interpreter(model_path):
    interpreter = Interpreter(model_path=model_path)
    interpreter.allocate_tensors()
    return interpreter, interpreter.get_input_details(), interpreter.get_output_details()


def get_density_map(frame_path, interpreter, input_details, output_details):
    target_h = input_details[0]["shape"][1]
    target_w = input_details[0]["shape"][2]
    img = cv2.imread(frame_path)
    img = cv2.resize(img, (target_w, target_h))
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    x = np.expand_dims(img, axis=0)

    interpreter.set_tensor(input_details[0]["index"], x)
    interpreter.invoke()
    out = interpreter.get_tensor(output_details[0]["index"])
    dmap = np.squeeze(out)
    if dmap.ndim == 3:
        dmap = dmap[..., 0]
    return dmap


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frame", action="append", required=True)
    ap.add_argument("--gt", action="append", required=True, type=float)
    ap.add_argument("--model", required=True)
    args = ap.parse_args()

    assert len(args.frame) == len(args.gt), "each --frame needs a matching --gt"

    interpreter, input_details, output_details = load_interpreter(args.model)

    dmaps = []
    for frame_path in args.frame:
        dmaps.append(get_density_map(frame_path, interpreter, input_details, output_details))

    # try a handful of relative thresholds (as a fraction of each map's own max value,
    # since absolute density values vary by frame)
    thresholds = [0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30]

    print(f"{'thresh':>8} {'MAE':>8} {'bias':>8}  (n={len(dmaps)} frames)")
    for t in thresholds:
        errs = []
        for dmap, gt in zip(dmaps, args.gt):
            cutoff = t * dmap.max()
            filtered = np.where(dmap >= cutoff, dmap, 0.0)
            pred = float(filtered.sum())
            errs.append(pred - gt)
        errs = np.array(errs)
        mae = np.mean(np.abs(errs))
        bias = np.mean(errs)
        print(f"{t:8.2f} {mae:8.2f} {bias:+8.2f}")




if __name__ == "__main__":
    main()