# CLASSCAN — Development Roadmap & PoC Scope

**Full project vision:** Intelligent classroom headcount system (CV + LED display + wireless dashboard).
**PoC objective:** Prove the core edge vision pipeline end-to-end: **camera → Pi 3B → TFLite person detection → count displayed.**

**Status:** Core software pipeline (`detector.py`, `change_trigger.py`, `zone_reconciler.py`, `dashboard_server.py`) operational and verified with real image tests on the Raspberry Pi 3B running **Raspberry Pi OS Lite (64-bit)**. Hardware integration and fine-tuning are active.

---

## PoC Goal

Prove the core detection pipeline works end-to-end on target hardware:

```
[OV4689 camera] → [Pi 3B: capture frame → TFLite person detection] → [count displayed]
```

"Displayed" for initial PoC = verified counts rendered on the wireless laptop dashboard or console output.

## In Scope for Current Phase

- [x] Raspberry Pi 3B set up with headless Raspberry Pi OS Lite (64-bit)
- [x] Core TFLite MobileNetV2-SSD inference pipeline implemented and bench-tested
- [x] Person-class detection verified across real test images
- [x] Change-trigger frame difference logic and zone reconciliation implemented and tested
- [x] Wireless dashboard server implemented
- [ ] Connect physical OV4689 UVC camera module once delivered
- [ ] Fine-tune MobileNetV2-SSD on SCUT-HEAD Part A + 35-image local classroom head-and-shoulders dataset
- [ ] Live end-to-end camera feed detection verification

## Full-System Integration (Post-PoC)

- Pan/tilt servos, sweep mode, quadrant/zone targeting
- LED matrix headcount display driven by ESP32
- Custom LDR-triggered illumination LED module
- 3D-printed ceiling-mount dome enclosure
- 18650 swappable battery power module
- Full hardware handshake between Pi 3B and ESP32 over serial

---

## Hardware Status

| Component | Status |
|---|---|
| Raspberry Pi 3B (1GB) | **In hand & running** (Raspberry Pi OS Lite 64-bit) |
| ESP32 | **In hand** (firmware development underway) |
| OV4689 4MP BSI USB Camera (UVC, Type-C) | **Sourced / in transit** |
| Light Sensor (LDR) + Illumination LEDs | **In hand / circuit in development** |
| Pan/Tilt Servos (MG90S x2) | **In hand** |
| LED Matrix Display | **In hand** |
| Power supply & batteries | **In hand & verified** |

---

## Architectural Decisions & Notes

- **OS Choice:** Raspberry Pi OS Lite (64-bit) chosen over debloated Android for superior stability, standard Linux V4L2 drivers, official LiteRT support, and reduced maintenance overhead.
- **Model Choice:** MobileNetV2-SSD quantized to `uint8` for low CPU latency on the quad-core Cortex-A53.
- **Labeling Convention:** Head-and-shoulders bounding boxes (not full-body COCO) to ensure robust detection of students seated behind wooden armchairs at 30°–50° ceiling pitch angles.
- **Compute-Aware Triggering:** Periodic snapshot + frame-difference re-detection to prevent thermal throttling and compute saturation on the Pi 3B.