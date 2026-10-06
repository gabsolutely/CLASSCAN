# CLASSCAN — Novelty & Competitive Analysis

**Project Title:** Development of an Intelligent Classroom Headcount Monitoring System using Computer Vision and LED Display Technology  
**Institution:** Philippine Christian University – Dasmariñas (PCU-D)

---

## 1. What Makes CLASSCAN Novel

CLASSCAN is not simply "a camera that counts people." It combines several technical and design choices that, taken together, constitute a system that does not exist as a packaged product or prior published implementation for the Philippine K–12/HEI classroom context.

### 1.1 Domain-Specific Density-Map Regression on a Sub-$100 Edge Board

The primary headcount engine (`classcan_density_v4`) is a **continuous density-map regression model** — a paradigm originally developed for crowd estimation at scales of hundreds or thousands of people in public spaces (concerts, plazas). CLASSCAN applies and adapts this paradigm to the **opposite end of the density spectrum**: a single classroom of 5–50 students, viewed from a steep ceiling angle with heavy desk occlusion.

Key architectural choices that are non-trivial in this context:

| Design Choice | Why It's Novel Here |
|---|---|
| MobileNetV3-Large backbone + progressive upsampling decoder | Balances accuracy with the hard constraint of ~700 ms/frame on a Pi 3B Cortex-A53 — no GPU, no NPU, no cloud |
| 104×104 Softplus density map output | Eliminates dying-ReLU collapse; allows fractional-count smoothing across students partially occluded by armchair desks |
| Gaussian density map generation from head-bounding-box annotations | Converts existing bounding-box labels to density targets without re-annotation — enabling dataset reuse |
| Operational regime optimization (0–20 students per quadrant scan) | The model achieves **MAE = 0.93 people** within the quadrant FOV operational window — a sub-1-person error at classroom scale on CPU-only hardware |

No known off-the-shelf product or published local capstone/thesis applies density-map regression at this scale, on this hardware, in this classroom geometry.

### 1.2 Classroom-Geometry-Aware Head Detection (Not Full-Body)

Standard COCO-trained person detectors (MobileNetV2-SSD, YOLOv8n, etc.) are trained on upright full-body images. In a Philippine classroom:

- The camera is ceiling-mounted at a **30°–50° downward pitch**.
- Wooden/plastic armchair desks occlude **60–80% of each student's body** from that angle.
- Only the cranial region, shoulders, and top-back are visible.

CLASSCAN's secondary box detector (`classcan_head_v1`) is trained end-to-end on a curated dataset of **head-and-shoulders crops** from the SCUT-HEAD benchmark plus domain-adapted Philippine classroom footage. It targets a single `head` class rather than the 80-class COCO taxonomy, directly minimizing confusion between occluded-student heads and desk surfaces.

The system **empirically documented** that stock full-body detectors produce 0 detections in this scenario (see `docs/benchmark_results.md` and `docs/design_rationale.md` ADR-03) — making the custom training not optional but necessary.

### 1.3 Compute-Aware Triggering with Servo Motion Awareness

Rather than running continuous live-stream inference (which saturates and thermally throttles even stronger boards), CLASSCAN uses a **hybrid periodic-snapshot + motion-triggered** strategy that is uniquely aware of its own hardware state:

- **Frame buffer drain** (`_grab_fresh_frame` via `cap.grab()` loop): Solves the well-known OpenCV/V4L2 buffer-staleness problem that plagues any slow inference pipeline on Linux — documented and solved as part of this project in ADR-09 (Sept 24, 2026).
- **ESP32 state-gate on motion trigger**: The Pi 3B only fires a change-detection re-scan when the ESP32 reports `idle` — preventing the turret's own physical pan/tilt motion from generating false positive motion events. This state feedback loop is not present in any off-the-shelf motion-triggered camera system.

### 1.4 Dual-Tier Industrial-Architecture Design for a Capstone

The explicit separation of concerns between:
- **Pi 3B (Brain):** inference, networking, logic
- **ESP32 (Hands):** PWM servo control, LDR ADC, LED matrix, autonomous failsafe

...mirrors standard industrial robotics and automation design (IEC 61131-style controller separation). For a single-developer capstone system at PCU-D, applying this architectural pattern to a classroom occupancy device at this hardware budget (~₱4,000–₱5,000 BOM) is not common in Philippine capstone literature.

The ESP32 failsafe guarantee — room sweeping, lighting, and LED count display continue independently even if the Pi crashes or Wi-Fi drops — is an operational reliability property that cloud-connected competitors explicitly do not offer.

### 1.5 Fully Documented Negative Result Trail

CLASSCAN is unusual in that it rigorously documents every dead end:

- COCO MobileNetV2-SSD: 0 detections in classroom (empirically confirmed)
- YOLOLite Nano fine-tune: plateau at mAP@50=16.6%
- CrowdHuman augmentation: objectness collapse (F1 → 0%)
- Naive ensemble (custom + COCO SSD): F1=15.1% (worse than either alone)
- Flip-TTA: MAE exploded to 12.59
- WBF merging: worse than Soft-NMS (MAE 4.55 vs. 3.84)
- From-scratch letterbox training: collapsed in all 5 independent attempts

This level of negative-result documentation is not standard in commercial products and is specifically valuable for the academic capstone context — it provides an evidence trail for model selection that examiners can audit.

### 1.6 Privacy-by-Design as an Architectural Guarantee

Most commercial occupancy systems either (a) process video in the cloud, or (b) offer "privacy mode" as a software toggle that can be disabled. CLASSCAN's privacy guarantee is **structural**:

- No cloud endpoint exists in the codebase.
- No face recognition model is included in the repository.
- The `head` class is a generic cranial-region detector — it cannot be repurposed for identification without retraining from scratch.
- All telemetry (frames, counts) stays within the LAN; no external egress.

---

## 2. Competitive Landscape

### 2.1 Overview Matrix

| System / Product | Detection Method | Privacy | Edge-Only | Classroom-Geometry-Aware | Cost | Servo Sweep | LED Display | Dashboard | Failsafe |
|---|---|---|---|---|---|---|---|---|---|
| **CLASSCAN** | Density-map regression + head detector (custom TFLite) | ✅ Structural | ✅ Full | ✅ Armchair-occlusion trained | ~₱4–5K BOM (~$70–$90) | ✅ Pan/tilt | ✅ LED matrix | ✅ Wi-Fi | ✅ ESP32 autonomous |
| Hikvision DeepinView Counting Camera | Full-body detection (proprietary DNN) | ❌ Cloud/NVR | ❌ Cloud option | ❌ Generic | $200–$800 | ❌ Fixed | ❌ | ❌ External | ❌ |
| Axis People Counter | Full-body depth/stereo | ❌ Cloud/server | ❌ | ❌ Generic | $400–$1,200 | ❌ Fixed | ❌ | External | ❌ |
| RetailNext / Sensormatic | Video analytics SaaS | ❌ Cloud required | ❌ | ❌ Retail-tuned | Subscription | ❌ | ❌ | SaaS | ❌ |
| Generic OpenCV people counter (GitHub) | Background subtraction / HOG+SVM | ✅ | ✅ | ❌ Needs calibration | Free | ❌ | ❌ | ❌ | ❌ |
| RFID-based attendance (common capstone) | NFC/RFID tap-in tap-out | ✅ | ✅ | N/A | ~₱1–2K | ❌ | Optional | Optional | ❌ Requires tap |
| Facial recognition attendance | Face embedding + DB match | ❌ Privacy risk | ❌ Often cloud | N/A | $100–$500 | ❌ | ❌ | Optional | ❌ |
| Manual headcount | Human | ✅ | ✅ | N/A | ₱0 | N/A | N/A | N/A | N/A |

### 2.2 Commercial People-Counting Cameras (Hikvision, Axis, Dahua)

**What they do:** Ceiling-mounted fixed cameras with embedded people-counting analytics. Some use stereo depth for better accuracy. Data is sent to a cloud NVR or cloud analytics platform.

**Why CLASSCAN differs:**
- Commercial units are **fixed** — no pan/tilt servo sweep. A single Hikvision DS-TD Series unit has a fixed FOV; covering a 7×9m classroom requires multiple units.
- They are designed for **retail door counting** (people passing a threshold line), not occupancy estimation over a room with seated, partially-occluded students.
- They cost $200–$1,200+ per unit — vs. CLASSCAN's ~₱4,000–₱5,000 ($70–$90) BOM.
- They process video on the cloud or on a proprietary NVR — CLASSCAN is strictly edge/LAN only.
- They are not customizable for classroom-specific geometry or failure modes.

### 2.3 Cloud Video Analytics SaaS (RetailNext, Sensormatic, Azure Video Analyzer)

**What they do:** Stream video to a cloud endpoint where inference runs on server GPUs; results pushed back via API.

**Why CLASSCAN differs:**
- **Not viable in Philippine classroom settings** where internet connectivity is inconsistent or metered, and where uploading classroom video raises immediate concerns under the Philippine Data Privacy Act (Republic Act 10173).
- Zero offline functionality — if internet drops, counting stops entirely.
- Ongoing subscription cost per camera, per month — not suitable for a DepEd/CHED school budget.
- CLASSCAN has no external network dependency whatsoever.

### 2.4 Generic Open-Source People Counters (GitHub HOG/Background Subtraction)

**What they do:** Use classical computer vision (MOG2 background subtraction, HOG+SVM person detection, or lightweight YOLO) to count people crossing a line or in a region.

**Why CLASSCAN differs:**
- Classical HOG+SVM has the same fundamental failure mode as COCO full-body detectors: **0 detections on occluded, seated students at steep angles** (CLASSCAN empirically confirmed this).
- Background subtraction counts "blobs of motion," not people — a student shifting in their seat registers as movement; a still class registers 0.
- These pipelines require a fixed, calibrated camera with stable background. The CLASSCAN turret sweeps the room, making background models per-zone non-trivial.
- No dashboard, no LED display, no servo control, no illumination — just a counting module.

### 2.5 RFID / NFC Badge-Based Attendance (Common Philippine Capstone)

**What they do:** Students tap an RFID card at a reader on entry. The system logs the tap as attendance.

**Why CLASSCAN differs:**
- **Requires active student participation** — a student who forgets, loses, or doesn't tap their card is not counted. CLASSCAN is fully passive (camera-based).
- RFID counts tap events, not room occupancy — it cannot answer "how many people are currently in the room right now?"
- No physical-space awareness: RFID cannot tell if a student is present but seated in the back vs. just near the door.
- CLASSCAN is suitable for **emergency evacuation checks**, transitional occupancy between classes, and real-time "is anyone in this room?" queries — use cases that RFID cannot serve.
- That said, RFID is cheaper and simpler — it is a different tool for a different (identity-centric) problem. CLASSCAN deliberately does not do identity.

### 2.6 Facial Recognition Attendance Systems

**What they do:** Capture face images, compute embeddings, match against a student database.

**Why CLASSCAN differs:**
- Facial recognition is **out of scope by design** — CLASSCAN's `head` class detector cannot identify individuals.
- Facial recognition systems raise significant privacy and legal concerns under RA 10173 (Philippines Data Privacy Act) when deployed on minors in school settings.
- Facial recognition fails under masks, dim lighting, and steep overhead angles — the same conditions CLASSCAN is designed to handle.
- CLASSCAN does not store any biometric data, ever.

---

## 3. Summary: Where CLASSCAN Is Positioned

CLASSCAN occupies a niche that is **not served by any existing product or common local capstone approach**:

> A **fully edge-resident**, **privacy-structural**, **classroom-geometry-aware** occupancy counter that is passive (no student action required), affordable (~₱5K BOM), has a physical display + wireless dashboard, and fails gracefully when the network drops.

The closest comparable commercial systems (Hikvision, Axis) cost 5–15× more, require cloud or NVR infrastructure, are calibrated for retail geometry, and are not open or customizable. The closest open-source alternatives lack domain adaptation for armchair-desk occlusion and have none of the hardware integration.

The key technical differentiator that separates CLASSCAN from every open-source alternative is the **density-map regression paradigm adapted to classroom scale on CPU-only edge hardware** — a combination that required 9 rounds of real-footage fine-tuning and systematic ensemble search to achieve, and is documented end-to-end in this repository.

---

*For model training details: [`docs/dataset_and_training.md`](dataset_and_training.md)*  
*For architectural decisions: [`docs/design_rationale.md`](design_rationale.md)*  
*For benchmark numbers: [`docs/benchmark_results.md`](benchmark_results.md)*  
*For scope and delimitations: [`docs/scope_delimitation.md`](scope_delimitation.md)*
