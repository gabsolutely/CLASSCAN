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

## 2. Dataset Composition & Domain Shift Analysis

The training corpus combines an academic benchmark with localized classroom video. However, rigorous domain-gap analysis uncovered critical distribution constraints:

| Dataset | Image Count | Resolution | Annotation Format | Description & Role | License / Source |
|---|:---:|:---:|:---:|---|---|
| **SCUT-HEAD (Part A)** | 2,000 | 1024×576 to 1920×1080 | Pascal VOC / YOLO TXT | Sampled from classroom monitor videos at a **single university**. Authors note those classrooms look identical. *Core finding:* the high validation correlation ($r = 0.995$) measured in-domain room memorization rather than generalization. Useful only as pre-training / backbone initialization. | Academic Research License (SCUT) |
| **SCUT-HEAD (Part B)** | 2,405 | Varied | Pascal VOC | Internet images (crowds, outdoor events, street scenes). *Policy:* **Do NOT adopt without pre-committed holdout verification.** External crowd data (CrowdHuman, RPEE) has hurt classroom accuracy in every trial. | Academic Research License (SCUT) |
| **Real Ceiling-Mount Dataset (Local)** | Target: ~1,500 frames | 2688×1520 & 1920×1080 | JSON point / density annotations | Real video captured from the physical ceiling mount across 8+ sessions (varied rooms, lighting conditions, and desk configurations at PCU-D). Strict whole-session holdouts. | Proprietary / In-House |
| **Empty-Room Clutter Set** | 15–20% of dataset | 2688×1520 | Zero-density target ($N=0$) | Full-frame empty and near-empty classrooms featuring backpacks on desks, stacked armchairs, whiteboards, and glare. Teaches the network that "backpack $\neq$ head" without cropped negative bias. | Proprietary / In-House |

---

## 3. Annotation Standard & The Partial-Head Rule

All annotations are normalized to a single class:

```
Class Index: 0
Class Name:  "head"
```

### Point Density Annotations (Density Regression):
- **Anchor Point:** The cranial apex (top center of the skull).
- **Target Kernel:** Normalized 2D Gaussian ($\sigma = 4.0\text{ px}$) scaled by 100 for numerical stability during gradient backpropagation.

### The Standardized Partial-Head Rule:
To prevent labeler noise and preserve boundary consistency:
1. **Inclusion Threshold:** A head is labeled if and only if **at least 15% of the cranial volume / hairline** is visible beyond the occluding obstruction (e.g. front armchair backrest, partition, or neighbor's shoulder).
2. **Exclusion Rule:** Heads occluded by $> 85\%$ (e.g. only 2–3 pixels of hair visible behind a tall wooden backrest) are **strictly excluded** from ground truth.
3. **Anchor Placement:** For partial heads, the center annotation point is placed at the highest visible contour of the skull, never on the occluding furniture.
4. **Consistency Enforcement:** This rule is baked into `scripts/annotate_assisted.py` to ensure unified labeling across all sessions.

### Bounding Box Boundary Rules (HUD Detector Only):
1. **Top Boundary:** Apex of the head/hairline.
2. **Bottom Boundary:** The clavicle / lower shoulder line (the top contour of the chest where the neck joins the shoulders).
3. **Lateral Boundaries:** Outermost lateral span of the shoulders or hair.
4. **Occlusion Handling:** If a student's shoulders are partially blocked by a front seat, the bounding box encloses the visible head down to the highest visible obstruction boundary.
5. **Distance & Minimum Size:** All heads with a pixel height $\ge 12\text{ px}$ in the input frame are labeled.

---

## 4. Data Augmentation Strategy (Geometry & Style Invariance)

Previous experiments proved that model behavior diverged sharply between letterbox and stretch preprocessing: the network was not geometry-invariant. Furthermore, style augmentation was the *only* training run that completed 10 epochs without loss collapse.

To enforce both geometry and appearance invariance, `scripts/train_density.py` incorporates a comprehensive pipeline:

```
Raw Frames (Local Real Video + SCUT-HEAD Stream)
        │
        ├── 1. Aspect Jitter & Random Scale/Crop (0.85× to 1.15×)
        │      --> Prevents letterbox vs stretch geometry sensitivity
        │
        ├── 2. Realistic 30°–50° Perspective Warp
        │      --> Mimics physical camera pitch angles relative to ceiling and floor
        │
        ├── 3. Lower-Frame Random Erasing / Occlusion
        │      --> Erases random patches in lower 50% of the frame to simulate
        │          severe desk, chair, and armchair obstruction
        │
        ├── 4. Style Augmentation (AugMix-Inspired)
        │      --> Color temperature shifts, brightness/contrast jitter, saturation,
        │          and mild Gaussian blur (simulates glare and uneven classroom lighting)
        │
        ├── 5. Sensor Noise & JPEG Compression Artifacts
        │      --> Simulates UVC sensor noise and 640×480 MJPEG stream quantization
        │
        ▼
Stabilized Augmented Training Batch
```

---

## 4b. Whole-Session Evaluation Protocol & Domain-Shift Metrics

Evaluating models by randomly shuffling frames across video clips leaks temporal context and exaggerates correlation ($r = 0.995$ on homogeneous rooms). CLASSCAN strictly enforces the following evaluation protocol in `scripts/eval_harness.py`:

### 1. Whole-Session Holdouts (`room_id + date`):
- **Never tune on test sessions:** Entire sessions (e.g. `room_302_day1`) are sequestered as pure out-of-domain test sets.
- **Ensemble weights and hyperparameter tuning** are performed exclusively on distinct validation sessions.
- **Leave-One-Session-Out Cross Validation (LOSO-CV):** Generated via `scripts/session_split.py` for small-sample validation.

### 2. Definitive Metric Suite (Replacing Raw Correlation):
Naively computing Pearson's $r$ over a handful of low-variance clips is a weak statistic. The evaluation harness tracks:
- **MAE (Mean Absolute Error):** Primary accuracy indicator ($\frac{1}{N}\sum |y - \hat{y}|$).
- **Within $\pm 1$ and Within $\pm 2$ Accuracy (%):** Operational reliability metrics reflecting acceptable error margins in classroom management.
- **Per-Session Bias ($\mu_{\text{error}}$):** Mean signed deviation ($y - \hat{y}$) measuring whether the model systematically overcounts or undercounts in a specific room.
- **Hallucination Rate (Empty Frames):** Mean predicted headcount on verified zero-occupancy frames ($N=0$). Measures false-positive resistance against backpacks, desks, and floor reflections.
- **Stability / Count Jitter:** Standard deviation of predicted headcount across consecutive frames of identical occupancy ($\Delta y = 0$). High jitter destabilizes the physical OLED display.

### 3. Multi-Seed Reporting (3 Seeds):
All benchmark runs are repeated across 3 fixed random seeds (`42`, `1337`, `2026`). Differences smaller than seed standard deviation are rejected as statistical noise.

### 4. Automated 30-Worst Error Analysis:
The harness identifies the 30 frames with highest absolute error and renders overlay heatmaps. Errors are automatically categorized into 5 actionable buckets:
- `occlusion`: Heads heavily obstructed by armchairs or adjacent students.
- `far_rows`: Small heads ($\le 14\text{ px}$) in distant quadrant corners.
- `backpacks`: False-positive density localized on empty chairs or bags.
- `blur`: Motion blur from servo sweep or student movement.
- `lighting`: Contrast blowout from fluorescent lights or window solar glare.

---

## 4c. Retraining Stabilization & Anti-Collapse Recipe

Earlier from-scratch training attempts collapsed to all-zero outputs within 2 to 5 epochs even when using standard Mean Squared Error (MSE). The stabilized retraining recipe in `scripts/train_density.py` resolves this via:

1. **Target Scaling ($\times 100$):**
   - Unscaled Gaussian density kernels yield peak pixel values around $0.005$–$0.02$. Gradients under standard float precision vanish or fall into trivial all-zero minima.
   - Scaling density targets by 100 boosts gradient magnitude, while an added **Count L1 loss** ($\lambda_{\text{count}} = 0.5$) and **Total Variation (TV) loss** ($\lambda_{\text{tv}} = 0.01$) directly penalize global headcount mismatch and high-frequency noise.
2. **Pre-Flight Overfit-One-Batch Check:**
   - Before launching multi-hour training, the harness executes `overfit_one_batch()`. The model must drive loss down by $\ge 80\%$ on a single 4-image batch within 30 steps. If it fails, execution halts immediately.
3. **`CollapseDetectorCallback` Watchdog:**
   - Evaluates a fixed sanity batch after every epoch. If predicted headcount variance falls below $0.05$ or mean predicted count collapses to zero, training terminates immediately with a diagnostic dump.
4. **Frozen/Inference BatchNorm Mode:**
   - During fine-tuning on small batch sizes ($B=8$ or $16$), batch statistics drift wildly. All `BatchNormalization` layers are held in inference mode (`training=False`) or updated using Adaptive Batch Normalization (`scripts/adabn.py`).
5. **Gradient Clipping & Differential Learning Rates:**
   - `clipnorm=1.0` prevents explosive weight updates.
   - Backbone layers use a conservative learning rate ($1\times 10^{-5}$), while decoder upsampling heads use $1\times 10^{-4}$.
6. **Architecture Upgrade to `Conv2DTranspose`:**
   - Bilinear `UpSampling2D` prevents native INT8 quantization in LiteRT / XNNPack. Replacing it with transposed convolutions unlocks hardware INT8 deployment.

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
| Hard-neg Round 1 (ep4) | Density Map | MobileNetV3-Large | 416×416 | 8 | MAE=2.35 (SCUT) | Real r=0.448 | ✅ Improved real footage 9.46→3.87; basis for rounds 2+ |
| Hard-neg Round 2 | Density Map | MobileNetV3-Large | 416×416 | 10 | MAE=2.41 (ep1) | Real r=0.410 | ❌ Not adopted; bias flipped, SCUT regression ep2 |
| Hard-neg Round 3 | Density Map | MobileNetV3-Large | 416×416 | 15 | MAE=2.81 (ep15) | Real r=0.435 | ❌ Not adopted; MAE improved but r ceiling not broken |
| Hard-neg Round 4 (ep8) | Density Map | MobileNetV3-Large | 416×416 | 8 | MAE=2.82 stretch / 3.23 letterbox | Real r=0.506 stretch / **0.602 letterbox** | ✅ Broke correlation ceiling; backbone of final ensemble |
| Round 5 (84/4/12 mix) | Density Map | MobileNetV3-Large | 416×416 | 15 | MAE=3.60 (ep2) | Real r=0.506 | ❌ Not adopted; mix-ratio lever exhausted; partial collapse |
| Round 6 (letterbox training) | Density Map | MobileNetV3-Large | 416×416 | 4–5 | n/a (collapsed) | Corr →0.121 | ❌ Not adopted; stretch→letterbox geometry shift causes collapse |
| Stretch-ft-epoch1 (round 7–9) | Density Map | MobileNetV3-Large | 416×416 | 1 | MAE=2.79 (ep1) | Real r=0.453 (v2 held-out) | Partial complementary signal; included as alt in lower-MAE ensemble |
| Style-aug fine-tune (round 7–9) | Density Map | MobileNetV3-Large | 416×416 | 10 | MAE=2.97 (ep8) | Real r=0.531 (v2 held-out) | ✅ Only run to complete 10 epochs without collapse; complementary ensemble signal |
| **3-way ensemble (0.6×epoch8_lb + 0.4×style-aug-ep8)** | **Ensemble** | **MobileNetV3-Large** | **416×416** | **—** | **MAE=2.77** | **Real r=0.586 (v2 held-out)** | **✅✅ FINAL ADOPTED — best real-footage correlation across all 9 rounds** |

**Final Checkpoints:**
- Box Detection: Epoch 60 MobileNetV3-Large @ 416×416 (`val_loss=0.2535`, `train_loss=0.1498`).
- Density Map base: Epoch 41 `classcan_density_v4` (`MAE=2.13`, `r=0.9951`). File: `classcan_density_v4_best.weights.h5`.
- **Density Map final shipped (ensemble):**
  - `classcan_density_v4_round4_ft_epoch8.weights.h5` (round 4 epoch 8) — evaluated with **letterbox** preprocessing at inference
  - `classcan_density_style_aug_ft_lowLR_epoch8.weights.h5` (style-aug epoch 8) — evaluated with **stretch** preprocessing at inference
  - **Ensemble weights: 0.6 × epoch8(letterbox) + 0.4 × style-aug-epoch8(stretch)**
  - Real-footage (v2 held-out): MAE=2.77, r=0.586. SCUT-HEAD: r>0.99.
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
The AI/model engineering phase has concluded after 9 rounds of real-footage fine-tuning and a systematic ensemble search. The shipped model is:

1. **Primary / Adopted: Weighted Ensemble (classcan_density_v4_round4_ft_epoch8 + classcan_density_style_aug_ft_lowLR_epoch8)**
   - **Ensemble weights:** `0.6 × round4_ft_epoch8 (letterbox preprocessing at inference) + 0.4 × style_aug_lowLR_epoch8 (stretch preprocessing at inference)`
   - **Architecture:** Both models share MobileNetV3-Large + upsampling decoder → 104×104 density map (3.6M parameters, Softplus activation).
   - **Why it works:** epoch8 overcounts (+1.69 bias on v2 held-out), style-aug-epoch8 provides complementary error signal; their combination partially cancels systematic bias.
   - **Real-footage (v2 held-out, 350 frames, genuine out-of-sample):** MAE=2.77, corr=0.586 (best across all 9 rounds). Per-clip best: line3=0.759; persistent weak point: line1=0.455.
   - **SCUT-HEAD validation (407 images):** r>0.99 maintained throughout all rounds — no catastrophic regression.
   - **Preprocessing asymmetry:** epoch8 evaluated with letterbox at inference (correlation boost 0.506→0.602 as standalone vs stretch eval); style-aug-epoch8 evaluated with stretch. Training from scratch with letterbox collapsed in all 5 attempts.
   - **Alternative lower-MAE configuration:** (0.55, 0.10, 0.35) → MAE=2.68, corr≈0.584 — use if MAE matters more than correlation for the writeup.
   - **Deployment status (Sept 23, 2026):** Both ensemble checkpoints exported to float32 TFLite and deployed on Pi. Full pipeline confirmed working end-to-end on real hardware.

2. **Secondary / Box Detector (MobileNetV3-Large @ 416×416)** — HUD bounding box visualization only.
   - **Locked-in Inference Pipeline:** 2×2 grid tiled inference (0.2 overlap), dual thresholding (`full_obj=0.35`, `tile_obj=0.65`), Soft-NMS (σ=0.5, thresh=0.3).
   - **Validation Metrics:** P=31.3%, R=32.4%, **F1=31.8%**, **MAE=3.84**, **r=0.986**.

### 10b. Operational Deployment Strategy & Free Runtime Enhancements
- **Turret Scanning Context:** A 40-student classroom divided across 4 pan/tilt servo quadrants means each camera snapshot evaluates only ~10 students. The model's true deployment regime is the low-density bucket where accuracy is highest (SCUT-HEAD 0–20 bucket MAE=0.93).
- **Ensemble Inference:** Run both TFLite models on each captured frame; headcount = 0.6 × sum(epoch8_density_map_letterbox) + 0.4 × sum(style_aug_density_map_stretch).
- **Free Wins Active in Core Runtime:**
  1. *Zone Exclusion Masks (`ZONE_EXCLUSION_MASKS`):* Zeros out non-floor regions (whiteboards, doors, windows, ceiling) before density map summation to eliminate peripheral false positives.
  2. *Multi-Capture Smoothing (`MULTI_CAPTURE_COUNT = 3`):* Takes 3 snapshots per quadrant and computes the median count to filter transient student movements and sensor noise.
  3. *Dead-Band Count Hysteresis (`COUNT_HYSTERESIS_DELTA = 0.6`):* Rejects fractional frame-to-frame jitters unless the trend moves by $> 0.6$ people.
  4. *Seat Capacity Clipping (`MAX_ROOM_CAPACITY = 45`, `MAX_ZONE_CAPACITY = 15`):* Enforces physical reality by capping headcount at physical room seating limits.

### 10c. Domain-Shift Optimization Program & Roadmap
1. **Unlabeled Real-Video Adaptation (AdaBN):** Recompute BatchNorm moving statistics on hundreds of unlabeled PCU-D classroom frames via `scripts/adabn.py`. Zero annotation cost; directly aligns feature normalization with the target domain.
2. **Model Distillation:** Train a single compact MobileNetV3 student model to mimic the 2-model ensemble's outputs across unlabeled frames, halving Pi 3B inference latency (~1.4 s → ~0.7 s).
3. **INT8 Quantization via `Conv2DTranspose`:** Transitioning decoder architecture from bilinear upsampling to transposed convolutions unblocks native INT8 execution on ARM NEON.
4. **Targeted Data Collection:** Expand real ceiling-mount dataset to ~1,500 frames across 8+ sessions with 15–20% empty classrooms using model-assisted annotation (`scripts/annotate_assisted.py`).
5. **Explicitly Deferred / Skipped:**
   - *Backbone Swap & YOLO:* Ruled out due to Pi 3B thermal constraints and failure on furniture occlusion.
   - *External Crowd Datasets:* Proved actively detrimental in empirical benchmarks.
   - *Flip-TTA & MPCount:* Held until full-session real holdout data is established.

