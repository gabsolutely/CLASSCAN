# CLASSCAN — System Documentation
**Classroom Occupancy Sensing Turret**  
PCU-D Capstone Project · Sept 2026 · Programmer: gabsolutely

---

## 1 · What It Does

CLASSCAN is a CV-based classroom headcount system that mounts to a ceiling and continuously estimates the number of people present in a room. It uses a Raspberry Pi 3B running a custom-trained TFLite density-map model to count heads from camera frames, and streams live counts + video to a wireless web dashboard. An ESP32 co-processor drives a pan/tilt servo camera mount, an LED matrix display, and an automatic illumination circuit.

**Core pipeline:**
```
OV4689 camera → Pi 3B TFLite inference (density ensemble) → headcount
    ├── Wi-Fi → dashboard (browser on any LAN device)
    └── USB serial → ESP32 → LED matrix display + servo control
```

---

## 2 · Hardware

| Component | Details |
|---|---|
| Raspberry Pi 3B (1 GB RAM) | Main compute; runs OS, detection, dashboard server |
| OV4689 4MP BSI USB camera | UVC driver; active at `/dev/video0`; MJPG up to 2688×1520@30fps |
| ESP32 DevKit | Co-processor; serial JSON protocol; GPIO for servos, LDR, LED matrix |
| MG90S 360° servos ×2 | Pan + tilt for camera mount sweep |
| LED matrix display | Shows live headcount |
| LDR + MOSFET + LEDs | Auto illumination: dims room lights when ambient lux drops |
| Pi acrylic case + active fan | Thermal management; ~36°C operating temp |

See [`hardware/wiring_guide.md`](hardware/wiring_guide.md) and [`hardware/esp32_pinout.md`](hardware/esp32_pinout.md) for wiring.

---

## 3 · Software Architecture

```
CLASSCAN/
├── src/
│   ├── pi/
│   │   ├── main.py              ← Unified entry point (detection loop + server)
│   │   ├── config.py            ← All tuneable constants
│   │   ├── detection/
│   │   │   ├── detector.py      ← TFLite wrappers: EnsembleDensityDetector, Detector
│   │   │   ├── change_trigger.py← Frame-diff trigger for on-demand re-detection
│   │   │   └── zone_reconciler.py
│   │   ├── comms/
│   │   │   ├── dashboard_server.py ← HTTP server: static assets, /status, /stream, /command
│   │   │   └── serial_bridge.py    ← JSON serial protocol to ESP32
│   │   └── setup/
│   │       ├── startup.py       ← Boot self-test sequence (camera, model, serial checks)
│   │       ├── wifi-powersave-off.service  ← systemd: keeps Wi-Fi from sleeping
│   │       └── wifi-watchdog.sh ← cron: cycles wlan0 / reboots on connectivity loss
│   ├── dashboard/
│   │   ├── index.html           ← Dashboard UI
│   │   ├── styles.css
│   │   └── app.js               ← Polling client, command send, zone display
│   └── esp32/
│       ├── src/main.cpp         ← Firmware: serial rx, servo control, LED matrix, LDR
│       └── include/config.h     ← GPIO pins, timing constants
├── models/
│   ├── classcan_density_round4_ep8.tflite    ← Ensemble component 1 (weight 0.6)
│   ├── classcan_density_style_aug_ep8.tflite ← Ensemble component 2 (weight 0.4)
│   └── mobilenet_v2_ssd_classcan.tflite      ← COCO SSD fallback (smoke-test only)
├── tests/                       ← 27 unit tests (all hardware-free)
└── scripts/                     ← Training, export, calibration, bench utilities
```

### 3.1 Detection Loop (`main.py`)

```
while True:
  frame = detector.capture_frame()       # freshest frame (stale-buffer fix)
  if frame is not None:                  # guard: skip motion check on missed reads
    if trigger.check(frame):             # frame-diff → extend motion window
      motion_active_until = now + 2.0
  if frame is not None and (motion_active OR heartbeat):
    count = ensemble.predict(frame)       # density map sum → headcount
    detections = detector.detect(frame)   # bounding boxes for HUD only
    serial_bridge.send_count(count)       # → ESP32 → LED matrix
  annotated = draw_hud_overlay(frame, detections)
  dashboard.push(count, annotated, ...)  # → MJPEG stream + /status JSON
  cmd = dashboard.poll_command()         # handle UI commands (mode switch, zone)
  time.sleep(0.05)                       # ~20 Hz frame poll
```

### 3.2 Detection Trigger Logic

Re-detection fires when any of three conditions are true:
1. **Frame-diff trigger** — `ChangeTrigger` compares Gaussian-blurred grayscale frames; triggers if mean absolute pixel diff exceeds 15% of 255 (configurable via `CHANGE_THRESHOLD`)
2. **Heartbeat** — forced re-scan every 10 seconds regardless of motion (configurable via `HEARTBEAT_INTERVAL`)
3. **Cold start** — fires unconditionally on the first loop iteration

ESP32 state (`idle` / `moving`) gates motion-triggered re-detection: detections are skipped while the servo mount is sweeping to avoid blurry/transitional frames.

**`None`-frame guard (Sept 30, 2026):** `trigger.check()` and `frame.copy()` are now skipped entirely when `capture_frame()` returns `None` (e.g., a dropped USB read). This prevents an unhandled `cv2.cvtColor(None, ...)` exception from crashing the loop mid-session and from incorrectly resetting `last_check_time`, which would silently suppress the heartbeat counter during camera glitches.

### 3.3 Stale-Buffer Fix (Sept 24, 2026)

OpenCV / V4L2 maintains an internal ring buffer (3–4 frames deep). TFLite inference on Pi 3B takes ~700 ms–1.4 s; by the time inference finishes, several new camera frames have queued up. A naive `cap.read()` returns the oldest buffered frame — potentially seconds stale.

**Fix (`_grab_fresh_frame` in `detector.py`):** calls `cap.grab()` in a tight loop (up to 8×, no pixel decode, just advances the V4L2 DMA pointer), then `cap.retrieve()` to decode only the final freshest frame. Falls back to `cap.read()` if retrieve fails.

---

## 4 · AI Model

### 4.1 Final Adopted Model — Weighted Ensemble

```
count = max(0, round(
    0.6 × sum(density_map_round4_ep8_letterbox) +
    0.4 × sum(density_map_style_aug_ep8_stretch)
))
```

| Model file | Checkpoint | Preprocessing | Weight |
|---|---|---|:---:|
| `classcan_density_round4_ep8.tflite` | `classcan_density_v4_round4_ft_epoch8.weights.h5` | **Letterbox** (preserve aspect ratio, pad black) | 0.6 |
| `classcan_density_style_aug_ep8.tflite` | `classcan_density_style_aug_ft_lowLR_epoch8.weights.h5` | **Stretch** (direct `cv2.resize`) | 0.4 |

**Architecture (both models):** MobileNetV3-Large backbone + progressive upsampling decoder → 104×104 spatial density map (Softplus activation, 3.6M parameters).  
**Input:** `[1, 416, 416, 3]` float32, normalized [0, 1] RGB  
**Output:** `[1, 104, 104, 1]` float32 density surface; `sum()` ≈ headcount

### 4.2 Performance

| Metric | Value |
|---|---|
| Real-footage MAE (v2 held-out, 350 frames) | **2.77 people** |
| Real-footage correlation | **r = 0.586** |
| SCUT-HEAD benchmark (407 images) | r > 0.99 throughout all rounds |
| Pi 3B inference time | ~702 ms/model, **~1.4 s/ensemble scan** |

Per-clip correlation: `line3=0.759`, `sit2=0.519`, `sit1=0.538`, `line2=0.555`, `line1=0.455`

### 4.3 Why the Preprocessing is Asymmetric

`round4_ep8` was trained with stretch preprocessing. Evaluating it at inference time with **letterbox** (no retraining) lifts its standalone correlation from 0.506 → 0.602 — specifically fixing the `sit2` clip. Training from scratch with letterbox collapsed in all 5 attempts. The ensemble uses this asymmetry deliberately.

### 4.4 Training History (summary)

9 rounds of fine-tuning from `classcan_density_v4` base:
- Rounds 1–3: hard-negative fine-tuning (176 → 595 FP crops: bags, chairs, floor, hands); MAE 9.46 → 3.87 → 3.22 → 2.81, correlation ceiling stuck at 0.448
- **Round 4:** LR raised 1e-5 → 5e-5 (first LR change across all rounds); epoch 8 broke the ceiling → r=0.506 (stretch), r=0.602 (letterbox eval, no retrain)
- Rounds 5–6: mix rebalance + letterbox training — all collapsed or failed to improve
- Rounds 7–8: 8 further attempts (from-scratch letterbox, frozen backbone, stretch fine-tune) — correlation never broken
- **Round 9 / style-aug:** brightness/contrast/color/sharpness jitter on SCUT-HEAD stream; LR=5e-6; only run to complete 10 epochs without collapse; epoch 8 → r=0.531
- **3-way ensemble grid search:** weights (0.6, 0.0, 0.4) for [round4_ep8, stretch-ft-ep1, style-aug-ep8] → **MAE=2.77, r=0.586** — best across all rounds

**Domain-gap root cause (confirmed by QA reviewer PeaNat):** SCUT-HEAD depicts orderly/seated/well-lit lecture halls; real Philippine classrooms have moving lines, irregular wooden armchairs, dim/uneven lighting. The 0.43–0.60 real-footage correlation ceiling is a data-domain limitation. Only genuine Filipino-classroom training data would meaningfully break it.

---

## 5 · Dashboard

Served directly from the Pi on port 8080. No build step required — plain HTML/CSS/JS.

### Endpoints

| Route | Description |
|---|---|
| `GET /` or `/index.html` | Dashboard UI |
| `GET /status` | JSON: `{count, fps, top_conf, timestamp, snapshot (b64), zones, mode}` |
| `GET /stream` | Multipart MJPEG live video stream |
| `POST /command` | JSON body `{command: "..."}` → queued to main loop |

### Commands accepted via POST /command

| Command | Effect |
|---|---|
| `MODE_SWEEP` | Switch to full-frame sweep mode |
| `MODE_ZONE` | Switch to quadrant zone-check mode |
| `ZONE_Q1` … `ZONE_Q4` | Move servo to named quadrant |
| `STOP_SERVOS` | Stop servo movement |
| `SET_CENTER` | Stop and set current position as angle reference |

### Polling

`app.js` polls `/status` every 2 s when connected. Snapshot is base64 JPEG encoded by `dashboard_server.py` and decoded client-side. The MJPEG stream is available separately at `/stream` for browsers that support `<img src="/stream">`.

The **Event Log** panel in the dashboard UI accumulates all log messages for the session (uncapped in memory, capped at 200 entries in the DOM). The **⬇ Download Log** button exports the full in-memory log as a timestamped `classcan_eventlog_<datetime>.csv` with `Timestamp, Type, Message` columns — entirely client-side via a Blob URL, no server endpoint required.

---

## 6 · ESP32 Serial Protocol

Newline-delimited JSON over USB serial at 115200 baud.

**Pi → ESP32:**
```json
{"type": "count",   "value": 12}
{"type": "command", "value": "MODE_SWEEP"}
{"type": "servo",   "pan": 155, "tilt": 90, "duration_ms": 700}
{"type": "servo",   "pan_angle": 90, "tilt_angle": 30, "speed": 155}
```

**ESP32 → Pi:**
```json
{"type": "state", "value": "idle"}
{"type": "state", "value": "moving"}
```

`SerialBridge` in `serial_bridge.py` runs a daemon reader thread to keep `_state` updated. If the serial port is unavailable (bench-testing), it silently enters simulated serial mode (all sends are no-ops, state stays `"idle"`).

---

## 7 · Configuration (`src/pi/config.py`)

All deployment knobs in one place. Key values:

| Config key | Default | Notes |
|---|---|---|
| `SERIAL_PORT` | `/dev/ttyUSB0` | Update to actual device (ttyUSB0/ttyACM0) |
| `SERIAL_BAUD` | `115200` | Must match `SERIAL_BAUD` in `esp32/include/config.h` |
| `DASHBOARD_PORT` | `8080` | Dashboard HTTP port |
| `CONF_THRESHOLD` | `0.35` | Box detector confidence cutoff (HUD only) |
| `HEARTBEAT_INTERVAL` | `10.0 s` | Minimum time between forced re-scans |
| `LOOP_SLEEP` | `0.05 s` | Main loop sleep (~20 Hz frame poll) |
| `CHANGE_THRESHOLD` | `0.15` | Frame-diff ratio to trigger immediate re-detect |
| `MODE` | `"SWEEP"` | `"SWEEP"` or `"ZONE_CHECK"` |
| `DENSITY_THRESHOLD` | `0.15` | Per-frame density map noise floor fraction |

---

## 8 · Running the System

### On the Pi (standard launch)
```bash
cd ~/CLASSCAN/src/pi
python main.py
```

### Simulation mode (no hardware needed — for demos on a laptop)
```bash
python main.py --mock --mock-count 8
```

### Key CLI flags
```
--mock              Force mock camera + simulated serial (no hardware)
--mock-count N      Simulated headcount in mock mode (default: 4)
--skip-boot-check   Skip hardware self-test at startup
--camera N          OpenCV camera device index (default: 0)
--port N            Dashboard HTTP port (default: 8080)
--conf 0.35         Confidence threshold for box detector
--serial-port PATH  Serial device for ESP32 (default: /dev/ttyUSB0)
```

---

## 9 · Tests

```bash
python -m pytest tests/ -v
```

27 tests, all hardware-free (cv2 and ai_edge_litert are mocked):

| File | What it covers |
|---|---|
| `test_detector.py` | `Detector` init, detect, zone counting, capture failure |
| `test_postprocess.py` | NMS and Soft-NMS correctness |
| `test_change_trigger.py` | Frame-diff trigger logic |
| `test_reconciler.py` | Zone-count reconciliation |

---

## 10 · Deployment Notes & Gotchas

1. **Camera config must be applied after every reboot** — the `v4l2-ctl` baseline (gamma=300, gain=192, etc.) is not yet wired into a boot script. Run it manually or add to `/etc/rc.local`.

2. **Ensemble TFLite files are not in the git repo** — too large (~13 MB each). Export from Colab Drive and `scp` to the Pi before demo.

3. **`startup.py`** runs an interactive boot-gate: if a critical check fails (camera, model, serial), it prompts `[R]etry / [C]ontinue / [A]bort`. Use `--skip-boot-check` to bypass entirely in dev.

4. **Float32 only** — INT8 quantization is broken (XNNPack raises "failed to prepare" on `UpSampling2D(bilinear)` layers); retraining decoder with `Conv2DTranspose` would fix it but was deferred.

5. **MJPEG stream vs snapshot** — the dashboard polls `/status` for the base64 snapshot; the raw MJPEG stream at `/stream` is also available if you want a lower-latency video-only view.

6. **Single-process, no restart** — if `main.py` crashes, restart it manually. No watchdog daemon wraps the main process (add `nohup python main.py &` + a systemd service for production hardening).
