# CLASSCAN — Benchmark Results & Performance Records

This document records the empirical testing results, latency benchmarks, hardware resource profiling, and the evaluation protocol for the CLASSCAN system on the Raspberry Pi 3B.

---

## 1. Baseline Vision Pipeline Validation (Smoke-Test Results)

Prior to model fine-tuning, the core edge inference pipeline (`detector.py` with LiteRT/TFLite interpreter) was evaluated on hardware using real representative test images.

### Empirical Results Table:

| Test Scenario | Ground Truth | System Count | Confidence Scores | Outcome & Detection Observations |
|---|:---:|:---:|:---:|---|
| **Scenario 1: Single Subject (Close/Medium Range)** | 1 person | 1 person | **0.72** | Clean bounding box; foreground subject clearly resolved. |
| **Scenario 2: Multi-Person Group (Seated & Standing Mix)** | 3 people | 3 people | **0.50 – 0.67** | All 3 subjects successfully localized across medium focal depth. |
| **Scenario 3: Multi-Person Foreground/Midground Scene** | 4 people | 4 people | **0.76 – 0.98** | 4/4 detected with high confidence; accurate bounding box boundaries. |
| **Scenario 4: Angled Overhead / Partial Profile** | 1 person | 1 person | **0.80** | Upper body / torso successfully detected under a tilted downward angle. |
| **Scenario 5: Distant Classroom Wide Shot (Far Rows / Desks)** | Multiple (>8) | 0 people | **< 0.50 cutoff** | **0 detections.** Model failed to resolve distant subjects occluded by wooden armchairs. |

### Technical Analysis & Justification for the Model Pivot:
1. **Pipeline Integrity Confirmed:** The underlying edge software stack (LiteRT runtime, image preprocessing, coordinate scaling, change triggering, web dashboard streaming, and serial bridging) operates deterministically on Raspberry Pi OS Lite (64-bit).
2. **Failure Analysis of Stock Full-Body Models:** The 0-detection failure in Scenario 5 proved that generic COCO models requiring full torso/leg visibility are mathematically ill-suited for classroom seating, where 80%+ of a student's body is physically blocked by desks. This empirical finding provides direct experimental justification for building a dedicated **"head"** (head-and-shoulders) class detector. The final approach taken: custom Keras multi-scale MobileNetV2 head detector (3-head FPN, occupancy-based target encoding). YOLOLite CPU Nano was trialled first (92 epochs, mAP@50=16.6%) but Roboflow credits were exhausted before it could be improved. See Section 5 for full evaluation history.

---

## 2. Hardware Resource & Latency Benchmarks (Raspberry Pi 3B)

All benchmarks measured on a **Raspberry Pi 3 Model B (1GB RAM, Quad-Core ARM Cortex-A53 @ 1.2 GHz)** running **Raspberry Pi OS Lite (64-bit Debian 13 / Trixie)**.

### Latency Profile Breakdown (Per-Frame Execution Time):

```
┌──────────────────────────────────────────────────────────────┐
│                  TOTAL FRAME CYCLE: ~260 ms                 │
│                                                              │
│  [Capture]     [Preprocess]    [TFLite Inference]     [HUD]  │
│   ~15 ms          ~8 ms             ~220 ms          ~15 ms  │
│  (V4L2 Grab)   (Resize+RGB)    (YOLOLite Nano)     (Draw+Enc)│
└──────────────────────────────────────────────────────────────┘
```

| Pipeline Stage | Module / Function | Avg. Execution Time | CPU Load Impact |
|---|---|:---:|:---:|
| **Frame Capture** | `cv2.VideoCapture.read()` (V4L2) | 12 – 18 ms | Minimal (< 3%) |
| **Change Differencing** | `ChangeTrigger.check()` (Gaussian Blur + AbsDiff) | 4 – 7 ms | Minimal (< 4%) |
| **Image Preprocessing** | `Detector._preprocess()` (Resize 320×320 + RGB convert) | 6 – 10 ms | Low (< 5%) |
| **TFLite Neural Inference** | `Interpreter.invoke()` (Quantized INT8 / Float32) | 195 – 240 ms | Burst (~50% across 4 cores) |
| **NMS & Zone Parsing** | Bounding box thresholding & Zone bucketing | 1 – 3 ms | Negligible |
| **HUD Overlay & MJPEG Encode**| `draw_hud_overlay()` + `cv2.imencode('.jpg')` | 12 – 18 ms | Low (< 8%) |
| **Serial JSON Dispatch** | `SerialBridge.send_count()` (PySerial @ 115200) | < 1 ms | Negligible |

---

## 3. System Power & Thermal Performance

| Metric | Idle State (Monitoring / Change Poll) | Active Inference Burst (Detecting) |
|---|:---:|:---:|
| **CPU Core Frequency** | 600 MHz (ondemand governor) | 1200 MHz (burst) |
| **Average CPU Utilization** | **4% – 7%** | **45% – 60%** (multi-threaded TFLite) |
| **RAM Consumption (System + App)**| **~175 MB** / 920 MB available | **~210 MB** / 920 MB available |
| **SoC Temperature (Passive Heatsink)**| $41.5^\circ\text{C} – 44.0^\circ\text{C}$ | $48.0^\circ\text{C} – 53.5^\circ\text{C}$ (No thermal throttling) |
| **Estimated Battery Life (2× 18650 Cells)**| ~6.5 – 8.0 hours | ~4.0 – 5.5 hours (periodic scan mode) |

---

## 4. Evaluation Protocol for Full-System Validation

During final classroom field trials, the system is evaluated across standard machine learning and embedded systems metrics:

### Statistical Evaluation Formulas:
$$\text{Precision} = \frac{TP}{TP + FP}, \quad \text{Recall} = \frac{TP}{TP + FN}, \quad F_1 = 2 \cdot \frac{\text{Precision} \cdot \text{Recall}}{\text{Precision} + \text{Recall}}$$

$$\text{Mean Absolute Error (MAE)} = \frac{1}{N} \sum_{i=1}^N |\text{Detected Count}_i - \text{Actual Count}_i|$$

### Field Evaluation Test Matrix:

| Test Group | Lighting Condition | Student Density | Evaluation Metric Targets |
|---|---|---|---|
| **Group A: Optimal Daylight** | Natural daylight (300–500 lux) | Low (1–10 students) | Precision $\ge 95\%$, MAE $\le 0.5$ |
| **Group B: Standard Classroom** | Fluorescent lights (150–300 lux)| Medium (11–25 students) | Precision $\ge 90\%$, MAE $\le 1.0$ |
| **Group C: High Density Seating** | Standard lighting | High (26–45 students) | Precision $\ge 85\%$, MAE $\le 2.0$ |
| **Group D: Dim / Evening** | Low ambient (< 100 lux) + LED Module | Variable | Precision $\ge 85\%$, MAE $\le 1.5$ |

---

## 5. Custom CLASSCAN Head Detector — Inference Results

Results for the trained Keras multi-scale MobileNetV2 head detector.
Best checkpoint: **epoch 55** (box_loss_weight=2.0 phase, Drive-verified).

### 5a. YOLOLite Nano Intermediate Result (Roboflow, Abandoned)

| Metric | Value | Notes |
|---|:---:|---|
| Training epochs | 92 | Loss plateaued at 0.1638 |
| mAP@50 | **16.6%** | Non-zero but weak |
| Precision | 29.1% | |
| Recall | 29.0% | |
| Outcome | **Abandoned** | Roboflow credits exhausted; not enough to retry |

---

### 5b. Epoch-50 Inference + NMS Check (box_loss_weight=1.0)

Test image: validation sample with 13 ground-truth head boxes.
Threshold: objectness ≥ 0.35, NMS IoU ≤ 0.45.

| Metric | Value |
|---|:---:|
| Ground truth boxes | 13 |
| Raw model predictions | 13 |
| After NMS | **13** |
| Count match | **✅ Exact (13/13)** |
| Confidence scores | ~0.38–0.49 range |
| Box tightness | Somewhat loose/offset vs. ground truth |
| Duplicate suppression | No duplicates to suppress (NMS clean) |

**Observation:** Model has learned to cluster predictions on the real group of people
(correctly ignoring empty chairs). Box tightness is loose and offset from ground truth —
expected at this training stage with box_loss_weight=1.0.

---

### 5c. Epoch-55 Inference + NMS Check (box_loss_weight=2.0)

Same test image, same thresholds. Continuing from epoch-50 with box_loss_weight bumped to 2.0.

| Metric | Value | Δ vs. Epoch-50 |
|---|:---:|:---:|
| Ground truth boxes | 13 | — |
| Raw model predictions | 13 | Same |
| After NMS | **13** | Same |
| Count match | **✅ Exact (13/13)** | Same |
| val_loss at epoch 55 | 0.2519 | ↓ from 0.2564 (marginal improvement) |
| Box tightness | Improved — boxes closer to GT boundaries | ✅ Better |
| val_loss by epoch 60 | 0.2531 (rising) | Plateau confirmed |

**Epoch 55 is the best checkpoint.** val_loss bottomed at epoch 55 and started rising by
epoch 60 — plateau reached. No benefit to additional training epochs.

**Box tightness assessment:** The box_loss_weight=2.0 bump produced a visible improvement
in box regression at epoch 55 vs. epoch 50 — bounding boxes are closer to ground-truth
head boundaries. Confidence scores remain in the ~0.4 range, which is expected from focal
loss's conservative bias (threshold of 0.35 is appropriate for deployment).

---

### 5d. Training Loss Convergence Summary

| Epoch | train_loss | val_loss | Notes |
|:---:|:---:|:---:|---|
| 1 | 3.2571 | 1.1443 | Start (from scratch, run 2) |
| 10 | — | — | Smooth decrease throughout |
| 30 | 0.2524 | 0.2687 | Run 2 end — val still decreasing |
| 50 | 0.2239 | 0.2564 | Val plateau (~ep47-50) |
| 55 | 0.2115 | **0.2519** | ← **Best checkpoint** (box_loss_weight=2.0) |
| 60 | — | 0.2531 | Val rising — overfitting signal, stopped |

---

### 5e. Live Camera Results (OV4689 — Bring-Up Status)

OV4689 camera **is in hand and confirmed functional** at `/dev/video0` (MJPG up to 2688×1520@30fps, YUYV also available).

| Test | Status | Notes |
|---|---|---|
| Camera enumeration (`camera_verify.py --camera-only`) | ✅ **Done** | Confirmed at `/dev/video0` |
| Exposure / gain calibration | ⚠️ **In progress** | Default auto-exposure underexposes badly. Manual (auto_exposure=1, exposure_time=500, gain=100) still too dark. Next: try exposure_time up to max 2047 and/or higher gain. |
| First live frame → TFLite inference (end-to-end test) | ❌ **Not yet done** | Blocked on exposure calibration + `classcan_head_v1.tflite` export |
| Single student — PCU-D classroom | ❌ **Pending** | — |
| Full class (seated, fluorescent) | ❌ **Pending** | — |

---

## 6. NMS Threshold Sweep — Custom Head Detector

Ran a 9-combination objectness × IoU threshold sweep on ~100 validation images to address over-counting in dense shots.

**Observation before sweep:** Sparse images (few ground-truth heads) were accurate. Dense images (60–90+ GT heads) over-predicted by 30–50%. Root cause: low-confidence false positives, not duplicate detections — `obj_threshold` matters far more than IoU threshold.

| obj_threshold | iou_threshold | Avg Abs Error | Avg Bias |
|:---:|:---:|:---:|:---:|
| 0.3 | 0.3 | 7.21 | +24.1% |
| 0.3 | 0.4 | 6.98 | +21.3% |
| 0.3 | 0.5 | 6.74 | +19.8% |
| 0.4 | 0.3 | 5.31 | -8.9% |
| **0.4** | **0.4** | **5.07** | **-10.7%** |
| 0.4 | 0.5 | 5.14 | -11.2% |
| 0.5 | 0.3 | 6.02 | -18.4% |
| 0.5 | 0.4 | 6.15 | -19.1% |
| 0.5 | 0.5 | 6.22 | -19.7% |

**Best:** `obj_threshold=0.4 / iou_threshold=0.4` — avg error 5.07, bias -10.7% (down from +35.8% at default thresholds).

> **Note:** Deployment `config.py` uses `CONF_THRESHOLD=0.35` (slightly more permissive than eval best of 0.4) to recover marginal detections in quadrant shots with ~10 people. Revisit after exposure calibration.

---

## 7. Formal mAP\@50 Evaluation — Custom Head Detector (Baseline)

IoU-matched precision/recall eval on 30 validation images. `obj_threshold=0.4`, IoU matching threshold=0.5 (standard mAP@50).

| Metric | Value |
|---|:---:|
| Eval images | 30 |
| Total ground-truth heads | ~1,200 |
| Precision | **18.7%** |
| Recall | **16.7%** |
| F1 | **17.6%** |

**This is the benchmark number for all subsequent comparisons.**

Key finding: count-diff comparisons and single-image eyeball checks are both misleading. A model can get the right number of boxes in roughly the right area while failing strict IoU-overlap matching — exactly what persistent loose/offset box tightness was signaling.

**Annotation quality spot-check finding (confirmed root cause of weak P/R):**
- Overly tight/cropped boxes on clear close-up heads (missing crown area)
- Unlabeled small distant heads
- Wildly inconsistent box tightness image-to-image
- At least one clearly visible head (red shirt) with no box at all

---

## 8. Ruled-Out Improvement Attempts

All three attempts rigorously tested; all failed to beat the 18.7%/16.7% baseline.

### 8a. CrowdHuman Augmentation

Added 1,739 dense (20+ head) images from CrowdHuman val split (official crowdhuman.org links were dead; used HuggingFace mirror `sshao0516/CrowdHuman`). Trained 30 then extended to 50 epochs to rule out undertraining.

| Metric | Value | vs. Baseline |
|---|:---:|:---:|
| Best threshold combo | obj=0.3, iou=0.3 | — |
| Precision | 14.5% | ↓ -4.2pp |
| Recall | 16.8% | ↑ +0.1pp |
| F1 | **15.5%** | ↓ worse |
| val_loss trajectory | Improved to ~0.175–0.177 (no plateau at 50 ep) | — |

**Root cause of failure:** CrowdHuman is street-level / event-crowd photography — genuine domain mismatch vs. top-down classroom shots. Augmenting with mismatched-domain data diluted rather than reinforced the model.

### 8b. Naive Ensemble (Custom + COCO SSD + NMS)

Union of custom model detections + stock COCO MobileNetV2-SSD detections, deduplicated with NMS.

| Metric | Value | vs. Baseline |
|---|:---:|:---:|
| Precision | 13.7% | ↓ worse |
| Recall | 16.8% | ↑ marginal |
| F1 | **15.1%** | ↓ worse |

**Root cause:** Both models struggle on the same dense/occluded-head difficulty, so errors compound (more false positives) rather than complementing each other.

### 8c. COCO SSD Standalone (Count-Based Comparison)

Methodology note: box-IoU-matching a person detector against head-only ground truth is invalid (person boxes are much taller). Used count-based comparison instead.

| Metric | Value |
|---|:---:|
| Eval images | 30 |
| Total ground-truth heads | ~1,200 |
| Total predicted (person count) | 417 |
| Avg absolute error / image | 27.97 |
| Overall bias | **-65.2%** (massive undercount) |

**Root cause:** COCO person detector is confident on people it *does* detect, but misses most people in dense overhead classroom shots where 70–85% of body is desk-occluded.

---

## 9. Architecture Speed Benchmark — MobileNetV3-Large @ 416×416 (Pi 3B)

Pure architecture speed test (random/untrained weights) to evaluate the cost of a resolution + backbone upgrade before committing.

| Model | Input Resolution | Inference Time (avg, 5 warmup iters) | Delegate |
|---|:---:|:---:|:---:|
| MobileNetV3-Large (arch test) | 416×416 | **0.557 s** | XNNPACK |
| Current custom model (MobileNetV2, trained) | 300×300 | **~0.22 s** | TFLite default |

Measured on physical Pi 3B CPU using `ai_edge_litert.interpreter`. Real hardware-verified number — not a Colab/GPU estimate.

**Decision pending:** At 0.557s/inference × 4 quadrants, a full sweep cycle would be ~2.2s + servo move time. Evaluate whether that latency is acceptable for the periodic-snapshot architecture before pursuing resolution/backbone bump.

