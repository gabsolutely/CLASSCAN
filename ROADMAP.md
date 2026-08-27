# CLASSCAN — Sept 28 PoC Scope

**Full project vision:** intelligent classroom headcount system (CV + LED display + dashboard).
**This document:** the *minimum* that must work by Sept 28 to prove the core claim: **camera → Pi → detection → count shown somewhere.** Everything else is deferred.

Status: Core architecture locked. Hardware sourcing in progress (Pi 3B in hand; camera + microSD reader being ordered now due to laptop wipe / shipping lag).

---

## PoC Goal

Prove the core pipeline works end-to-end:

```
[OV4689 camera] → [Pi 3B: capture frame → TFLite person detection] → [count displayed]
```

"Displayed" for the PoC = a number on screen (dashboard/terminal/log), **not** the LED matrix.

## In Scope for Sept 28

- Camera captures a frame on the Pi 3B (driver-free UVC, confirmed working)
- TFLite MobileNetV2-SSD runs inference on that frame, detects "person" class
- A count is produced and shown somewhere visible (simple laptop-side view or console output is fine)
- Basic periodic-snapshot loop (capture → detect → repeat), even without the full change-trigger logic yet

## Explicitly Deferred (post-PoC)

- Pan/tilt servos, sweep mode, quadrant/zone targeting
- LED matrix display
- Custom LDR-triggered illumination module
- 3D-printed enclosure
- 18650 battery/swappable power
- Change-detection trigger + ESP32 idle/moving handshake
- Quadrant self-consistency reconciliation
- Full bidirectional dashboard commands (mode switch, zone-check)

These are real, designed, and staying in the full architecture doc — just not required to prove the pipeline works.

## Hardware — PoC Only

| Component | Status |
|---|---|
| Raspberry Pi 3B (1GB) | In hand |
| ESP32 | In hand, **not required for PoC** (no serial link needed until servos/LED matrix come back in) |
| OV4689 4MP BSI USB Camera (UVC, Type-C) | Ordering now |
| USB microSD card reader | Ordering now — blocking, can't flash Pi without it |
| microSD 32GB Class10/A1 (optional) | Ordering now if current 16GB feels tight |
| Power supply | Confirmed working |

## Design Notes Carried Over (still valid, just not built yet)

- Android build will be debloated (not stock Raspberry Pi OS) to free the Cortex-A53 for TFLite — same philosophy as a prior award-winning Orange Pi PC/H3 project (~30 FPS), not yet benchmarked on this board
- MobileNetV2-SSD chosen over EfficientDet-Lite/YOLO variants for CPU-only inference speed/accuracy trade-off
- Live continuous-stream inference is a known risk on this hardware tier; periodic snapshot detection is the long-term strategy (full change-trigger logic is deferred, see above)
- No facial recognition, no identity logging — occupancy/count only

## Open Items for the PoC Specifically

- [ ] Order microSD reader + OV4689 camera (today/tomorrow)
- [ ] Flash debloated Android build on Pi 3B once parts arrive
- [ ] Confirm OV4689 works driver-free on that build
- [ ] Get a basic TFLite MobileNetV2-SSD inference loop running on a captured frame
- [ ] Wire up minimal count display (dashboard view or console is fine for PoC)
- [ ] End-to-end test with real people in frame

## Repository Structure

```
/docs      → Scope & Delimitation, Significance, BOM, full design docs
/cad       → Enclosure design files/renders (post-PoC)
/src       → (planned) CV model, detection logic, display driver
/hardware  → (planned) wiring diagrams, GPIO pinout
```

---

*Full-feature architecture (quadrant zoning, servo sweep, custom illumination, LED matrix, dashboard commands) remains the target end-state and is documented separately — this file exists so PoC work doesn't get built against the full-feature vision under time pressure.*