# CLASSCAN — Raspberry Pi 3B Hardware & Interface Reference

This document describes the physical ports, communication interfaces, power distribution, and thermal parameters for the **Raspberry Pi 3 Model B (1GB RAM)** compute unit.

---

## 1. Physical Interface Map

```
┌─────────────────────────────────────────────────────────────┐
│                   Raspberry Pi 3 Model B                    │
│                                                             │
│   [ Micro-USB Power (5V/2.5A) ]                             │
│   [ HDMI Video (Diagnostic Only) ]                          │
│   [ 40-Pin GPIO Header (Unused / Reserved) ]                │
│                                                             │
│                                           ┌───────────────┐ │
│                                           │ USB Port 1:   │ │
│                                           │ ESP32 Serial  │ │
│                                           ├───────────────┤ │
│                                           │ USB Port 2:   │ │
│                                           │ OV4689 Camera │ │
│                                           ├───────────────┤ │
│   [ Broadcom BCM2837 SoC (Cortex-A53) ]   │ USB Port 3:   │ │
│   [ Onboard Wi-Fi / Bluetooth BCM43438 ]  │ (Unused/Spare)│ │
│                                           ├───────────────┤ │
│                                           │ USB Port 4:   │ │
│                                           │ (Unused/Spare)│ │
│   [ Micro-SD Card Slot (Underneath) ]     ├───────────────┤ │
│   Raspberry Pi OS Lite (64-bit)           │ RJ45 Ethernet │ │
│                                           └───────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Port & Device Mapping Table

| Physical Port | Connected Device | OS Device Path | Configuration & Purpose |
|---|---|---|---|
| **USB 2.0 Port 1 (Top-Left)** | **ESP32 DevKit V1** (via Micro-USB to USB-A cable) | `/dev/ttyUSB0` (or `/dev/ttyACM0`) | Full-duplex serial communication @ **115200 baud**. Transfers JSON telemetry (`{"type":"state"}`) and headcount commands. |
| **USB 2.0 Port 2 (Bottom-Left)** | **OmniVision OV4689 4MP Camera** (via Type-C/A cable) | `/dev/video0` (V4L2 capture device) | Driverless UVC video stream. Captures raw frames into OpenCV (`cv2.CAP_V4L2`) at 15–30 FPS. |
| **USB 2.0 Ports 3 & 4** | Unused / Reserved | — | Available for debugging peripherals (USB keyboard, diagnostics). |
| **Micro-USB In** | **5V / 3A DC-DC Boost Output** | Main Power In | 5.0V regulated DC power input from the battery power supply module. |
| **Micro-SD Card Slot** | **32GB Class 10 Micro-SD Card** | `/dev/mmcblk0` | Stores OS rootfs, `ai-edge-litert` environment, Python source code, and TFLite model weights. |
| **Onboard Wi-Fi (BCM43438)** | **Wireless Local Area Network** | `wlan0` interface | Hosts asynchronous HTTP Dashboard server (`http://0.0.0.0:8080`) on the local classroom subnet. |
| **RJ45 Ethernet Port** | Diagnostic / Lab Wired Network | `eth0` interface | Optional high-speed wired SSH access during bench calibration. |

---

## 3. Power Consumption & Electrical Specifications

| Parameter | Specification | Notes |
|---|:---:|---|
| **Input Supply Voltage** | $5.1\text{V} \pm 5\%$ DC | Supplied via Micro-USB port or direct 5V GPIO pin header. |
| **Idle Current Draw** | ~260 mA – 320 mA | Pi OS Lite headless baseline (Wi-Fi connected, camera idle). |
| **Peak Current Draw (Inference Burst)**| ~650 mA – 850 mA | Quad-core ARM Cortex-A53 executing quantized TFLite inference. |
| **Camera Module Current Draw** | ~180 mA – 240 mA | OV4689 active UVC streaming. |
| **Recommended Power Supply** | $\ge 2.5\text{A}$ (5V DC) | Ensures zero undervoltage warnings (`throttled=0x0`). |

---

## 4. Thermal Management & Operating Limits

- **SoC Package:** Broadcom BCM2837 (Quad-core ARM Cortex-A53).
- **Cooling Solution:** Passive aluminum heatsink ($14\text{mm} \times 14\text{mm} \times 6\text{mm}$) affixed via thermally conductive adhesive tape.
- **Thermal Throttling Ceiling:** The Raspberry Pi firmware initiates core frequency throttling at $80.0^\circ\text{C}$.
- **CLASSCAN Operating Temperature:** Under periodic snapshot inference (10-second heartbeat + motion change triggers), the SoC stabilizes between **$43.0^\circ\text{C}$ and $52.0^\circ\text{C}$**, providing over $28^\circ\text{C}$ of thermal margin without requiring an active cooling fan.
