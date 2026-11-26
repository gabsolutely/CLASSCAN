# CLASSCAN — ESP32 Pinout & GPIO Reference

This document defines the physical GPIO pin assignments and electrical characteristics for the **ESP32-WROOM-32 DevKit V1 (30-Pin)** microcontroller used in CLASSCAN.

All definitions in this document strictly align with `src/esp32/include/config.h` and the modular firmware drivers (`lcd_display.h`).

> [!NOTE]
> **Hardware Status (Nov 2026):** No perfboard or battery module is used — the ESP32 DevKit V1 is wired directly with **part-side terminal leads hot-glued** at the pins (including LCD2004, servo signals, LDR, and inline IRLZ44N MOSFET) and **electrical-taped mid-span splices** for serviceability. Power comes from the tethered 5V wall supply (via Pi USB serial for logic, plus taped 5V/GND rail for servos/LCD/LED).

> [!NOTE]
> **Pin Configuration:** Pan Servo is assigned to **GPIO 14**, Tilt Servo to **GPIO 13**. LCD I2C interface uses the standard hardware I2C pins **GPIO 21 (SDA)** and **GPIO 22 (SCL)**, completely eliminating any pin conflicts between servos and display.

---

## 1. GPIO Pin Assignment Table

| Pin Name / Number | GPIO Number | Function / Peripheral | Connected Component | Direction / Type | Electrical Notes |
|---|:---:|---|---|:---:|---|
| **GPIO 34** | `GPIO 34` | `ADC1_CH6` | **GL5528 Light Dependent Resistor (LDR)** | Input (Analog) | Reads analog voltage (0–3.3V → 0–4095 ADC counts). Connected to LDR + 10kΩ pull-down divider. Input-only pin (no internal pull-up/down). |
| **GPIO 25** | `GPIO 25` | Digital I/O | **Auxiliary Illumination Driver** | Output (Digital) | Drives gate of **IRLZ44N logic-level N-MOSFET** (or 2N2222 base via 1kΩ) to switch the 5V white LED strip. 10kΩ gate pulldown to GND. |
| **GPIO 14** | `GPIO 14` | Hardware PWM (Timer 0) | **MG90S Pan Servo (Horizontal)** | Output (PWM) | 50 Hz PWM control pulse (1000 μs – 2000 μs pulse width). Servos assigned to GPIO 14 (Pan) and GPIO 13 (Tilt). |
| **GPIO 13** | `GPIO 13` | Hardware PWM | **MG90S Tilt Servo (Vertical Pitch)** | Output (PWM) | 50 Hz PWM speed command; 1500 μs is stop (Standard 180° positional servo, 30° default pitch). |
| **GPIO 21** | `GPIO 21` | I2C SDA (Bus 1) | **LCD2004 SDA (PCF8574 backpack)** | Output (I2C) | I2C data line for LCD2004 20×4 character display. 400 kHz fast mode (Default ESP32 hardware I2C SDA). |
| **GPIO 22** | `GPIO 22` | I2C SCL (Bus 1) | **LCD2004 SCL (PCF8574 backpack)** | Output (I2C) | I2C clock line for LCD2004. Default PCF8574 address: 0x27 (try 0x3F if blank). Default ESP32 hardware I2C SCL. |
| **GPIO 1 (TX0)** | `GPIO 1` | UART0 TX | **USB-UART Bridge → Pi 3B** | Output (Serial) | Transmits JSON status (`{"type":"state","value":"idle"}`) to Pi 3B at 115200 baud. |
| **GPIO 3 (RX0)** | `GPIO 3` | UART0 RX | **USB-UART Bridge → Pi 3B** | Input (Serial) | Receives JSON headcount/commands from Pi 3B at 115200 baud. |
| **VIN** | — | Power Input | **5V Power Bus** | Power In | Regulated 5.0V DC input from the taped wall-PSU 5V splice (or USB VBUS). Also powers LCD2004 VCC via the 5V bus. |
| **3V3** | — | Regulated Output | **Sensor 3.3V Rail** | Power Out | 3.3V reference for LDR voltage divider. I2C pull-ups (4.7kΩ) reference this rail. |
| **GND** | — | Common Ground | **System Ground Bus** | Ground | Common system ground shared with Pi 3B, servos, LED MOSFET source, LCD, and wall PSU ground splice. |

---

## 2. DevKit V1 Pinout Diagram

```
                       +-------------------------+
                       |     ESP32 DevKit V1     |
                       |                         |
            3.3V Rail -+ 3V3                 GND +- Common Ground Bus
                       | EN               GPIO23 +-
     LDR Analog (ADC1)-+ GPIO34           GPIO22 +- LCD SCL (I2C Bus 1)
                       | GPIO35            GPIO1 +- UART0 TX (Serial to Pi)
                       | GPIO32            GPIO3 +- UART0 RX (Serial from Pi)
                       | GPIO33           GPIO21 +- LCD SDA (I2C Bus 1)
  Illumination (Gate) -+ GPIO25           GPIO18 +-
                       | GPIO27            GPIO5 +-
                       | GPIO14 (Pan PWM) GPIO17 +-
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
6. **LCD I2C Interface (GPIO 21 / 22):**
   - LCD I2C is configured on default hardware pins **GPIO 21 (SDA)** and **GPIO 22 (SCL)** via `Wire.begin(PIN_LCD_SDA, PIN_LCD_SCL)`.
7. **Servo Pins (GPIO 14 / 13):**
   - Pan servo signal is assigned to **GPIO 14** (hardware PWM).
   - Tilt servo signal is assigned to **GPIO 13** (hardware PWM). Both pins provide reliable 50 Hz PWM without conflicting with I2C or boot strapping.
8. **Serial Level Shifting:**
   - The onboard CP2102/CH340 USB-UART bridge provides compliant USB signaling to the Raspberry Pi 3B USB-A port without requiring external level shifters.
