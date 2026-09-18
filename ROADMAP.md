# CLASSCAN — Development Roadmap & PoC Scope

**Full project vision:** Intelligent classroom headcount system (CV + LED display + wireless dashboard).
**PoC objective:** Prove the core edge vision pipeline end-to-end: **camera → Pi 3B → TFLite head detection → count displayed.**

**Status (as of Sept 18, 2026 — 10 days to deadline):** Core software pipeline operational and bench-tested.
AI/model engineering reached a stable milestone after 4 rounds of real-footage fine-tuning:
1. **Adopted model:** `classcan_density_v4_hardneg_ft_epoch4` — density-map regression fine-tuned on 176 hard-negative real-footage crops. Real-footage MAE=3.87 (↓59% from 9.46 pre-fine-tune), bias=+2.33 (↓75%). With post-inference threshold=0.15: MAE=3.08, bias≈0.
2. **SCUT-HEAD benchmark (original 407-image eval):** MAE=2.35, r=0.9908 — no catastrophic regression from fine-tuning.
3. **Round 4 fine-tuning in progress** (LR raised to 5e-5, first LR change across all rounds); result pending.
4. **Secondary HUD Model:** MobileNetV3-Large + 416×416 FPN head detector (F1 = 31.8%, MAE = 3.84) for bounding box visualization.
Critical remaining non-model tasks: **deploy adopted model into main app** (currently missing from `models/`, silently falling back to COCO SSD), **live end-to-end camera test** (never done), **camera exposure/color tuning** (color still unresolved), **rotate leaked Roboflow API key**.
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
- [x] **Count-accuracy threshold sweep:** Found `obj_thresh=0.35` optimal for headcount (MAE=3.57, r=0.987), resolving overcounting bias
- [x] **Tiled inference investigation:** 2×2 grid, 0.2 overlap, dual threshold (`full_obj=0.35`, `tile_obj=0.65`) + Soft-NMS: P=31.3%, R=32.4%, F1=31.8%, MAE=3.84, r=0.986 (locked-in box config)
- [x] **Density-Map Regression v4 (`classcan_density_v4`):** Developed following QA review (PeaNat)
      — Architecture: MobileNetV3-Large + progressive upsampling decoder, 104×104 density map output, Softplus activation
      — Training stabilization: warmup + scheduled LR decay (0.94/epoch to 2e-6), verified best checkpoints
      — Final 407-image benchmark: **MAE = 2.13**, **r = 0.9951**, MAPE = 16.1%
      — Operational quadrant regime (0–20 students): **MAE = 0.93 people**
- [x] `detector.py` updated with NMS, Soft-NMS, and CLASSCAN output format support
- [x] `classcan_training_pipeline.py` committed to `/scripts`
- [x] Connect physical OV4689 UVC camera module (4-pin harness to USB Port 2)
- [x] OV4689 camera is functional at `/dev/video0` (MJPG up to 2688×1520@30fps); feed verified with `scripts/camera_verify.py`
- [x] 11-shot exposure sweep captured on Pi (exposure 25–1800, gain=32, 1280×720/MJPG, saved to `~/camera_tests/`)
- [x] 225-image 4-variable sweep (exposure × gain × brightness × gamma) with automated brightness scoring via ImageMagick
      — **Root cause found:** default `gamma=110` crushed images; `gamma=300` fixed it
      — **Known-good baseline:** 640×480 MJPEG @ 30 FPS, `exposure=500`, `gain=192`, `brightness=64`, `gamma=300` (brightness OK; color/desaturation remaining)
      — `auto_exposure=3 + white_balance_automatic=1 + gamma=300` tested but confirmed dark vs manual settings
- [ ] **Camera color calibration:** narrow sweep (exposure ~300–700, gain ~128–220, brightness ~32–64, gamma ~250–300) targeting color/white-balance controls; also: disable `region_of_interest_auto_ctrls` (locked to 1284×724 crop — likely underexposure root cause), try `sharpness=3` (currently maxed at 7)
- [x] **TFLite float32 export confirmed:** `classcan_density_v4` → 13.77 MB float32 TFLite runs on Pi 3B at **702.3 ms/frame** via `ai_edge_litert`
      — int8 export **deferred**: XNNPack "failed to prepare" on `UpSampling2D(bilinear)` layers; fix requires retraining with `Conv2DTranspose` — not worth risking v4
- [x] Annotation quality spot-check on training images (confirmed root cause of weak P/R)
- [x] CrowdHuman augmentation trial (V2 + V3 architectures) — ruled out (objectness collapse on V3)
- [x] Naive ensemble (custom + COCO SSD) — ruled out (compounded false positives)
- [x] COCO SSD standalone count-based eval: -65.2% bias, avg error 27.97/image. Ruled out.
- [x] YOLOLite Nano fine-tune (Roboflow/Colab): plateaued at mAP@50=16.6%. Ruled out.
- [x] Flip-TTA and WBF merging — ruled out (Soft-NMS superior)
- [x] RPEE-Heads dataset (CC BY-SA 4.0, ~1.1 GB) — **confirmed negative result:** MAE=10.79, 0-20 bucket MAE=8.30/MAPE=341.2%; same dense-crowd-skew failure as CrowdHuman. `classcan_density_v4_best.weights.h5` untouched.
- [x] **Real classroom footage domain-gap test (5 clips, 117 frames, 1fps extraction):**
      — clips: line1 (12s), line2 (22s), line3 (23s), sit1 (29s), sit2 (31s) — all shot while camera physically rotates (simulates pan/tilt quadrant sweep)
      — **Result: large domain-gap cliff.** Overall MAE=9.46 (vs 2.13 on SCUT-HEAD), correlation=0.373, consistent +9.37 positive bias on every clip
      — Root cause confirmed via heatmaps: model hallucinates head-level density on backpacks, stacked chairs, chair headrests at intensity comparable to real heads
      — sit clips generalize better than line clips (MAE 8.99 vs 9.99, corr 0.578 vs 0.282) — motion/atypical pose degrades correlation more than static seated pose
      — Pre-fine-tune threshold-only fix (threshold=0.30): improved MAE but correlation got worse (0.373→0.215). Rejected.
- [x] **Hard-negative fine-tune Round 1 — ADOPTED (new shipped model):**
      — 176 confirmed FP objects manually cropped (bags ~50, chairs ~30–40, tables, floor, hands, pants, shoes, walls)
      — 8-epoch fine-tune from `classcan_density_v4_best`, 85%/15% mix, LR=1e-5, fresh optimizer
      — SCUT-HEAD regression check: MAE 2.35–2.57, r 0.988–0.993 — held up
      — **Real footage epoch 4 (best):** MAE=3.87 (↓59%), bias=+2.33 (↓75%), r=0.448 (↑ from 0.373)
      — + threshold=0.15: MAE=3.08, bias=-0.73 (near-zero), r=0.393
      — **`classcan_density_v4_hardneg_ft_epoch4` ADOPTED as shipped model**, superseding `classcan_density_v4_best`
- [x] **Hard-negative Round 2 (NOT adopted):**
      — Expanded to 595 hard-neg examples + 490 hard-positive point annotations (from `annotate_missed_heads.py`, 115/117 frames)
      — 3-way 75%/15%/10% mix, 10 epochs; best MAE=3.22 (epoch1) but correlation dropped to 0.410, bias flipped to undercounting, SCUT-HEAD regression on epoch2. Not adopted.
- [x] **Hard-negative Round 3 (NOT adopted):**
      — Rebalanced to 84%/8%/8% mix, 15 epochs, from round 2 best-correlation checkpoint
      — Best MAE=2.81 (epoch15, 27% vs round 1) but correlation ceiling never broken (best 0.435)
      — Key pattern across 3 rounds (33 epochs): MAE 9.46→3.87→3.22→2.81, correlation stuck ≤0.448
      — sit2 clip is persistent correlation drag every round (r 0.15–0.35 range, unresolved)
- [ ] **Hard-negative Round 4 (in progress):**
      — Same 84%/8%/8% mix, from round 3 epoch15, **LR raised 1e-5 → 5e-5** (first LR change across all rounds)
      — Spike guard added; result pending
- [x] `annotate_missed_heads.py` (matplotlib click-annotation tool, runs locally) committed to `/scripts`
- [x] `hardpos_annotations.json` (490 missed-head points, 115/117 frames) committed to `/scripts`
- [!] **CRITICAL — Deploy adopted model:** Main app `models/` folder still missing `classcan_density_v4_hardneg_ft_epoch4` float32 TFLite. App silently falls back to COCO SSD at runtime. Must export epoch4 checkpoint and replace `classcan_density_float32.tflite`.
- [ ] **Live end-to-end camera test:** OV4689 frame → TFLite density model → headcount on Pi (never done)
- [!] **Security:** Roboflow API key pasted in plaintext into shared Colab notebooks/docs multiple times (deliberately kept in scripts this session). **Rotate immediately** in Roboflow dashboard → Account Settings → API Keys.

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
- **Model Architecture:** Custom Keras MobileNetV3-Large + 416×416 FPN head detector (3-head feature pyramid at 52×52/26×26/13×13, occupancy-based target encoding, focal loss + smooth-L1). Chosen after exhausting MobileNetV2+300 baseline and ruling out 4 improvement paths. V3+416 epoch-60 scored F1=30.1% vs V2+300 epoch-60 F1=19.5%. See `docs/design_rationale.md` ADR-03.
- **Density-Map Regression Pivot:** Switched from box-detection (tiled+NMS) to density-map regression after V3+416 work. Density model (`classcan_density_v4`) achieves MAE=2.13/r=0.9951 on SCUT-HEAD validation vs box-detector MAE=3.65–3.84/r=0.986. Pivot confirmed correct.
- **Hard-Negative Fine-Tuning:** Domain-gap test on 5 real classroom clips (117 frames) showed MAE=9.46, r=0.373 — large cliff from SCUT-HEAD's clean/orderly scenes to real chaotic PH classrooms. Root cause: hallucinating head density on backpacks/chairs/headrests. Fixed via hard-negative fine-tuning (176 confirmed FP objects), reducing real-footage MAE to 3.87 (↓59%) and bias from +9.37 to +2.33. Adopted model: `classcan_density_v4_hardneg_ft_epoch4`.
- **Labeling Convention:** Single "head" class with head-and-shoulders bounding boxes (not full-body COCO) ensures robust detection of students seated behind wooden armchairs at 30°–50° ceiling pitch angles.
- **Compute-Aware Triggering:** Periodic snapshot + frame-difference re-detection to prevent thermal throttling and compute saturation on the Pi 3B. See `docs/design_rationale.md` ADR-04.
- **LoRa Rejected:** Considered (offered cheaply by a colleague) but explicitly rejected. Project is single-room/local — Pi↔ESP32 communicate over USB serial, no long-range wireless needed. Would only reconsider if scope expands to multi-room/multi-building deployment.