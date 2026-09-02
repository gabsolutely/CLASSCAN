# CLASSCAN — Architectural Design Rationale & Decision Records

This document details the engineering principles, architectural trade-offs, and technical rationale underlying the hardware and software design of the CLASSCAN system.

---

## ADR-01: Operating System Selection — Raspberry Pi OS Lite (64-bit) vs. Debloated Android

### Context
Running neural network inference and computer vision pipelines on constrained single-board computers (SBCs) like the Raspberry Pi 3B requires maximizing available CPU cycles, memory bandwidth, and thermal headroom. Prior research in edge AI prototyping often explores custom debloated Android builds (e.g., LineageOS/Android Things) for lightweight execution.

### Decision
CLASSCAN deliberately standardizes on **Raspberry Pi OS Lite (64-bit Debian Bookworm/Bullseye)**.

### Rationale & Trade-offs
1. **Zero Display-Server Overhead:**
   - Raspberry Pi OS Lite boots directly into a headless terminal environment with X11, Wayland, and desktop composite managers completely omitted.
   - Idle RAM consumption is under 55 MB (leaving >900 MB free for inference tensors and frame buffers), and background CPU utilization remains under 1%.
2. **First-Class Driver & Kernel Stability:**
   - Linux Video4Linux2 (V4L2) kernel modules provide deterministic, low-latency USB video capture (`cv2.CAP_V4L2`) for UVC cameras like the OV4689.
   - Standard POSIX TTY drivers handle reliable full-duplex USB serial communication via PySerial without proprietary Android USB-host permission dialogues.
3. **Official LiteRT / TFLite Support:**
   - Google maintains official 64-bit ARM (`aarch64`) wheels for `ai-edge-litert` (and `tflite-runtime`), enabling native NEON SIMD vectorization on the Cortex-A53 cores.
   - Android builds introduce unnecessary Hardware Abstraction Layer (HAL) complexity, binder IPC latency, and non-standard toolchains that complicate continuous maintenance for solo developers.

---

## ADR-02: Heterogeneous Dual-Tier Architecture — Pi 3B (Brain) vs. ESP32 (Hands)

### Context
The system combines heavy computational tasks (neural network inference, HTTP MJPEG streaming, frame differencing) with real-time hardware I/O (PWM servo driving, analog sensor polling, LED matrix multiplexing).

### Decision
Adopt a decoupled, dual-tier architecture mirroring industrial robotics:
- **Raspberry Pi 3B ("The Brain"):** Dedicated high-level computing, computer vision, networking, and decision logic.
- **ESP32 Microcontroller ("The Hands"):** Dedicated deterministic physical I/O, PWM actuation, ADC sampling, and local display management.

```
┌─────────────────────────────────────────────────────────────┐
│                   RASPBERRY PI 3B (BRAIN)                  │
│                                                             │
│  [OV4689 UVC] ──► [ChangeTrigger] ──► [TFLite Detector]    │
│                           │                    │            │
│                   [ZoneReconciler] ◄───────────┘            │
│                           │                                 │
│                   [DashboardServer] (Wi-Fi 802.11n)         │
└───────────────────────────┬─────────────────────────────────┘
                            │ USB Serial (JSON @ 115200 baud)
┌───────────────────────────▼─────────────────────────────────┐
│                     ESP32 DEVKIT (HANDS)                    │
│                                                             │
│   ├── [ServoController] ──► Pan/Tilt Servos (PWM)           │
│   ├── [LdrIllumination] ──► LDR (ADC) + White LEDs (MOSFET)│
│   └── [LedMatrix]       ──► Local Count Display (MAX7219)   │
└─────────────────────────────────────────────────────────────┘
```

### Rationale & Trade-offs
1. **Real-Time Jitter Elimination:**
   - Software PWM on non-real-time Linux kernels is prone to scheduling jitter under heavy CPU loads (e.g., during model inference bursts), causing servo flutter and jerky camera sweeps. The ESP32's dedicated hardware PWM timers generate crystal-clean 50 Hz control pulses regardless of what the Pi is computing.
2. **Electrical Isolation & Back-EMF Protection:**
   - Servos can draw peak stall currents exceeding 800 mA, introducing voltage dips and inductive flyback spikes. Isolating servo power and control to the ESP32 tier protects the Pi's sensitive SoC from brownouts.
3. **Autonomous Failsafe Capability:**
   - The ESP32 firmware operates autonomously in a state-machine loop. If the Pi 3B reboots, drops off Wi-Fi, or crashes, the ESP32 continues sweeping the room, controlling scene illumination, and holding the last valid headcount on the LED display.
4. **Security by Isolation:**
   - The ESP32's onboard Wi-Fi radio is intentionally left uninitialized. Physical actuators cannot be addressed directly over the network; all physical commands must pass through the Pi's authenticated serial bridge.

---

## ADR-03: Vision Model Selection & Pivot — MobileNetV2-SSD vs. YOLOLite CPU (Nano) Single-Class "Head"

### Context
Initial baseline testing of the computer vision pipeline utilized a standard MobileNetV2-SSD model pre-trained on the COCO dataset (80 full-body classes).

### The Pivot Driver (Empirical Failure Analysis)
During physical benchmark trials across realistic classroom test photographs, MobileNetV2-SSD performed well on unobstructed, close-to-medium subjects (confidence scores: 0.72 – 0.98). However, when evaluated on a realistic wide-angle classroom shot with seated students in distant rows, the model recorded **0 detections** (all detections fell below the 0.50 confidence threshold).

```
Why Full-Body Models Fail in Classrooms:
┌────────────────────────────────────────────────────────┐
│ [Ceiling Camera @ 40° Angle]                           │
│        \                                               │
│         \ Visible cranial region & shoulders (15–20%)  │
│          ▼                                             │
│       [Head/Torso]                                     │
│      ══════════════ [Wooden Armchair Desk]             │
│       [Lower Body]  (80% completely occluded)          │
└────────────────────────────────────────────────────────┘
```

### Decision
Pivot model architecture to **YOLOLite CPU (Nano)** fine-tuned specifically for a single **"head"** (head-and-shoulders) class on elevated classroom datasets (SCUT-HEAD Part A + Local Classroom images).

### Rationale & Trade-offs
1. **Overcoming Desk Occlusion:**
   - Classroom furniture (standard wooden armchairs, study desks) physically conceals 70%–85% of a seated student's body. Full-body models rely heavily on limb, torso, and leg features. Training the detector to recognize cranial and shoulder contours ensures robust detection regardless of desk depth.
2. **Cortex-A53 Inference Throughput:**
   - YOLOLite CPU (Nano) features an ultra-compact single-stage architecture with a streamlined depthwise separable backbone. It is explicitly optimized for real-time edge CPU inference without requiring an NPU/GPU coprocessor, achieving low inference latencies on the Raspberry Pi 3B.
3. **Single-Class Efficiency:**
   - Reducing the classification head from 80 COCO classes to a single `head` class eliminates output tensor bloat and simplifies post-processing overhead.

---

## ADR-04: Inference Triggering Strategy — Periodic Snapshot + Change Differencing vs. Continuous Live Stream Inference

### Context
Continuous live video stream inference (running 20–30 FPS real-time object detection) on a quad-core ARM Cortex-A53 CPU generates sustained 100% CPU core saturation, causing rapid thermal accumulation and aggressive CPU frequency throttling (dropping from 1.2 GHz down to 600 MHz).

### Decision
Implement a **Compute-Aware Triggering Pipeline** combining a periodic heartbeat scan with motion-triggered change detection.

```
                        ┌──────────────────┐
                        │  Capture Frame   │
                        └────────┬─────────┘
                                 │
                                 ▼
                     /───────────────────────\
                    < ESP32 State == "idle"?  >
                     \───────────────────────/
                                 │ Yes
                                 ▼
                    /─────────────────────────\
                   <  Significant Change?      >
                   <  (ratio >= CHANGE_THRESH) >
                    \─────────────────────────/
                       │ Yes               │ No
                       │                   ▼
                       │       /───────────────────────\
                       │      <  Heartbeat Interval Due?>
                       │       \───────────────────────/
                       │            │ Yes          │ No
                       ▼            ▼              │
               ┌───────────────────────────┐       │
               │ Execute TFLite Inference  │       │
               └─────────────┬─────────────┘       │
                             │                     │
                             ▼                     │
               ┌───────────────────────────┐       │
               │ Push HUD Frame & Telemetry│◄──────┘
               └───────────────────────────┘
```

### Rationale & Trade-offs
1. **Classroom Dynamics:**
   - Classrooms are predominantly static environments during lectures. Headcount changes primarily occur during arrival, dismissal, or student seat transitions.
2. **Sub-10ms Change Detection:**
   - The `ChangeTrigger` module computes a Gaussian-blurred absolute difference (`cv2.absdiff`) against the previous reference frame in ~4 ms on CPU.
   - When motion is detected (mean difference ratio $\ge 0.15$), an immediate full TFLite inference is dispatched, achieving instantaneous reaction times while maintaining idle CPU usage below 8%.
3. **Servo Motion Awareness:**
   - The Pi 3B checks the serial state reported by the ESP32. When the turret is actively executing a servo pan step (`"moving"`), change detection triggers are paused to prevent the turret's own physical movement from creating false-positive motion triggers.

---

## ADR-05: Spatial Zoning — Macro Quadrants (Q1–Q4) with Reconciliation vs. Per-Seat Micro-Tracking

### Context
Tracking individual seats requires creating dense pixel polygons for every chair in a classroom.

### Decision
Divide the classroom space into **four macro quadrants (Q1–Q4)** and enforce self-consistency reconciliation.

### Rationale & Trade-offs
1. **Robustness to In-Class Motion:**
   - Students frequently shift chairs, pull desks together, or lean into adjacent aisles. Per-seat bounding boxes result in high flicker and false "vacant/occupied" toggles. Macro quadrants absorb in-cluster shuffling as non-events.
2. **Reduced Servo Scan Cycles:**
   - A 4-quadrant scan requires only 4 discrete pan/tilt positions (e.g., $0^\circ, 60^\circ, 120^\circ, 180^\circ$ at $30^\circ$ tilt), completing a full room sweep in under 4 seconds.
3. **Self-Consistency Reconciler (`ZoneReconciler`):**
   - After completing a quadrant scan cycle, the sum of detections across Q1–Q4 is compared against the baseline full-room count. If a discrepancy exceeding the configured tolerance occurs, the system automatically triggers a verification re-scan before publishing the final headcount.

---

## ADR-06: Custom Visible LED Illumination + LDR vs. Off-The-Shelf IR Units

### Context
Low-light and evening classroom conditions degrade camera signal-to-noise ratio, leading to edge blur and dropped detections.

### Decision
Implement a custom visible-spectrum LED array controlled via an analog Light Dependent Resistor (LDR) and ESP32 ADC, rather than an active Infrared (IR) night-vision illuminator.

### Rationale & Trade-offs
1. **No IR-Cut Filter Mechanical Switching:**
   - Standard CMOS sensors require an electro-mechanical IR-Cut switch to transition between daytime color and nighttime IR monochrome modes. Inexpensive IR modules introduce mechanical failure points and chromatic aberration.
2. **Natural Visual Stream for Dashboard:**
   - Visible auxiliary lighting preserves natural color and contrast on the live MJPEG dashboard stream viewed by instructors or administrators.
3. **Closed-Loop Thresholding:**
   - The ESP32 continuously polls the LDR on ADC channel 34. Hysteresis thresholding prevents rapid oscillation near the ambient light boundary.
