# CLASSCAN — Scope & Delimitation

**Project Title:** Development of an Intelligent Classroom Headcount Monitoring System using Computer Vision and LED Display Technology  
**Institution:** Philippine Christian University – Dasmariñas (PCU-D)  
**Target Domain:** Edge AI / Computer Vision / Embedded Systems

---

## 1. System Overview

CLASSCAN is an automated, ceiling-mounted edge computer vision turret engineered to monitor classroom occupancy and headcount in real time. The system processes visual data locally on a Raspberry Pi 3B using a lightweight TensorFlow Lite object detection model, broadcasts live counts and frame snapshots to a local wireless web dashboard, and drives a local dot-matrix LED display via an ESP32 microcontroller.

---

## 2. In-Scope Capabilities (What the System Does)

The system is designed and verified to perform the following core operations:

1. **Edge-Based Head and Occupancy Detection:**
   - Detects people in classroom seating using a lightweight single-class **"head"** (head-and-shoulders) TFLite object detection model (`yololite_nano_head_classcan.tflite`).
   - Executes all image preprocessing, tensor inference, and non-maximum suppression locally on the Raspberry Pi 3B quad-core ARM Cortex-A53 CPU without external cloud offloading.

2. **Compute-Aware Triggering:**
   - Employs a hybrid inference schedule combining a baseline heartbeat interval (default: 10 seconds) with an immediate motion-triggered re-detection mechanism (`ChangeTrigger`) based on normalized frame differencing.
   - Suppresses unnecessary inference runs during periods of room stagnation, preserving CPU headroom and avoiding thermal throttling on edge hardware.

3. **Dual-Tier Hardware Architecture (Pi 3B + ESP32):**
   - **Pi 3B (Brain):** Video capture via UVC, frame differencing, TFLite inference, zone reconciliation, dashboard web server, and serial command bridging.
   - **ESP32 (Hands):** Real-time pan/tilt servo PWM control, analog ambient light monitoring via LDR, driving custom LED illumination, and refreshing the local LED matrix headcount display.
   - **Autonomous Failsafe:** The ESP32 maintains room sweeping, lighting regulation, and local LED count display independently if the Pi 3B or local Wi-Fi connection is disrupted.

4. **Macro-Quadrant Spatial Zoning & Self-Consistency Checking:**
   - Divides the room into four macro quadrants (**Q1–Q4**) via calibrated pan/tilt angles.
   - Operates in either **Continuous Sweep Mode (`SWEEP`)** for general occupancy or **Sequential Quadrant Mode (`ZONE_CHECK`)** for localized sector counts.
   - Implements a self-consistency validation module (`ZoneReconciler`) that compares the sum of quadrant counts against the last known room total and automatically requests a re-scan upon discrepancy.

5. **Wireless Web Dashboard & Remote Control:**
   - Hosts an asynchronous HTTP/MJPEG web server directly on the Pi 3B over local Wi-Fi (`http://<pi-ip>:8080`).
   - Streams live annotated video frames with a heads-up display (HUD) overlay showing bounding boxes, confidence scores, FPS, operating mode, and quadrant breakdowns.
   - Accepts mode-switch (`MODE_SWEEP`, `MODE_ZONE`) and targeted quadrant inspection commands from authorized client browsers.

6. **Automated Scene Illumination:**
   - Continuously samples ambient classroom illumination via an analog Light Dependent Resistor (LDR).
   - Activates a dedicated custom white LED illumination module when ambient light drops below a calibrated threshold (`LDR_DIM_THRESHOLD`), ensuring consistent detection accuracy during overcast or evening sessions.

7. **Swappable Battery Power:**
   - Operates untethered using a dual 18650 Li-ion battery pack with onboard charge management (TP4056/BMS) and 5V step-up voltage regulation, enabling flexible mounting and field testing across various classrooms.

---

## 3. Delimitations & Out-of-Scope (What the System Does NOT Do)

To preserve system focus, privacy compliance, and real-time edge viability, the following capabilities are explicitly delimited from the project scope:

1. **No Facial Recognition or Individual Identification:**
   - The vision model is strictly trained for generic head-and-shoulders localization (`head` class).
   - The system does not extract facial landmarks, compute facial embeddings, or match faces against student databases.

2. **No Named Attendance Logging or Record-Keeping:**
   - CLASSCAN functions strictly as a headcount and occupancy monitoring tool. It does not record student names, attendance timestamps, or student ID numbers.

3. **No Continuous Cloud Streaming or External API Dependencies:**
   - The architecture is strictly edge-first and air-gapped. Visual frames and raw telemetry remain within the local area network (LAN); no visual data is transmitted to third-party cloud services.

4. **No Persistent Video Recording or Surveillance Storage:**
   - Video frames are captured to volatile RAM for inference and MJPEG dashboard streaming. No video recordings or surveillance archives are stored to disk or external storage media.

5. **No Granular Per-Seat Micro-Tracking:**
   - Seating zones are scoped to four macro quadrants (Q1–Q4). The system does not track micro-level individual desk allocations, ensuring robustness against students shifting seats within the same desk row or cluster.

6. **Single-Turret Sequential Field of View:**
   - As a single-turret scanning device, the camera observes one sector at a time. Zone presence represents the state captured during the most recent dwell pass rather than instantaneous 360-degree visibility.

---

## 4. Target Operational Environment & Constraints

- **Physical Space:** Standard Philippine classroom layout (approx. 7m × 9m, capacity: 40–50 students) equipped with wooden/plastic armchairs arranged in rows.
- **Mounting Position:** Ceiling-mounted at the center or front-center of the room at an elevation of 2.5m to 3.0m with a downward pitch angle of 30° to 50°.
- **Ambient Illumination Range:** 50 lux (dim evening classroom) to 500+ lux (bright daylight).
- **Target Inference Speed:** ≤ 300 ms per frame on Raspberry Pi 3B CPU.
