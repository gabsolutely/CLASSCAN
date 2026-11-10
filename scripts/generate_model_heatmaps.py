"""
generate_model_heatmaps.py — Generate clean full-frame heatmap overlays for v4 and v5 models.

Matches the project's standard JET overlay (50% image + 50% color map).
"""

import os
import sys
import pathlib
import cv2
import numpy as np

# Set environment variable to silence TF oneDNN messages
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src" / "pi"))

from detection.detector import DensityDetector, EnsembleDensityDetector

OUT_DIR = ROOT / "scripts" / "heatmap_out"
OUT_DIR.mkdir(parents=True, exist_ok=True)

V5_MODEL = str(ROOT / "models" / "classcan_v5_final.tflite")
V4_ROUND4 = str(ROOT / "models" / "classcan_density_round4_ep8.tflite")
V4_STYLE_AUG = str(ROOT / "models" / "classcan_density_style_aug_ep8.tflite")


def make_heatmap_overlay(frame, density_map, alpha=0.5):
    """
    CLASSCAN heatmap overlay with UNPADDED alignment.

    The model preprocesses frames using gray-114 letterbox into 416x416, so the
    104x104 density map includes black padding rows/columns that map outside the
    actual image content. Cropping those padding rows/columns before upscaling
    ensures heatmap hotspots land exactly on heads rather than floating above them.

    For a 16:9 source frame (e.g. 1920x1080):
      scale = 416 / max(1080, 1920) = 416/1920 = 0.2167
      nh = int(1080 * 0.2167) = 233  nw = int(1920 * 0.2167) = 416
      pad_y = (416 - 233) // 2 = 91 px  (top + bottom)
      -> in 104x104 map: y0 = round(91*104/416) = 23  y1 = round((91+233)*104/416) = 81
    So dm[23:81, 0:104] is the actual image content region.
    """
    h, w = frame.shape[:2]
    target = 416
    dm_size = 104

    # Compute letterbox padding for this frame's aspect ratio
    scale = target / max(h, w)
    nh = int(h * scale)
    nw = int(w * scale)
    pad_y = (target - nh) // 2
    pad_x = (target - nw) // 2

    # Map padding pixels -> density map coordinates
    y0 = round(pad_y * dm_size / target)
    y1 = round((pad_y + nh) * dm_size / target)
    x0 = round(pad_x * dm_size / target)
    x1 = round((pad_x + nw) * dm_size / target)

    # Clamp to valid range
    y0 = max(0, min(y0, dm_size))
    y1 = max(y0 + 1, min(y1, dm_size))
    x0 = max(0, min(x0, dm_size))
    x1 = max(x0 + 1, min(x1, dm_size))

    # Crop out the letterbox-padded rows/cols
    dm_cropped = density_map[y0:y1, x0:x1]

    # Normalize and colorize
    norm_map = dm_cropped - dm_cropped.min()
    if norm_map.max() > 0:
        norm_map = norm_map / norm_map.max()
    heat_u8 = (norm_map * 255).astype(np.uint8)
    colored_heat = cv2.applyColorMap(heat_u8, cv2.COLORMAP_JET)

    # Upscale cropped heatmap back to full frame size
    colored_heat = cv2.resize(colored_heat, (w, h), interpolation=cv2.INTER_CUBIC)
    overlay = cv2.addWeighted(frame, 1.0 - alpha, colored_heat, alpha, 0)
    return overlay


def main():
    target_names = ["line1_0001", "line1_0010", "line2_0011"]
    if len(sys.argv) > 1:
        target_names = sys.argv[1:]

    print("=" * 60)
    print("CLASSCAN Heatmap Generator: v4 Ensemble & v5 Final")
    print("=" * 60)

    print("\n[Init] Loading v5 model...")
    det_v5 = DensityDetector(model_path=V5_MODEL, density_threshold=0.0)

    print("\n[Init] Loading v4 ensemble models...")
    det_v4 = EnsembleDensityDetector(
        round4_ep8_path=V4_ROUND4,
        style_aug_ep8_path=V4_STYLE_AUG,
        density_threshold=0.0,
    )

    results_summary = []

    for name in target_names:
        # Check potential file paths
        p = pathlib.Path(name)
        if not p.is_file():
            candidates = [
                ROOT / "scripts" / "extracted_frames" / f"{name}.jpg",
                ROOT / "scripts" / "extracted_frames" / f"{name}.png",
                ROOT / f"{name}.jpg",
            ]
            for c in candidates:
                if c.is_file():
                    p = c
                    break

        if not p.is_file():
            print(f"\n[Warning] File not found: {name}")
            continue

        base_stem = p.stem
        print(f"\n--> Processing: {p.name}")
        frame = cv2.imread(str(p))
        if frame is None:
            print(f"[Error] Failed to read image: {p}")
            continue

        # Inference: v4 ensemble
        res_v4 = det_v4.predict(frame)
        dmap_v4 = res_v4["density_map"]
        count_v4 = res_v4["count"]
        raw_v4 = res_v4["raw_sum"]

        # Inference: v5
        res_v5 = det_v5.predict(frame)
        dmap_v5 = res_v5["density_map"]
        count_v5 = res_v5["count"]
        raw_v5 = res_v5["raw_sum"]

        # Generate Heatmaps
        heatmap_v4 = make_heatmap_overlay(frame, dmap_v4, alpha=0.5)
        heatmap_v5 = make_heatmap_overlay(frame, dmap_v5, alpha=0.5)

        # Save files
        out_v4_path = OUT_DIR / f"{base_stem}_v4.jpg"
        out_v5_path = OUT_DIR / f"{base_stem}_v5.jpg"

        cv2.imwrite(str(out_v4_path), heatmap_v4, [cv2.IMWRITE_JPEG_QUALITY, 95])
        cv2.imwrite(str(out_v5_path), heatmap_v5, [cv2.IMWRITE_JPEG_QUALITY, 95])

        print(f"    v4 ensemble: count={count_v4:2d} (raw_sum={raw_v4:6.2f}) -> {out_v4_path.name}")
        print(f"    v5 model:    count={count_v5:2d} (raw_sum={raw_v5:6.2f}) -> {out_v5_path.name}")

        results_summary.append({
            "name": base_stem,
            "v4_count": count_v4,
            "v4_raw": raw_v4,
            "v4_path": out_v4_path,
            "v5_count": count_v5,
            "v5_raw": raw_v5,
            "v5_path": out_v5_path,
        })

    print("\n" + "=" * 60)
    print("Summary of Generated Heatmaps:")
    print("=" * 60)
    for r in results_summary:
        print(f"{r['name']}:")
        print(f"  v4: {r['v4_path']} (Count: {r['v4_count']}, Raw: {r['v4_raw']:.2f})")
        print(f"  v5: {r['v5_path']} (Count: {r['v5_count']}, Raw: {r['v5_raw']:.2f})")
    print(f"\nAll files saved in: {OUT_DIR}")


if __name__ == "__main__":
    main()

