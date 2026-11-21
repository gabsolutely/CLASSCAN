# CLASSCAN — ESP32 Pinout & GPIO Reference

This document defines the physical GPIO pin assignments and electrical characteristics for the **ESP32-WROOM-32 DevKit V1 (30-Pin)** microcontroller used in CLASSCAN.

All definitions in this document strictly align with `src/esp32/include/config.h` and the modular firmware drivers (`lcd_display.h`).

> [!NOTE]
> **Hardware Status (Nov 2026):** ESP32 DevKit V1 is **soldered and permanently integrated** into the CLASSCAN circuit board. All GPIO connections below reflect the final soldered pinout.

> [!CAUTION]
> **Trial 1 pin conflict (resolved):** During the Nov 12 build trial, `PIN_PAN` was incorrectly set to GPIO 14 — the same pin as `PIN_LCD_SDA`. This caused a hardware conflict. The pan servo signal was corrected to **GPIO 18** in `config.h` after the trial.

---

## 1. GPIO Pin Assignment Table

| Pin Name / Number | GPIO Number | Function / Peripheral | Connected Component | Direction / Type | Electrical Notes |
|---|:---:|---|---|:---:|---|
| **GPIO 34** | `GPIO 34` | `ADC1_CH6` | **GL5528 Light Dependent Resistor (LDR)** | Input (Analog) | Reads analog voltage (0–3.3V → 0–4095 ADC counts). Connected to LDR + 10kΩ pull-down divider. Input-only pin (no internal pull-up/down). |
| **GPIO 25** | `GPIO 25` | Digital I/O | **Auxiliary Illumination Driver** | Output (Digital) | Drives gate of **IRLZ44N logic-level N-MOSFET** (or 2N2222 base via 1kΩ) to switch the 5V white LED strip. 10kΩ gate pulldown to GND. |
| **GPIO 18** | `GPIO 18` | Hardware PWM (Timer 0) | **MG90S Pan Servo (Horizontal)** | Output (PWM) | 50 Hz PWM control pulse (1000 μs – 2000 μs pulse width). Corrected from GPIO 14 after Trial 1. |
| **GPIO 13** | `GPIO 13` | Hardware PWM | **MG90S Tilt Servo (Vertical Pitch)** | Output (PWM) | 50 Hz PWM speed command; 1500 μs is stop. Remapped from GPIO 21 (freed for LCD SDA). |
| **GPIO 14** | `GPIO 14` | I2C SDA (Bus 1) | **LCD2004 SDA (PCF8574 backpack)** | Output (I2C) | I2C data line for LCD2004 20×4 character display. 400 kHz fast mode. Remapped from GPIO 21 to free default I2C bus for other peripherals. |
| **GPIO 27** | `GPIO 27` | I2C SCL (Bus 1) | **LCD2004 SCL (PCF8574 backpack)** | Output (I2C) | I2C clock line for LCD2004. Default PCF8574 address: 0x27 (try 0x3F if blank). Remapped from GPIO 22 (paired with SDA on GPIO 14, Wire.begin(14, 27)). |
| **GPIO 1 (TX0)** | `GPIO 1` | UART0 TX | **USB-UART Bridge → Pi 3B** | Output (Serial) | Transmits JSON status (`{"type":"state","value":"idle"}`) to Pi 3B at 115200 baud. |
| **GPIO 3 (RX0)** | `GPIO 3` | UART0 RX | **USB-UART Bridge → Pi 3B** | Input (Serial) | Receives JSON headcount/commands from Pi 3B at 115200 baud. |
| **VIN** | — | Power Input | **5V Power Bus** | Power In | Regulated 5.0V DC input from 18650 step-up boost converter. Also powers LCD2004 VCC. |
| **3V3** | — | Regulated Output | **Sensor 3.3V Rail** | Power Out | 3.3V reference for LDR voltage divider. I2C pull-ups (4.7kΩ) reference this rail. |
| **GND** | — | Common Ground | **System Ground Bus** | Ground | Common system ground shared with Pi 3B, servos, boost converter, and battery protection. |

---

## 2. DevKit V1 Pinout Diagram

```
                       +-------------------------+
                       |     ESP32 DevKit V1     |
                       |                         |
            3.3V Rail -+ 3V3                 GND +- Common Ground Bus
                       | EN               GPIO23 +-
     LDR Analog (ADC1)-+ GPIO34           GPIO22 +-
                       | GPIO35            GPIO1 +- UART0 TX (Serial to Pi)
                       | GPIO32            GPIO3 +- UART0 RX (Serial from Pi)
                       | GPIO33           GPIO21 +-
  Illumination (Gate) -+ GPIO25           GPIO18 +- Pan Servo Signal (PWM) ← corrected from D12
                       | GPIO27 (LCD SCL)  GPIO5 +-
                       | GPIO14 (LCD SDA) GPIO17 +-
                       | GPIO2            GPIO16 +-
                       | GPIO4            GPIO15 +-
                       | GND              GPIO13 +- Tilt Servo Signal (PWM)
        5V Power Input-+ VIN              GPIO12 +-
                       +-------------------------+
```

---

## 3. Electrical Guidelines & Precautions

1. **ADC Input Voltage Protection:**
   - The ESP32 ADC inputs (including GPIO 34) are rated for a maximum of **3.3V**. The LDR voltage divider must be energized from the **3V3 pin**, never from the 5V power rail.
2. **Servo Power Isolation:**
   - Never power the MG90S servo $V_{cc}$ lines directly from the ESP32 3.3V or VIN pins. Servo positive power ($+5\text{V}$) must connect directly to the main 5V power bus, with the ground tied to the common system ground.
3. **Logic-Level Illumination Switching (IRLZ44N):**
   - Use a logic-level N-MOSFET (IRLZ44N) that fully turns on with 3.3V logic. Always wire a 10kΩ resistor between GPIO 25 and GND to prevent the LEDs from glowing during bootloader startup.
4. **LCD2004 Power (5V Required):**
   - The LCD2004 module and its PCF8574 backpack require **5V** on VCC for the backlight and contrast. Wiring to 3.3V results in a dim or blank display. Connect VCC directly to the 5V bus (ESP32 VIN or the system 5V rail).
5. **I2C Pull-ups:**
   - The PCF8574 backpack typically includes onboard 4.7kΩ pull-up resistors. If not, add 4.7kΩ between SDA/SCL and the 3.3V rail. Do not pull up to 5V — the ESP32 I2C pins are 3.3V logic.
6. **GPIO Remap (I2C):**
   - LCD I2C is on **GPIO 14 (SDA) / GPIO 27 (SCL)** via `Wire.begin(14, 27)`. GPIO 21 was freed from tilt servo duty (tilt is on GPIO 13). GPIO 13 is hardware-PWM capable and has no boot-time strapping constraints.
7. **Pan Servo Pin (Trial 1 fix):**
   - Pan servo was originally wired to GPIO 12 during the Nov 12 build trial, then briefly set to GPIO 14 in `config.h` (conflicting with LCD SDA). **Final correct pin: GPIO 18.** GPIO 12 has a boot-strapping function and should be avoided for servo signals.
8. **Serial Level Shifting:**
   - The onboard CP2102/CH340 USB-UART bridge provides compliant USB signaling to the Raspberry Pi 3B USB-A port without requiring external level shifters.
