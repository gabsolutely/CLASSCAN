"""
Diagnostic: visualize the raw density map for a handful of frames to see
WHERE the model is predicting density, instead of just the summed count.

This will help distinguish between:
  (a) background/floor bias -- model predicts low but nonzero density
      everywhere, even on empty walls/floor -> explains a roughly
      CONSTANT additive overcount regardless of true crowd size
  (b) real overcounting on people -- density correctly concentrated on
      people but amplitude is too high -> suggests a scaling/calibration
      fix, not a preprocessing bug
  (c) resize/aspect-ratio distortion -- check by comparing predictions
      with plain stretch-resize (current behavior) vs letterboxed resize

USAGE (on the Pi, same venv):
  python3 diagnose_density.py \
      --frame extracted_frames/line1_0001.jpg \
      --frame extracted_frames/line1_0010.jpg \
      --model classcan_density_float32.tflite \
      --out-dir diagnostics
"""

import argparse
import os

import cv2
import numpy as np

try:
    from ai_edge_litert.interpreter import Interpreter
except ImportError:
    from tflite_runtime.interpreter import Interpreter


def load_interpreter(model_path: str):
    interpreter = Interpreter(model_path=model_path)
    interpreter.allocate_tensors()
    return interpreter, interpreter.get_input_details(), interpreter.get_output_details()


def preprocess_stretch(frame, target_hw):
    """Current behavior: naive stretch resize, ignores aspect ratio."""
    h, w = target_hw
    img = cv2.resize(frame, (w, h))
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    return np.expand_dims(img, axis=0)


def preprocess_letterbox(frame, target_hw):
    """Alternative: pad to preserve aspect ratio, like many training pipelines use."""
    h, w = target_hw
    ih, iw = frame.shape[:2]
    scale = min(w / iw, h / ih)
    nw, nh = int(iw * scale), int(ih * scale)
    resized = cv2.resize(frame, (nw, nh))
    canvas = np.zeros((h, w, 3), dtype=np.uint8)
    top = (h - nh) // 2
    left = (w - nw) // 2
    canvas[top:top + nh, left:left + nw] = resized
    img = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    return np.expand_dims(img, axis=0)


def run(interpreter, input_details, output_details, x):
    interpreter.set_tensor(input_details[0]["index"], x)
    interpreter.invoke()
    out = interpreter.get_tensor(output_details[0]["index"])
    return out


def analyze_frame(frame_path, interpreter, input_details, output_details, out_dir):
    target_h = input_details[0]["shape"][1]
    target_w = input_details[0]["shape"][2]

    frame = cv2.imread(frame_path)
    name = os.path.splitext(os.path.basename(frame_path))[0]

    x_stretch = preprocess_stretch(frame, (target_h, target_w))
    out_stretch = run(interpreter, input_details, output_details, x_stretch)
    sum_stretch = float(np.sum(out_stretch))

    x_letterbox = preprocess_letterbox(frame, (target_h, target_w))
    out_letterbox = run(interpreter, input_details, output_details, x_letterbox)
    sum_letterbox = float(np.sum(out_letterbox))

    dmap = np.squeeze(out_stretch)  # drop batch/channel dims for visualization
    if dmap.ndim == 3:
        dmap = dmap[..., 0]

    # background stat: density in border 10% of the map (should be near-empty
    # in most real classroom framings unless people are edge-to-edge)
    bh, bw = dmap.shape
    border = max(1, int(0.1 * min(bh, bw)))
    border_mask = np.ones_like(dmap, dtype=bool)
    border_mask[border:-border, border:-border] = False
    border_density_sum = float(dmap[border_mask].sum())
    border_frac = border_density_sum / (sum_stretch + 1e-8)

    print(f"\n[{name}]")
    print(f"  stretch-resize predicted count : {sum_stretch:.2f}")
    print(f"  letterbox-resize predicted count: {sum_letterbox:.2f}")
    print(f"  density map shape              : {dmap.shape}, min={dmap.min():.4f}, max={dmap.max():.4f}, mean={dmap.mean():.4f}")
    print(f"  density mass in outer 10% border: {border_density_sum:.2f} ({border_frac*100:.1f}% of total)")

    # save a heatmap overlay for visual inspection
    os.makedirs(out_dir, exist_ok=True)
    heat = dmap - dmap.min()
    if heat.max() > 0:
        heat = heat / heat.max()
    heat_u8 = (heat * 255).astype(np.uint8)
    heat_color = cv2.applyColorMap(heat_u8, cv2.COLORMAP_JET)
    heat_color = cv2.resize(heat_color, (frame.shape[1], frame.shape[0]))
    overlay = cv2.addWeighted(frame, 0.5, heat_color, 0.5, 0)
    out_path = os.path.join(out_dir, f"{name}_heatmap.jpg")
    cv2.imwrite(out_path, overlay)
    print(f"  saved heatmap overlay -> {out_path}")

    return {
        "frame": name,
        "sum_stretch": sum_stretch,
        "sum_letterbox": sum_letterbox,
        "border_frac_pct": border_frac * 100,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frame", action="append", required=True, help="Path to a frame image. Repeat for multiple.")
    ap.add_argument("--model", required=True)
    ap.add_argument("--out-dir", default="diagnostics")
    args = ap.parse_args()

    interpreter, input_details, output_details = load_interpreter(args.model)
    print(f"[model] loaded {args.model}, input shape {input_details[0]['shape']}")

    rows = []
    for frame_path in args.frame:
        rows.append(analyze_frame(frame_path, interpreter, input_details, output_details, args.out_dir))

    print("\n=== SUMMARY ===")
    print(f"{'frame':20} {'stretch':>10} {'letterbox':>10} {'border%':>10}")
    for r in rows:
        print(f"{r['frame']:20} {r['sum_stretch']:10.2f} {r['sum_letterbox']:10.2f} {r['border_frac_pct']:10.1f}")

    print("\nInterpretation guide:")
    print("- If border% is high (e.g. >15-20%) on frames where the border is mostly")
    print("  empty wall/floor -> model is hallucinating background density -> points")
    print("  to a training/label issue or a needed post-hoc offset correction.")
    print("- If stretch vs letterbox counts differ a lot -> your training preprocessing")
    print("  likely didn't match this script's stretch-resize -> switch preprocessing")
    print("  in the main inference script to match training exactly.")
    print("- Open the saved *_heatmap.jpg files and check: is density concentrated on")
    print("  actual heads, or spread diffusely across furniture/floor/background?")


if __name__ == "__main__":
    main()