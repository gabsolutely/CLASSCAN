# CLASSCAN — Complete System Wiring & Circuit Guide

This document provides full hardware interconnections, circuit schematics, and power distribution diagrams for the CLASSCAN system.

---

## 1. System Interconnection Architecture

```
                      [ 1× 18650 Li-ion Cell (3.0V – 4.2V) ]
                                      │
                                      ▼
                      [ 18650 Battery Protection / Charger ]
                                      │
                                      ▼
                      [ 5V / 2A DC-DC Boost Converter ]
          (Note: Skip booster if charge board has integrated 5V ≥2A out)
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
                                     │               │   GPIO 13 (PWM) ├┼┐│   │
                                     ▼               │   GPIO 21/22 I2C├┼┼┐   │
                           [ OV4689 Camera Module ]  └─────────────────┘│││   │
                                                                        │││   │
  ┌─────────────────────────────────────────────────────────────────────┘││   │
  │ Pan Servo (MG90S): Signal ── GPIO18, Power ── +5V, Ground ── GND    ││   │
  ├──────────────────────────────────────────────────────────────────────┘│   │
  │ Tilt Servo (MG90S): Signal ── GPIO13, Power ── +5V, Ground ── GND     │   │
  ├───────────────────────────────────────────────────────────────────────┘   │
  │ LCD2004 Display: SDA ── GPIO21, SCL ── GPIO22, Power ── +5V, GND ── GND   │
  ├───────────────────────────────────────────────────────────────────────────┤
  │ Illumination Driver (IRLZ44N): Gate ── GPIO25, Strip ── +5V, GND ── GND   │
  └───────────────────────────────────────────────────────────────────────────┘
    LDR Ambient Sensor: Signal ── GPIO34, Power ── 3.3V, Ground ── GND

> [!IMPORTANT]
> **Boost vs. Buck Regulation:** A single 18650 cell delivers 3.0V to 4.2V nominal. Because this voltage is lower than the 5.0V system rail, a **step-up BOOST converter** is strictly required. Do not use a buck (step-down) converter. Check first whether your 18650 charging/BMS module already includes an integrated 5V ≥2A boost output.
```

---

## 2. Custom LDR & Illumination Circuit Schematic

The illumination system combines an ambient Light Dependent Resistor (LDR) analog voltage divider with an **IRLZ44N logic-level N-channel MOSFET** (or 2N2222 NPN transistor) driving a **5V white LED strip** (or LED array).

```
LDR Sensor Divider:                     Auxiliary 5V White LED Strip Driver:
-------------------                     ------------------------------------

     +3.3V Rail (ESP32)                              +5.0V Main Power Bus
            │                                                 │
            │                                                 ├──[ (+) 5V White LED Strip ]
            ▼                                                 │            │
        ┌───────┐                                             │            ▼ (-) Cathode
        │  LDR  │ (GL5528)                                    │         Drain
        └───────┘                                             │         ┌───┐
            │                                                 │   Gate  │   │ IRLZ44N N-MOSFET
            ├────────► To ESP32 GPIO 34 (ADC1_CH6)     ESP32  ├──[100Ω]─┤   │ (Logic-Level, Vgs ≤ 2V)
            │                                         GPIO 25 │         └───┘ (or 2N2222 NPN via 1kΩ)
        ┌───────┐                                     (Signal)│        Source
        │  10kΩ │ (1/4W Pull-Down)                            │          │
        └───────┘                                             └─[10kΩ]───┤ (Gate Pulldown)
            │                                                            │
            ▼                                                            ▼
       Common GND                                                   Common GND
```

### Circuit Operation & Component Notes:
1. **IRLZ44N Logic-Level Threshold:** The IRLZ44N is specifically chosen because its gate threshold ($V_{GS(th)} \le 2.0\text{V}$) enables full channel saturation directly from the ESP32's 3.3V GPIO. Standard MOSFETs (like the IRF540N) require 10V gate drive and will overheat or fail to switch properly under 3.3V logic.
2. **Gate Pulldown Resistor (10kΩ):** Tied between the MOSFET gate and GND to prevent floating gate states and accidental LED flickering during ESP32 boot/reset.
3. **Power Budget:** Ensure the 5V white LED strip segment draws $\le 500\text{ mA}$ so the 5V/2A boost converter retains ample headroom ($\ge 1.5\text{ A}$) for the Raspberry Pi 3B, ESP32, and camera module.
4. **Daylight Conditions:** Light falls on LDR $\to$ resistance drops ($< 2\text{k}\Omega$) $\to$ GPIO 34 voltage rises toward 3.3V (ADC count $> 2500$). ESP32 firmware holds GPIO 25 `LOW` (LEDs remain OFF).
5. **Dark / Dim Conditions:** Ambient light falls $\to$ resistance increases ($> 50\text{k}\Omega$) $\to$ GPIO 34 voltage drops toward 0V (ADC count $< 1500$). ESP32 firmware drives GPIO 25 `HIGH`, turning ON the MOSFET and illuminating the target area.

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

## 4. LCD2004 I2C Display Connection (20×4 Character LCD, PCF8574 Backpack)

The headcount is shown on a **LCD2004 20×4 character LCD module** with a soldered-on **PCF8574 I2C backpack** — four wires only (VCC, GND, SDA, SCL).

> [!NOTE]
> **Why LCD2004?** Selected over the original SSD1309 OLED for superior character legibility at classroom distances and a simpler 4-wire I2C interface. No SPI wiring, no hardware reset line, no SMD soldering required.

### Wiring Table

| LCD2004 Pin | ESP32 Pin | Wire Color | Description |
|---|:---:|:---:|---|
| **VCC** | `VIN` (5V) | Red | 5V backlight + logic power (**must be 5V**, not 3.3V) |
| **GND** | `Common GND` | Black | Ground reference |
| **SDA** | `GPIO 21` | Yellow | I2C data (Bus 1, 400 kHz) |
| **SCL** | `GPIO 22` | Blue | I2C clock (Bus 1, 400 kHz) |

```
         +5V Power Bus ────────────────────────────────────► VCC (LCD2004)
         Common GND   ────────────────────────────────────► GND (LCD2004)
ESP32 GPIO 21 (SDA)  ──────[4.7kΩ pull-up to 3.3V]───────► SDA (PCF8574)
ESP32 GPIO 22 (SCL)  ──────[4.7kΩ pull-up to 3.3V]───────► SCL (PCF8574)
```

> [!IMPORTANT]
> **GPIO 21 Remap:** GPIO 21 was previously the tilt servo signal pin. It is now the LCD I2C SDA line. **Tilt servo has been remapped to GPIO 13** (`PIN_TILT` in `config.h`). Update your physical wiring accordingly before flashing.

> [!TIP]
> **I2C Address:** The PCF8574 backpack ships at **0x27** by default. If the display stays blank, try **0x3F** — change `LCD_I2C_ADDR` in `src/esp32/include/config.h`. Pull-up resistors (4.7kΩ to 3.3V) are recommended if the bus cable run exceeds ~20 cm.


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

---

## 8. Physical Enclosure Assembly & Layout (ABS Junction Box 150×110×70 mm)

The central hardware hub is housed within a **150 × 110 × 70 mm ABS junction box** (waterproof / weatherproof rated), providing mechanical rigidity, dust protection, and airflow for continuous thermal dissipation.

### Component Placement & Airflow Guidelines:
1. **Pre-Fit Measurement:** Before final drilling or mounting, measure the Raspberry Pi 3B inside its assembled acrylic case. Confirm that the Pi (~90 × 60 × 30 mm including fan and standoff height) fits comfortably with at least 15–20 mm clearance around the sides for cable bends (Micro-USB power and camera USB harness).
2. **Internal Component Partitioning:**
   - **Base Floor:** Secure the Raspberry Pi 3B (in its acrylic case) and the ESP32 DevKit to the box floor using M3 nylon standoffs or mounting rails.
   - **Battery & Boost Converter:** Secure the 18650 battery holder and boost converter board along the opposite wall, isolated from direct heat exhaust.
   - **Cable Management:** Use short (15–20 cm) USB sync cables between Pi and ESP32. Bundle and secure Dupont jumpers with cable ties to prevent wire snagging.
3. **Convective Airflow:** Drill four to six 4mm ventilation holes along the lower lateral sides and upper perimeter of the enclosure (or use cable glands) to allow warm air expelled by the Pi's 5V cooling fan to vent naturally.
4. **Pan/Tilt Head Mounting:** Secure the MG90S pan/tilt bracket platform externally to the enclosure lid or designated mounting flange, routing the servo leads and camera USB cable into the box through a sealed rubber grommet.

