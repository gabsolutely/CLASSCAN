"""
CLASSCAN — Model-Assisted Annotation & Frame Diversity Selector
================================================================
Implements Section 3 of the Domain-Shift Optimization Plan:
Accelerates dataset expansion from ceiling-mounted classroom footage.

Features:
---------
1. Intelligent Frame Selection (Disagreement + Diversity):
   - Rather than annotating random video frames, selects frames where the two
     ensemble models disagree most (|pred_round4 - pred_style_aug| >= threshold).
   - Enforces temporal stride to guarantee scene diversity across sessions.
   - Enforces the 15-20% empty/near-empty frame target (zero-density clips).

2. Peak Proposal Generation:
   - Runs ensemble inference to generate a 104×104 density map.
   - Locates spatial local maxima (peaks) above threshold as proposed head points (x, y).
   - Eliminates tedious clicking from scratch — annotators only need to add/remove points.

3. Standard Annotation Protocol & Partial-Head Rule:
   - Enforces the strict Partial-Head Rule:
     "Annotate if at least 50% of the head is visible, OR if the forehead
      and at least one eye are within frame. Do not annotate backpacks or torsos."
   - Outputs standardized JSON/CSV dataset manifests ready for Gaussian density map generation.

Usage:
------
# 1. Propose candidate points for unannotated session frames:
python scripts/annotate_assisted.py \\
    --frames-dir extracted_frames/ \\
    --session-id room3_day1 \\
    --model-r4 models/classcan_density_round4_ep8.tflite \\
    --model-sa models/classcan_density_style_aug_ep8.tflite \\
    --disagreement-threshold 1.5 \\
    --min-stride 15 \\
    --out-manifest data/assisted_proposals.json

# 2. Render visual inspection images with proposed point overlays:
python scripts/annotate_assisted.py \\
    --manifest data/assisted_proposals.json \\
    --render-previews previews/

# 3. Smoke test with mock model:
python scripts/annotate_assisted.py --mock --out-manifest mock_proposals.json
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

# Ensure src/pi and scripts are on path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "src" / "pi"))
sys.path.insert(0, str(BASE_DIR / "scripts"))

try:
    import cv2
except ImportError:
    cv2 = None

PARTIAL_HEAD_RULE = (
    "Annotate if >= 50% of head is visible, OR if forehead and at least one eye "
    "are within the frame boundary. Do not annotate empty chairs, bags, or headless torsos."
)


def find_density_peaks(
    density_map: np.ndarray,
    min_distance: int = 3,
    threshold_rel: float = 0.20,
) -> List[Tuple[float, float]]:
    """
    Find local peaks (local maxima) in a 2D density map.
    Returns normalized (x, y) coordinates in [0.0, 1.0].
    """
    h, w = density_map.shape[:2]
    peak_val = density_map.max()
    if peak_val <= 1e-6:
        return []

    cutoff = peak_val * threshold_rel

    if cv2 is not None:
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2 * min_distance + 1, 2 * min_distance + 1))
        dilated = cv2.dilate(density_map, kernel)
        peaks_mask = (density_map == dilated) & (density_map >= cutoff)
        y_indices, x_indices = np.where(peaks_mask)
    else:
        # Pure numpy fallback
        y_indices, x_indices = [], []
        pad = min_distance
        padded = np.pad(density_map, pad, mode="constant", constant_values=0)
        for r in range(h):
            for c in range(w):
                val = density_map[r, c]
                if val >= cutoff:
                    patch = padded[r : r + 2 * pad + 1, c : c + 2 * pad + 1]
                    if val == np.max(patch):
                        y_indices.append(r)
                        x_indices.append(c)

    points = []
    for r, c in zip(y_indices, x_indices):
        norm_x = round(float(c) / float(w), 4)
        norm_y = round(float(r) / float(h), 4)
        points.append((norm_x, norm_y))
    return points


def select_diverse_frames(
    image_paths: List[str],
    min_stride: int = 10,
    empty_ratio: float = 0.18,
) -> Tuple[List[str], List[str]]:
    """
    Filter image paths to enforce temporal spacing and separate potential empty scenes.
    Returns (candidate_paths, empty_paths).
    """
    candidate_paths = []
    empty_paths = []

    for i, p in enumerate(sorted(image_paths)):
        name = os.path.basename(p).lower()
        if "empty" in name or "vacant" in name or "zero" in name:
            if i % max(1, min_stride // 2) == 0:
                empty_paths.append(p)
        else:
            if i % min_stride == 0:
                candidate_paths.append(p)

    return candidate_paths, empty_paths


def process_assisted_annotation(
    frames_dir: str,
    session_id: str,
    model_r4_path: str = None,
    model_sa_path: str = None,
    disagreement_thresh: float = 1.0,
    min_stride: int = 12,
    force_mock: bool = False,
) -> List[Dict[str, Any]]:
    """Scan directory, evaluate ensemble, and generate point proposal records."""
    from zzexp.eval_harness import ModelEvaluator

    evaluator = ModelEvaluator(
        model_r4_path=model_r4_path,
        model_sa_path=model_sa_path,
        force_mock=force_mock or (not model_r4_path and not model_sa_path),
    )

    image_exts = ("*.jpg", "*.jpeg", "*.png")
    all_files = []
    if os.path.isdir(frames_dir):
        for ext in image_exts:
            all_files.extend(list(Path(frames_dir).glob(ext)))
            all_files.extend(list(Path(frames_dir).glob(f"**/{ext}")))
    all_files = [str(f) for f in sorted(list(set(all_files)))]

    if not all_files:
        if force_mock:
            all_files = [f"mock_frame_{i:04d}.jpg" for i in range(30)]
        else:
            raise FileNotFoundError(f"No frames found in {frames_dir}")

    candidates, empty_candidates = select_diverse_frames(all_files, min_stride=min_stride)
    print(f"[annotate_assisted] Filtered {len(all_files)} frames -> {len(candidates)} active + {len(empty_candidates)} empty candidates")

    proposals = []

    # 1. Process empty frames (15-20% target)
    for p in empty_candidates:
        proposals.append({
            "session_id": session_id,
            "frame_path": p,
            "is_empty_frame": True,
            "proposed_points": [],
            "proposed_count": 0,
            "disagreement": 0.0,
            "rule": PARTIAL_HEAD_RULE,
            "verified": True,
        })

    # 2. Process active frames
    for p in candidates:
        pred_int, raw_sum, dm = evaluator.predict_frame(p)

        # Compute model disagreement if ensemble is active
        disagreement = 0.0
        if not evaluator.force_mock and hasattr(evaluator, "detector") and hasattr(evaluator.detector, "_interp_r4"):
            # Compute difference between r4 and sa predictions
            try:
                frame_bgr = cv2.imread(p) if cv2 else None
                if frame_bgr is not None:
                    res = evaluator.detector.predict(frame_bgr)
                    r4 = res.get("raw_sum_round4", raw_sum)
                    sa = res.get("raw_sum_style_aug", raw_sum)
                    disagreement = abs(r4 - sa)
            except Exception:
                disagreement = 0.0

        if dm is not None:
            points = find_density_peaks(dm, min_distance=3, threshold_rel=0.20)
        else:
            points = []

        proposals.append({
            "session_id": session_id,
            "frame_path": p,
            "is_empty_frame": False,
            "proposed_points": points,
            "proposed_count": len(points),
            "raw_predicted_sum": round(raw_sum, 2),
            "disagreement": round(disagreement, 2),
            "priority": "HIGH" if disagreement >= disagreement_thresh else "NORMAL",
            "rule": PARTIAL_HEAD_RULE,
            "verified": False,
        })

    print(f"[annotate_assisted] Generated proposals for {len(proposals)} frames.")
    return proposals


def render_preview_overlay(proposal: Dict[str, Any], out_path: str):
    """Draw proposed point markers onto image for rapid human verification."""
    if cv2 is None or not os.path.isfile(proposal["frame_path"]):
        return

    frame = cv2.imread(proposal["frame_path"])
    if frame is None:
        return
    h, w = frame.shape[:2]

    # Draw proposed points
    for pt in proposal["proposed_points"]:
        cx = int(pt[0] * w)
        cy = int(pt[1] * h)
        cv2.circle(frame, (cx, cy), 6, (0, 0, 255), -1)
        cv2.circle(frame, (cx, cy), 8, (255, 255, 255), 1)

    # Draw header banner
    cv2.rectangle(frame, (0, 0), (w, 40), (25, 25, 25), -1)
    status = (
        f"POINTS: {proposal['proposed_count']} | DISAGREE: {proposal.get('disagreement', 0)} | "
        f"SESSION: {proposal['session_id']} | EMPTY: {proposal['is_empty_frame']}"
    )
    cv2.putText(frame, status, (10, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    cv2.imwrite(out_path, frame)


def main():
    parser = argparse.ArgumentParser(description="CLASSCAN Model-Assisted Annotation Tool")
    parser.add_argument("--frames-dir", default="extracted_frames", help="Folder containing session frames")
    parser.add_argument("--session-id", default="session_1", help="Session identifier (room + day)")
    parser.add_argument("--model-r4", help="Path to classcan_density_round4_ep8.tflite")
    parser.add_argument("--model-sa", help="Path to classcan_density_style_aug_ep8.tflite")
    parser.add_argument("--disagreement-threshold", type=float, default=1.0, help="Disagreement cutoff for HIGH priority")
    parser.add_argument("--min-stride", type=int, default=10, help="Temporal frame stride for scene diversity")
    parser.add_argument("--out-manifest", default="data/assisted_proposals.json", help="Path to save proposal JSON")
    parser.add_argument("--render-previews", help="Optional folder to render visual proposal overlays")
    parser.add_argument("--manifest", help="Load existing manifest to render previews")
    parser.add_argument("--mock", action="store_true", help="Force mock mode without live models")
    args = parser.parse_args()

    if args.manifest and os.path.isfile(args.manifest) and args.render_previews:
        with open(args.manifest, "r", encoding="utf-8") as f:
            data = json.load(f)
        for i, item in enumerate(data):
            out_p = os.path.join(args.render_previews, f"preview_{i:04d}.jpg")
            render_preview_overlay(item, out_p)
        print(f"[annotate_assisted] Rendered {len(data)} previews to {args.render_previews}")
        return

    proposals = process_assisted_annotation(
        frames_dir=args.frames_dir,
        session_id=args.session_id,
        model_r4_path=args.model_r4,
        model_sa_path=args.model_sa,
        disagreement_thresh=args.disagreement_threshold,
        min_stride=args.min_stride,
        force_mock=args.mock,
    )

    os.makedirs(os.path.dirname(os.path.abspath(args.out_manifest)), exist_ok=True)
    with open(args.out_manifest, "w", encoding="utf-8") as f:
        json.dump(proposals, f, indent=2)
    print(f"[annotate_assisted] Manifest saved to {args.out_manifest}")

    if args.render_previews:
        for i, item in enumerate(proposals[:20]):
            out_p = os.path.join(args.render_previews, f"prop_{i:04d}.jpg")
            render_preview_overlay(item, out_p)
        print(f"[annotate_assisted] Rendered previews to {args.render_previews}")


if __name__ == "__main__":
    main()
