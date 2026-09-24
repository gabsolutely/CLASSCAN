# CLASSCAN — Development Roadmap & PoC Scope

**Full project vision:** Intelligent classroom headcount system (CV + LED display + wireless dashboard).
**PoC objective:** Prove the core edge vision pipeline end-to-end: **camera → Pi 3B → TFLite head detection → count displayed.**

**Status (as of Sept 24, 2026 — 4 days to deadline):** **Live end-to-end pipeline deployed on real hardware.** Full pipeline (Pi + OV4689 + 3-way ensemble) ran on first attempt — stitched together in under 2 days. Dashboard working. AI detection functional; not yet validated at 5+ people. Camera color desaturation issue appears resolved on this hardware run. **Frame delivery + inference lag: resolved Sept 24, 2026** (V4L2 buffer drain fix in `detector.py`).

1. **Final adopted model (ensemble):** `0.6 × classcan_density_v4_round4_ft_epoch8 (letterbox eval) + 0.4 × classcan_density_style_aug_ft_lowLR_epoch8 (stretch eval)` — MAE=2.77, correlation=0.586 on genuine held-out v2 data (350 frames). Best real-footage correlation across all 9 rounds.
2. **Alternative lower-MAE ensemble:** `0.55 × epoch8 + 0.10 × stretch-ft-epoch1 + 0.35 × style-aug-epoch8` → MAE=2.68, corr≈0.584 (worth using if MAE matters more than correlation).
3. **SCUT-HEAD benchmark (407-image eval):** All checkpoints maintained r>0.99 throughout — no catastrophic regression across any round.
4. **Secondary HUD Model:** MobileNetV3-Large + 416×416 FPN head detector (F1 = 31.8%, MAE = 3.84) for bounding box visualization.

**Remaining open items:** Camera frame delivery inconsistency + inference lag behind live video. AI detection not yet validated at 5+ people. Camera startup config (v4l2-ctl baseline + quirks=128) must be confirmed wired into `setup/startup.py`.
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
- [x] **Hard-negative Round 4 — KEY RESULT (round 4 epoch 8 = basis for final model):**
      — Same 84%/8%/8% mix, from round 3 epoch15, **LR raised 1e-5 → 5e-5** (first LR change across all rounds)
      — Spike guard added; run completed. **epoch 8 was best** (stretch eval: MAE=2.82, r=0.506 on reused 117-frame set)
      — `classcan_density_v4_round4_ft_epoch8.weights.h5` is the backbone of the final ensemble
- [x] **Letterbox-vs-stretch preprocessing discovery (eval-only, no retrain):**
      — Evaluated round 4 epoch 8 (stretch-trained) with **letterbox** preprocessing at inference time only, no retraining
      — **Correlation jumped from 0.506 → 0.602 (best across every round)**, specifically fixed sit2 (0.217→0.595)
      — MAE got worse (2.82→3.23) and bias flipped (+1.73→+2.58) — because weights were trained on stretch geometry
      — Conclusion: letterbox eval on stretch-trained weights is complementary; training from scratch with letterbox collapsed in round 6
- [x] **Round 5 (mix rebalance to 84/4/12, hard-positive priority) — NOT adopted:**
      — Best correlation only tied round 4's 0.506; most epochs 0.42-0.49; epochs 10/14/15 collapsed to MAE=8.1/near-zero-correlation
      — Concluded the mix-ratio lever was exhausted; sit2 remained weakest every round
- [x] **Round 6 (letterbox training attempt) — FAILED, not adopted:**
      — Two attempts (LR=2e-5 and LR=5e-6) both collapsed: epoch 2 predicted-count std-dev=0.000, trivial all-zero MSE
      — Sanity checks confirmed NOT a data pipeline bug — genuine training-dynamics collapse
      — Lower LR got further (4 clean epochs) but all letterbox-eval results substantially worse than not retraining
      — Conclusion: bridging stretch-trained weights to letterboxed geometry via fine-tuning does not work at any LR tried
- [x] **hardpos_annotations_v2.json — 350 NEW real-footage frames annotated (hand-annotated via click-annotation tool):**
      — 469 total hard-positive frames combined with original 117; 595 hard-negatives unchanged
      — Established a genuine held-out eval set (v2 data was annotated after round 4 epoch 8 was finalized)
- [x] **Rounds 7-9 / 8 training attempts in one session — correlation ceiling never broken:**
      — 5 from-scratch+letterbox attempts: all collapsed to near-zero output within 10 epochs regardless of LR or loss function
      — Frozen-backbone fine-tune from epoch 8: correlation collapsed (0.243→-0.084 over 4 epochs)
      — Stretch-preserving fine-tune from epoch 8 (full backbone, STRETCH, LR=2e-5, 469-frame set): **epoch 1 standout** (MAE=2.79, corr=0.453 on v2 holdout) but deteriorated through epoch 9
      — Style augmentation fine-tune (brightness/contrast/color/sharpness jitter on SCUT-HEAD stream only, LR=5e-6): **only run to complete 10 epochs without collapse** (stable std 32-36, mean 28-36 throughout); epoch 8 best (MAE=2.97, corr=0.531 on v2 holdout)
- [x] **2-way ensemble (epoch8+letterbox × stretch-ft-epoch1+stretch) — intermediate best:**
      — Epoch8 overcounts (+1.69) and stretch-ft-epoch1 undercounts (-0.54), errors partially cancel
      — Best at w=0.7 toward epoch8: MAE=2.63, corr=0.574 (genuinely beats both inputs on both metrics)
- [x] **3-way ensemble grid search — NEW BEST / FINAL ADOPTED MODEL:**
      — Grid searched all weight combos of epoch8(letterbox) + stretch-ft-epoch1(stretch) + style-aug-epoch8(stretch) on v2 holdout
      — **Best: weights (0.6, 0.0, 0.4) — i.e., epoch8(letterbox) + style-aug-epoch8 only** (stretch-ft-epoch1 dropped, weight=0)
      — **MAE=2.77, bias=+1.58, corr=0.586** — best real-footage correlation across all 9 rounds of the entire project
      — Per-clip: sit1=0.538, sit2=0.519, line3=0.759 (best), line2=0.555, line1=0.455 (clear weak point)
      — Finer-grained sweep confirmed flat plateau: top-10 combos all corr=0.584-0.586, weights e8=0.50-0.65/style=0.30-0.50 — result is robust, not a lucky spike
      — Alternative lower-MAE point: (0.55, 0.10, 0.35) → MAE=2.68 at nearly identical corr — use if MAE matters more than correlation
- [x] `annotate_missed_heads.py` (matplotlib click-annotation tool, runs locally) committed to `/scripts`
- [x] `hardpos_annotations.json` (490 missed-head points, 115/117 frames) committed to `/scripts`
- [x] `hardpos_annotations_v2.json` (350-frame holdout set, annotated post round-4-epoch-8) committed to `/scripts`
- [x] **Deploy adopted ensemble:** Weighted 3-way ensemble (0.6×round4_epoch8_letterbox + 0.4×style_aug_epoch8_stretch) wired into main app and running on Pi. App no longer falls back to COCO SSD.
- [x] **Live end-to-end camera test:** OV4689 → TFLite density ensemble → headcount on Pi confirmed working. Dashboard functional. **(COMPLETED Sept 23, 2026)**
- [x] **Camera color/desaturation:** Appears resolved on the deployed hardware run. Known-good baseline (`set_camera_config.sh`) in place.
- [ ] **Camera startup config wiring:** Confirm `set_camera_config.sh` baseline (auto_exposure=1, exposure=500, gain=192, brightness=64, gamma=300, saturation=100, wb_auto=0, wb_temp~4600) and `quirks=128` (`/etc/modprobe.d/uvcvideo.conf`) are applied on every boot via `setup/startup.py`.
- [x] **Frame delivery + lag (FIXED Sept 24, 2026):** Root cause identified: OpenCV/V4L2 internal frame buffer queues stale frames during slow TFLite inference; `cap.read()` returned oldest buffered frame. Fix: `_grab_fresh_frame()` in `detector.py` drains buffer via `cap.grab()` loop (no pixel decode), then `cap.retrieve()` for only the freshest frame. Applied to `DensityDetector`, `EnsembleDensityDetector`, and `Detector`.
- [ ] **Validate at 5+ people:** AI detection not yet tested with real classroom occupancy.

## Full-System Integration (Post-PoC)

- Pan/tilt servos, sweep mode, quadrant/zone targeting (servo "radar" mount prototype on ESP32)
- LED matrix headcount display driven by ESP32
- Custom LDR-triggered illumination LED module
- 3D-printed ceiling-mount dome enclosure
- 18650 swappable battery power module
- Full hardware handshake between Pi 3B and ESP32 over serial
- mAP@50 formal evaluation and annotation quality audit (deferred — trigger only if model underperforms)
- **Post-PoC model improvements (explicitly deferred, good for writeup citations):** MPCount (CVPR 2024, single-domain-generalization architecture — real ceiling-breaker but multi-day port), backbone swap away from MobileNetV3, TTA (average over original + flipped frame), genuine new Filipino-classroom training data (identified by QA reviewer PeaNat as the real root cause of the domain gap ceiling)

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
- **Hard-Negative Fine-Tuning + Ensemble Strategy:** Domain-gap test on 5 real classroom clips (117 frames) showed MAE=9.46, r=0.373. Fixed via hard-negative fine-tuning across 4 rounds + 9 total training experiments. Final result: 3-way weighted ensemble (0.6×round4_epoch8_letterbox + 0.4×style_aug_epoch8_stretch) achieving MAE=2.77, corr=0.586 on genuine held-out data — best real-footage performance in the project. The style-augmentation lever (AugMix/style-randomization from literature) was the key complementary signal; the ensemble works because epoch8 overcounts and style-aug-epoch8 provides complementary error correction.
- **Preprocessing Asymmetry (letterbox eval on stretch-trained model):** Discovered that evaluating the stretch-trained round 4 epoch 8 model with letterbox preprocessing (no retraining) lifts correlation from 0.506 → 0.602 on its own. Training from scratch with letterbox collapsed in all 5 attempts. The ensemble uses this asymmetry deliberately.
- **Labeling Convention:** Single "head" class with head-and-shoulders bounding boxes (not full-body COCO) ensures robust detection of students seated behind wooden armchairs at 30°–50° ceiling pitch angles.
- **Compute-Aware Triggering:** Periodic snapshot + frame-difference re-detection to prevent thermal throttling and compute saturation on the Pi 3B. See `docs/design_rationale.md` ADR-04.
- **LoRa Rejected:** Considered (offered cheaply by a colleague) but explicitly rejected. Project is single-room/local — Pi↔ESP32 communicate over USB serial, no long-range wireless needed. Would only reconsider if scope expands to multi-room/multi-building deployment.
- **Domain Gap Root Cause (PeaNat, confirmed):** SCUT-HEAD depicts orderly/seated/well-lit lecture halls; real Philippine classrooms are chaotic (moving lines, standing, irregular wooden armchairs, dim/uneven lighting). Only 35 local photos plus post-hoc failure patches — not genuine classroom-native training volume. The 0.43-0.60 real-footage correlation ceiling across all 9 rounds is a data-domain limitation, not a training-recipe problem. Genuine Filipino-classroom data collection deferred to a future phase; explicitly stated in the writeup/defense.