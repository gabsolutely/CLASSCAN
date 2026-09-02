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
2. **Failure Analysis of Stock Full-Body Models:** The 0-detection failure in Scenario 5 proved that generic COCO models requiring full torso/leg visibility are mathematically ill-suited for classroom seating, where 80%+ of a student's body is physically blocked by desks. This empirical finding provides direct experimental justification for fine-tuning **YOLOLite CPU (Nano)** on a dedicated **"head"** (head-and-shoulders) class.

---

## 2. Hardware Resource & Latency Benchmarks (Raspberry Pi 3B)

All benchmarks measured on a **Raspberry Pi 3 Model B (1GB RAM, Quad-Core ARM Cortex-A53 @ 1.2 GHz)** running **Raspberry Pi OS Lite (64-bit Debian Bookworm)**.

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
