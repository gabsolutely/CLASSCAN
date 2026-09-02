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
                                     │               │   GPIO 19 (PWM) ├┼┐│   │
                                     ▼               └─────────────────┘│││   │
                           [ OV4689 Camera Module ]                     │││   │
                                                                        │││   │
  ┌─────────────────────────────────────────────────────────────────────┘││   │
  │ Pan Servo (MG90S): Signal ── GPIO18, Power ── +5V, Ground ── GND    ││   │
  ├──────────────────────────────────────────────────────────────────────┘│   │
  │ Tilt Servo (MG90S): Signal ── GPIO19, Power ── +5V, Ground ── GND     │   │
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
ESP32 GPIO 19 (Tilt PWM) ──────────────────►│ Signal (Orange Wire)│  [ MG90S Tilt Servo ]
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
