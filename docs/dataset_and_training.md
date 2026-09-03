# CLASSCAN — Dataset Specification & Model Training Pipeline

This document defines the dataset composition, labeling standards, augmentation strategy, and quantization procedures for the CLASSCAN vision detection model.

---

## 1. Problem Definition & Architectural Objective

Standard object detection models (such as COCO-pretrained MobileNet-SSD or YOLO full-body models) fail when deployed in classroom settings because classroom furniture (wooden armchairs, shared tables, partition boards) physically obstructs 70% to 85% of a seated student's body.

```
                   [Ceiling Camera Angle: 30°–50°]
                                \
                                 ▼
                     ┌───────────────────────┐
                     │ Cranial Apex          │  <-- VISIBLE REGION
                     │ Neck & Shoulders Line │      (Annotated as "head")
                     ├───────────────────────┤
                     │ Torso & Arms          │  <-- PARTIALLY OCCLUDED
                     │ Desk / Armchair Wood  │      by classroom furniture
                     │ Legs & Feet           │  <-- FULLY OCCLUDED
                     └───────────────────────┘
```

**Target Objective:** Train an edge-optimized detector (**custom Keras multi-scale MobileNetV2 head detector**) on a dedicated single **"head"** class (head-and-shoulders bounding boxes) to reliably detect seated students under severe furniture occlusion from an elevated perspective.

---

## 2. Dataset Composition

The training and evaluation corpus combines a large-scale academic benchmark with a localized classroom dataset:

| Dataset | Image Count | Resolution | Annotation Format | Description & Purpose | License / Source |
|---|:---:|:---:|:---:|---|---|
| **SCUT-HEAD (Part A)** | 2,000 | 1024×576 to 1920×1080 | Pascal VOC / YOLO TXT | Dense classroom and indoor surveillance scenes with high student density and overlapping heads. Provides broad feature diversity across seating patterns. | Academic Research License (SCUT) |
| **Local Classroom Dataset** | 35 | 3840×2160 (4K) | YOLO TXT (Roboflow) | High-resolution photographs captured inside Philippine Christian University – Dasmariñas (PCU-D) classrooms at realistic ceiling pitch angles ($30^\circ$–$50^\circ$), capturing local wooden armchairs, uniforms, and fluorescent/ambient sunlight variations. | Proprietary / In-House |

---

## 3. Annotation & Labeling Standard

All annotations are normalized to a single class:

```
Class Index: 0
Class Name:  "head"
```

### Bounding Box Boundary Rules:
1. **Top Boundary:** Apex of the head/hairline.
2. **Bottom Boundary:** The clavicle / lower shoulder line (the top contour of the chest where the neck joins the shoulders).
3. **Lateral Boundaries:** Outermost lateral span of the shoulders or hair.
4. **Occlusion Handling:** If a student's shoulders are partially blocked by a front seat, the bounding box encloses the visible head down to the highest visible obstruction boundary.
5. **Distance & Minimum Size:** All heads with a pixel height $\ge 12\text{ px}$ in the input frame are labeled.

---

## 4. Data Augmentation Strategy (Roboflow Pipeline)

To ensure model resilience against ambient lighting changes, camera lens distortions, and varied classroom layouts, the following augmentations are applied:

```
Raw Images (SCUT-HEAD + Local)
        │
        ├── 1. Exposure / Brightness Shifts (±25%)    --> Simulates morning sun vs. evening darkness
        ├── 2. Contrast Adjustments (±20%)            --> Simulates harsh fluorescent classroom lamps
        ├── 3. Horizontal Flip (50% probability)      --> Doubles perspective variation
        ├── 4. Perspective Warping (±10° pitch/yaw)   --> Simulates varied ceiling mounting angles
        ├── 5. Mild Gaussian Blur (up to 1.5 px)      --> Simulates slight camera vibration during sweep
        │
        ▼
Augmented Training Dataset (~5,500 total images)
```

---

## 5. Model Architecture & Training Hyperparameters

### Architecture: Custom Keras Multi-Scale Head Detector

| Component | Details |
|---|---|
| **Backbone** | MobileNetV2 (300×300 input, ImageNet pre-weights, fine-tuned) |
| **Feature Pyramid** | 3-scale FPN: P3 (38×38, stride 8), P4 (19×19, stride 16), P5 (10×10, stride 32) |
| **Feature Layers** | `block_6_expand_relu` → P3, `block_13_expand_relu` → P4, `out_relu` → P5 |
| **Detection Heads** | Shared structure: Conv2D(128, 3×3, ReLU) → objectness (1 ch, logits) + boxes (4 ch, sigmoid) |
| **Total Parameters** | ~4.6M |
| **Input** | 300×300×3 float32 normalized [0, 1] |
| **Output (per scale)** | objectness logits + box [ymin, xmin, ymax, xmax] normalized |

### Target Encoding: Occupancy-Based Overflow Routing

Box-to-grid assignment does **not** use size-based routing. Box-size analysis across
20 real training images found ALL 641 boxes had `max(h,w) ≤ 0.07` (fully overhead-angle
dataset with no scale variety) — size-gated routing gave zero signal to P4/P5.

Instead, an occupancy-based overflow scheme routes densely-packed heads across scales:

```
For each box:
  1. Compute center cell in P3 (38×38)
  2. If P3 cell unoccupied → assign to P3
  3. Else if P4 cell unoccupied → overflow to P4
  4. Else if P5 cell unoccupied → overflow to P5
  5. Else → silently drop (extremely rare)
```

This repurposes multi-scale to solve **dense-crowd cell collisions** rather than scale variance.
Verified on a 83-box training image: P3=69, P4=11, P5=3, 0 drops (vs. 14 silently overwritten
under the old size-gated version).

### Loss Function

| Component | Method | Notes |
|---|---|---|
| **Objectness** | Focal loss (α=0.25, γ=2.0, `from_logits=True`) | `from_logits=True` is critical — manual sigmoid + log is numerically unstable |
| **Box Regression** | Smooth-L1 (δ=1.0) | Applied only to positive cells (mask) |
| **Normalization** | Divide by positive cell count | Prevents loss scale from varying with crowd density |
| **Multi-scale** | Sum across P3 + P4 + P5 | |
| **`box_loss_weight`** | 1.0 (epochs 1–50) → 2.0 (epochs 51–65) | Bumped to address box tightness/offset |

### Training Configuration

| Hyperparameter | Value |
|---|---|
| **Optimizer** | Adam (lr=1e-5, clipnorm=1.0) |
| **Batch Size** | 8 |
| **Batches/Epoch** | ~356 (on 2,850 training images) |
| **Time/Epoch** | ~10.8 min (Colab T4 GPU) |
| **Training pipeline** | Batched `tf.data` + `@tf.function` compiled steps |

### Training Results

| Run | Epochs | Final train_loss | Final val_loss | Notes |
|---|:---:|:---:|:---:|---|
| Initial smoke test | 3 | 0.4817 | 0.4841 | Pipeline confirmed working |
| Extended run 1 (original account) | 23→63 | — | — | **Lost** — Drive checkpoint saves silently failed (account/session mismatch). Disaster fixed by `save_checkpoint_verified()`. |
| Run 2 (brother's laptop, hardened script) | 50 | 0.2239 | 0.2564 | All 10 checkpoints Drive-verified (18922768 bytes each) |
| Run 3 (box_loss_weight=2.0, ep51–65) | +15 | 0.2115 | 0.2572 | val bottomed epoch 55 (0.2519), started rising epoch 60 |

**Best checkpoint: epoch 55** (box_loss_weight=2.0 phase).

### Key Banked Lessons

> **NaN Recovery Protocol:** Any time a NaN loss appears:
> 1. Diagnose and fix the actual code bug
> 2. **ALWAYS** rebuild BOTH model AND optimizer from scratch before retrying
>
> A single bad gradient step permanently corrupts model weights AND Adam's internal
> momentum/variance accumulators. No downstream code fix will recover a corrupted model.

> **tf.data pipeline reuse:** Redefining a function in a new Colab cell does NOT
> retroactively update an already-built `tf.data` pipeline or a `@tf.function` trace.
> Always rebuild the full pipeline (all cells in dependency order) after any function change.

---

## 6. TFLite Export

The trained Keras checkpoint (epoch-55) is exported via a `tf.Module` wrapper that
bakes sigmoid + NMS post-processing into the TFLite graph:

```bash
# From repo root (requires TF 2.x locally, or run in Colab)
python scripts/export_to_tflite.py \
    --weights path/to/ckpt_ep55.weights.h5 \
    --output  models/classcan_head_v1.tflite \
    --quant   float32

# With INT8 quantization (requires representative images dir):
python scripts/export_to_tflite.py \
    --weights path/to/ckpt_ep55.weights.h5 \
    --output  models/classcan_head_v1.tflite \
    --quant   int8 \
    --rep-images path/to/val_images/
```

The export wrapper outputs a **clean 3-tensor interface** to `detector.py`:

| Output | Shape | dtype | Description |
|---|---|---|---|
| `boxes`  | `[1, 100, 4]` | float32 | `[ymin,xmin,ymax,xmax]` normalized, zero-padded |
| `scores` | `[1, 100]`    | float32 | Objectness scores, zero-padded |
| `count`  | `[1]`         | int32   | Valid detections — slice with `[:count]` |

NMS (IoU threshold=0.45) is applied inside the TFLite graph — `detector.py` receives
already-deduplicated detections.

---

## 7. Model Signature Verification

After export, verify tensor signatures:

```python
from ai_edge_litert.interpreter import Interpreter

interpreter = Interpreter(model_path="models/classcan_head_v1.tflite")
interpreter.allocate_tensors()

print("--- CLASSCAN TFLite Model Inspection ---")
for d in interpreter.get_input_details():
    print(f"  INPUT  shape={d['shape']}  dtype={d['dtype'].__name__}")
for d in interpreter.get_output_details():
    print(f"  OUTPUT shape={d['shape']}  dtype={d['dtype'].__name__}  name={d['name']}")
```

### Expected Output:
```
  INPUT  shape=[1, 300, 300, 3]  dtype=float32
  OUTPUT shape=[1, 100, 4]  dtype=float32  name=...boxes
  OUTPUT shape=[1, 100]     dtype=float32  name=...scores
  OUTPUT shape=[1]          dtype=int32    name=...count
```

If the output names or tensor counts differ, check the `CLASSCANExportWrapper`
class in `scripts/export_to_tflite.py` and verify `tf.image.non_max_suppression`
converted cleanly (it requires `SELECT_TF_OPS` if graph conversion fails).

> **Note on label map:** Roboflow exports label name `"person"` with id 1 even for
> this dataset. This is a cosmetic naming artifact — the class IS head-and-shoulders
> detection. No relabeling is needed. The exported model has no class labels embedded
> (single-class implicit); `detector.py` treats all detections as `"head"`.
