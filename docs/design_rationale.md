# CLASSCAN — Architectural Design Rationale & Decision Records

This document details the engineering principles, architectural trade-offs, and technical rationale underlying the hardware and software design of the CLASSCAN system.

---

## ADR-01: Operating System Selection — Raspberry Pi OS Lite (64-bit) vs. Debloated Android

### Context
Running neural network inference and computer vision pipelines on constrained single-board computers (SBCs) like the Raspberry Pi 3B requires maximizing available CPU cycles, memory bandwidth, and thermal headroom. Prior research in edge AI prototyping often explores custom debloated Android builds (e.g., LineageOS/Android Things) for lightweight execution.

### Decision
CLASSCAN deliberately standardizes on **Raspberry Pi OS Lite (64-bit Debian 13 / Trixie)**.

### Rationale & Trade-offs
1. **Zero Display-Server Overhead:**
   - Raspberry Pi OS Lite boots directly into a headless terminal environment with X11, Wayland, and desktop composite managers completely omitted.
   - Idle RAM consumption is under 55 MB (leaving >900 MB free for inference tensors and frame buffers), and background CPU utilization remains under 1%.
2. **First-Class Driver & Kernel Stability:**
   - Linux Video4Linux2 (V4L2) kernel modules provide deterministic, low-latency USB video capture (`cv2.CAP_V4L2`) for UVC cameras like the OV4689.
   - Standard POSIX TTY drivers handle reliable full-duplex USB serial communication via PySerial without proprietary Android USB-host permission dialogues.
3. **Official LiteRT / TFLite Support:**
   - Google maintains official 64-bit ARM (`aarch64`) wheels for `ai-edge-litert` (and `tflite-runtime`), enabling native NEON SIMD vectorization on the Cortex-A53 cores.
   - Android builds introduce unnecessary Hardware Abstraction Layer (HAL) complexity, binder IPC latency, and non-standard toolchains that complicate continuous maintenance for solo developers.

---

## ADR-02: Heterogeneous Dual-Tier Architecture — Pi 3B (Brain) vs. ESP32 (Hands)

### Context
The system combines heavy computational tasks (neural network inference, HTTP MJPEG streaming, frame differencing) with real-time hardware I/O (PWM servo driving, analog sensor polling, LCD2004 I2C display updates).

### Decision
Adopt a decoupled, dual-tier architecture mirroring industrial robotics:
- **Raspberry Pi 3B ("The Brain"):** Dedicated high-level computing, computer vision, networking, and decision logic.
- **ESP32 Microcontroller ("The Hands"):** Dedicated deterministic physical I/O, PWM actuation, ADC sampling, and local display management.

```
┌─────────────────────────────────────────────────────────────┐
│                   RASPBERRY PI 3B (BRAIN)                  │
│                                                             │
│  [OV4689 UVC] ──► [ChangeTrigger] ──► [TFLite Detector]    │
│                           │                    │            │
│                   [ZoneReconciler] ◄───────────┘            │
│                           │                                 │
│                   [DashboardServer] (Wi-Fi 802.11n)         │
└───────────────────────────┬─────────────────────────────────┘
                            │ USB Serial (JSON @ 115200 baud)
┌───────────────────────────▼─────────────────────────────────┐
│                     ESP32 DEVKIT (HANDS)                    │
│                                                             │
│   ├── [ServoController] ──► Pan/Tilt Servos (PWM)           │
│   ├── [LdrIllumination] ──► LDR (ADC) + White LEDs (MOSFET)│
│   └── [LcdDisplay]     ──► Local Count Display (LCD2004 I2C 20×4)  │
└─────────────────────────────────────────────────────────────┘
```

### Rationale & Trade-offs
1. **Real-Time Jitter Elimination:**
   - Software PWM on non-real-time Linux kernels is prone to scheduling jitter under heavy CPU loads (e.g., during model inference bursts), causing servo flutter and jerky camera sweeps. The ESP32's dedicated hardware PWM timers generate crystal-clean 50 Hz control pulses regardless of what the Pi is computing.
2. **Electrical Isolation & Back-EMF Protection:**
   - Servos can draw peak stall currents exceeding 800 mA, introducing voltage dips and inductive flyback spikes. Isolating servo power and control to the ESP32 tier protects the Pi's sensitive SoC from brownouts.
3. **Autonomous Failsafe Capability:**
   - The ESP32 firmware operates autonomously in a state-machine loop. If the Pi 3B reboots, drops off Wi-Fi, or crashes, the ESP32 continues sweeping the room, controlling scene illumination, and holding the last valid headcount on the LED display.
4. **Security by Isolation:**
   - The ESP32's onboard Wi-Fi radio is intentionally left uninitialized. Physical actuators cannot be addressed directly over the network; all physical commands must pass through the Pi's authenticated serial bridge.

---

## ADR-03: Vision Model Selection & Final Architecture — Custom Keras Multi-Scale MobileNetV3-Large + 416×416 Head Detector

### Context
Initial baseline testing of the computer vision pipeline utilized a standard MobileNetV2-SSD model pre-trained on the COCO dataset (80 full-body classes).

### The Decision Path (Four-Stage Evolutionary Trail)

**Stage 1 — COCO MobileNetV2-SSD fails (empirical):**
During benchmark trials on realistic classroom test photographs, the COCO model performed well on unobstructed close/medium subjects (confidence 0.72–0.98) but recorded **0 detections** on a wide-angle classroom shot with seated students behind desks.

```
Why Full-Body Models Fail in Classrooms:
┌────────────────────────────────────────────────────────┐
│ [Ceiling Camera @ 40° Angle]                           │
│        \                                               │
│         \ Visible cranial region & shoulders (15–20%)  │
│          ▼                                             │
│       [Head/Torso]                                     │
│      ══════════════ [Wooden Armchair Desk]             │
│       [Lower Body]  (80% completely occluded)          │
│└────────────────────────────────────────────────────────┘
```

**Stage 2 — YOLOLite CPU Nano (Roboflow) & TF OD API dead ends:**
Attempted a YOLOLite CPU (Nano) fine-tune on Roboflow: 92 epochs, loss plateaued at 0.1638, final mAP@50=16.6%, precision=29.1%, recall=29.0%. Roboflow free credits exhausted. Subsequent TF Object Detection API attempt in Colab failed due to `tensorflow_io` dependency incompatibilities with Colab's Python version.

**Stage 3 — From-Scratch MobileNetV2 Baseline & Plateau:**
Built a from-scratch Keras 3-scale FPN detector (300×300, P3/P4/P5). While it solved desk occlusion, evaluation plateaued at F1=19.5% (epoch 60). Three improvement hypotheses were rigorously tested and ruled out:
- *CrowdHuman augmentation:* Led to domain mismatch (F1 dropped to 15.5% on V2; collapsed to 0.0% objectness collapse on V3).
- *Naive ensemble:* Compounded false positives (F1=15.1%).
- *Annotation quality audit:* Revealed ground-truth inconsistencies as the primary precision/recall bottleneck.

**Stage 4 — Architectural Swing: MobileNetV3-Large @ 416×416:**
Hypothesized that small/distant heads lacked resolution at 300px and MobileNetV2 was too shallow. Upgraded to MobileNetV3-Large with 416×416 input resolution (grids: 52×52, 26×26, 13×13). Benchmarked inference latency on physical Pi 3B CPU: **0.557 s/frame** (XNNPACK) — confirmed fully viable for snapshot-based detection. Checkpoint at epoch 60 achieved **Precision = 35.2%, Recall = 26.3%, F1 = 30.1%** (+10.6 pp F1 over MobileNetV2 baseline).

**Stage 5 — Count-Based Calibration & Tiled Inference:**
Discovered that threshold tuning for box F1 (obj=0.30) caused an overcounting bias (+12%) in crowd counting. Swept thresholds explicitly for headcount MAE: `obj_thresh = 0.35` dropped MAE to **3.57 people** ($r = 0.987$) with near-zero count bias (-3.4%). Evaluated tiled inference (2×2 grid, 0.2 overlap, dual threshold: full pass at 0.35, tile passes at 0.65, soft-NMS) to recover small heads: achieved **F1 = 31.8%, MAE = 3.84, $r = 0.986$**. WBF and flip-TTA were tested and ruled out.

**Stage 6 — Density-Map Regression Paradigm Shift (`classcan_density_v4`):**
Following technical peer review challenging box-level assumptions in chaotic classroom environments, a continuous **density-map regression** model was designed:
- Bounding boxes artificially penalize partially occluded heads and introduce NMS suppression errors in dense seating rows.
- Converted head annotations into continuous 2D Gaussian density maps.
- Replaced the detection heads with a progressive upsampling decoder yielding a 104×104 density map with **Softplus** activation (eliminating dying-ReLU failures).
- Applied scheduled LR decay (0.94/epoch to $2 \times 10^{-6}$) and best-checkpoint tracking, reaching stable convergence across epochs 26–41.
- **Empirical Validation (407 images):** Overall **MAE = 2.13**, **$r = 0.9951$**, **MAPE = 16.1%**.
- In the actual operational regime (0–20 students per quadrant scan), **MAE is 0.93 people**.

### Final Decision
1. **Primary Headcount Architecture:** Deploy the **`classcan_density_v4` density-map regression model** (MAE = 2.13 overall, MAE = 0.93 in quadrant FOV) as the definitive occupancy counting engine.
2. **Secondary Visualization Architecture:** Maintain the **MobileNetV3-Large @ 416×416 box detector** with 2×2 dual-threshold tiling and Gaussian Soft-NMS ($\sigma=0.5, \text{thresh}=0.3$) for optional dashboard HUD bounding box rendering.

### Rationale
1. **Direct Alignment with Functional Goal:** Occupancy monitoring requires counting accuracy ($r=0.9951$, MAE < 1 person per quadrant), not arbitrary IoU box overlaps. Density maps directly integrate crowd counts while gracefully handling desk occlusions.
2. **Deterministic Edge Performance:** Both models share the lightweight MobileNetV3-Large backbone, executing within ~0.56s on Pi 3B CPU without thermal throttling under the periodic snapshot architecture.
3. **Domain Gap Realism:** Acknowledges that public dataset tuning has saturated; further optimization shifts entirely to on-site physical classroom validation. Live deployment on real hardware confirmed Sept 23, 2026 — full pipeline (Pi + OV4689 + 3-way weighted ensemble) working end-to-end on first attempt.


---

## ADR-04: Inference Triggering Strategy — Periodic Snapshot + Change Differencing vs. Continuous Live Stream Inference

### Context
Continuous live video stream inference (running 20–30 FPS real-time object detection) on a quad-core ARM Cortex-A53 CPU generates sustained 100% CPU core saturation, causing rapid thermal accumulation and aggressive CPU frequency throttling (dropping from 1.2 GHz down to 600 MHz).

### Decision
Implement a **Compute-Aware Triggering Pipeline** combining a periodic heartbeat scan with motion-triggered change detection.

```
                        ┌──────────────────┐
                        │  Capture Frame   │
                        └────────┬─────────┘
                                 │
                                 ▼
                     /───────────────────────\
                    < ESP32 State == "idle"?  >
                     \───────────────────────/
                                 │ Yes
                                 ▼
                    /─────────────────────────\
                   <  Significant Change?      >
                   <  (ratio >= CHANGE_THRESH) >
                    \─────────────────────────/
                       │ Yes               │ No
                       │                   ▼
                       │       /───────────────────────\
                       │      <  Heartbeat Interval Due?>
                       │       \───────────────────────/
                       │            │ Yes          │ No
                       ▼            ▼              │
               ┌───────────────────────────┐       │
               │ Execute TFLite Inference  │       │
               └─────────────┬─────────────┘       │
                             │                     │
                             ▼                     │
               ┌───────────────────────────┐       │
               │ Push HUD Frame & Telemetry│◄──────┘
               └───────────────────────────┘
```

### Rationale & Trade-offs
1. **Classroom Dynamics:**
   - Classrooms are predominantly static environments during lectures. Headcount changes primarily occur during arrival, dismissal, or student seat transitions.
2. **Sub-10ms Change Detection:**
   - The `ChangeTrigger` module computes a Gaussian-blurred absolute difference (`cv2.absdiff`) against the previous reference frame in ~4 ms on CPU.
   - When motion is detected (mean difference ratio $\ge 0.15$), an immediate full TFLite inference is dispatched, achieving instantaneous reaction times while maintaining idle CPU usage below 8%.
3. **Servo Motion Awareness:**
   - The Pi 3B checks the serial state reported by the ESP32. When the turret is actively executing a servo pan step (`"moving"`), change detection triggers are paused to prevent the turret's own physical movement from creating false-positive motion triggers.

---

## ADR-05: Spatial Zoning — Macro Quadrants (Q1–Q4) with Reconciliation vs. Per-Seat Micro-Tracking

### Context
Tracking individual seats requires creating dense pixel polygons for every chair in a classroom.

### Decision
Divide the classroom space into **four macro quadrants (Q1–Q4)** and enforce self-consistency reconciliation.

### Rationale & Trade-offs
1. **Robustness to In-Class Motion:**
   - Students frequently shift chairs, pull desks together, or lean into adjacent aisles. Per-seat bounding boxes result in high flicker and false "vacant/occupied" toggles. Macro quadrants absorb in-cluster shuffling as non-events.
2. **Reduced Servo Scan Cycles:**
   - A 4-quadrant scan requires only 4 discrete pan/tilt positions (e.g., $0^\circ, 60^\circ, 120^\circ, 180^\circ$ at $30^\circ$ tilt), completing a full room sweep in under 4 seconds.
3. **Self-Consistency Reconciler (`ZoneReconciler`):**
   - After completing a quadrant scan cycle, the sum of detections across Q1–Q4 is compared against the baseline full-room count. If a discrepancy exceeding the configured tolerance occurs, the system automatically triggers a verification re-scan before publishing the final headcount.

---

## ADR-06: Custom Visible LED Illumination + LDR vs. Off-The-Shelf IR Units

### Context
Low-light and evening classroom conditions degrade camera signal-to-noise ratio, leading to edge blur and dropped detections.

### Decision
Implement a custom visible-spectrum LED array controlled via an analog Light Dependent Resistor (LDR) and ESP32 ADC, rather than an active Infrared (IR) night-vision illuminator.

### Rationale & Trade-offs
1. **No IR-Cut Filter Mechanical Switching:**
   - Standard CMOS sensors require an electro-mechanical IR-Cut switch to transition between daytime color and nighttime IR monochrome modes. Inexpensive IR modules introduce mechanical failure points and chromatic aberration.
2. **Natural Visual Stream for Dashboard:**
   - Visible auxiliary lighting preserves natural color and contrast on the live MJPEG dashboard stream viewed by instructors or administrators.
3. **Closed-Loop Thresholding:**
   - The ESP32 continuously polls the LDR on ADC channel 34. Hysteresis thresholding prevents rapid oscillation near the ambient light boundary.

---

## ADR-07: LoRa Wireless Rejected — USB Serial Sufficient for Single-Room Scope

### Context
During hardware sourcing, a colleague offered LoRa modules cheaply (potentially free) as an additional wireless communication layer between the Pi and ESP32.

### Decision
LoRa was explicitly **rejected** for the current project scope.

### Rationale
1. **Single-Room Deployment:** CLASSCAN is designed as a single-room system. Pi and ESP32 are co-mounted in the same ceiling unit, communicating over USB serial at 115200 baud. There is no range problem to solve.
2. **Unnecessary Complexity:** Adding LoRa introduces an additional radio stack, additional firmware on the ESP32, and additional failure modes (signal, antenna placement, duty-cycle limits) with zero benefit for the current use case.
3. **Scope Discipline:** Adding external wireless long-range protocols introduces unnecessary complexity for single-room deployments and is explicitly deferred.

### Revisit Condition
LoRa (or equivalent LPWAN) would be worth considering if the project scope expands to multi-room or multi-building deployments where each classroom has its own CLASSCAN unit and counts need to aggregate over a building-wide network.

---

## ADR-08: TF Object Detection API / tensorflow_io — Abandoned Path

### Context
After the YOLOLite Roboflow fine-tune produced weak results (mAP@50=16.6%) and credits were exhausted, the next approach was to fine-tune the literal MobileNetV2-SSD architecture using the TensorFlow Object Detection API in Google Colab.

### Decision
This path was **abandoned** as a dead end.

### Root Cause
`tensorflow_io` — required by the TF Object Detection API's TFRecord ingestion pipeline — had no available pre-built wheel compatible with the Colab environment's Python version at the time of the attempt. Forcing an older Python version or building `tensorflow_io` from source would have introduced significant environment management overhead and Colab compatibility risks.

### Resolution
The project moved to a custom Keras/TF training pipeline (see ADR-03) that:
- Uses `tf.io.parse_single_example` and `tf.data.TFRecordDataset` directly — no `tensorflow_io` dependency
- Maintains full control over the model architecture, loss function, and target encoding
- Runs in a standard Colab GPU environment with no special Python version requirements

---

## ADR-09: Camera Frame Synchronization — V4L2 Buffer Drain via `cap.grab()` Loop

**Date:** Sept 24, 2026

### Context
After the live end-to-end pipeline was confirmed working (Sept 23, 2026), two related symptoms remained:

1. **AI operating on stale/late frames:** The density ensemble reported counts that appeared to reflect scenes from seconds earlier rather than the current live view.
2. **Perceived inference lag behind the live video stream:** The HUD stream and the AI count output seemed temporally misaligned.

### Root Cause Analysis
OpenCV (using V4L2 on Linux/Pi OS) maintains an internal ring buffer of camera frames — typically 3–4 frames deep. The camera hardware writes to this buffer continuously at the configured frame rate (e.g., 30 FPS → 1 new frame every ~33 ms) regardless of Python process activity.

TFLite inference on the Pi 3B is slow:
- Single density model: ~700 ms/frame
- Ensemble (two sequential invocations): ~1.4 s/frame

During a 1.4-second inference pass, the camera produces ~42 new frames. These all queue in the buffer. After inference, the main loop calls `cap.read()` which pops the **oldest** queued frame — not the latest one. The AI was therefore always operating on footage that was 1–2 seconds behind real time, and the mismatch worsened as inference took longer.

This is a well-known OpenCV/V4L2 issue in any application where capture and processing have asymmetric rates.

### Decision
Add `_grab_fresh_frame(cap)` — a module-level buffer-drain helper in `detector.py` — and replace every real-hardware `cap.read()` call in `capture_frame()` with it.

```python
def _grab_fresh_frame(cap) -> np.ndarray:
    grabbed = False
    for _ in range(8):        # drain up to 8 queued frames
        ok = cap.grab()       # advances DMA pointer — no pixel decode
        if not ok:
            break
        grabbed = True

    if grabbed:
        ret, frame = cap.retrieve()   # decode only the final frame
        if ret and frame is not None:
            return frame

    ret, frame = cap.read()   # fallback for edge cases
    ...
    return frame
```

`cap.grab()` is the key operation: it advances the V4L2 DMA buffer pointer and discards the frame from the queue without decoding its pixels. This makes it effectively free (microseconds per call). Only the final `cap.retrieve()` performs a JPEG decode.

### Rationale
1. **Correct-by-construction frame freshness:** Every AI inference and every HUD push now operates on the most recently captured frame, regardless of how long the previous inference took.
2. **No decode overhead for discarded frames:** `cap.grab()` without `cap.retrieve()` avoids JPEG decompression for intermediate buffer entries. Draining 8 frames costs negligible CPU.
3. **Minimal code impact:** The fix is contained entirely within `_grab_fresh_frame()`. No threading, no queue primitives, no changes to the main loop logic.
4. **Mock mode unaffected:** `_MockCapture.read()` is used directly in mock/simulation mode — it has no internal buffer concept.

### Scope
Applied to all three detector classes: `DensityDetector.capture_frame()`, `EnsembleDensityDetector.capture_frame()`, and `Detector.capture_frame()`.

### Alternatives Considered
- **Background capture thread with a `queue.Queue(maxsize=1)`:** Frames are decoded in a dedicated thread; the main loop always reads the most recent decoded frame from a 1-item queue (drop-if-full). Provides true parallel capture/inference but adds threading complexity, GIL interaction with NumPy array handoff, and thread lifecycle management — unnecessary overhead for an embedded single-board computer.
- **`cv2.CAP_PROP_BUFFERSIZE = 1`:** OpenCV exposes a property to set the V4L2 buffer size. However, on many kernel/driver versions this property is ignored or silently clamped; it cannot be relied upon across Pi OS releases. The grab-loop approach works unconditionally.
- **Reducing `LOOP_SLEEP` or restructuring the main loop:** These address symptoms (throughput) rather than the root cause (buffer staleness).

---

## ADR-10: Domain Shift & Whole-Session Evaluation Protocol

**Date:** Oct 20, 2026

### Context
Previous validation of the density-map models on SCUT-HEAD Part A showed an apparent correlation ceiling of $r = 0.995$. However, subsequent testing on real Philippine classroom footage revealed significant domain drop (MAE degraded to 9.46, correlation dropped to 0.373).
Deep analysis of SCUT-HEAD Part A revealed its true composition: 2,000 frames sampled from classroom monitor videos at a single university, whose authors noted that all rooms look virtually identical. The $r = 0.995$ figure was measuring room memorization, not genuine out-of-domain generalization. Furthermore, tuning ensemble weights across 5 short clips produced optimistic metric estimates.

### Decision
Establish a strict Whole-Session Holdout Evaluation Harness (`scripts/eval_harness.py`):
1. **Whole-Session Holdouts:** Split data strictly by session (`room_id + date`). Test sessions are sequestered and never tuned on.
2. **Definitive Metric Suite:** Replace raw Pearson correlation with:
   - MAE (Mean Absolute Error)
   - Within $\pm 1$ and Within $\pm 2$ accuracy percentages
   - Per-session signed bias ($\mu_{\text{error}}$)
   - Empty-room hallucination rate (mean predicted count on verified $N=0$ frames)
   - Stability/jitter (standard deviation across constant ground-truth frames)
3. **Multi-Seed Robustness:** Report mean $\pm$ standard deviation across 3 random seeds (42, 1337, 2026).
4. **Automated 30-Worst Error Analysis:** Automatically bucket the 30 worst frame failures into `occlusion`, `far_rows`, `backpacks`, `blur`, and `lighting`.

### Rationale
- Prevents data leakage between temporally adjacent video frames.
- Replaces brittle correlation metrics with actionable operational performance statistics.
- Directs engineering effort directly to the highest failure bucket before attempting model retraining.

---

## ADR-11: Edge Runtime Free-Win Enhancements (Zero Retraining)

**Date:** Oct 20, 2026

### Context
While model retraining requires substantial compute and annotated datasets, real-time edge deployment on the Pi 3B suffers from predictable peripheral noise, camera servo vibration, and physical constraint violations (e.g. predictions exceeding physical room capacity).

### Decision
Implement four zero-retraining runtime filters in `src/pi/config.py`, `src/pi/detection/detector.py`, and `src/pi/detection/zone_reconciler.py`:
1. **Zone Exclusion Masks:** Zero out non-floor regions (whiteboards, open doors, windows, ceiling lighting fixtures) before summing the density map.
2. **Multi-Capture Median Smoothing (`MULTI_CAPTURE_COUNT = 3`):** Capture 3 successive frames per quadrant and select the median density sum, filtering out transient motion blurs and servo vibration.
3. **Dead-Band Count Hysteresis (`COUNT_HYSTERESIS_DELTA = 0.6`):** Prevent integer display flicker on the LCD2004 screen by only updating displayed counts when moving beyond a $\pm 0.6$ person threshold.
4. **Physical Capacity Clipping (`MAX_ROOM_CAPACITY = 45`, `MAX_ZONE_CAPACITY = 15`):** Hard-clip aggregated counts to the physical number of seats installed in the room.

### Rationale
- Zero training cost or regression risk.
- Directly eliminates edge hallucinations on non-seating structures.
- Provides rock-solid temporal stability on the local ESP32 LCD2004 display and web dashboard.

---

## ADR-12: Training Dynamics Stabilization & INT8 Quantization Path

**Date:** Oct 20, 2026

### Context
Previous attempts to train density regression models from scratch collapsed to trivial all-zero outputs within 2 to 5 epochs across all loss functions (MSE, Huber). Furthermore, the existing `UpSampling2D(bilinear)` decoder layer caused XNNPack to fail during INT8 quantization, locking deployment to float32 (~700 ms per model on ARM Cortex-A53).

### Decision
Standardize the retraining pipeline in `scripts/train_density.py`:
1. **Target Scaling ($\times 100$) + Count L1 Loss:** Scale Gaussian density maps by 100 to prevent vanishing gradients, and add a composite Count L1 loss ($\lambda=0.5$) and Total Variation loss ($\lambda=0.01$).
2. **Pre-Flight Overfit Check & Collapse Watchdog:** Execute `overfit_one_batch()` before training, and monitor variance with `CollapseDetectorCallback` to abort non-viable runs at epoch 2 instead of epoch 10.
3. **Frozen BatchNorm Mode:** Set `BatchNormalization` layers to `training=False` during small-batch fine-tuning to prevent batch-statistic drift.
4. **Geometry & Occlusion Augmentation:** Enforce 30°–50° perspective warp, aspect jitter, random crop, lower-frame armchair erasing, and style jitter.
5. **Transposed Convolutions (`Conv2DTranspose`):** Offer a `Conv2DTranspose` decoder replacement to enable hardware-accelerated INT8 quantization via TFLite.

### Rationale
- Completely eliminates training collapse dynamics.
- Enforces geometry and lighting invariance directly during backpropagation.
- Establishes a verified path to ~350 ms INT8 inference on the Raspberry Pi 3B.
