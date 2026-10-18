# CLASSCAN — ESP32 Pinout & GPIO Reference

This document defines the physical GPIO pin assignments and electrical characteristics for the **ESP32-WROOM-32 DevKit V1 (30-Pin)** microcontroller used in CLASSCAN.

All definitions in this document strictly align with `src/esp32/include/config.h` and the modular firmware drivers (`oled_display.h`).

---

## 1. GPIO Pin Assignment Table

| Pin Name / Number | GPIO Number | Function / Peripheral | Connected Component | Direction / Type | Electrical Notes |
|---|:---:|---|---|:---:|---|
| **GPIO 34** | `GPIO 34` | `ADC1_CH6` | **GL5528 Light Dependent Resistor (LDR)** | Input (Analog) | Reads analog voltage (0–3.3V $\to$ 0–4095 ADC counts). Connected to LDR + 10kΩ pull-down divider. Input-only pin (no internal pull-up/down). |
| **GPIO 25** | `GPIO 25` | Digital I/O | **Auxiliary Illumination Driver** | Output (Digital) | Drives gate of **IRLZ44N logic-level N-MOSFET** (or 2N2222 base via 1kΩ) to switch the 5V white LED strip. 10kΩ gate pulldown to GND. |
| **GPIO 18** | `GPIO 18` | Hardware PWM (Timer 0) | **MG90S Pan Servo (Horizontal)** | Output (PWM) | 50 Hz PWM control pulse (500 μs – 2500 μs pulse width corresponding to $0^\circ$ – $180^\circ$ rotation). |
| **GPIO 21** | `GPIO 21` | Hardware PWM | **MG90S Tilt Servo (Vertical Pitch)** | Output (PWM) | 50 Hz PWM speed command; 1500 μs is stop. |
| **GPIO 14** | `GPIO 14` | SPI SCK | **SSD1309 OLED D0 / SCK (Primary SPI)** | Output (Clock) | SPI clock line for 7-pin SSD1309 OLED display module (as shipped, no soldering). |
| **GPIO 27** | `GPIO 27` | SPI MOSI | **SSD1309 OLED D1 / MOSI (Primary SPI)** | Output (Data) | SPI data line for 7-pin SSD1309 OLED display module. |
| **GPIO 4** | `GPIO 4` | Digital Output | **SSD1309 OLED RES (Reset)** | Output (Digital) | Hardware reset line (active low) for SSD1309 OLED. |
| **GPIO 2** | `GPIO 2` | Digital Output | **SSD1309 OLED DC (Data/Command)** | Output (Digital) | Data/Command select line for SSD1309 OLED in SPI mode. |
| **GPIO 5** | `GPIO 5` | SPI CS | **SSD1309 OLED CS (Chip Select)** | Output (Digital) | Chip select line (active low) for SSD1309 OLED in SPI mode. |
| *GPIO 16* | *GPIO 16* | *I2C SDA (Bus 1)* | *SSD1309 OLED SDA (Alternative I2C)* | *Output (I2C)* | *Used only if OLED module has been soldered/configured for I2C mode.* |
| *GPIO 17* | *GPIO 17* | *I2C SCL (Bus 1)* | *SSD1309 OLED SCL (Alternative I2C)* | *Output (I2C)* | *Used only if OLED module has been soldered/configured for I2C mode.* |
| **GPIO 1 (TX0)** | `GPIO 1` | UART0 TX | **USB-UART Bridge $\to$ Pi 3B** | Output (Serial) | Transmits JSON status (`{"type":"state","value":"idle"}`) to Pi 3B at 115200 baud. |
| **GPIO 3 (RX0)** | `GPIO 3` | UART0 RX | **USB-UART Bridge $\to$ Pi 3B** | Input (Serial) | Receives JSON headcount/commands from Pi 3B at 115200 baud. |
| **VIN** | — | Power Input | **5V Power Bus** | Power In | Regulated 5.0V DC input from 18650 step-up boost converter. |
| **3V3** | — | Regulated Output | **Sensor 3.3V Rail** | Power Out | 3.3V reference voltage for LDR voltage divider circuit and OLED logic power. |
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
                       | GPIO33           GPIO21 +- Tilt Servo Signal (PWM)
  Illumination (Gate) -+ GPIO25           GPIO18 +- Pan Servo Signal (PWM)
      OLED MOSI / D1  -+ GPIO27            GPIO5 +- OLED CS (SPI)
      OLED SCK / D0   -+ GPIO14           GPIO17 +- (Alt: I2C SCL)
      OLED DC (Data)  -+ GPIO2            GPIO16 +- (Alt: I2C SDA)
      OLED Reset (RES)-+ GPIO4            GPIO15 +-
                       | GND               GPIO13 +-
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
4. **OLED SPI Default (No Soldering):**
   - Most 2.42" SSD1309 boards ship configured for 7-pin SPI. Avoid modding SMD resistors on the board; connect via SPI (GPIO 14, 27, 4, 2, 5) for high performance and zero risk of soldering damage.
5. **Serial Level Shifting:**
   - The onboard CP2102/CH340 USB-UART bridge provides compliant USB signaling to the Raspberry Pi 3B USB-A port without requiring external level shifters.
