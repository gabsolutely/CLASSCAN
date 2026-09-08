# CLASSCAN
**Development of an Intelligent Classroom Headcount Monitoring System using Computer Vision and LED Display Technology**

A ceiling-mounted smart camera turret that automatically detects and counts people in a classroom in real time, displaying the live headcount on an LED display and a wireless laptop dashboard — no manual attendance checking, no facial recognition, just occupancy (and optionally, seat-zone presence).

**Status:** Core software pipeline operational and bench-tested. Raspberry Pi 3B is in hand and running on **Raspberry Pi OS Lite (64-bit)**. Final detection model: **custom Keras MobileNetV3-Large + 416×416 head detector** (SCUT-HEAD + 35 local images, epoch-60 checkpoint) — P=35.2% / R=26.3% / F1=30.1% with soft-NMS (σ=0.5 / t=0.3, obj_thresh=0.4). TFLite export and camera exposure calibration are the two remaining PoC steps before end-to-end integration.

---

## The Problem

Most schools still rely on manual headcount and attendance checking — slow, error-prone, and unhelpful in situations like emergencies or class transitions where a fast, accurate room count actually matters. CLASSCAN automates this using computer vision and a real-time display, without collecting any identifying information about students.

## What It Does

- Detects and counts people in a classroom using periodic snapshot detection, with immediate re-detection triggered by significant frame change (avoids the compute cost of continuous live-stream inference, which struggled even on stronger boards per community precedent)
- Displays the current headcount on an LED display in real time
- Switchable camera behavior: continuous room-wide sweep for general occupancy, or targeted sequential quadrant/seat positioning (servo points at each calibrated position) for verified per-zone vacant/occupied status
- Quadrant-based zone detection (not per-seat) to shrink blind-spot windows, reduce inference load, and absorb in-quadrant seat shuffling as a non-event; includes a self-consistency check that re-scans if per-quadrant counts don't reconcile with the expected total, rather than trusting a single pass blindly
- Streams count + periodic snapshot images to a wireless laptop dashboard; dashboard can also send commands (e.g. mode switch, check specific zone) back to the turret
- Custom LDR-triggered illumination module (own-built, not a packaged IR unit) — brightens the scene automatically in dim/evening conditions
- Uses pan/tilt servos to sweep the room for wider coverage from a single ceiling-mounted unit
- Runs on swappable battery power for flexible testing across rooms
- Keeps functioning locally (sweep, lighting, LED count) even if Wi-Fi or the dashboard goes down

## What It Does NOT Do

- No facial recognition
- No individual student identification
- No attendance logging by name
- Not a security/surveillance system — occupancy and seat-zone presence only

---

## System Architecture

```
[Camera — OV4689 BSI USB module] → [Raspberry Pi 3B — Raspberry Pi OS Lite (64-bit) + TFLite inference (custom MobileNetV3-Large+416 head detector)]
                    │
                    ├──◄► Onboard Wi-Fi ◄►  [Laptop Dashboard]
                    │      (count + snapshots out;    (data in;
                    │       commands in)                commands out)
                    │
                    └──◄► USB Serial ──◄► [ESP32]
                                                    │
                                                    ├──► Servo PWM (sweep or quadrant-targeted positioning)
                                                    ├──► LDR read → custom illumination LED module
                                                    └──► LED Matrix Display (local headcount)
```

Commands from the dashboard (e.g. "switch to zone-check mode", "check quadrant 2") travel laptop → Pi 3B over Wi-Fi, and the Pi 3B translates/forwards them to the ESP32 over USB serial. The ESP32 never connects to the network directly — it only receives serial commands from the Pi 3B, keeping physical control fully isolated from networking. Before commanding a servo move or illumination change, the Pi 3B expects an ESP32 state acknowledgment (idle/moving) so the change-detection trigger doesn't mistake the turret's own motion or lighting for a person entering/leaving.

### Division of Labor

**Raspberry Pi 3B — the brain.** Runs headless **Raspberry Pi OS Lite (64-bit)**. The quad-core Cortex-A53 CPU is dedicated to running TFLite inference (`ai-edge-litert`), change detection, and communication bridging. Live continuous-stream inference is treated as a known risk; CLASSCAN instead defaults to periodic snapshot detection with immediate re-trigger on significant frame change, cutting sustained compute load. Detection model: **custom Keras MobileNetV3-Large + 416×416 head detector** (3-scale FPN, focal loss + smooth-L1, occupancy-based target encoding) trained on SCUT-HEAD Part A (2,000 images) + 35 local Philippine classroom images. Epoch-60 checkpoint benchmarked at **0.557 s/frame on Pi 3B CPU** (XNNPACK backend) — acceptable for the periodic-snapshot use case. Soft-NMS (σ=0.5 / t=0.3) applied post-inference. Handles all networking directly (count/snapshots to laptop, commands from laptop) via onboard Wi-Fi. Talks to the ESP32 over USB serial — translates dashboard commands into serial messages and relays headcount/status back.

**ESP32 — the hands.** Fully isolated from networking (its Wi-Fi radio is unused by design — networking stays on the Pi 3B); handles physical I/O only: servo positioning (sweep or quadrant-targeted), LDR-triggered custom illumination module, and driving the LED matrix. Receives commands only via USB serial from the Pi 3B — never connects to the network directly. Runs autonomously in default sweep mode — sweep and lighting logic continue even if the network or laptop dashboard drops. Reports its own state (idle/moving) back over serial so the Pi 3B's change-detection trigger can distinguish the turret's own motion from an actual change in the room. Supports a calibrated quadrant/seat pan-tilt lookup table for targeted mode, switchable with general sweep mode via dashboard command.

**Laptop Dashboard — the display.** Receives headcount and periodic snapshots over Wi-Fi from the Pi 3B, and presents a real-time monitoring view. Can send mode-switch and zone-check commands back to the turret.

### Design Rationale & OS Decision

- **Operating System Selection (Debloated Android vs. Raspberry Pi OS Lite 64-bit):** An ultra-lean Android build was initially evaluated based on prior SBC edge AI precedent. However, after technical assessment against project timelines and solo-development maintenance constraints, **Raspberry Pi OS Lite (64-bit)** was deliberately adopted. Raspberry Pi OS Lite provides a headless, low-overhead Linux environment with zero display-server burden, first-class V4L2/UVC camera stability, native PySerial support, and official LiteRT/TFLite wheels — avoiding Android HAL and driver maintenance risks without sacrificing inference efficiency.
- **Model Selection & Pivot Rationale:** Baseline tests with a stock MobileNetV2-SSD full-body model confirmed the pipeline works but produced 0 detections on far-row classroom seating (armchair occlusion, steep ceiling angle). Three improvement paths were tried and ruled out before the final model: (a) CrowdHuman-augmented V2 — worse across both V2 and V3 architectures (objectness collapse under extreme head density); (b) naive ensemble (custom + COCO SSD) — compounded false positives rather than catching complementary true positives; (c) extended training alone — diminishing returns past plateau. Final model: **custom Keras MobileNetV3-Large + 416×416 FPN head detector** (3 detection scales: 52×52 / 26×26 / 13×13, focal loss + smooth-L1, soft-NMS σ=0.5 / threshold=0.3). Epoch-60 (F1=30.1%) decisively outperforms the previous MobileNetV2+300 best (F1=19.5%) on the same IoU-matched eval. See `docs/design_rationale.md` ADR-03.
- **Compute-aware detection strategy:** periodic snapshot + change-triggered re-detection (rather than continuous live inference) keeps sustained CPU load low on hardware known to struggle with live detection, while still responding immediately when something actually changes.
- **Quadrant-based zoning with self-consistency checking:** dividing the room into quadrants (rather than per-seat zones) shortens the full-scan cycle and blind-spot window, absorbs in-quadrant seat shuffling as a non-event, and cuts inference calls per cycle. A reconciliation check flags and re-scans when per-quadrant counts don't add up to the expected total, rather than silently trusting a possibly-stale scan.
- **Reduced hardware risk:** onboard Wi-Fi and Bluetooth on the Pi 3B eliminate the USB Wi-Fi dongle chipset-compatibility risk present in earlier alternative SBC paths.
- **Isolating core operations:** physical safety/monitoring functions (sweep, lighting, local display) live entirely on the ESP32 and do not depend on network or dashboard uptime.
- **Industrial systems design pattern:** separating the AI/logic engine (Pi 3B) from the physical actuator controller (ESP32) mirrors standard practice in commercial robotics and automation, avoiding processing delays and single points of failure.
- **Privacy-by-design:** zone presence is computed from bounding-box position relative to a predefined quadrant/zone, not identity — no recognition or student-specific data is ever produced or stored. Per-zone status reflects the most recent scan, not a continuous real-time truth — an intentional, honestly-scoped limitation of any single-camera scanning system.

---

## Progress & Validated Benchmarks (The Pivot Justification)

Initial smoke-testing of the software pipeline (`detector.py` with LiteRT/TFLite interpreter) evaluated a stock quantized MobileNetV2-SSD model across real representative test scenes:

| Test Scenario | Ground Truth | Detected | Confidence Scores | Outcome & Observations |
|---|---|---|---|---|
| **Single Subject (Close/Medium Range)** | 1 person | 1 person | **0.72** | Clean bounding box; person clearly resolved in foreground. |
| **Multi-Person Group (Seated & Standing Mix)** | 3 people | 3 people | **0.50 – 0.67** | All 3 subjects detected successfully across medium depth. |
| **Multi-Person Foreground/Midground Scene** | 4 people | 4 people | **0.76 – 0.98** | 4/4 detected with high confidence; accurate bounding boxes. |
| **Angled Overhead / Partial Profile** | 1 person | 1 person | **0.80** | Successfully detected upper body / torso under tilted angle. |
| **Distant Classroom Wide Shot (Far Rows / Desks)** | Multiple | 0 people | **N/A (< 0.50 cutoff)** | **0 detections.** Model completely failed to resolve distant subjects occluded by desks. |

### What These Results Proved & Why We Pivoted
1. **Pipeline Validation:** The underlying software stack (LiteRT runtime, preprocessing, coordinate scaling, change triggering, and dashboard server) is fully functional on hardware.
2. **Methodology Justification for Model Swap:** While the stock full-body model succeeded on close and unobstructed subjects (0.50–0.98 confidence), it broke down completely (0 detections) on the distant classroom shot where students were seated behind armchairs. Stock full-body models require torso/limb cues that are physically occluded in classroom seating.
3. **The Solution:** Rather than relying on generic full-body COCO weights, we pivoted to **YOLOLite CPU (Nano)** fine-tuned specifically for a single **"head"** (head-and-shoulders) class on elevated classroom datasets.

---

## Dataset, Model Architecture & Training

### Final Model — MobileNetV3-Large + 416×416 FPN Head Detector

1. **Architecture:**
   - **Backbone:** MobileNetV3-Large (ImageNet-pretrained), feature extraction tapped at strides /8, /16, /32.
   - **Detection Heads:** 3-scale feature pyramid (52×52, 26×26, 13×13 grids for 416-px input), each predicting objectness + 4 box offsets per cell.
   - **Loss:** Focal loss (objectness) + Smooth-L1 (box regression). Occupancy-based target-cell overflow routing (not size-gated).
   - **Inference hardening:** Box-prediction clipping (±8.0) to prevent Huber-loss blowup on dense images; 5-epoch linear LR warmup (1e-5 → 1e-4); spike guard halts checkpoint save if val_loss jumps >20× vs. last good epoch.
2. **Training Datasets:**
   - **SCUT-HEAD Part A (2,000 Images):** Dense classroom/indoor surveillance head-detection benchmark (academic-research-use license, sourced from HCIILAB GitHub).
   - **Local Classroom Dataset (35 Images):** Philippine public school classrooms at realistic ceiling pitch angles (**30°–50°**), covering local wooden armchairs, fluorescent/sunlight variations, and high student density. Annotated by hand.
3. **Labeling Convention:** Single **"head"** class with head-and-shoulders bounding boxes — ensures detection even when 80%+ of body is occluded by furniture.
4. **Final Checkpoint:** Epoch-60 (val_loss 0.2535, train_loss 0.1498). Trained in Colab (T4 GPU). Soft-NMS applied at inference (σ=0.5, threshold=0.3, obj_thresh=0.4).
5. **Eval Result (IoU-matched mAP@50, 30 val images):** **P=35.2% / R=26.3% / F1=30.1%**.
6. **Deployment Target:** Float32 TFLite (`.tflite`) via `scripts/export_to_tflite.py`. Pi 3B CPU benchmark: **0.557 s/frame** (XNNPACK backend) — viable for periodic-snapshot use case.

### Ruled-Out Approaches (documented negative results)

| Attempt | Result | Reason Ruled Out |
|---|---|---|
| CrowdHuman augmentation (V2 + V3 architectures) | Worse than baseline in all configs; V3 version collapsed to 0% P/R (objectness collapse) | Extreme head-density imbalance in CrowdHuman destabilizes objectness head; domain mismatch |
| Naive ensemble (custom + COCO SSD) | P=13.7% / R=16.8% / F1=15.1% — worse than either alone | Union compounds false positives; both models fail on same hard cases |
| COCO SSD MobileNetV2 standalone | −65.2% bias, avg error 27.97/image | Full-body model cannot resolve occluded seated students |
| YOLOLite Nano fine-tune (Roboflow/Colab) | Plateaued at mAP@50=16.6% | TF OD API tensorflow_io build unavailable for Colab Python version; credits exhausted |

---

## Known Limitations & Open Items

- **Model Precision/Recall:** F1=30.1% at epoch-60 is a genuine improvement but not production-grade. Primary root cause is annotation-quality variance in the training set (overly-tight/inconsistent boxes, unlabeled distant heads). Further improvement would require a systematic re-annotation pass — explicitly deferred post-PoC.
- **Camera Exposure Calibration:** OV4689 camera is live at `/dev/video0` but exposure tuning is in progress. 11-shot sweep (exposure 25–1800, gain=32, 1280×720/MJPG) was captured on Pi; visual selection of best exposure value + gain sweep are pending before live end-to-end test.
- **TFLite Export:** Epoch-60 checkpoint not yet exported. Blocked until training account's Drive is accessible (`/content/drive/MyDrive/models/` on the new Colab account).
- **Single-Camera Blind Spots:** By design, a sweeping turret observes one field of view at a time. Zone-occupancy reflects the latest quadrant scan rather than continuous instantaneous truth — handled via change-triggered re-scans and reconciler consistency checks. An intentional, honestly-scoped limitation.
- **Roboflow API Key:** Was accidentally exposed in a shared notebook; must be rotated in the Roboflow dashboard before any further Roboflow API use.

---

## Hardware Bill of Materials (BOM) Summary

| Component | Status / Purpose |
|---|---|
| Raspberry Pi 3B (1GB RAM) | **In hand & running** — Main compute: Raspberry Pi OS Lite (64-bit) + TFLite inference; onboard Wi-Fi + Bluetooth |
| ESP32 | **In hand** — Physical I/O controller: servos, LDR, illumination, LED matrix, USB serial link to Pi 3B |
| OV4689 4MP BSI USB Camera Module (UVC, Type-C/A) | **In hand & connected** — Video feed for detection: back-side-illuminated sensor for improved performance in dim/evening classroom lighting, standard driverless UVC interface |
| Light Sensor (LDR) | **In hand** — Detects ambient brightness, triggers illumination module |
| Custom illumination LED module (self-built, LDR-triggered) | **In development** — Brightens scene in dim conditions: built in-house rather than a packaged IR unit, driven by the ESP32 |
| Pan/Tilt Servos (MG90S x2) | **In hand** — Rotates the turret to sweep or target quadrants |
| LED Matrix Display | **In hand** — Shows live headcount locally |
| 18650 Battery + Charging Module | **In hand** — Swappable, untethered power |
| 3D-Printed Dome Enclosure | **In design** — Houses all components, ceiling-mounted (Pi running in acrylic case + active fan) |

Full itemized BOM and cost breakdown: see [`docs/bom.md`](docs/bom.md).

**Current Progress & Open Items:**
- [x] **Compute & OS:** Raspberry Pi 3B running headless Raspberry Pi OS Lite (64-bit, Trixie) with all dependencies (`ai-edge-litert`, OpenCV, NumPy, PySerial) in acrylic case with active cooling fan (GPIO Pins 4/6); Wi-Fi hardened (power-save disabled via `wifi-powersave-off.service`, cron watchdog `wifi-watchdog.sh` for auto-recovery).
- [x] **Inference Pipeline:** Core `Detector` implementation verified on hardware; inference execution confirmed working on real test images (23/23 unit tests pass).
- [x] **Logic & Communications:** `ChangeTrigger`, `ZoneReconciler`, `DashboardServer`, and serial bridge modules implemented and unit tested.
- [x] **Custom Model Training:** Final model — **Keras MobileNetV3-Large + 416×416 FPN head detector** trained to epoch 60 (P=35.2% / R=26.3% / F1=30.1%, soft-NMS σ=0.5/t=0.3). Epoch-60 checkpoint on Colab Drive (`/content/drive/MyDrive/models/`).
- [x] **Eval & Model Selection:** 9 threshold combos swept; formal IoU-matched mAP@50 eval on 30 val images; 3 improvement attempts benchmarked and ruled out (CrowdHuman augment, ensemble, COCO standalone). V3+416 epoch-60 confirmed best.
- [x] **Physical Camera Integration:** OV4689 detected at `/dev/video0` (MJPG up to 2688×1520@30fps); 11-shot exposure sweep captured on Pi (exposure 25–1800, gain=32, 1280×720).
- [ ] **Camera Exposure Calibration:** Visual review of exposure sweep → pick optimal value → gain sweep at that setting → commit V4L2 config.
- [ ] **TFLite Model Export:** Export epoch-60 V3+416 weights to `models/classcan_head_v1.tflite` via `scripts/export_to_tflite.py`.
- [ ] **Live End-to-End Camera Test:** OV4689 frame → TFLite inference → headcount on Pi (first real live run).
- [ ] **Illumination Module:** Finalize circuit design (LED array, driver transistor, LDR threshold) and wire to ESP32 ADC/GPIO.
- [ ] **Turret & Quadrant Calibration:** Calibrate pan/tilt servo angles for Quadrants 1–4 once mounted in dome enclosure.
- [ ] **Full-System Benchmarking:** Record end-to-end latency, temperature, and detection accuracy under live classroom lighting.

---

## How It Works

```
ESP32 loop (autonomous, runs independent of network):
    read LDR
    if dim: enable illumination module
    else: illumination off

    if mode == SWEEP:
        continuously sweep servos through pan/tilt pattern
    if mode == ZONE_CHECK:
        step through calibrated quadrant lookup table,
        report "moving" then "idle" over serial at each step,
        hold briefly at each position for Pi 3B to detect

    if command received via serial: update mode / move to specific quadrant
    if new headcount received via serial: update LED matrix

Pi 3B loop:
    capture camera frame
    if ESP32 reports "idle" and frame differs significantly from last checked frame:
        run TFLite (MobileNetV3-Large+416 custom head detector) inference immediately
    else:
        run detection on regular heartbeat interval instead
    apply soft-NMS (σ=0.5, threshold=0.3, obj_thresh=0.4) to raw detections
    count detections per zone; sum and compare against last full-cycle total
    if counts don't reconcile: re-scan before reporting
    send headcount/status → ESP32 (USB serial)
    send count + snapshot → laptop dashboard (Wi-Fi)
    if command received from dashboard (Wi-Fi): forward to ESP32 (USB serial)
```

---

## Repository Structure

```
├── models/             → TFLite model files (classcan_head_v1.tflite — pending export from epoch-60 checkpoint)
├── src/
│   ├── pi/             → Raspberry Pi 3B core codebase
│   │   ├── detection/  → detector.py, change_trigger.py, zone_reconciler.py
│   │   ├── comms/      → dashboard_server.py, serial bridge
│   │   ├── config.py   → Deployment constants, thresholds, zone coordinates
│   │   └── main.py     → Main execution loop & system coordinator
│   ├── esp32/          → ESP32 firmware (servo control, LDR illumination, LED matrix)
│   └── dashboard/      → Laptop web/client monitoring interface
├── scripts/            → Hardware & inference smoke-test scripts (run_on_image.py)
├── tests/              → Automated pytest test suite
├── docs/               → System boundaries, design rationales, and BOM
├── hardware/           → Schematics, wiring diagrams, pinouts
└── cad/                → 3D-printable dome enclosure design files
```

## Academic Context

This is a capstone project developed at Philippine Christian University – Dasmariñas (PCU-D).

---

This README is updated continuously as the physical integration and hardware assembly progress.
