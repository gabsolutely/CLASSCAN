# CLASSCAN — Development Roadmap & PoC Scope

**Full project vision:** Intelligent classroom headcount system (CV + LED display + wireless dashboard).
**PoC objective:** Prove the core edge vision pipeline end-to-end: **camera → Pi 3B → TFLite head detection → count displayed.**

**Status (as of Sept 10, 2026):** Core software pipeline operational and bench-tested.
AI/model engineering is **functionally complete**:
1. Primary Headcount Model: **`classcan_density_v4` density-map regression** (MobileNetV3-Large + 104×104 density map output, softplus activation). Validated on 407 images: **MAE = 2.13**, **$r = 0.9951$**, MAPE = 16.1%. In the actual operational quadrant scanning range (0–20 students), **MAE is 0.93 people** (< 1 student error).
2. Secondary HUD Model: **MobileNetV3-Large + 416×416 FPN head detector** locked in with 2×2 dual-threshold tiling + Soft-NMS (F1 = 31.8%, MAE = 3.84, $r = 0.986$) for bounding box visualization.
Evaluation history complete: count threshold sweep (`obj_thresh=0.35` optimal), tiling grid sweeps, Soft-NMS vs WBF vs Flip-TTA, and density-map regression evolution (v1–v4).
Active priority: **camera exposure calibration** and **live end-to-end testing on the Raspberry Pi 3B**.
Hard deadline: **September 28, 2026**.

---

## PoC Goal

Prove the core detection pipeline works end-to-end on target hardware:

```
[OV4689 camera] → [Pi 3B: capture frame → TFLite inference (density map / head detector) → count displayed]
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
- [x] **Custom model — MobileNetV3-Large+416 Box Detector:** Keras 3-head FPN (52×52/26×26/13×13) at 416×416 input
      — Epoch-60 checkpoint: P=35.2% / R=26.3% / F1=30.1% (soft-NMS σ=0.5/t=0.3, obj_thresh=0.4)
      — Pi 3B CPU benchmark: **0.557 s/frame** (XNNPACK) — viable for periodic-snapshot use case
      — Checkpoint on Colab Drive: `/content/drive/MyDrive/models/`
- [x] **Count-accuracy threshold sweep:** Found `obj_thresh=0.35` optimal for headcount (MAE=3.57, $r=0.987$), resolving overcounting bias
- [x] **Tiled inference investigation:** 2×2 grid, 0.2 overlap, dual threshold (`full_obj=0.35`, `tile_obj=0.65`) + Soft-NMS: P=31.3%, R=32.4%, F1=31.8%, MAE=3.84, $r=0.986$ (locked-in box config)
- [x] **Density-Map Regression v2 (`classcan_density_v4`):** Developed following QA review (PeaNat)
      — Architecture: MobileNetV3-Large + progressive upsampling decoder, 104×104 density map output, Softplus activation
      — Training stabilization: warmup + scheduled LR decay (0.94/epoch to $2 \times 10^{-6}$), verified best checkpoints
      — Final 407-image benchmark: **MAE = 2.13**, **$r = 0.9951$**, MAPE = 16.1%
      — Operational quadrant regime (0–20 students): **MAE = 0.93 people**
      — **Confirmed best model overall**
- [x] `detector.py` updated with NMS, Soft-NMS, and CLASSCAN output format support
- [x] `classcan_training_pipeline.py` committed to `/scripts`
- [x] Connect physical OV4689 UVC camera module (4-pin harness to USB Port 2)
- [x] OV4689 camera is functional at `/dev/video0` (MJPG up to 2688×1520@30fps); feed verified with `scripts/camera_verify.py`
- [x] 11-shot exposure sweep captured on Pi (exposure 25–1800, gain=32, 1280×720/MJPG, saved to `~/camera_tests/`)
- [ ] **Camera exposure calibration:** visual review of sweep → pick optimal exposure → gain sweep → commit V4L2 config
- [ ] **Export final model weights to TFLite (`scripts/export_to_tflite.py`)**
- [ ] **Live end-to-end camera test:** OV4689 frame → TFLite → headcount on Pi
- [x] Annotation quality spot-check on training images (confirmed root cause of weak P/R)
- [x] CrowdHuman augmentation trial (V2 + V3 architectures) — ruled out (objectness collapse on V3)
- [x] Naive ensemble (custom + COCO SSD) — ruled out (compounded false positives)
- [x] COCO SSD standalone count-based eval: -65.2% bias, avg error 27.97/image. Ruled out.
- [x] YOLOLite Nano fine-tune (Roboflow/Colab): plateaued at mAP@50=16.6%. Ruled out.
- [x] Flip-TTA and WBF merging — ruled out (Soft-NMS superior)
- [x] Public dataset investigation: RPEE-Heads (CC BY-SA 4.0) and academic domain gap review
- [x] **AI/model development functionally complete**

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