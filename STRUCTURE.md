# CLASSCAN

**Intelligent Classroom Headcount Monitoring System**  
PCU-D Capstone · Computer Vision + Embedded Systems

---

## Repository Layout

```
CLASSCAN/
├── src/
│   ├── pi/                     ← Raspberry Pi 3B (Python, Raspberry Pi OS Lite 64-bit)
│   │   ├── main.py             ← Main detection + comms loop
│   │   ├── config.py           ← All tuneable constants
│   │   ├── requirements.txt
│   │   ├── detection/
│   │   │   ├── detector.py         ← TFLite YOLOLite CPU (Nano) / model wrapper
│   │   │   ├── change_trigger.py   ← Frame-diff re-detect trigger
│   │   │   └── zone_reconciler.py  ← Quadrant count self-consistency check
│   │   └── comms/
│   │       ├── serial_bridge.py    ← USB serial ↔ ESP32 (JSON protocol)
│   │       └── dashboard_server.py ← HTTP server → laptop dashboard
│   │
│   ├── esp32/                  ← ESP32 firmware (PlatformIO / Arduino Framework)
│   │   ├── platformio.ini      ← PlatformIO build & dependency config
│   │   ├── include/            ← Modular header files
│   │   │   ├── config.h            ← Pin & timing constants
│   │   │   ├── ldr_illumination.h  ← LDR-triggered illumination module
│   │   │   ├── servo_controller.h  ← Pan/tilt sweep + zone-step
│   │   │   └── led_matrix.h        ← LED matrix display driver stub
│   │   └── src/
│   │       └── main.cpp        ← Firmware entry point & state loops
│   │
│   └── dashboard/              ← Laptop monitoring dashboard
│       ├── index.html          ← Semantic markup & layout structure
│       ├── styles.css          ← Dark-mode design system & animations
│       └── app.js              ← Polling logic, event handlers & UI state
│
├── models/                     ← TFLite model files (YOLOLite Nano .tflite)
├── docs/                       ← Scope, BOM, design docs
├── cad/                        ← Enclosure CAD files
├── hardware/                   ← Wiring diagrams, pinouts
├── tests/                      ← Offline unit tests (no hardware needed)
│   ├── test_change_trigger.py
│   ├── test_reconciler.py
│   └── test_detector.py
├── README.md
└── ROADMAP.md
```

---

## Quick Start

### Pi 3B

```bash
cd src/pi
pip install -r requirements.txt
# Copy your trained .tflite model to models/
python main.py
```

### ESP32 (PlatformIO)

```bash
cd src/esp32
# Build firmware & automatically install library dependencies:
pio run

# Flash to connected ESP32:
pio run -t upload

# Open Serial Monitor:
pio device monitor
```
*(Alternatively, open `src/esp32` in VS Code / Cursor with the PlatformIO extension and click Build / Upload).*

### Dashboard

Open `src/dashboard/index.html` in a browser on the same network as the Pi.  
Enter the Pi's IP address and click **Connect**.

---

## Running Tests (no hardware)

```bash
python tests/test_change_trigger.py
python tests/test_reconciler.py
```

---

See [README.md](README.md) for full system architecture and design rationale.
