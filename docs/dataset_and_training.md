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

**Target Objective:** Train an edge-optimized vision model (**custom Keras multi-scale MobileNetV3-Large head detector** and **density-map regression model `classcan_density_v4`**) on a dedicated single **"head"** class (head-and-shoulders bounding boxes and center-point density maps) to reliably detect seated students under severe furniture occlusion from an elevated perspective.

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

| Phase | Model Type | Backbone | Input | Epochs | Best Val Loss / MAE | Best Eval | Notes |
|---|---|---|:---:|:---:|:---:|:---:|---|
| Run 1–3 (Baseline) | Box Detector | MobileNetV2 | 300×300 | 60 | 0.2519 (ep55) | F1=19.5% (ep60) | Plateaued; dense images overpredicted |
| CrowdHuman (V2) | Box Detector | MobileNetV2 | 300×300 | 50 | ~0.175 | F1=15.5% | Domain mismatch; underperformed baseline |
| V3 Full Run | Box Detector | MobileNetV3-Large | 416×416 | 60 | 0.2535 (ep60) | F1=30.1% | +10.6 pp F1 over V2; count-sweep best MAE=3.57 |
| CrowdHuman (V3) | Box Detector | MobileNetV3-Large | 416×416 | 10 | 2.93 (ep7) | F1=0.0% | Objectness collapse; experiment concluded |
| Tiled Box Model | Box Detector (2×2) | MobileNetV3-Large | 416×416 | 60 | — | F1=31.8%, MAE=3.84 | Locked-in box config (dual threshold + soft-NMS) |
| Density v4 base | Density Map | MobileNetV3-Large | 416×416 | 41 | MAE=2.13 (ep41) | r=0.9951 | SCUT-HEAD 407-img benchmark; base for fine-tuning |
| RPEE-Heads fine-tune | Density Map | MobileNetV3-Large | 416×416 | 8 | MAE=10.79 | r=0.9670 | ❌ Catastrophic negative; 0-20 MAPE=341%. Rejected. |
| **Hard-neg Round 1 (ep4)** | **Density Map** | **MobileNetV3-Large** | **416×416** | **8** | **MAE=2.35 (SCUT)** | **Real r=0.448** | **✅ ADOPTED — 176 hard-neg crops; real MAE 9.46→3.87** |
| Hard-neg Round 2 | Density Map | MobileNetV3-Large | 416×416 | 10 | MAE=2.41 (ep1) | Real r=0.410 | ❌ Not adopted; bias flipped, SCUT regression ep2 |
| Hard-neg Round 3 | Density Map | MobileNetV3-Large | 416×416 | 15 | MAE=2.81 (ep15) | Real r=0.435 | ❌ Not adopted; MAE improved but r ceiling not broken |
| Hard-neg Round 4 | Density Map | MobileNetV3-Large | 416×416 | TBD | TBD | TBD | In progress — LR raised to 5e-5 |

**Final Checkpoints:**
- Box Detection: Epoch 60 MobileNetV3-Large @ 416×416 (`val_loss=0.2535`, `train_loss=0.1498`).
- Density Map base: Epoch 41 `classcan_density_v4` (`MAE=2.13`, `r=0.9951`). File: `classcan_density_v4_best.weights.h5`.
- **Density Map adopted (shipped):** `classcan_density_v4_hardneg_ft_epoch4.weights.h5` (round 1 fine-tune, epoch 4).
  SCUT-HEAD: MAE=2.35, r=0.9908. Real footage: MAE=3.87 raw / 3.08 with threshold=0.15.
- All checkpoints on Colab Drive at `/content/drive/MyDrive/models/` (secondary Google account).

### Density-Map Regression Pipeline (`classcan_density_v4`)
Following external QA review (PeaNat), a density-map regression model was constructed to target MAE $\le 2.0$ and eliminate NMS bounding-box quantization errors:
- **Target Density Maps:** Sourced head annotations converted to continuous Gaussian density surfaces ($\sigma = 3.0$) normalized so the 2D surface integral equals exact ground-truth head count.
- **Decoder Architecture:** Progressive convolutional upsampling decoder attached to MobileNetV3-Large feature stages, outputting a 104×104 single-channel spatial density tensor (3.6M parameters).
- **Activation & Schedule:** Softplus output activation (prevents dying-ReLU collapse); warmup ($10^{-6} \to 5 \times 10^{-5}$) followed by scheduled decay (0.94/epoch to $2 \times 10^{-6}$) and instantaneous best-checkpoint persistence.

### Key Banked Lessons

> **NaN & Spike Recovery Protocol:** Any time a gradient corruption or loss spike appears:
> 1. Diagnose root cause (e.g., unconstrained box regression or pathological batch).
> 2. **ALWAYS** rebuild BOTH model AND optimizer from scratch before retrying.
> 3. Never save weights from a post-spike epoch — verify loss before persisting.

> **Consolidated Recovery Cell:** Colab runtime disconnects happen frequently. Keep a single, self-contained recovery script that mounts Drive, initializes data pipelines, reconstructs model/optimizer, and resumes directly from the latest verified checkpoint without re-running earlier notebook cells.

---

## 6. TFLite Export

### 6a. Box Detector (`classcan_head_v1.tflite`)

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

### 6b. Density-Map Regression Model (`classcan_density_float32.tflite`)

The `classcan_density_v4` Keras checkpoint is exported via `scripts/export_to_tflite.py` with `--mode density`:

```bash
# Export classcan_density_v4 to float32 TFLite (PRIMARY deployment model):
python scripts/export_to_tflite.py \
    --mode    density \
    --weights path/to/classcan_density_v4.weights.h5 \
    --output  models/classcan_density_float32.tflite \
    --quant   float32
```

**Export Status:** ✅ Confirmed working. File size: **13.77 MB** (float32). Verified running on physical Pi 3B at **702.3 ms/frame** via `ai_edge_litert`.

**Int8 export status:** ❌ Deferred. XNNPack raises "failed to prepare" at runtime due to `UpSampling2D(bilinear)` layers lacking int8 kernel support. Fix requires retraining the decoder using `Conv2DTranspose` instead — not pursued to protect the hard-won v4 checkpoint.

The density model outputs a **single-tensor interface**:

| Output | Shape | dtype | Description |
|---|---|---|---|
| `density_map` | `[1, 104, 104]` or `[1, 104, 104, 1]` | float32 | Spatial density surface; `.sum()` gives the headcount |

**Count extraction:**
```python
raw = interpreter.get_tensor(output_details[0]["index"])  # (1, 104, 104) or (1, 104, 104, 1)
density_map = np.squeeze(raw).astype(np.float32)          # → (104, 104)
headcount = max(0, round(float(density_map.sum())))
```

---

## 7. Model Signature Verification

### Box Detector (`classcan_head_v1.tflite`)

```python
from ai_edge_litert.interpreter import Interpreter

interpreter = Interpreter(model_path="models/classcan_head_v1.tflite")
interpreter.allocate_tensors()

print("--- CLASSCAN Box Detector TFLite Inspection ---")
for d in interpreter.get_input_details():
    print(f"  INPUT  shape={d['shape']}  dtype={d['dtype'].__name__}")
for d in interpreter.get_output_details():
    print(f"  OUTPUT shape={d['shape']}  dtype={d['dtype'].__name__}  name={d['name']}")
```

#### Expected Output:
```
  INPUT  shape=[1, 416, 416, 3]  dtype=float32
  OUTPUT shape=[1, 100, 4]        dtype=float32  name=boxes
  OUTPUT shape=[1, 100]           dtype=float32  name=scores
  OUTPUT shape=[1]                dtype=int32    name=count
```

### Density Model (`classcan_density_float32.tflite`)

```python
interpreter = Interpreter(model_path="models/classcan_density_float32.tflite")
interpreter.allocate_tensors()

print("--- CLASSCAN Density Model TFLite Inspection ---")
for d in interpreter.get_input_details():
    print(f"  INPUT  shape={d['shape']}  dtype={d['dtype'].__name__}")
for d in interpreter.get_output_details():
    print(f"  OUTPUT shape={d['shape']}  dtype={d['dtype'].__name__}")
```

#### Expected Output:
```
  INPUT  shape=[1, 416, 416, 3]  dtype=float32
  OUTPUT shape=[1, 104, 104, 1]  dtype=float32
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

## 10. Final Model Decisions & Deployment Architecture

### 10a. Confirmed Model Architecture Status
The AI/model engineering phase has completed 4 rounds of real-footage fine-tuning. The shipped model is:

1. **Primary / Adopted: `classcan_density_v4_hardneg_ft_epoch4`** (Hard-Negative Fine-Tune Round 1, Epoch 4)
   - **Backbone & Output:** MobileNetV3-Large + upsampling decoder producing a 104×104 density map (3.6M parameters, Softplus activation).
   - **Base model:** `classcan_density_v4_best` (SCUT-HEAD+local, MAE=2.13, r=0.9951).
   - **Fine-tune:** 8 epochs, 85%/15% original/hard-neg mix, 176 confirmed FP objects from real footage, LR=1e-5, fresh optimizer.
   - **SCUT-HEAD validation (407 images):** MAE=2.35, r=0.9908 (no catastrophic regression).
   - **Real-footage (5 clips, 117 frames):** Raw MAE=3.87 (↓59% from 9.46), r=0.448 (↑). With threshold=0.15: MAE=3.08, bias=-0.73.
   - **Operational Range Performance:** 0–20 bucket (SCUT-HEAD): MAE=0.93 people (matching the ~10 students per quadrant scan).
   - **⚠️ Deployment status:** `models/classcan_density_float32.tflite` must be regenerated from epoch4 checkpoint (currently contains old v4_best weights — app silently falls back to COCO SSD).

2. **Secondary / Box Detector (MobileNetV3-Large @ 416×416)** — HUD bounding box visualization only.
   - **Locked-in Inference Pipeline:** 2×2 grid tiled inference (0.2 overlap), dual thresholding (`full_obj=0.35`, `tile_obj=0.65`), Soft-NMS (σ=0.5, thresh=0.3).
   - **Validation Metrics:** P=31.3%, R=32.4%, **F1=31.8%**, **MAE=3.84**, **r=0.986**.

### 10b. Operational Deployment Strategy
- **Turret Scanning Context:** A 40-student classroom divided across 4 pan/tilt servo quadrants means each camera snapshot evaluates only ~10 students. The model's true deployment regime is the low-density bucket where accuracy is highest (SCUT-HEAD 0–20 bucket MAE=0.93).
- **Post-Inference Threshold:** Apply `DENSITY_THRESHOLD=0.15` (per-frame relative threshold) before summing density map. Reduces real-footage MAE 3.87 → 3.08 and near-zeroes bias. Set in `config.py`.
- **Immediate Focus Shift:** Rounds 1–3 fine-tuning complete. Round 4 (LR=5e-5) result pending. Non-model priority: export adopted checkpoint to TFLite, camera exposure/color tuning, first live camera→inference test.

### 10c. Long-Term / Post-PoC Research Avenues
1. **Round 4 result (pending):** If LR=5e-5 breaks the correlation=0.448 ceiling, adopt; otherwise declare round 1 final.
2. **sit2 clip root-cause investigation:** This clip has been the correlation drag in every round (r 0.15–0.35). Diagnosing its specific content may unlock a targeted fix.
3. **Track 2 hard-positive expansion:** Current 490 hard-positive annotations may be insufficient relative to clip diversity. Denser annotation coverage of missed heads could help correlation.
4. **Active Learning loop:** Sample real classroom video frames, annotate failures, retrain, repeat — per original PeaNat recommendation.
5. **RPEE-Heads dataset:** Confirmed negative result (MAE=10.79). Not pursued further.

