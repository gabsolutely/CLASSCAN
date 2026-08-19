# CLASSCAN
**Development of an Intelligent Classroom Headcount Monitoring System using Computer Vision and LED Display Technology**

A ceiling-mounted smart camera turret that automatically detects and counts people in a classroom in real time, displaying the live headcount on an LED display and a wireless laptop dashboard — no manual attendance checking, no facial recognition, just occupancy (and optionally, seat-zone presence).

**Status:** Core architecture locked; hardware sourcing in progress (Pi 3B in transit, camera/illumination parts being finalized) — model training and firmware implementation next.

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
[Camera — OV4689 BSI USB module] → [Raspberry Pi 3B — debloated Android + TFLite inference]
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

**Raspberry Pi 3B — the brain.** Runs a heavily debloated Android build (not stock Raspberry Pi OS) so the quad-core Cortex-A53 CPU is dedicated to TFLite inference. Same debloat philosophy validated by a prior award-winning student project on Orange Pi PC/H3 hardware (~30 FPS multi-detection) — the 3B's stronger CPU (Cortex-A53 @ 1.2GHz vs. the H3's Cortex-A7 @ 1GHz) is expected to match or exceed that result, though this is an extrapolation from a different board, not a direct replication, and will need its own benchmarking. Live continuous-stream inference is treated as a known risk (a Raspberry Pi 4 reportedly struggled with it in a comparable live-detection project); CLASSCAN instead defaults to periodic snapshot detection with immediate re-trigger on significant frame change, cutting sustained compute load. Detection model: MobileNetV2-SSD (COCO-pretrained, person class), fine-tuned/quantized for the ceiling-mount classroom scenario — chosen over EfficientDet-Lite and YOLO variants for the best speed/accuracy trade-off on CPU-only inference at this performance tier. Handles all networking directly (count/snapshots to laptop, commands from laptop) via onboard Wi-Fi — no USB dongle or chipset-compatibility risk, unlike the Orange Pi PC. Talks to the ESP32 over USB serial — translates dashboard commands into serial messages and relays headcount/status back.

**ESP32 — the hands.** Fully isolated from networking (its Wi-Fi radio is unused by design — networking stays on the Pi 3B); handles physical I/O only: servo positioning (sweep or quadrant-targeted), LDR-triggered custom illumination module, and driving the LED matrix. Receives commands only via USB serial from the Pi 3B — never connects to the network directly. Runs autonomously in default sweep mode — sweep and lighting logic continue even if the network or laptop dashboard drops. Reports its own state (idle/moving) back over serial so the Pi 3B's change-detection trigger can distinguish the turret's own motion from an actual change in the room. Supports a calibrated quadrant/seat pan-tilt lookup table for targeted mode, switchable with general sweep mode via dashboard command.

**Laptop Dashboard — the display.** Receives headcount and periodic snapshots over Wi-Fi from the Pi 3B, and presents a real-time monitoring view. Can send mode-switch and zone-check commands back to the turret.

### Design Rationale (for defense/documentation)

- **Resource optimization:** the Raspberry Pi 3B's stronger CPU (vs. the originally considered Orange Pi PC) reduces reliance on a single unverified benchmark, while the same Android-debloat-for-inference philosophy still applies — freeing the CPU from OS overhead to maximize TFLite throughput.
- **Compute-aware detection strategy:** periodic snapshot + change-triggered re-detection (rather than continuous live inference) keeps sustained CPU load low on hardware known to struggle with live detection, while still responding immediately when something actually changes.
- **Quadrant-based zoning with self-consistency checking:** dividing the room into quadrants (rather than per-seat zones) shortens the full-scan cycle and blind-spot window, absorbs in-quadrant seat shuffling as a non-event, and cuts inference calls per cycle. A reconciliation check flags and re-scans when per-quadrant counts don't add up to the expected total, rather than silently trusting a possibly-stale scan.
- **Reduced hardware risk:** onboard Wi-Fi and Bluetooth on the Pi 3B eliminate the USB Wi-Fi dongle chipset-compatibility risk present in the Orange Pi PC path (no dongle sourcing, no driver gamble).
- **Ecosystem support:** the Raspberry Pi platform has significantly broader community documentation and prior art for Android/LineageOS builds, camera pipelines, and troubleshooting than Orange Pi boards — reducing time lost to undocumented issues.
- **Isolating core operations:** physical safety/monitoring functions (sweep, lighting, local display) live entirely on the ESP32 and do not depend on network or dashboard uptime.
- **Industrial systems design pattern:** separating the AI/logic engine (Pi 3B) from the physical actuator controller (ESP32) mirrors standard practice in commercial robotics and automation, avoiding processing delays and single points of failure.
- **Privacy-by-design:** zone presence (if implemented) is computed from bounding-box position relative to a predefined quadrant/zone, not identity — no recognition or student-specific data is ever produced or stored. Per-zone status reflects the most recent scan, not a continuous real-time truth — an intentional, honestly-scoped limitation of any single-camera scanning system.

---

## Hardware Bill of Materials (BOM) Summary

| Component | Purpose |
|---|---|
| Raspberry Pi 3B (1GB RAM) | Main compute — debloated Android + TFLite inference; onboard Wi-Fi + Bluetooth (sourced, in transit) |
| ESP32 | Physical I/O controller — servos, LDR, illumination, LED matrix, USB serial link to Pi 3B (already owned) |
| OV4689 4MP BSI USB Camera Module (UVC, Type-C) | Video feed for detection — back-side-illuminated sensor for improved performance in dim/evening classroom lighting, no external driver required |
| Light Sensor (LDR) | Detects ambient brightness, triggers illumination module |
| Custom illumination LED module (self-built, LDR-triggered) | Brightens scene in dim conditions — built in-house rather than a packaged IR unit, driven by the ESP32 |
| Pan/Tilt Servos (MG90S x2) | Rotates the turret to sweep or target quadrants |
| LED Matrix Display | Shows live headcount |
| 18650 Battery + Charging Module | Swappable, untethered power |
| 3D-Printed Dome Enclosure | Houses all components, ceiling-mounted |

Full itemized BOM and cost breakdown: see `/docs` (update path once added).

**Open items:**
- Systematic (not trial-and-error) Android debloat process for Pi 3B — remove unused apps/services/UI layers incrementally, testing USB serial, Wi-Fi, and TFLite inference after each step; keep a log of what's removed for documentation
- Benchmark actual FPS/accuracy on Pi 3B — the ~30 FPS figure is precedent from Orange Pi PC/H3 hardware, not yet confirmed on this board
- Confirm OV4689 camera module works driver-free on the debloated Android build specifically (UVC compliance implies it should, not yet tested)
- Design and build the custom LDR-triggered illumination module (LED type, trigger threshold, ESP32 wiring)
- Quadrant calibration procedure — record pan/tilt values for each quadrant once mounted
- Train/quantize MobileNetV2-SSD on classroom-specific data (ceiling angle, density, occlusion)
- Pi 3B currently in transit; seller delay may push arrival back a week

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
        run TFLite (MobileNetV2-SSD) person-detection inference immediately
    else:
        run detection on regular heartbeat interval instead
    count detections per zone; sum and compare against last full-cycle total
    if counts don't reconcile: re-scan before reporting
    send headcount/status → ESP32 (USB serial)
    send count + snapshot → laptop dashboard (Wi-Fi)
    if command received from dashboard (Wi-Fi): forward to ESP32 (USB serial)
```

---

## Repository Structure

```
/docs         → Scope & Delimitation, Significance, BOM, design docs
/cad          → Enclosure design files/renders
/src          → (planned) CV model, detection logic, display driver
/hardware     → (planned) wiring diagrams, GPIO pinout
```

(Adjust structure above to match actual repo layout once code is added.)

## Team

(Add contributors here — e.g. names + roles: Hardware/Enclosure, CV/AI Model, Embedded/Firmware, Documentation)

## Academic Context

This is a capstone project developed at Philippine Christian University – Dasmariñas (PCU-D).

---

This README will be updated as the CV model, firmware, and hardware assembly progress from design to implementation.
