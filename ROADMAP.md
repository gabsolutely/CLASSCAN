# CLASSCAN — Development Roadmap & PoC Scope

**Full project vision:** Intelligent classroom headcount system (CV + LED display + wireless dashboard).
**PoC objective:** Prove the core edge vision pipeline end-to-end: **camera → Pi 3B → TFLite head detection → count displayed.**

**Status (as of Sept 3, 2026):** Core software pipeline operational and bench-tested.
Custom Keras multi-scale head detector **fully trained** (60 epochs, best checkpoint epoch-55,
Drive-verified). TFLite export + live camera integration are the remaining PoC steps.
Hard deadline: **September 28, 2026**.

---

## PoC Goal

Prove the core detection pipeline works end-to-end on target hardware:

```
[OV4689 camera] → [Pi 3B: capture frame → TFLite (CLASSCAN head detector) → count displayed]
```

"Displayed" for initial PoC = verified counts rendered on the wireless laptop dashboard or console output.

## In Scope for Current Phase

- [x] Raspberry Pi 3B set up with headless Raspberry Pi OS Lite (64-bit)
- [x] Core TFLite inference pipeline implemented and bench-tested
- [x] COCO-baseline detection verified across real test images (and failure analysis done)
- [x] Change-trigger frame difference logic and zone reconciliation implemented and tested
- [x] Wireless dashboard server implemented
- [x] Custom Keras multi-scale head detector trained (60 epochs, epoch-55 best checkpoint)
      — Architecture: MobileNetV2 backbone, P3/P4/P5 FPN, occupancy-based target encoding
      — Training: focal loss + smooth-L1, Adam lr=1e-5, batch=8, ~356 batches/epoch
      — Inference check at epoch-55: 13/13 exact count match on val image with NMS
- [x] `detector.py` updated with NMS and CLASSCAN 3-tensor output format support
- [x] `classcan_training_pipeline.py` committed to `/scripts`
- [ ] Export epoch-55 checkpoint to `models/classcan_head_v1.tflite`
      (`python scripts/export_to_tflite.py --weights ckpt_ep55.weights.h5`)
- [x] Connect physical OV4689 UVC camera module (4-pin harness to USB Port 2)
- [/] Live end-to-end camera feed verification (`scripts/camera_verify.py` with `--camera-only` & model mode)

## Full-System Integration (Post-PoC)

- Pan/tilt servos, sweep mode, quadrant/zone targeting (servo "radar" mount prototype on ESP32)
- LED matrix headcount display driven by ESP32
- Custom LDR-triggered illumination LED module
- 3D-printed ceiling-mount dome enclosure
- 18650 swappable battery power module
- Full hardware handshake between Pi 3B and ESP32 over serial
- mAP@50 formal evaluation and annotation quality audit (deferred — trigger only if model underperforms)

---

## Hardware Status

| Component | Status |
|---|---|
| Raspberry Pi 3B (1GB) | **In hand & running** (Raspberry Pi OS Lite 64-bit) |
| Pi Acrylic Case (clear, enclosed, with active fan) | **✅ Installed & Wired** (GPIO Pin 4/6, ~36°C operating temp) |
| ESP32 | **In hand** (firmware development underway) |
| OV4689 4MP BSI USB Camera (UVC, Type-C/A) | **✅ In hand & connected** (USB Port 2, 4-pin JST harness) |
| Light Sensor (LDR) + Illumination LEDs | **In hand / circuit in development** |
| Pan/Tilt Servos (MG90S x2) | **In hand** |
| LED Matrix Display | **In hand** |
| Power supply & batteries | **In hand & verified** |

---

## Architectural Decisions & Methodology Justification

- **OS Choice:** Raspberry Pi OS Lite (64-bit) chosen over debloated Android for superior stability, standard Linux V4L2 drivers, official LiteRT support, and reduced maintenance overhead. See `docs/design_rationale.md` ADR-01.
- **Model Architecture:** Custom Keras multi-scale MobileNetV2 head detector (3-head FPN, occupancy-based target encoding, focal loss + smooth-L1). Chosen after (a) COCO MobileNetV2-SSD failed on desk-occluded classroom shots, (b) YOLOLite Nano fine-tune plateaued at mAP@50=16.6% on Roboflow (exhausted credits), and (c) TF Object Detection API / tensorflow_io had no available build for the Colab Python version. See `docs/design_rationale.md` ADR-03.
- **Labeling Convention:** Single "head" class with head-and-shoulders bounding boxes (not full-body COCO) ensures robust detection of students seated behind wooden armchairs at 30°–50° ceiling pitch angles.
- **Compute-Aware Triggering:** Periodic snapshot + frame-difference re-detection to prevent thermal throttling and compute saturation on the Pi 3B. See `docs/design_rationale.md` ADR-04.
- **LoRa Rejected:** Considered (offered cheaply by a colleague) but explicitly rejected. Project is single-room/local — Pi↔ESP32 communicate over USB serial, no long-range wireless needed. Would only reconsider if scope expands to multi-room/multi-building deployment.