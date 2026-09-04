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
│   [ 40-Pin GPIO Header (Pins 4/6: Active Cooling Fan) ]     │
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
| **USB 2.0 Port 2 (Bottom-Left)** | **OmniVision OV4689 4MP Camera** (via Type-C / JST-to-USB-A cable) | `/dev/video0` (V4L2 capture device) | Driverless UVC video stream. Captures raw frames into OpenCV (`cv2.CAP_V4L2`) at 15–30 FPS. |
| **GPIO Header (Pin 4 & Pin 6)** | **Acrylic Case 5V Cooling Fan** (Brushless DC 30mm/40mm) | Direct hardware rail | Active continuous forced-air cooling over BCM2837 SoC heatsink. |
| **USB 2.0 Ports 3 & 4** | Unused / Reserved | — | Available for debugging peripherals (USB keyboard, diagnostics). |
| **Micro-USB In** | **5V / 3A DC-DC Boost Output** | Main Power In | 5.0V regulated DC power input from the battery power supply module. |
| **Micro-SD Card Slot** | **32GB Class 10 Micro-SD Card** | `/dev/mmcblk0` | Stores OS rootfs, `ai-edge-litert` environment, Python source code, and TFLite model weights. |
| **Onboard Wi-Fi (BCM43438)** | **Wireless Local Area Network** | `wlan0` interface | Hosts asynchronous HTTP Dashboard server (`http://0.0.0.0:8080`) on the local classroom subnet. |
| **RJ45 Ethernet Port** | Diagnostic / Lab Wired Network | `eth0` interface | Optional high-speed wired SSH access during bench calibration. |

---

## 3. 40-Pin GPIO Header Reference (Cooling Fan Connection)

The Raspberry Pi 3B features a 40-pin standard GPIO header. The active cooling fan mounts to the acrylic lid and connects via two female Dupont connectors:

```
                  RASPBERRY PI 3B GPIO HEADER
                    (Top-Down View, Pin 1 at Top-Left)

   3.3V Power (Quiet Fan +)  [ 1] [ 2]  5V Power
                      GPIO 2 [ 3] [ 4]  5V Power (Standard Fan +)
                      GPIO 3 [ 5] [ 6]  GND (Fan Ground -)
                      GPIO 4 [ 7] [ 8]  GPIO 14 (UART TX)
                         GND [ 9] [10]  GPIO 15 (UART RX)
                     GPIO 17 [11] [12]  GPIO 18
                     GPIO 27 [13] [14]  GND
                     GPIO 22 [15] [16]  GPIO 23
                   3.3V Power[17] [18]  GPIO 24
                     GPIO 10 [19] [20]  GND
                      GPIO 9 [21] [22]  GPIO 25
                     GPIO 11 [23] [24]  GPIO 8
                         GND [25] [26]  GPIO 7
                       ID_SD [27] [28]  ID_SC
                      GPIO 5 [29] [30]  GND
                      GPIO 6 [31] [32]  GPIO 12
                     GPIO 13 [33] [34]  GND
                     GPIO 19 [35] [36]  GPIO 16
                     GPIO 26 [37] [38]  GPIO 20
                         GND [39] [40]  GPIO 21
```

### Fan Wiring Modes:

| Mode | Red Wire (+) Pin | Black Wire (-) Pin | Voltage | Acoustic Profile | Cooling Performance |
|---|:---:|:---:|:---:|:---:|:---:|
| **5V Performance Mode (Recommended)** | **Pin 4** (or Pin 2) | **Pin 6** | 5.0V | Moderate hum | Drops SoC temp to **~34°C – 40°C** under continuous load |
| **3.3V Quiet Mode** | **Pin 1** | **Pin 6** | 3.3V | Whisper-quiet | Drops SoC temp to **~39°C – 45°C** under snapshot inference |

> [!TIP]
> **Fan Airflow Direction:** Mount the fan so air exhausts downward directly onto the aluminum heatsink affixed to the Broadcom BCM2837 SoC.

---

## 4. Power Consumption & Electrical Specifications

| Parameter | Specification | Notes |
|---|:---:|---|
| **Input Supply Voltage** | $5.1\text{V} \pm 5\%$ DC | Supplied via Micro-USB port or direct 5V GPIO pin header. |
| **Idle Current Draw** | ~260 mA – 320 mA | Pi OS Lite headless baseline (Wi-Fi connected, camera idle). |
| **Active Cooling Fan Draw** | ~60 mA – 110 mA | Brushless DC fan running continuously on 5V rail (~40 mA on 3.3V rail). |
| **Peak Current Draw (Inference Burst)**| ~650 mA – 850 mA | Quad-core ARM Cortex-A53 executing quantized TFLite inference. |
| **Camera Module Current Draw** | ~180 mA – 240 mA | OV4689 active UVC streaming. |
| **Total System Peak Draw** | ~1.1 A – 1.3 A | Well within the 3.0A boost converter limit. |
| **Recommended Power Supply** | $\ge 2.5\text{A}$ (5V DC) | Ensures zero undervoltage warnings (`throttled=0x0`). |

---

## 5. Thermal Management & Operating Limits

- **SoC Package:** Broadcom BCM2837 (Quad-core ARM Cortex-A53).
- **Cooling Solution:** Passive aluminum heatsink ($14\text{mm} \times 14\text{mm} \times 6\text{mm}$) + **Active Acrylic Case Cooling Fan** (forced-air).
- **Thermal Throttling Ceiling:** The Raspberry Pi firmware initiates core frequency throttling at $80.0^\circ\text{C}$.
- **CLASSCAN Operating Temperature (With Active Fan):**
  - **Idle:** **$33.0^\circ\text{C} – 36.0^\circ\text{C}$**
  - **Under Snapshot Inference:** **$36.0^\circ\text{C} – 41.0^\circ\text{C}$**
  - **Thermal Headroom:** Over **$39^\circ\text{C}$ margin** before throttling ceiling, preventing any thermal-induced FPS drops or frame stutter.
- **Monitoring Command:**
  ```bash
  vcgencmd measure_temp
  ```
