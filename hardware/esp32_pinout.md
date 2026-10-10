# CLASSCAN — ESP32 Pinout & GPIO Reference

This document defines the physical GPIO pin assignments and electrical characteristics for the **ESP32-WROOM-32 DevKit V1 (30-Pin)** microcontroller used in CLASSCAN.

All definitions in this document strictly align with `src/esp32/include/config.h` and the modular firmware drivers.

---

## 1. GPIO Pin Assignment Table

| Pin Name / Number | GPIO Number | Function / Peripheral | Connected Component | Direction / Type | Electrical Notes |
|---|:---:|---|---|:---:|---|
| **GPIO 34** | `GPIO 34` | `ADC1_CH6` | **GL5528 Light Dependent Resistor (LDR)** | Input (Analog) | Reads analog voltage (0–3.3V $\to$ 0–4095 ADC counts). Connected to LDR + 10kΩ pull-down divider. Input-only pin (no internal pull-up/down). |
| **GPIO 25** | `GPIO 25` | Digital I/O | **Auxiliary Illumination Module** | Output (Digital) | Drives gate of 2N7000 N-MOSFET (or base of 2N2222 transistor via 1kΩ resistor) to switch 4× White LEDs. |
| **GPIO 18** | `GPIO 18` | Hardware PWM (Timer 0) | **MG90S Pan Servo (Horizontal)** | Output (PWM) | 50 Hz PWM control pulse (500 μs – 2500 μs pulse width corresponding to $0^\circ$ – $180^\circ$ rotation). |
| **GPIO 21** | `GPIO 21` | Hardware PWM | **MG90S Tilt Servo (Vertical Pitch)** | Output (PWM) | 50 Hz PWM speed command; 1500 μs is stop. |
| **GPIO 16** | `GPIO 16` | I2C SDA (Bus 1) | **SSD1306 OLED Display (SDA)** | Output (I2C Data) | I2C serial data to 0.96" 128×64 OLED headcount display (400 kHz fast mode). |
| **GPIO 17** | `GPIO 17` | I2C SCL (Bus 1) | **SSD1306 OLED Display (SCL)** | Output (I2C Clock) | I2C clock to SSD1306; uses ESP32 hardware I2C bus 1 to avoid conflicts. |
| **GPIO 1 (TX0)** | `GPIO 1` | UART0 TX | **USB-UART Bridge $\to$ Pi 3B** | Output (Serial) | Transmits JSON status (`{"type":"state","value":"idle"}`) to Pi 3B at 115200 baud. |
| **GPIO 3 (RX0)** | `GPIO 3` | UART0 RX | **USB-UART Bridge $\to$ Pi 3B** | Input (Serial) | Receives JSON headcount/commands from Pi 3B at 115200 baud. |
| **VIN** | — | Power Input | **5V Power Bus** | Power In | Regulated 5.0V DC input from step-up boost converter. |
| **3V3** | — | Regulated Output | **Sensor 3.3V Rail** | Power Out | 3.3V reference voltage for LDR voltage divider circuit. |
| **GND** | — | Common Ground | **System Ground Bus** | Ground | Common system ground shared with Pi 3B, servos, and battery management. |

---

## 2. DevKit V1 Pinout Diagram

`
                       +-------------------------+
                       |     ESP32 DevKit V1     |
                       |                         |
            3.3V Rail -+ 3V3                 GND +- Common Ground Bus
                       | EN                GPIO23 +-
     LDR Analog (ADC1)-+ GPIO34            GPIO22 +-
                       | GPIO35             GPIO1 +- UART0 TX (Serial to Pi)
                       | GPIO32             GPIO3 +- UART0 RX (Serial from Pi)
                       | GPIO33            GPIO21 +- Tilt Servo Signal (PWM)
   Illumination Driver-+ GPIO25            GPIO18 +- Pan Servo Signal (PWM)
                       | GPIO26             GPIO5 +-
                       | GPIO27            GPIO17 +- SSD1306 OLED SCL (I2C)
                       | GPIO14            GPIO16 +- SSD1306 OLED SDA (I2C)
                       | GPIO12             GPIO4 +-
                       | GPIO13             GPIO2 +-
                       | GND               GPIO15 +-
        5V Power Input -+ VIN              GPIO15 +-
                       +-------------------------+
`

## 3. Electrical Guidelines & Precautions

1. **ADC Input Voltage Protection:**
   - The ESP32 ADC inputs (including GPIO 34) are rated for a maximum of **3.3V**. The LDR voltage divider must be energized from the **3V3 pin**, never from the 5V power rail.
2. **Servo Power Isolation:**
   - Never power the MG90S servo $V_{cc}$ lines directly from the ESP32 3.3V or VIN pins. Servo positive power ($+5\text{V}$) must connect directly to the main 5V power bus, with the ground tied to the common system ground.
3. **Serial Level Shifting:**
   - The onboard CP2102/CH340 USB-UART bridge provides compliant USB signaling to the Raspberry Pi 3B USB-A port without requiring external level shifters.
