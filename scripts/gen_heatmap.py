"""
gen_heatmap.py — Generate v4 ensemble + v5 density heatmap overlays for chosen images.

Usage:
    python scripts/gen_heatmap.py path/to/image1.jpg path/to/image2.jpg ...

Outputs (in scripts/heatmap_out/):
    <name>_v4.jpg   — v4 ensemble overlay
    <name>_v5.jpg   — v5 overlay
    <name>_compare.jpg — side-by-side v4 | v5
"""

import sys
import os
import pathlib
import numpy as np
import cv2

# ── Paths ──────────────────────────────────────────────────────────────────────
ROOT   = pathlib.Path(__file__).resolve().parent.parent
MODELS = ROOT / "models"

V5_PATH  = MODELS / "classcan_v5_final.tflite"
V4A_PATH = MODELS / "classcan_density_round4_ep8.tflite"
V4B_PATH = MODELS / "classcan_density_style_aug_ep8.tflite"

OUT_DIR = pathlib.Path(__file__).parent / "heatmap_out"
OUT_DIR.mkdir(exist_ok=True)

TARGET_W, TARGET_H = 416, 416
DM_H, DM_W = 104, 104

# ── TFLite loader ──────────────────────────────────────────────────────────────
def load_interp(path):
    try:
        import tflite_runtime.interpreter as tflite
        Interpreter = tflite.Interpreter
    except ImportError:
        import tensorflow as tf
        Interpreter = tf.lite.Interpreter
    interp = Interpreter(model_path=str(path))
    interp.allocate_tensors()
    in_idx  = interp.get_input_details()[0]["index"]
    out_idx = interp.get_output_details()[0]["index"]
    return interp, in_idx, out_idx

# ── Preprocessing ──────────────────────────────────────────────────────────────
def letterbox(frame, size=416):
    """Gray-114 letterbox, returns float32 0-255 RGB [1,H,W,3]."""
    h, w = frame.shape[:2]
    scale = size / max(h, w)
    nh, nw = int(h * scale), int(w * scale)
    canvas = np.full((size, size, 3), 114, dtype=np.float32)
    resized = cv2.resize(frame, (nw, nh))
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB).astype(np.float32)
    canvas[:nh, :nw] = rgb
    return np.expand_dims(canvas, 0)

def stretch(frame, size=416):
    """Stretch resize, returns float32 0-1 RGB [1,H,W,3] (v4 style_aug uses 0-1)."""
    resized = cv2.resize(frame, (size, size))
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    return np.expand_dims(rgb, 0)

def letterbox_norm(frame, size=416):
    """Letterbox, returns float32 0-1 (v4 round4 uses 0-1)."""
    h, w = frame.shape[:2]
    scale = size / max(h, w)
    nh, nw = int(h * scale), int(w * scale)
    canvas = np.zeros((size, size, 3), dtype=np.float32)
    resized = cv2.resize(frame, (nw, nh))
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    canvas[:nh, :nw] = rgb
    return np.expand_dims(canvas, 0)

# ── Inference ──────────────────────────────────────────────────────────────────
def run_v5(interp, in_idx, out_idx, frame):
    """v5: letterbox 0-255 float32 input (built-in Rescaling layer)."""
    inp = letterbox(frame, 416)
    interp.set_tensor(in_idx, inp)
    interp.invoke()
    dm = np.squeeze(interp.get_tensor(out_idx)).astype(np.float32)
    return dm  # (104, 104)

def run_v4_ensemble(r4_interp, r4_in, r4_out, sa_interp, sa_in, sa_out, frame):
    """v4 ensemble: 0.6 * round4_letterbox + 0.4 * style_aug_stretch."""
    inp_lb = letterbox_norm(frame, 416)
    r4_interp.set_tensor(r4_in, inp_lb)
    r4_interp.invoke()
    dm_r4 = np.squeeze(r4_interp.get_tensor(r4_out)).astype(np.float32)

    inp_st = stretch(frame, 416)
    sa_interp.set_tensor(sa_in, inp_st)
    sa_interp.invoke()
    dm_sa = np.squeeze(sa_interp.get_tensor(sa_out)).astype(np.float32)

    return 0.6 * dm_r4 + 0.4 * dm_sa  # (104, 104)

# ── Heatmap overlay ───────────────────────────────────────────────────────────
def overlay_heatmap(bgr_frame, density_map, alpha=0.55):
    """
    Upscale density_map to frame size, apply jet colormap, blend over frame.
    Returns a new BGR image.
    """
    h, w = bgr_frame.shape[:2]
    dm = density_map.copy()

    # Suppress very low background noise
    dm_max = dm.max()
    if dm_max > 0:
        dm = dm / dm_max  # normalise 0-1

    # Upscale to frame size
    dm_up = cv2.resize(dm, (w, h), interpolation=cv2.INTER_CUBIC)
    dm_up = np.clip(dm_up, 0, 1)

    # Apply jet colormap
    dm_u8   = (dm_up * 255).astype(np.uint8)
    jet     = cv2.applyColorMap(dm_u8, cv2.COLORMAP_JET)

    # Blend: darken the original slightly, then composite heatmap
    base = (bgr_frame.astype(np.float32) * 0.55).astype(np.uint8)

    # Mask: fully transparent where density is very low (<8%)
    mask = (dm_up > 0.08).astype(np.float32)
    mask = cv2.GaussianBlur(mask.astype(np.float32), (21, 21), 0)

    out = base.astype(np.float32)
    out += (jet.astype(np.float32) * alpha * mask[:, :, np.newaxis])
    out = np.clip(out, 0, 255).astype(np.uint8)

    return out

def annotate(img, label, count):
    """Stamp model label and predicted count on the image."""
    h, w = img.shape[:2]
    # Dark pill background
    cv2.rectangle(img, (0, 0), (w, 52), (10, 10, 20), -1)
    cv2.putText(img, label, (12, 22),
                cv2.FONT_HERSHEY_DUPLEX, 0.65, (200, 200, 255), 1, cv2.LINE_AA)
    cv2.putText(img, f"Count: {count:.2f}", (12, 44),
                cv2.FONT_HERSHEY_DUPLEX, 0.65, (100, 255, 160), 1, cv2.LINE_AA)
    return img

# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/gen_heatmap.py image1.jpg image2.jpg ...")
        sys.exit(1)

    images = sys.argv[1:]

    # Load models
    print("Loading v5 model...")
    v5_interp, v5_in, v5_out = load_interp(V5_PATH)

    print("Loading v4 ensemble models...")
    r4_interp, r4_in, r4_out = load_interp(V4A_PATH)
    sa_interp, sa_in, sa_out = load_interp(V4B_PATH)

    for img_path in images:
        img_path = pathlib.Path(img_path)
        if not img_path.exists():
            print(f"[SKIP] Not found: {img_path}")
            continue

        frame = cv2.imread(str(img_path))
        if frame is None:
            print(f"[SKIP] Cannot read: {img_path}")
            continue

        name = img_path.stem
        print(f"\nProcessing: {img_path.name}")

        # Run v5
        dm_v5    = run_v5(v5_interp, v5_in, v5_out, frame)
        count_v5 = float(dm_v5.sum())
        print(f"  v5  raw_sum={count_v5:.3f}  peak={dm_v5.max():.4f}")

        # Run v4 ensemble
        dm_v4    = run_v4_ensemble(r4_interp, r4_in, r4_out, sa_interp, sa_in, sa_out, frame)
        count_v4 = float(dm_v4.sum())
        print(f"  v4  raw_sum={count_v4:.3f}  peak={dm_v4.max():.4f}")

        # Build overlays
        ov_v5 = overlay_heatmap(frame.copy(), dm_v5)
        ov_v5 = annotate(ov_v5, "v5  (MobileNetV3-L, MAE=1.47)", count_v5)

        ov_v4 = overlay_heatmap(frame.copy(), dm_v4)
        ov_v4 = annotate(ov_v4, "v4 ensemble (round4+style_aug, MAE=2.77)", count_v4)

        # Save individual
        out_v5 = OUT_DIR / f"{name}_v5.jpg"
        out_v4 = OUT_DIR / f"{name}_v4.jpg"
        cv2.imwrite(str(out_v5), ov_v5, [cv2.IMWRITE_JPEG_QUALITY, 92])
        cv2.imwrite(str(out_v4), ov_v4, [cv2.IMWRITE_JPEG_QUALITY, 92])

        # Side-by-side compare (v4 | divider | v5)
        h = max(ov_v4.shape[0], ov_v5.shape[0])
        div = np.full((h, 4, 3), 60, dtype=np.uint8)  # thin grey divider
        compare = np.hstack([
            cv2.resize(ov_v4, (ov_v4.shape[1], h)),
            div,
            cv2.resize(ov_v5, (ov_v5.shape[1], h)),
        ])
        out_cmp = OUT_DIR / f"{name}_compare.jpg"
        cv2.imwrite(str(out_cmp), compare, [cv2.IMWRITE_JPEG_QUALITY, 92])

        print(f"  Saved → {out_v4.name}")
        print(f"  Saved → {out_v5.name}")
        print(f"  Saved → {out_cmp.name}")

    print(f"\nDone. All outputs in: {OUT_DIR}")

if __name__ == "__main__":
    main()

