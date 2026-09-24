# CLASSCAN
**Development of an Intelligent Classroom Headcount Monitoring System using Computer Vision and LED Display Technology**

A ceiling-mounted smart camera turret that automatically detects and counts people in a classroom in real time, displaying the live headcount on an LED display and a wireless laptop dashboard — no manual attendance checking, no facial recognition, just occupancy (and optionally, seat-zone presence).

### __WORK IN PROGRESS, ACTIVELY CHANGING__

**Status (Sept 24, 2026):** **Live end-to-end pipeline deployed on real hardware.** Full pipeline (Pi + OV4689 + 3-way weighted ensemble) ran on first attempt — stitched together in under 2 days. Dashboard working. Camera color desaturation issue appears resolved. AI detection functional; not yet validated at 5+ people. Final adopted model is a **3-way weighted ensemble** (`0.6 × classcan_density_v4_round4_ft_epoch8` letterbox + `0.4 × classcan_density_style_aug_ft_lowLR_epoch8` stretch): **MAE=2.77, corr=0.586** on 350-frame genuine held-out real classroom footage. SCUT-HEAD benchmark: MAE=2.13, $r=0.9951$; quadrant operational regime MAE=0.93. Secondary HUD model: MobileNetV3-Large @ 416×416 (F1=31.8%, MAE=3.84). Open items: inference lag **resolved** (V4L2 buffer drain fix deployed Sept 24), camera startup config wiring, 5+ people validation.

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

**Raspberry Pi 3B — the brain.** Runs headless **Raspberry Pi OS Lite (64-bit, Trixie)**. The quad-core Cortex-A53 CPU runs TFLite inference (`ai-edge-litert`), change detection, and communication bridging. Live continuous-stream inference is avoided due to CPU limits; CLASSCAN instead uses periodic snapshot detection with immediate re-trigger on significant frame change. Primary model: **`classcan_density_v4` density-map regression** (MobileNetV3-Large backbone, 104×104 density map output, softplus activation) achieving **MAE = 2.13 ($r=0.9951$) overall and MAE = 0.93 in the 0–20 quadrant operational regime**. Pi 3B CPU benchmark: density model **702.3 ms/frame**, box detector **0.557 s/frame** (both XNNPACK, float32). The **MobileNetV3-Large @ 416×416 box detector** (F1=31.8%, MAE=3.84, $r=0.986$ with 2×2 tiling and Soft-NMS) is available for visual HUD bounding boxes. Handles all networking via onboard Wi-Fi and bridges to ESP32 over USB serial.

**ESP32 — the hands.** Fully isolated from networking (its Wi-Fi radio is unused by design — networking stays on the Pi 3B); handles physical I/O only: servo positioning (sweep or quadrant-targeted), LDR-triggered custom illumination module, and driving the LED matrix. Receives commands only via USB serial from the Pi 3B — never connects to the network directly. Runs autonomously in default sweep mode — sweep and lighting logic continue even if the network or laptop dashboard drops. Reports its own state (idle/moving) back over serial so the Pi 3B's change-detection trigger can distinguish the turret's own motion from an actual change in the room. Supports a calibrated quadrant/seat pan-tilt lookup table for targeted mode, switchable with general sweep mode via dashboard command.

**Laptop Dashboard — the display.** Receives headcount and periodic snapshots over Wi-Fi from the Pi 3B, and presents a real-time monitoring view. Can send mode-switch and zone-check commands back to the turret.

### Design Rationale & OS Decision

- **Operating System Selection (Debloated Android vs. Raspberry Pi OS Lite 64-bit):** An ultra-lean Android build was initially evaluated based on prior SBC edge AI precedent. However, after technical assessment against project timelines and solo-development maintenance constraints, **Raspberry Pi OS Lite (64-bit, Trixie)** was deliberately adopted. Raspberry Pi OS Lite provides a headless, low-overhead Linux environment with zero display-server burden, first-class V4L2/UVC camera stability, native PySerial support, and official LiteRT/TFLite wheels — avoiding Android HAL and driver maintenance risks without sacrificing inference efficiency.
- **Model Selection & Pivot Rationale:** Baseline tests with a stock MobileNetV2-SSD full-body model confirmed the pipeline works but produced 0 detections on far-row classroom seating (armchair occlusion, steep ceiling angle). Progression moved through MobileNetV2 FPN (F1=19.5%) to MobileNetV3-Large @ 416×416 (F1=30.1%). Following external QA review (PeaNat), the system expanded to continuous **density-map regression (`classcan_density_v4`)**, achieving **MAE = 2.13 ($r=0.9951$) overall and MAE = 0.93 in quadrant scanning (0–20 students)**, eliminating bounding-box aspect ratio artifacts and NMS failures. See `docs/design_rationale.md` ADR-03 and `docs/benchmark_results.md`.
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
3. **The Solution:** Rather than relying on generic full-body COCO weights, the project built a dedicated **custom Keras multi-scale head detector** ("head" class, head-and-shoulders bounding boxes) that was later extended to **density-map regression (`classcan_density_v4`)** following external QA review. YOLOLite CPU (Nano) was an intermediate attempt that plateaued at mAP@50=16.6% and was abandoned before the custom approach succeeded.

---

## Dataset, Model Architecture & Training

### Validated Production Models

#### 1. Primary Headcount Engine: `classcan_density_v4` (Density-Map Regression)
- **Architecture:** MobileNetV3-Large backbone with lightweight progressive upsampling decoder, outputting a 104×104 single-channel continuous density map (3.6M total parameters). Uses **Softplus** output activation.
- **Accuracy Metrics (407 validation images):**
  - **Overall:** MAE = **2.13 people**, Correlation $r = \mathbf{0.9951}$, MAPE = 16.1%, Within $\pm 2$ heads = 66.1%.
  - **Operational Quadrant Regime (0–20 students):** **MAE = 0.93 people** (< 1 student error).
- **Justification:** Avoids rigid bounding-box aspect ratio assumptions and eliminates NMS suppression failures in dense seating rows. Directly optimizes for the capstone's core objective: headcount accuracy.

#### 2. Secondary HUD Engine: MobileNetV3-Large @ 416×416 FPN Head Detector
- **Architecture:** 3-scale feature pyramid (52×52, 26×26, 13×13 grids for 416-px input), predicting objectness + 4 normalized box coordinates per cell with occupancy-based overflow routing.
- **Inference Pipeline:** 2×2 grid tiled inference (0.2 overlap) with dual thresholding (`full_obj=0.35`, `tile_obj=0.65`) and Soft-NMS merging ($\sigma=0.5, \text{thresh}=0.3$).
- **Accuracy Metrics:** Precision = 31.3%, Recall = 32.4%, **F1 = 31.8%**, **MAE = 3.84 people**, Correlation $r = 0.986$.
- **Edge Speed:** **0.557 s/frame** on physical Pi 3B CPU (XNNPACK). Provides visual bounding boxes for dashboard HUD streaming.

### Ruled-Out Approaches (documented negative results)

| Attempt | Result | Reason Ruled Out |
|---|---|---|
| CrowdHuman augmentation (V2 + V3 architectures) | Worse than baseline in all configs; V3 version collapsed to 0% P/R (objectness collapse) | Extreme head-density imbalance in CrowdHuman destabilizes objectness head; domain mismatch |
| Naive ensemble (custom + COCO SSD) | P=13.7% / R=16.8% / F1=15.1% — worse than either alone | Union compounds false positives; both models fail on same hard cases |
| COCO SSD MobileNetV2 standalone | −65.2% bias, avg error 27.97/image | Full-body model cannot resolve occluded seated students |
| YOLOLite Nano fine-tune (Roboflow/Colab) | Plateaued at mAP@50=16.6% | TF OD API tensorflow_io build unavailable for Colab Python version; credits exhausted |
| Flip-TTA & WBF merging | Flip-TTA MAE exploded to 12.59; WBF MAE worsened to 4.55 | Flip introduced noise due to un-augmented training; Soft-NMS remained superior |

---

## Known Limitations & Open Items

- **AI/Model Side Status:** Functionally complete. Final model is a 3-way weighted ensemble (MAE=2.77, corr=0.586 on genuine held-out real footage). Model development is frozen.
- **Camera:** OV4689 live at `/dev/video0`. Known-good baseline: `auto_exposure=1, exposure=500, gain=192, brightness=64, gamma=300, saturation=100, white_balance_automatic=0, white_balance_temperature~4600`. Color desaturation issue appears resolved on deployed hardware. Camera startup config (`set_camera_config.sh` + `quirks=128` via `/etc/modprobe.d/uvcvideo.conf`) must be confirmed wired into `setup/startup.py` for every boot.
- **Frame delivery + inference lag:** **Resolved (Sept 24, 2026).** Root cause: OpenCV/V4L2 internal ring buffer queues frames during slow TFLite inference; `cap.read()` returned the oldest buffered (stale) frame rather than the latest live frame. Fix: `_grab_fresh_frame()` in `detector.py` drains the buffer via repeated `cap.grab()` calls (cheap — no pixel decode) then does a single `cap.retrieve()` to get only the newest frame.
- **5+ people validation:** AI detection not yet tested with real classroom occupancy (5+ people).
- **Single-Camera Blind Spots:** By design, a sweeping turret observes one sector at a time. Zone-occupancy reflects the latest quadrant scan rather than continuous instantaneous truth — handled via change-triggered re-scans and reconciler consistency checks. An intentional, honestly-scoped limitation.

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
- [x] **Custom Model Training (Box):** Keras MobileNetV3-Large + 416×416 FPN head detector trained to epoch 60; locked in with 2×2 tiled inference + Soft-NMS (F1=31.8%, MAE=3.84, $r=0.986$).
- [x] **Custom Model Training (Density):** Density-map regression v2 (`classcan_density_v4`) trained to epoch 41; confirmed best model overall (MAE=2.13, $r=0.9951$, quadrant MAE=0.93).
- [x] **Physical Camera Integration:** OV4689 detected at `/dev/video0` (MJPG up to 2688×1520@30fps); 11-shot and 225-shot (4-variable) exposure sweeps completed on Pi.
- [x] **Camera Baseline Calibration:** Gamma root cause identified (`gamma=110` → `gamma=300`). Known-good baseline: `auto_exposure=1, exposure=500, gain=192, brightness=64, gamma=300, saturation=100, wb_auto=0, wb_temp~4600`.
- [x] **TFLite Model Export:** Both ensemble checkpoints → float32 TFLite (13.77 MB each, ~702 ms/frame on Pi 3B via `ai_edge_litert`). Int8 deferred (XNNPack bilinear incompatibility).
- [x] **Camera Color:** Color desaturation issue appears resolved on deployed hardware. `set_camera_config.sh` baseline script in place.
- [x] **Live End-to-End Camera Test:** OV4689 → 3-way ensemble TFLite inference → headcount on Pi confirmed working. Dashboard functional. **(COMPLETED Sept 23, 2026)**
- [ ] **Camera Startup Config Wiring:** Confirm `set_camera_config.sh` and `quirks=128` (`/etc/modprobe.d/uvcvideo.conf`) are applied every boot via `setup/startup.py`.
- [x] **Frame Delivery + Lag (FIXED Sept 24, 2026):** Root cause: OpenCV/V4L2 internal frame buffer queued stale frames during slow TFLite inference; `cap.read()` returned the oldest buffered frame. Fix: `_grab_fresh_frame()` in `detector.py` — drains buffer via `cap.grab()` loop (no pixel decode), then `cap.retrieve()` for only the freshest frame. Applied to all three detector classes.
- [ ] **5+ People Validation:** AI detection not yet tested with real classroom occupancy.
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
        run TFLite (`classcan_density_v4` density-map regression, primary) inference immediately
    else:
        run detection on regular heartbeat interval instead
    sum density map output for headcount; assign to current zone
    count detections per zone; sum and compare against last full-cycle total
    if counts don’t reconcile: re-scan before reporting
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
