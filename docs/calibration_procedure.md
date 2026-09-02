# CLASSCAN — Calibration Procedure & Field Commissioning Guide

This document outlines the step-by-step physical and software calibration workflow required after mounting the CLASSCAN turret in a target classroom.

---

## 1. Physical Mounting & Mechanical Alignment

```
       [Ceiling Baseplate]
             │
             ├── Pan Servo (MG90S) — 0° to 180° Horizontal
             │      │
             │      └── Tilt Servo (MG90S) — 0° to 60° Downward Pitch
             │             │
             │             └── OV4689 Camera + LED Illumination Module
             ▼
      [Classroom Center @ 2.5m – 3.0m Elevation]
```

1. **Mounting Location:**
   - Install the turret baseplate at the geographic center or front-center of the classroom ceiling.
   - Recommended ceiling height: **2.5 meters to 3.0 meters** above finished floor level.
2. **Mechanical Zero Alignment:**
   - Before securing servo horns, command both servos to their default zero positions:
     - **Pan Servo:** Set to $90^\circ$ (center facing forward toward the back of the classroom).
     - **Tilt Servo:** Set to $30^\circ$ (pointing downward at a $30^\circ$ angle from horizontal).
   - Fasten the servo horns ensuring the camera lens points directly along the classroom center line.

---

## 2. Pan/Tilt Quadrant Angle Calibration

The classroom is divided into four spatial quadrants:
- **Quadrant 1 (Q1):** Front-Left Seating
- **Quadrant 2 (Q2):** Front-Right Seating
- **Quadrant 3 (Q3):** Rear-Right Seating
- **Quadrant 4 (Q4):** Rear-Left Seating

```
┌─────────────────────────┬─────────────────────────┐
│       QUADRANT 1        │       QUADRANT 2        │
│       (Front-Left)      │       (Front-Right)     │
│   Pan: 0° | Tilt: 35°   │   Pan: 60° | Tilt: 35°  │
├─────────────────────────┼─────────────────────────┤
│       QUADRANT 4        │       QUADRANT 3        │
│       (Rear-Left)       │       (Rear-Right)      │
│   Pan: 180° | Tilt: 25° │   Pan: 120° | Tilt: 25° │
└─────────────────────────┴─────────────────────────┘
                   [TURRET ORIGIN]
```

### Calibration Steps:
1. Open the wireless dashboard on a laptop connected to the turret's Wi-Fi network: `http://<pi-ip>:8080`.
2. Switch the system to **ZONE_CHECK** mode.
3. Observe the camera field of view for each quadrant dwell position.
4. If a quadrant is misaligned, update the coordinate lookup table in `src/esp32/include/servo_controller.h`:
   ```cpp
   static const ZoneEntry ZONE_TABLE[] = {
       {"Q1",   0, 35},  // {Zone Name, Pan Degrees, Tilt Degrees}
       {"Q2",  60, 35},
       {"Q3", 120, 25},
       {"Q4", 180, 25},
   };
   ```
5. Update the corresponding zone dictionary in `src/pi/config.py`:
   ```python
   ZONE_POSITIONS = {
       "Q1": (0,   35),
       "Q2": (60,  35),
       "Q3": (120, 25),
       "Q4": (180, 25),
   }
   ```
6. Re-flash the ESP32 via `pio run -t upload` and restart the Pi service.

---

## 3. LDR Illumination Threshold Calibration

The ambient light sensor (LDR) reads analog values via the ESP32 ADC (0 to 4095; lower values indicate darker environments).

### Calibration Steps:
1. Measure the raw ADC reading during **Normal Daytime Lighting** (classroom fluorescent lights ON + natural daylight):
   - Typical ADC reading: `2200 – 3400`.
2. Measure the raw ADC reading during **Dim / Evening Conditions** (overcast day or lights OFF):
   - Typical ADC reading: `600 – 1300`.
3. Set `LDR_DIM_THRESHOLD` in `src/esp32/include/config.h` to the midpoint between dim and normal conditions:
   ```cpp
   // Typical calibrated threshold:
   #define LDR_DIM_THRESHOLD  1500  // Values below 1500 activate white LED illumination
   ```
4. **Verification:** Cover the LDR with a finger or darken the room. Verify that the custom LED illumination array activates instantly and turns off when normal lighting resumes.

---

## 4. Frame Change-Trigger Sensitivity Calibration

The `ChangeTrigger` module computes the normalized mean absolute difference between consecutive video frames to detect movement (students entering, leaving, or changing seats).

### Calibration Steps:
1. In `src/pi/config.py`, locate the change threshold constant:
   ```python
   CHANGE_THRESHOLD = 0.15  # Default: 15% normalized mean frame difference
   ```
2. **Sensitivity Guidelines:**
   - **Decrease threshold (`0.08 – 0.12`):** Increases sensitivity. Use if subtle student movements or single-person entry is missed.
   - **Increase threshold (`0.18 – 0.25`):** Decreases sensitivity. Use if fluctuating ceiling fan shadows, window curtain breeze, or fluorescent light hum cause spurious re-detections.
3. Test by having a person walk into the room. Verify on the dashboard console that a re-detection is triggered immediately without waiting for the 10-second heartbeat timer.

---

## 5. Zone Reconciler Tolerance Tuning

The `ZoneReconciler` verifies that the sum of quadrant counts matches the full-room count within a configurable tolerance.

1. In `src/pi/config.py` / `src/pi/main.py`:
   ```python
   reconciler = ZoneReconciler(zone_names=["Q1", "Q2", "Q3", "Q4"], tolerance=1)
   ```
2. **Tolerance Rules:**
   - `tolerance = 1`: Standard for 30–50 seat classrooms. Accommodates 1 student sitting on the visual boundary between two quadrants.
   - `tolerance = 2`: Recommended for large lecture halls with wider field overlap.

---

## 6. Field Commissioning Checklist

| Step | Verification Task | Expected Result | Pass/Fail |
|:---:|---|---|:---:|
| **1** | Power-on initialization | Pi 3B boots headless; ESP32 initializes servos to home ($90^\circ, 30^\circ$) | [ ] |
| **2** | Serial communication link | ESP32 reports `{"type":"state","value":"idle"}` to Pi over USB serial | [ ] |
| **3** | Web dashboard connectivity | Browser loads `http://<pi-ip>:8080`, live MJPEG stream is active | [ ] |
| **4** | LDR illumination trigger | Dimming room switches LED array ON; ADC reading drops below threshold | [ ] |
| **5** | Continuous sweep mode | Turret smoothly sweeps between $0^\circ$ and $180^\circ$ pan | [ ] |
| **6** | Zone mode step & dwell | Turret cycles through Q1 $\to$ Q2 $\to$ Q3 $\to$ Q4, dwelling 800ms at each | [ ] |
| **7** | Real-time detection accuracy | Seated test students in Q1–Q4 detected with bounding boxes and HUD count | [ ] |
| **8** | LED Matrix update | Local MAX7219 matrix displays exact integer headcount reported by Pi | [ ] |
