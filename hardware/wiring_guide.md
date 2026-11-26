# CLASSCAN — Complete System Wiring & Circuit Guide

> [!IMPORTANT]
> **Assembly Status (Nov 2026):** **Battery modules and perfboard are removed** — the unit runs directly on **tethered 5V wall power** via a soft power cable entering the enclosure through a single `15×10 mm` pass-through slot. **ESP32 and LCD2004 part-side terminal wires are hot-glued directly** to prevent vibration disconnects; **mid-span wire-to-wire splices are electrical-taped (not glued)** so components remain serviceable for troubleshooting inside the enclosure.

This document provides full hardware interconnections, circuit schematics, and power distribution diagrams for the CLASSCAN system.

---

## 1. System Interconnection Architecture

```
                      [ External Wall Power PSU (5V ≥3A / 45W USB-C Brick) ]
                                       │
                        Soft High-Current Power Cable
                     (Enters 15×10 mm wall pass-through slot)
                                       │
                                       ▼
                        [ Taped Inline 5V / GND Splice Hub ]
                        (Not glued — serviceable wire-to-wire tap)
                 ┌─────────────────────┴──────────────────────┐
                 │ +5V → Pi (via 5.1kΩ USB-C→Micro-USB        │ Direct +5V & Common GND Bus
                 │       adapter / breakout)                  │ (Servos, LCD VCC, LED Bar)
                 ▼                                            ▼
        ┌─────────────────┐                          ┌─────────────────┐
        │ Raspberry Pi 3B │                          │ ESP32 DevKit V1 │
        │ (Micro-USB In)  │◄────── USB Serial ──────►│ (Terminals Glued│
        │                 │  (CP2102 UART @ 115200)  │  no perfboard)  │
        │  USB Port 2 ────┼───────────┐              │                 │
        └─────────────────┘           │              │   GPIO 34 (ADC) ├──────┐
                         Soft DATA-Carrying          │   GPIO 25 (OUT) ├──┐   │
                         Type-C Camera Cable         │   GPIO 14 (PWM) ├┐ │   │
                                      │              │   GPIO 13 (PWM) ├┼┐│   │
                                      ▼              │   GPIO 21/22 I2C├┼┼┐   │
                            [ OV4689 Camera Module ] └─────────────────┘│││   │
                                                                        │││   │
  ┌─────────────────────────────────────────────────────────────────────┘││   │
  │ Pan Servo (MG90S): Signal ── GPIO14, Power ── +5V, Ground ── GND    ││   │
  ├──────────────────────────────────────────────────────────────────────┘│   │
  │ Tilt Servo (MG90S): Signal ── GPIO13, Power ── +5V, Ground ── GND     │   │
  ├───────────────────────────────────────────────────────────────────────┘   │
  │ LCD2004 Display: SDA ── GPIO21, SCL ── GPIO22, Power ── +5V, GND ── GND   │
  ├───────────────────────────────────────────────────────────────────────────┤
  │ Illumination Driver (IRLZ44N): Gate ── GPIO25, Strip ── +5V, GND ── GND   │
  └───────────────────────────────────────────────────────────────────────────┘
    LDR Ambient Sensor: Signal ── GPIO34, Power ── 3.3V, Ground ── GND
```

> [!IMPORTANT]
> **Two-Part Harness & Wall Power USB-C Notes:**
> 1. **Glue terminals only, tape wire-to-wire splices:** Hot-glue short part-side leads directly onto the ESP32 headers, LCD2004 backpack, and inline MOSFET/LDR terminals. Wrap mid-span **wire-to-wire joints in electrical tape only** so branches can be opened for troubleshooting even if the box isn't reopened frequently.
> 2. **USB-C Wall PSU → Pi 3B Micro-USB:** Because the Pi 3 Model B uses a **Micro-USB** power input (5V), pair a soft USB-C power cable with a **USB-C(F) → Micro-USB(M) adapter/5V breakout with 5.1kΩ CC pulldown resistors** (so a 45W USB-C PD charger outputs 5V VBUS), or use a **soft high-current USB-A → Micro-USB cable**.
> 3. **Soft Data Cable for Camera Head:** The OV4689 pan/tilt head must use a **lightweight, flexible data-carrying Type-C cable** — heavy stiff cables drag down the MG90S servos, and charge-only cables omit `D+`/`D-` data wires.

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
3. **Power Budget:** Ensure the 5V white LED strip segment draws $\le 500\text{ mA}$ and connects to the main +5V wall supply splice (never through the ESP32 USB diode) so the Raspberry Pi 3B retains clean headroom.
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
ESP32 GPIO 14 (Pan PWM) ───────────────────►│ Signal (Orange Wire)│  [ MG90S Pan Servo ]
                                            │                     │
                                            │ Ground (Brown Wire) │
                                            └──────────┬──────────┘
                                                       │
               Common GND Bus ─────────────────────────┼─────────────────────────┐
                                                       │                         │
                                            ┌──────────┴──────────┐              │
                                            │ Positive (Red Wire) │              │
                                            │                     │              │
ESP32 GPIO 13 (Tilt PWM) ──────────────────►│ Signal (Orange Wire)│  [ MG90S Tilt Servo ]
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
> **I2C, Servo Pins & Two-Part Harness:** LCD I2C uses default hardware pins **GPIO 21 (SDA)** and **GPIO 22 (SCL)** via `Wire.begin(PIN_LCD_SDA, PIN_LCD_SCL)`. Servos are wired to **GPIO 14 (Pan)** and **GPIO 13 (Tilt)**. **Hot-glue part-side leads directly onto both the ESP32 headers and LCD2004 backpack**, and join the mid-span wire-to-wire extensions with **electrical tape** (un-glued) so the display/ESP32 can still be serviced.

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
1. **Plug & Route Soft Data Cable:** Connect the OV4689 camera to **USB Port 2** of the Pi 3B using a **thin, flexible data-carrying USB Type-C cable** (`D+`, `D-`, `VCC`, `GND` — NOT a charge-only cable). Flexible silicone cabling is required so pan/tilt sweeps do not overload the MG90S servos.
2. **Remove Lens Cover:** Remove the protective plastic lens cap / film from the front of the M12 lens.
3. **Adjust Focus:** The OV4689 features an adjustable M12 screw-thread lens. If the initial video feed appears soft or out of focus:
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

## 8. Physical Enclosure Assembly & Layout (ABS Junction Box 174×174×73 mm)

The central hardware hub is housed within a **174 × 174 × 73 mm ABS junction box** (160 × 160 × 63 mm internal cavity, see `CAD/classcan_cad.py`), providing mechanical rigidity, dust protection, and airflow for continuous thermal dissipation.

### Component Placement, Holes & Two-Part Wiring Guidelines:
1. **Enclosure Cutouts & Power Cable Entry:**
   - **No separate battery/charger slot needed:** Because the battery/boost module is removed and an internal USB power port facing a wall cannot accept a rigid exterior plug comfortably, the dedicated USB-C charger cutout on `+Y` is omitted.
   - **Power Entry Slot (`15×10 mm` pass-through):** Uses a single `15×10 mm` slot (repurposing the former rocker switch cutout) on the `-X` wall so the **soft high-current power cable** threads cleanly inside toward the taped 5V split and Pi Micro-USB input with ≥20 mm bend clearance.
2. **Internal Component Placement (No Perfboard / No Battery):**
   - **Base Floor:** Secure the Raspberry Pi 3B (in its acrylic case) and the ESP32 DevKit inside the tray. Hot-glue part-side terminal leads directly at the ESP32 headers and LCD2004 backpack.
   - **Two-Part Harness & Serviceability:** Wire runs are divided into two parts — **part-side glued pigtails** and **electrical-taped mid-span wire-to-wire splices**. Never hot-glue wire-to-wire joins; electrical tape keeps every branch inspectable and replaceable if the enclosure needs troubleshooting.
3. **Convective Airflow:** Drill 4 mm ventilation hole arrays along opposite walls (see `classcan_cad_out/template_wall_*.svg`) to vent warm air from the Pi's cooling fan.
4. **Pan/Tilt Head & Soft Camera Cable:** Mount the MG90S pan/tilt bracket externally under the enclosure lid, routing servo leads and a **soft data-carrying Type-C camera cable** (thin/flexible jacket so servos are not overloaded) through the `16 mm` lid cable hole.

