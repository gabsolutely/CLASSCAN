# CLASSCAN
**Development of an Intelligent Classroom Headcount Monitoring System using Computer Vision and LED Display Technology**

A ceiling-mounted smart camera turret that automatically detects and counts people in a classroom in real time, displaying the live headcount on an LED display and a wireless laptop dashboard — no manual attendance checking, no facial recognition, just occupancy (and optionally, seat-zone presence).

**Status:** Design & architecture finalized — hardware sourcing and implementation in progress.

---

## The Problem

Most schools still rely on manual headcount and attendance checking — slow, error-prone, and unhelpful in situations like emergencies or class transitions where a fast, accurate room count actually matters. CLASSCAN automates this using computer vision and a real-time display, without collecting any identifying information about students.

## What It Does

- Detects and counts people in a classroom using a live camera feed, targeting real-time performance (~30 FPS on-device inference)
- Displays the current headcount on an LED display in real time
- Optionally maps detected presence to predefined seat zones for per-seat occupancy (not identity)
- Streams live video + count overlay to a wireless laptop dashboard
- Automatically switches to IR illumination in low-light conditions (no visible light shone on students)
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
[Camera] → [Orange Pi PC — debloated Android + TFLite inference]
                    │
                    ├──► Wi-Fi (USB dongle) direct to laptop dashboard (video + count overlay)
                    │
                    └──► UART/USB-serial ──► [Raspberry Pi Pico]
                                                    │
                                                    ├──► Servo PWM (pan/tilt sweep)
                                                    ├──► LDR read → IR illuminator control
                                                    └──► LED Matrix Display (local headcount)
```

### Division of Labor

**Orange Pi PC — the brain.** Runs a heavily debloated Android build (not Linux/Debian) so the full 1GHz H3 CPU is dedicated to TFLite inference — this exact configuration is a validated approach on this exact hardware, proven capable of ~30 FPS multi-detection by a prior award-winning student project on identical specs (Allwinner H3, 1GB RAM, Mali-400 GPU). Handles all networking directly (video + count to laptop) via a USB Wi-Fi dongle, since the OPi PC has no onboard Wi-Fi. Sends only the lightweight headcount number down to the Pico over serial.

**Raspberry Pi Pico — the hands.** Fully isolated from networking; handles physical I/O only: servo sweep pattern, LDR-triggered IR illumination, and driving the LED matrix. Runs autonomously — sweep and lighting logic continue even if the network or laptop dashboard drops. Chosen over ESP32 since it has no networking responsibility, making the cheaper, radio-free Pico the better fit once the OPi handles its own Wi-Fi.

**Laptop Dashboard — the display.** Receives live video and headcount over Wi-Fi from the OPi, overlays detection boxes, and presents a real-time monitoring view.

### Design Rationale (for defense/documentation)

- **Resource optimization:** an affordable ~₱1,500 Orange Pi PC, paired with the specific Android+TFLite debloat approach, gets competitive real-time inference performance out of otherwise severely constrained hardware (1GHz quad-core, no NPU).
- **Isolating core operations:** physical safety/monitoring functions (sweep, lighting, local display) live entirely on the Pico and do not depend on network or dashboard uptime.
- **Industrial systems design pattern:** separating the AI/logic engine (OPi) from the physical actuator controller (Pico) mirrors standard practice in commercial robotics and automation, avoiding processing delays and single points of failure.
- **Privacy-by-design:** seat-zone presence (if implemented) is computed from bounding-box position relative to a predefined zone, not identity — no recognition or student-specific data is ever produced or stored.

---

## Hardware Bill of Materials (BOM) Summary

| Component | Purpose |
|---|---|
| Orange Pi PC (1GB RAM) | Main compute — debloated Android + TFLite inference |
| USB Wi-Fi Dongle (chipset TBD — driver compatibility with Android build must be verified) | Wireless networking for OPi, since board has no onboard Wi-Fi |
| Raspberry Pi Pico | Physical I/O controller — servos, LDR, IR, LED matrix |
| Camera Module (low-light/IR capable) | Video feed for detection |
| IR Illuminator Module | Invisible-to-humans illumination for dim rooms |
| Light Sensor (LDR) | Detects ambient brightness, triggers IR illuminator |
| Pan/Tilt Servos (MG90S x2) | Rotates the turret to sweep the room |
| LED Matrix Display | Shows live headcount |
| 18650 Battery + Charging Module | Swappable, untethered power |
| 3D-Printed Dome Enclosure | Houses all components, ceiling-mounted |

Full itemized BOM and cost breakdown: see `/docs` (update path once added).

**Open item:** confirm exact USB Wi-Fi dongle chipset with known driver support on the debloated Android build before purchasing.

---

## How It Works

```
Pico loop (autonomous, runs independent of network):
    sweep servos through pan/tilt pattern
    read LDR
    if dim: enable IR illuminator
    else: IR illuminator off
    if new headcount received via serial: update LED matrix

OPi loop:
    capture camera frame
    run TFLite person-detection inference
    count detections (optionally: map to seat zones)
    send headcount → Pico (serial)
    send video + count overlay → laptop dashboard (Wi-Fi)
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
