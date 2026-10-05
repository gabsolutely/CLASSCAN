# CLASSCAN — Scripts Reference

All scripts in this directory. Scripts marked **Pi** run on the Raspberry Pi 3B;
those marked **Dev** run on a development machine (Windows/Linux/Mac with Python + dependencies).

---

## Inference & Hardware Smoke-Tests

| Script | Where | Purpose |
|---|---|---|
| `run_on_image.py` | Dev / Pi | Run a single `.tflite` model on an image file and print the result. Quickest way to verify a model file loads and produces output. |
| `camera_verify.py` | Pi | Live camera feed test — opens `/dev/video0` and streams frames to confirm the OV4689 is working and correctly exposed. |
| `pi_benchmark.py` | Pi | Time TFLite inference on the Pi 3B CPU and report ms/frame. Use to verify performance after any model change. |
| `speed_test.py` | Pi | Minimal inference timing script (lighter than `pi_benchmark.py`). |

## Model Export

| Script | Where | Purpose |
|---|---|---|
| `export_to_tflite.py` | Dev (Colab) | Convert a Keras `.weights.h5` checkpoint to a `.tflite` file (float32 or int8). Required before deploying a new model to the Pi. See `models/README.md` for exact export commands. |

## Training & Data Preparation

> These are **training-time only** — not needed for deployment.

| Script | Where | Purpose |
|---|---|---|
| `classcan_training_pipeline.py` | Dev (Colab) | Full Keras training pipeline for `classcan_density_v4` (density-map regression). Includes data loading, augmentation, LR scheduling, and checkpoint saving. |
| `annotate_missed_heads.py` | Dev | Matplotlib click-annotation tool. Opens extracted frames and lets you click to mark missed head positions. Saves output to `hardpos_annotations.json`. |
| `extract_hard_negatives.py` | Dev | Crops confirmed false-positive regions (bags, chairs, etc.) from frames for hard-negative fine-tuning. |
| `build_manual_hardneg_manifest.py` | Dev | Builds the training manifest JSON for manual hard-negative crops in `manual_clutter_crops/`. |
| `find_remaining_false_positives.py` | Dev | Runs the model over the extracted frames and flags cells above a density threshold that don't correspond to annotated heads. |
| `threshold_sweep.py` | Dev | Sweeps the `DENSITY_THRESHOLD` config value and reports MAE/correlation on the annotated frame set. Used to calibrate the per-frame density cutoff. |
| `diagnose_density.py` | Dev | Visualises raw density map heatmaps for a set of frames. Use to inspect what the model is "seeing" vs. ground truth. |
| `class_footage_test.py` | Dev | Evaluates the current model against the 5-clip real-footage test set and reports per-clip MAE and correlation. |

## Annotation Data

| File | Description |
|---|---|
| `hardpos_annotations.json` | 490 manually annotated missed-head points across 115/117 frames from the first real-footage clip set (used in Rounds 2–9 fine-tuning). |

---

## Key Commands

```bash
# Smoke-test a model file on any image
python scripts/run_on_image.py path/to/image.jpg models/classcan_density_round4_ep8.tflite

# Benchmark inference speed on the Pi
python scripts/pi_benchmark.py

# Export a checkpoint to TFLite (run on Colab/dev machine)
python scripts/export_to_tflite.py --mode density \
    --weights /path/to/checkpoint.weights.h5 \
    --output models/classcan_density_round4_ep8.tflite --quant float32
```
