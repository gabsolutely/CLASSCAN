# CLASSCAN — Complete System Wiring & Circuit Guide

This document provides full hardware interconnections, circuit schematics, and power distribution diagrams for the CLASSCAN system.

---

## 1. System Interconnection Architecture

```
                      [ 2× 18650 Li-ion Cells (7.4V / 3.7V) ]
                                      │
                                      ▼
                      [ TP4056 / 2S Battery Management ]
                                      │
                                      ▼
                      [ MT3608 5V / 3A DC-DC Boost Module ]
                                      │
              ┌───────────────────────┴───────────────────────┐
              │ +5V Regulated Bus                             │ Common GND Bus
              ▼                                               ▼
     ┌─────────────────┐                             ┌─────────────────┐
     │ Raspberry Pi 3B │                             │ ESP32 DevKit V1 │
     │ (Micro-USB In)  │◄──────── USB Serial ───────►│ (VIN / GND)     │
     │                 │   (CP2102 UART @ 115200)    │                 │
     │                 │                             │   GPIO 34 (ADC) ├──────┐
     │  USB Port 2 ────┼─────────────┐               │   GPIO 25 (OUT) ├──┐   │
     └─────────────────┘             │               │   GPIO 18 (PWM) ├┐ │   │
                                     │               │   GPIO 21 (PWM) ├┼┐│   │
                                     ▼               └─────────────────┘│││   │
                           [ OV4689 Camera Module ]                     │││   │
                                                                        │││   │
  ┌─────────────────────────────────────────────────────────────────────┘││   │
  │ Pan Servo (MG90S): Signal ── GPIO18, Power ── +5V, Ground ── GND    ││   │
  ├──────────────────────────────────────────────────────────────────────┘│   │
    │ Tilt Servo (MG90S): Signal ── GPIO21, Power ── +5V, Ground ── GND     │   │
  ├───────────────────────────────────────────────────────────────────────┘   │
  │ Custom Illumination Module: Gate ── GPIO25, Power ── +5V, Ground ── GND   │
  └───────────────────────────────────────────────────────────────────────────┘
    LDR Ambient Sensor: Signal ── GPIO34, Power ── 3.3V, Ground ── GND
```

---

## 2. Custom LDR & Illumination Circuit Schematic

The illumination system uses a Light Dependent Resistor (LDR) analog voltage divider and an N-channel MOSFET (or NPN transistor) to drive four ultra-bright white LEDs.

```
LDR Sensor Divider:                     Auxiliary LED Illumination Array:
-------------------                     ---------------------------------

     +3.3V Rail (ESP32)                              +5.0V Main Power Bus
            │                                                 │
            │                                                 ├──[ 47Ω ]──(>| LED 1 )──┐
            ▼                                                 ├──[ 47Ω ]──(>| LED 2 )──┤
        ┌───────┐                                             ├──[ 47Ω ]──(>| LED 3 )──┤
        │  LDR  │ (GL5528)                                    └──[ 47Ω ]──(>| LED 4 )──┤
        └───────┘                                                                      │
            │                                                                   Drain  │
            ├────────► To ESP32 GPIO 34 (ADC1_CH6)                       ESP32       ┌───┐
            │                                                           GPIO 25 ────┤   │ 2N7000 N-MOSFET
        ┌───────┐                                                      (Gate Pulse) │   │ (or 2N2222 NPN)
        │  10kΩ │ (1/4W Pull-Down)                                                  └───┘
        └───────┘                                                                 Source
            │                                                                        │
            ▼                                                                        ▼
       Common GND                                                               Common GND
```

### Circuit Operation:
1. **Daylight Conditions:** Light falls on LDR $\to$ LDR resistance drops ($< 2\text{k}\Omega$) $\to$ GPIO 34 voltage rises toward 3.3V (ADC count $> 2500$). ESP32 firmware holds GPIO 25 `LOW` (LEDs remain OFF).
2. **Dark / Dim Conditions:** Ambient light falls $\to$ LDR resistance increases ($> 50\text{k}\Omega$) $\to$ GPIO 34 voltage drops toward 0V (ADC count $< 1500$). ESP32 firmware drives GPIO 25 `HIGH`, turning ON the MOSFET channel and lighting the LED array.

---

## 3. Pan/Tilt Servo Connection Schematic

```
               +5.0V Main Bus ─────────────────────────┐
                                                       │
                                            ┌──────────┴──────────┐
                                            │ Positive (Red Wire) │
                                            │                     │
ESP32 GPIO 18 (Pan PWM) ───────────────────►│ Signal (Orange Wire)│  [ MG90S Pan Servo ]
                                            │                     │
                                            │ Ground (Brown Wire) │
                                            └──────────┬──────────┘
                                                       │
               Common GND Bus ─────────────────────────┼─────────────────────────┐
                                                       │                         │
                                            ┌──────────┴──────────┐              │
                                            │ Positive (Red Wire) │              │
                                            │                     │              │
ESP32 GPIO 21 (Tilt PWM) ──────────────────►│ Signal (Orange Wire)│  [ MG90S Tilt Servo ]
                                            │                     │              │
                                            │ Ground (Brown Wire) │              │
                                            └─────────────────────┘              │
                                                                                 │
                                            [ 100μF 16V Electrolytic Cap ] ──────┘
                                            (Buffered between +5V and GND)
```

> [!IMPORTANT]
> **Brownout Prevention:** Always place a $100\mu\text{F} – 470\mu\text{F}$ capacitor across the $+5\text{V}$ and $\text{GND}$ servo power rail to suppress voltage dips during rapid servo acceleration.

---

## 4. MAX7219 8×32 LED Matrix Display Connection

| MAX7219 Pin | ESP32 Pin | Wire Color Convention | Description |
|---|---|:---:|---|
| **VCC** | `+5V Bus` (or VIN) | Red | 5V display power |
| **GND** | `Common GND` | Black | Ground reference |
| **DIN** | `GPIO 23` | Yellow | SPI Master-Out Slave-In (MOSI) |
| **CS / LOAD** | `GPIO 5` | Green | SPI Chip Select / Latch |
| **CLK** | `GPIO 14` | Blue | SPI Clock |

---

## 5. Active Cooling Fan Wiring (Raspberry Pi 3B)

The Raspberry Pi acrylic case incorporates a 5V brushless DC miniature cooling fan (30×30mm or 40×40mm) to dissipate heat from the Broadcom BCM2837 SoC heatsink.

```
       Raspberry Pi 3B GPIO Header (Top Corner Pins 1-6)
       
              [Pin 1: 3.3V]  [Pin 2: 5.0V]
              [Pin 3: GPIO2] [Pin 4: 5.0V] ◄── Red Wire (+) [5V Mode]
              [Pin 5: GPIO3] [Pin 6: GND ] ◄── Black Wire (-) [Ground]
                                   │
               ┌───────────────────┴───────────────────┐
               │                                       │
               ▼                                       ▼
     [ Black Wire: GND ]                     [ Red Wire: +5V / +3.3V ]
     ┌───────────────────────────────────────────────────────────────┐
     │                Miniature Brushless Cooling Fan                │
     │                    (Mounted to Acrylic Lid)                   │
     └───────────────────────────────────────────────────────────────┘
```

### Fan Pin Connection Options:

| Operating Mode | Red Wire (+) Connection | Black Wire (-) Connection | Voltage | Cooling Effect | Noise Level |
|---|:---:|:---:|:---:|:---:|:---:|
| **5V Performance (Recommended)** | **Physical Pin 4** (5V DC Rail) | **Physical Pin 6** (Ground) | 5.0V | SoC stabilizes at **~34°C – 40°C** | Soft steady hum |
| **3.3V Quiet Mode** | **Physical Pin 1** (3.3V DC Rail) | **Physical Pin 6** (Ground) | 3.3V | SoC stabilizes at **~39°C – 45°C** | Virtually silent |

> [!TIP]
> **Airflow Orientation:** Mount the fan with the label facing **inward / downward** toward the Raspberry Pi processor so cool air is pushed directly onto the aluminum heatsink.

---

## 6. OV4689 Camera Module Wiring & Pinout

The **OmniVision OV4689 4MP Back-Side Illuminated (BSI)** camera module arrives with an M12 lens, lens cover, and a 4-wire interface cable with white plastic connector tips.

```
 OV4689 Camera PCB (Rear)                       Raspberry Pi 3B
┌───────────────────────────┐                ┌───────────────────┐
│                           │                │ USB 2.0 Port 2    │
│  [4-Pin White JST Socket] │                │ (Bottom-Left)     │
│   ┌───────────────────┐   │                │                   │
│   │ [1] [2] [3] [4]   │   │  USB Cable     │  ┌─────────────┐  │
│   └───┬───┬───┬───┬───┘   │═══════════════►│  │ USB-A Plug  │  │
│       │   │   │   │       │                │  └─────────────┘  │
└───────┼───┼───┼───┼───────┘                └───────────────────┘
        │   │   │   │
        │   │   │   └─ Pin 4: GND    (Black Wire)  ── Ground Reference
        │   │   └───── Pin 3: D+     (Green Wire)  ── USB Data Plus
        │   └───────── Pin 2: D-     (White Wire)  ── USB Data Minus
        └───────────── Pin 1: VCC/5V (Red Wire)    ── +5V Bus Power
```

### Connector Pinout Details:

| Pin # | Signal Name | Wire Color | Function | Notes |
|:---:|---|:---:|---|---|
| **1** | **VCC / 5V** | **Red** | USB Bus Power (+5.0V) | Powers sensor and onboard ISP controller |
| **2** | **D-** | **White** | USB Data Negative | High-speed differential USB 2.0 data line |
| **3** | **D+** | **Green** | USB Data Positive | High-speed differential USB 2.0 data line |
| **4** | **GND** | **Black** | Power / Signal Ground | Common system ground reference |

### Physical Setup Steps:
1. **Plug the White Connector Tip:** Locate the 4-pin white female socket on the reverse side of the OV4689 camera PCB. Align the small polarizing guides/notches on the white connector plug with the socket and push gently until fully seated.
2. **Connect to Pi USB:** Plug the USB Type-A end of the cable into **USB Port 2 (Bottom-Left)** of the Raspberry Pi 3B.
3. **Remove Lens Cover:** Remove the protective plastic lens cap / film from the front of the M12 lens.
4. **Adjust Focus:** The OV4689 features an adjustable M12 screw-thread lens. If the initial video feed appears soft or out of focus:
   - Loosen the locking set-screw if present.
   - Gently rotate the outer lens barrel clockwise or counter-clockwise until subjects at **2.0m – 6.0m (classroom desk distance)** appear crisp and sharp.

---

## 7. Quick Hardware Verification Commands (On Pi Terminal)

Execute these commands via SSH on the Raspberry Pi 3B to confirm both peripherals are functioning:

```bash
# 1. Verify CPU cooling fan and monitor SoC temperature:
vcgencmd measure_temp
# Expected: temp=34.0'C to 40.0'C (with active fan running)

# 2. Check if the OV4689 camera is recognized on the USB bus:
lsusb
# Look for OmniVision Technologies or USB 2.0 Camera device

# 3. Check V4L2 video capture devices:
v4l2-ctl --list-devices
# Expected: OmniVision OV4689 Camera (/dev/video0, /dev/video1)

# 4. Run standalone camera hardware verification (no model required):
cd /path/to/CLASSCAN
python scripts/camera_verify.py --camera-only --save-raw
# Captures 5 test frames, prints frame latency, and saves camera_raw_test.jpg

# 5. Run full camera + detection inference verification:
python scripts/camera_verify.py --save
# Runs live detection and outputs camera_verify_output.jpg with bounding boxes
```
