"""
Hard-positive (missed head) click-annotation tool.

Workflow:
  - Run this on your laptop (matplotlib needs a display; not for the headless Pi).
  - Point it at your 117 extracted frames + (optionally) the matching heatmap
    images from the fine-tuned model, so you can eyeball both side by side.
  - For each frame, click on any head the model MISSED or under-detected
    (occluded, bowed-down, edge-of-frame, etc). Skip frames where the heatmap
    already looks correct -- do NOT click every head, only the missed ones.
  - Close the window (or press 'n') to move to the next frame.
  - Progress is saved after every frame, so you can Ctrl+C and resume anytime.

Usage:
  python3 annotate_missed_heads.py --frames-dir extracted_frames --out hardpos_annotations.json
  python3 annotate_missed_heads.py --frames-dir extracted_frames --heatmaps-dir heatmaps --out hardpos_annotations.json

Controls while a frame is open:
  Left click   -> mark a missed head (red +)
  Right click  -> undo last click on this frame
  'n' key      -> next frame (same as closing the window)
  's' key      -> skip + mark this frame as "reviewed, 0 misses" (same as closing with no clicks)
  Close window -> save this frame's clicks and move on

Output format (hardpos_annotations.json):
  {
    "line2_0017.jpg": [[340.1, 118.9], [355.0, 120.2]],
    "sit1_0004.jpg": []
  }
Each list is [x, y] pixel coordinates (in the ORIGINAL frame's pixel space)
of missed head centers. An empty list means the frame was reviewed and no
heads were missed.
"""

import argparse
import glob
import json
import os

import matplotlib.pyplot as plt


def load_progress(out_path):
    if os.path.exists(out_path):
        with open(out_path, "r") as f:
            return json.load(f)
    return {}


def save_progress(out_path, annotations):
    tmp_path = out_path + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(annotations, f, indent=2)
    os.replace(tmp_path, out_path)


def find_heatmap_for(frame_path, heatmaps_dir):
    if not heatmaps_dir:
        return None
    stem = os.path.splitext(os.path.basename(frame_path))[0]
    for ext in (".jpg", ".jpeg", ".png"):
        candidate = os.path.join(heatmaps_dir, stem + ext)
        if os.path.exists(candidate):
            return candidate
    # also try a common "_heatmap" suffix convention
    for ext in (".jpg", ".jpeg", ".png"):
        candidate = os.path.join(heatmaps_dir, stem + "_heatmap" + ext)
        if os.path.exists(candidate):
            return candidate
    return None


def annotate(frames_dir, heatmaps_dir, out_path, exts):
    annotations = load_progress(out_path)

    frames = []
    for ext in exts:
        frames.extend(glob.glob(os.path.join(frames_dir, f"*{ext}")))
    frames = sorted(set(frames))

    if not frames:
        print(f"No frames found in {frames_dir} with extensions {exts}")
        return

    remaining = [f for f in frames if os.path.basename(f) not in annotations]
    print(f"{len(frames)} total frames, {len(remaining)} left to review "
          f"({len(annotations)} already done).")

    for idx, frame_path in enumerate(remaining, 1):
        fname = os.path.basename(frame_path)
        heatmap_path = find_heatmap_for(frame_path, heatmaps_dir)

        img = plt.imread(frame_path)
        points = []

        if heatmap_path:
            fig, axes = plt.subplots(1, 2, figsize=(14, 6))
            ax, ax_hm = axes
            hm_img = plt.imread(heatmap_path)
            ax_hm.imshow(hm_img)
            ax_hm.set_title("heatmap (reference only)")
            ax_hm.axis("off")
        else:
            fig, ax = plt.subplots(figsize=(8, 6))

        ax.imshow(img)
        ax.axis("off")

        def update_title():
            ax.set_title(
                f"[{idx}/{len(remaining)}] {fname} — click missed heads "
                f"({len(points)} marked) | close window / 'n' = next, 's' = no misses"
            )
            fig.canvas.draw_idle()

        update_title()

        markers = []

        def onclick(event):
            if event.inaxes != ax:
                return
            if event.button == 1 and event.xdata is not None:
                points.append((round(float(event.xdata), 1), round(float(event.ydata), 1)))
                (m,) = ax.plot(event.xdata, event.ydata, "r+", markersize=14, markeredgewidth=2)
                markers.append(m)
                update_title()
            elif event.button == 3 and points:
                points.pop()
                m = markers.pop()
                m.remove()
                update_title()

        def onkey(event):
            if event.key in ("n", "s"):
                plt.close(fig)

        fig.canvas.mpl_connect("button_press_event", onclick)
        fig.canvas.mpl_connect("key_press_event", onkey)

        plt.tight_layout()
        plt.show()  # blocks until window closed

        annotations[fname] = points
        save_progress(out_path, annotations)
        print(f"  saved {fname}: {len(points)} missed head(s)")

    print(f"\nDone. {len(annotations)} frames recorded in {out_path}")
    total_points = sum(len(v) for v in annotations.values())
    frames_with_misses = sum(1 for v in annotations.values() if v)
    print(f"Total missed-head points: {total_points} across {frames_with_misses} frames.")


def main():
    parser = argparse.ArgumentParser(description="Click-annotate missed heads for hard-positive fine-tuning.")
    parser.add_argument("--frames-dir", required=True, help="Folder of extracted frame images.")
    parser.add_argument("--heatmaps-dir", default=None,
                         help="Optional folder of matching heatmap images (same stem as frames) shown side by side.")
    parser.add_argument("--out", default="hardpos_annotations.json", help="Output JSON path.")
    parser.add_argument("--ext", default=".jpg,.jpeg,.png",
                         help="Comma-separated frame extensions to look for.")
    args = parser.parse_args()

    exts = [e if e.startswith(".") else f".{e}" for e in args.ext.split(",")]
    annotate(args.frames_dir, args.heatmaps_dir, args.out, exts)


if __name__ == "__main__":
    main()