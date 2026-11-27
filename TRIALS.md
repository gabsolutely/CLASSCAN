# CLASSCAN — Trial Log

Records of physical build trials, what failed, what was observed, and what changes were made as a result.

---

## Trial 1 — Build & First Live Run (Nov 12, 2026)

### Context

First attempt at running the full hardware stack together: Pi + camera + ESP32 + servos + LCD.
The ESP32 was placed on a **breadboard** (not yet soldered). Servos and LCD also had to be breadboarded for this trial.

### Hardware Configuration at Time of Trial

| Component | Pin / Setting | Notes |
|---|---|---|
| Pan Servo (MG90S) | D12 | Trial config — not yet the final GPIO18 |
| Tilt Servo (MG90S) | D13 | Retained in final config |
| LCD SDA (PCF8574) | D14 | Same as final |
| LCD SCL (PCF8574) | D27 | Same as final |
| ESP32 | Breadboard | Not yet soldered |
| Camera flip | Off | Ceiling-down mount not yet accounted for |
| Servo sweep speed | 120 (fast) | `SERVO_SWEEP_MOVE_MS = 4000` |
| Zone dwell | 800 ms | Fixed dwell, no zone handshake |
| Inference trigger | Every frame | No wait for servo to settle |
| Zone reporting | Each slice = room total | No accumulator |

### Issues Found

#### 1. LCD lit up but stayed blank
- The LCD backlight powered on, but no characters appeared.
- **Root cause:** Likely an I2C address mismatch (0x27 vs 0x3F) or insufficient `Wire.begin()` delay before LCD init. The PCF8574 backpack did not acknowledge writes.
- **Decision:** Deferred LCD debugging. Headcount displayed on the dashboard instead for trials.

#### 2. Inference ran during servo motion → blurry frames
- The Pi triggered AI inference continuously regardless of whether the servo was moving.
- Blurry motion frames fed into the density model produced wildly inaccurate counts.
- **Root cause:** No synchronization between servo position and inference timing.

#### 3. Each zone slice counted as the full-room total
- In the original sweep mode, each inference result was reported as the total headcount for the entire room.
- As the servo rotated through the room, the displayed count jumped: e.g., 6 → 11 → 4 → 0.
- **Root cause:** No accumulator — each narrow 60° slice was treated as a complete count.

#### 4. Camera mounted upside-down — 42% undercounting
- The OV4689 is mounted ceiling-down. Frames were fed to the AI model in the original (inverted) orientation.
- The v5 density model was trained on upright images. Inverted frames caused severe undercounting.
- **Measured:** Upright frame → 12 people. Same frame inverted → 7 people (~42% loss).

#### 5. Pan servo on D12 — pin conflict potential
- D12 is a boot-strapping pin on the ESP32 (affects SPI flash boot mode).
- Not an active failure during trial, but flagged as unreliable for production.

### Fixes Applied After Trial 1

| Issue | Fix | Where |
|---|---|---|
| LCD blank | Deferred — use dashboard for now | — |
| Inference during motion | `zone_ready` handshake: ESP32 signals Pi when turret is settled and stationary before inference fires | `servo_controller.h`, `serial_bridge.py`, `main.py` |
| Each slice = room total | Option B 4-Quadrant Accumulator: each zone count is stored; total = sum of all 4 zones after full cycle | `main.py`, `serial_bridge.py` |
| Camera upside-down | `CAMERA_FLIP = True` in `config.py`; frame is flipped 180° before inference | `detector.py`, `main.py` |
| Pan servo on D12 | Remapped to **GPIO 14** (`PIN_PAN = 14`, tilt on GPIO 13, LCD on GPIO 21/22) | `config.h` |
| Servo too fast → blur | `SERVO_SWEEP_MOVE_MS` 4000 → **8000 ms**; speed 120 → **104** | `config.h` |
| `NEXT_ZONE` handshake | Pi sends `NEXT_ZONE` command to ESP32 after inference completes; ESP32 advances to next quadrant | `main.cpp`, `serial_bridge.py` |
| Noise floor (AND cutoff) | Noise cutoff changed from OR to AND (`raw_sum < 0.5 AND peak < 0.025`) to avoid dropping real low-angle detections | `detector.py` |
| Trial result logging | Each completed 4-zone cycle logged to `trial_log.csv` (timestamp, total, Q1–Q4 counts) | `main.py` |
| Zone progress on dashboard | Zone chips (Q1 ✓ Q2 ⟳ Q3 — Q4 —), scan status badge, cycle-complete banner, Rescan button added | `app.js`, `index.html`, `styles.css` |

### Outcome

The system ran but produced unreliable headcounts due to the four issues above. The LCD was non-functional; the dashboard was used instead. All issues were diagnosed and fixes were committed before Trial 2.

---

## Earlier Milestones (Pre-Trial)

### First Live End-to-End Run
- Pi, OV4689 camera, and v5 density model ran together successfully on first attempt.
- Dashboard connected and displayed counts.
- **Known issues:** Frame delivery was inconsistent; detection lagged behind video; not tested with 5+ people.

### First v5 Model Run on Pi Hardware
- v5 density model (`classcan_v5_final.tflite`) run against hand-counted test images on the Pi.
- Results: `12.08` vs hand count `11–12` ✓ · `3.35` vs `3` ✓ · `1.90` vs `1` ✓
- Confirmed the model is viable on-device before physical trials.

### PoC Presentation
- Live prototype did not work during the presentation (hardware not ready in time).
- A pre-recorded demo video had already been submitted — presentation went well.

---

## Trial 2 — System Trial (Pending)

> Status: Firmware and Pi software updated with all Trial 1 fixes. Awaiting physical run.

Planned configuration:
- **No perfboard and no 18650 battery / charge-boost modules** — powered from wall 5V PSU via a soft high-current Type-C power cable (+ 5.1kΩ Micro-USB adapter/tap) entering through the `15×10 mm` wall pass-through slot (unused charger hole omitted; rocker switch hole repurposed)
- **Two-part wiring harness:** ESP32 and LCD2004 part-side terminal wires **hot-glued** directly at the pins/backpacks; mid-span wire-to-wire joints **electrical-taped (not glued)** so components can be disconnected for troubleshooting inside the enclosure
- **Soft flexible data-carrying Type-C cable** for OV4689 camera so MG90S servos can pan/tilt freely without stiff-cable drag
- Pan servo on GPIO 14, tilt on GPIO 13, LCD on GPIO 21 (SDA) / GPIO 22 (SCL)
- LCD debugging deferred — dashboard as primary display
- `MODE = "ZONE_CHECK"` (4-Quadrant Accumulator, Option B)
- `CAMERA_FLIP = True`
- `SERVO_SWEEP_MOVE_MS = 8000`, speed = 104
- `zone_ready` / `NEXT_ZONE` handshake active
- 3-shot median inference per zone (`predict_multicapture`)
