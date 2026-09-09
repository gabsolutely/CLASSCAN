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

### Final Architecture: Custom Keras Multi-Scale MobileNetV3-Large + 416×416 Head Detector

| Component | Details |
|---|---|
| **Backbone** | MobileNetV3-Large (416×416 input, ImageNet pre-weights, fine-tuned) |
| **Feature Pyramid** | 3-scale FPN: P3 (52×52, stride 8), P4 (26×26, stride 16), P5 (13×13, stride 32) |
| **Feature Layers** | `expanded_conv_5_add` → P3, `expanded_conv_11_add` → P4, `expanded_conv_14_add` → P5 |
| **Detection Heads** | Shared structure: Conv2D(128, 3×3, ReLU) → objectness (1 ch, logits) + boxes (4 ch, sigmoid) |
| **Input** | 416×416×3 float32 normalized [0, 1] |
| **Output (per scale)** | objectness logits + box [ymin, xmin, ymax, xmax] normalized |

### Target Encoding: Occupancy-Based Overflow Routing

Box-to-grid assignment does **not** use size-based routing. Box-size analysis across
training images found ALL boxes had `max(h,w) ≤ 0.07` (overhead classroom perspective
with no scale variety) — size-gated routing gave zero signal to P4/P5.

An occupancy-based overflow scheme routes densely-packed heads across scales:

```
For each box:
  1. Compute center cell in P3 (52×52)
  2. If P3 cell unoccupied → assign to P3
  3. Else if P4 cell unoccupied → overflow to P4 (26×26)
  4. Else if P5 cell unoccupied → overflow to P5 (13×13)
  5. Else → drop box (extremely rare)
```

This repurposes multi-scale to solve **dense-crowd cell collisions** rather than scale variance.

### Loss Function & Numerical Hardening

| Component | Method | Notes |
|---|---|---|
| **Objectness** | Focal loss (α=0.25, γ=2.0, `from_logits=True`) | `from_logits=True` avoids saturating-sigmoid log(0) NaN failure |
| **Box Regression** | Smooth-L1 (Huber, δ=1.0) | Masked to positive cells only |
| **Box Clipping** | Clip predictions to $\pm 8.0$ | **Critical stability fix:** prevents unconstrained early predictions (up to $\pm 36$) from blowing up loss on dense images |
| **Normalization** | Divide by positive cell count | Prevents loss scaling with crowd density |
| **Multi-scale** | Sum across P3 + P4 + P5 | |

### Training Configuration & Stability Protocol

| Hyperparameter | Value |
|---|---|
| **Optimizer** | Adam (lr=1e-4 with 5-epoch linear warmup from 1e-5; `clipnorm=0.5`) |
| **Batch Size** | 8 (`drop_remainder=True` to prevent ragged batch retracing) |
| **Dataset Cache** | Disk-backed cache (`/content/train_cache`) to prevent Colab system RAM exhaustion |
| **Spike Guard** | Automated safeguard: skips checkpoint save if `val_loss` jumps $>20\times$ vs. last known-good epoch |
| **Checkpoint Dir** | `/content/drive/MyDrive/models/` (secondary Google account) |

### Training Evolution & Checkpoints

| Phase | Backbone | Input | Epochs | Best Val Loss | Best Eval (F1) | Notes |
|---|---|:---:|:---:|:---:|:---:|---|
| Run 1–3 (Baseline) | MobileNetV2 | 300×300 | 60 | 0.2519 (ep55) | 19.5% (ep60) | Plateaued; dense images overpredicted |
| CrowdHuman (V2) | MobileNetV2 | 300×300 | 50 | ~0.175 | 15.5% | Domain mismatch; underperformed baseline |
| **V3 Full Run (Final)** | **MobileNetV3-Large** | **416×416** | **60** | **0.2535 (ep60)** | **30.1%** | **Confirmed best model across all tests** |
| CrowdHuman (V3) | MobileNetV3-Large | 416×416 | 10 | 2.93 (ep7) | 0.0% | Objectness collapse; experiment concluded |

**Final Checkpoint: Epoch 60 MobileNetV3-Large @ 416×416** (`val_loss=0.2535`, `train_loss=0.1498`).

### Key Banked Lessons

> **NaN & Spike Recovery Protocol:** Any time a gradient corruption or loss spike appears:
> 1. Diagnose root cause (e.g., unconstrained box regression or pathological batch).
> 2. **ALWAYS** rebuild BOTH model AND optimizer from scratch before retrying.
> 3. Never save weights from a post-spike epoch — verify loss before persisting.

> **Consolidated Recovery Cell:** Colab runtime disconnects happen frequently. Keep a single, self-contained recovery script that mounts Drive, initializes data pipelines, reconstructs model/optimizer, and resumes directly from the latest verified checkpoint without re-running earlier notebook cells.

---

## 6. TFLite Export

The trained Keras checkpoint (epoch-60 MobileNetV3-Large) is exported via `scripts/export_to_tflite.py`:

```bash
# Export MobileNetV3-Large @ 416×416 to float32 TFLite:
python scripts/export_to_tflite.py \
    --weights path/to/ckpt_ep60_v3.weights.h5 \
    --output  models/classcan_head_v1.tflite \
    --quant   float32
```

The export wrapper outputs a **clean 3-tensor interface** to `detector.py`:

| Output | Shape | dtype | Description |
|---|---|---|---|
| `boxes`  | `[1, 100, 4]` | float32 | `[ymin,xmin,ymax,xmax]` normalized, zero-padded |
| `scores` | `[1, 100]`    | float32 | Objectness scores, zero-padded |
| `count`  | `[1]`         | int32   | Valid detections — slice with `[:count]` |

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
  INPUT  shape=[1, 416, 416, 3]  dtype=float32
  OUTPUT shape=[1, 100, 4]        dtype=float32  name=boxes
  OUTPUT shape=[1, 100]           dtype=float32  name=scores
  OUTPUT shape=[1]                dtype=int32    name=count
```

---

## 8. Security Notice

> [!CAUTION]
> **Roboflow API Key Rotation:** If a Roboflow API key was previously pasted in plaintext into shared Colab notebooks or documents, rotate it immediately in the Roboflow workspace dashboard under Account Settings > API Keys. Never store raw API keys in version control or publicly shared notebooks.

---

## 9. Post-Training Evaluation

### 9a. Annotation Quality Audit

Manual spot-check on real training images confirmed labeling problems that are the **confirmed root cause** of weak precision/recall — not thresholds, NMS, or epoch count.

Found issues:
- Overly tight/cropped boxes on clear close-up heads (crown of head cut off)
- Unlabeled small distant heads (visible in frame, no box)
- Wildly inconsistent box tightness image-to-image
- At least one clearly visible head (red shirt, unambiguous) with no annotation at all

**Highest-confidence improvement path:** Fix annotation quality on the worst training images before any other intervention.

### 8b. NMS Threshold Sweep

9-combination objectness × IoU sweep on ~100 validation images. See `docs/benchmark_results.md` Section 6 for full table.

**Best:** `obj_threshold=0.4 / iou_threshold=0.4` — avg error 5.07, bias -10.7% (down from +35.8%).

Key insight: `obj_threshold` matters far more than IoU threshold — over-counting was mostly low-confidence false positives, not duplicate detections.

> Deployment `config.py` uses `CONF_THRESHOLD=0.35` (slightly more permissive) to recover marginal detections in quadrant shots (~10 people/shot). Revisit after exposure calibration and TFLite export.

### 8c. Formal mAP@50 Evaluation (Baseline)

IoU-matched eval on 30 validation images at `obj_threshold=0.4`. **This is the benchmark number for all comparisons.**

| Metric | Value |
|---|:---:|
| Precision | **18.7%** |
| Recall | **16.7%** |
| F1 | **17.6%** |

**Key lesson:** count-diff comparisons and single-image eyeball checks are both misleading. A model can match the count with loosely-positioned boxes and still fail mAP@50. Always use IoU-matched eval.

---

## 9. Ruled-Out Improvement Attempts

All three attempts rigorously tested and failed to beat the 18.7%/16.7% baseline.

### 9a. CrowdHuman Augmentation

1,739 dense (20+ head) images from CrowdHuman val split. Official download links dead; used HuggingFace mirror (`sshao0516/CrowdHuman`). Parsed `.odgt` format, filtered to dense images. Trained 30 then extended to 50 epochs.

Result: P=14.5% / R=16.8% / F1=**15.5%** — worse than baseline.
Root cause: street-level/event-crowd domain mismatch vs. top-down classroom shots.

### 9b. Naive Ensemble (Custom + COCO SSD + NMS)

Union of custom model + COCO MobileNetV2-SSD detections, deduplicated with NMS.

Result: P=13.7% / R=16.8% / F1=**15.1%** — worse than baseline.
Root cause: both models fail on the same hard cases (dense occluded heads), so errors compound rather than complement.

### 9c. COCO SSD Standalone

Note: box-IoU-matching a person detector against head-only ground truth is methodologically invalid (person boxes are much taller). Used count-based comparison instead.

Result: -65.2% bias (total pred 417 vs GT ~1,200 across 30 images), avg error 27.97/image.
Root cause: COCO person detector is confident on what it detects, but misses most people in dense overhead shots where 70–85% of the body is occluded.

---

## 10. Final Model Decision

**Shipping epoch-55 custom model** (`classcan_head_v1.tflite`) as the PoC detection backbone.

All three rigorously-tested improvement attempts underperformed it. The genuine difficulty of this problem (dense-overhead-classroom) means neither a fine-tuned head detector nor a mature pretrained person detector is a slam dunk — but the **quadrant architecture** (4 servo-aimed shots per sweep ≈ 10 people/shot vs. 60–90 dense) changes the actual operating regime to one where both models perform acceptably in testing.

**Ranked ideas for further improvement (if needed post-PoC):**
1. Fix annotation quality on worst training images ← highest confidence, confirmed root cause
2. Weighted/oversampling of dense/hard images during training
3. Increase input resolution to 416×416 or 512×512 (small/distant heads need more pixels)
4. Smarter ensemble (only add COCO detections that don't overlap existing custom detections)
5. Soft-NMS instead of hard-cutoff NMS
6. Heavier backbone (MobileNetV3-Large, EfficientDet-Lite0) — Pi 3B measured 0.557s at 416×416; evaluate latency budget first
