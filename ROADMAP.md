# CLASSCAN — Development Roadmap & PoC Scope

**Full project vision:** Intelligent classroom headcount system (CV + LED display + wireless dashboard).
**PoC objective:** Prove the core edge vision pipeline end-to-end: **camera → Pi 3B → TFLite head detection → count displayed.**

**Status (as of Sept 8, 2026):** Core software pipeline operational and bench-tested.
Final detection model: **custom Keras MobileNetV3-Large + 416×416 FPN head detector** (SCUT-HEAD + 35 local images),
epoch-60 checkpoint (P=35.2% / R=26.3% / F1=30.1%, soft-NMS σ=0.5/t=0.3, obj_thresh=0.4).
Full model evaluation history complete: threshold sweep, formal mAP@50 eval, and 4 ruled-out improvement attempts
(CrowdHuman augment ×2 architectures, naive ensemble, COCO standalone, YOLOLite fine-tune) all benchmarked.
V3+416 epoch-60 is the confirmed best model. TFLite export + camera exposure calibration are the two remaining PoC steps.
Hard deadline: **September 28, 2026**.

---

## PoC Goal

Prove the core detection pipeline works end-to-end on target hardware:

```
[OV4689 camera] → [Pi 3B: capture frame → TFLite (MobileNetV3-Large+416 custom head detector) → count displayed]
```

"Displayed" for initial PoC = verified counts rendered on the wireless laptop dashboard or console output.

## In Scope for Current Phase

- [x] Raspberry Pi 3B set up with headless Raspberry Pi OS Lite (64-bit, Debian 13/Trixie)
- [x] Pi 3B edge resilience: Wi-Fi power-save disabled via systemd (`wifi-powersave-off.service`), cron watchdog script (`wifi-watchdog.sh`), and setup configs committed to `src/pi/setup/`
- [x] Core TFLite inference pipeline implemented and bench-tested (23/23 unit tests pass on physical Pi 3B post-reflash)
- [x] COCO-baseline detection verified across real test images (and failure analysis done)
- [x] Change-trigger frame difference logic and zone reconciliation implemented and tested
- [x] Wireless dashboard server implemented
- [x] **Custom model — MobileNetV2+300 baseline:** Keras 3-head FPN trained (60 epochs, epoch-60 best: P=20.4%/R=18.7%/F1=19.5%)
      — Architecture: MobileNetV2 backbone, P3/P4/P5 FPN, occupancy-based target encoding
      — Loss: focal + smooth-L1, Adam lr=1e-5, batch=8
- [x] **Final model — MobileNetV3-Large+416:** Keras 3-head FPN (52×52/26×26/13×13) at 416×416 input, same loss/encoding
      — Epoch-60 checkpoint: P=35.2% / R=26.3% / F1=30.1% (soft-NMS σ=0.5/t=0.3, obj_thresh=0.4)
      — Pi 3B CPU benchmark: **0.557 s/frame** (XNNPACK) — viable for periodic-snapshot use case
      — Checkpoint on Colab Drive: `/content/drive/MyDrive/models/`
- [x] `detector.py` updated with NMS and CLASSCAN 3-tensor output format support
- [x] `classcan_training_pipeline.py` committed to `/scripts`
- [ ] **Export epoch-60 V3+416 weights to `models/classcan_head_v1.tflite`**
      (`python scripts/export_to_tflite.py --weights ckpt_ep60_v3.weights.h5`)
- [x] Connect physical OV4689 UVC camera module (4-pin harness to USB Port 2)
- [x] OV4689 camera is functional at `/dev/video0` (MJPG up to 2688×1520@30fps); feed verified with `scripts/camera_verify.py`
- [x] 11-shot exposure sweep captured on Pi (exposure 25–1800, gain=32, 1280×720/MJPG, saved to `~/camera_tests/`)
- [ ] **Camera exposure calibration:** visual review of sweep → pick optimal exposure → gain sweep → commit V4L2 config
- [ ] **Live end-to-end camera test:** OV4689 frame → TFLite (V3+416) → headcount on Pi
- [x] Annotation quality spot-check on training images (confirmed root cause of weak P/R:
      overly-tight boxes on clear heads, unlabeled small distant heads, inconsistent tightness,
      at least one clearly visible head with no box at all) — re-annotation deferred post-PoC
- [x] NMS threshold sweep (9 combos, ~100 val images) — best: obj=0.4 / iou=0.4 (avg err 5.07, -10.7% bias)
- [x] Soft-NMS sweep (Gaussian decay) — best: σ=0.5 / threshold=0.3 (small but real improvement, free/no retraining)
- [x] Formal mAP@50 eval (30 val images, IoU-matched): MobileNetV2+300 epoch-60: P=20.4%, R=18.7%, F1=19.5%
- [x] CrowdHuman augmentation trial — V2+300: P=14.5%/R=16.8%/F1=15.5%. V3+416: objectness collapse (0% P/R). Both worse. Ruled out.
- [x] Naive ensemble (custom + COCO SSD): P=13.7%/R=16.8%/F1=15.1% — worse. Ruled out.
- [x] COCO SSD standalone count-based eval: -65.2% bias, avg error 27.97/image. Ruled out.
- [x] YOLOLite Nano fine-tune (Roboflow/Colab): plateaued at mAP@50=16.6% (TF OD API dead end). Ruled out.
- [x] MobileNetV3-Large+416 Pi 3B speed benchmark: 0.557 s/frame (XNNPACK) — viable
- [x] **Final model decision:** MobileNetV3-Large+416 epoch-60 (F1=30.1%) — confirmed best across all tested approaches

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
| Raspberry Pi 3B (1GB) | **In hand & running** (Raspberry Pi OS Lite 64-bit Trixie; hardened Wi-Fi + watchdog) |
| Pi Acrylic Case (clear, enclosed, with active fan) | **✅ Installed & Wired** (GPIO Pin 4/6, ~36°C operating temp) |
| ESP32 | **In hand** (firmware development underway) |
| OV4689 4MP BSI USB Camera (UVC, Type-C/A) | **✅ In hand & active at /dev/video0** (exposure calibration in progress) |
| Light Sensor (LDR) + Illumination LEDs | **In hand / circuit in development** |
| Pan/Tilt Servos (MG90S x2) | **In hand** |
| LED Matrix Display | **In hand** |
| Power supply & batteries | **In hand & verified** |

---

## Architectural Decisions & Methodology Justification

- **OS Choice:** Raspberry Pi OS Lite (64-bit) chosen over debloated Android for superior stability, standard Linux V4L2 drivers, official LiteRT support, and reduced maintenance overhead. See `docs/design_rationale.md` ADR-01.
- **Model Architecture:** Custom Keras MobileNetV3-Large + 416×416 FPN head detector (3-head feature pyramid at 52×52/26×26/13×13, occupancy-based target encoding, focal loss + smooth-L1). Chosen after exhausting MobileNetV2+300 baseline and ruling out 4 improvement paths (CrowdHuman augmentation ×2 architectures, naive ensemble, COCO SSD standalone, YOLOLite fine-tune). V3+416 epoch-60 scored F1=30.1% vs V2+300 epoch-60 F1=19.5% on the same IoU-matched eval. See `docs/design_rationale.md` ADR-03.
- **Labeling Convention:** Single "head" class with head-and-shoulders bounding boxes (not full-body COCO) ensures robust detection of students seated behind wooden armchairs at 30°–50° ceiling pitch angles.
- **Compute-Aware Triggering:** Periodic snapshot + frame-difference re-detection to prevent thermal throttling and compute saturation on the Pi 3B. See `docs/design_rationale.md` ADR-04.
- **LoRa Rejected:** Considered (offered cheaply by a colleague) but explicitly rejected. Project is single-room/local — Pi↔ESP32 communicate over USB serial, no long-range wireless needed. Would only reconsider if scope expands to multi-room/multi-building deployment.