# CLASSCAN — Bill of Materials (BOM) & Sourcing Specification

**Project:** Intelligent Classroom Headcount Monitoring System  
**Hardware Revision:** Prototype v1.1  
**Currency Conversion Baseline:** ~₱56.00 PHP = $1.00 USD  

---

## 1. Itemized Component Breakdown

| Item | Category | Component & Specification | Qty | Unit Cost (PHP) | Total Cost (PHP) | Est. Cost (USD) | Sourcing / Vendor | Hardware Status |
|---|---|---|:---:|:---:|:---:|:---:|---|:---:|
| **1** | Compute Engine | **Raspberry Pi 3 Model B (1GB RAM)**<br>• Quad-core 64-bit ARM Cortex-A53 @ 1.2 GHz<br>• Onboard Wi-Fi (802.11n) & Bluetooth 4.1<br>• 4× USB 2.0, HDMI, CSI, DSI, Micro-SD | 1 | ₱1,400.00 | ₱1,400.00 | $25.00 | Used bundle (incl. 16GB SD card) / Local secondhand | **In Hand & Active** |
| **2** | Microcontroller | **ESP32-WROOM-32 DevKit V1 (30-pin)**<br>• Dual-core Xtensa 32-bit LX6 @ 240 MHz<br>• 520 KB SRAM, 4 MB Flash<br>• Native ADC, PWM timers, Micro-USB UART | 1 | ₱190.00 | ₱190.00 | $3.40 | Shopee / Lazada / Makerlab | **In Hand & Active** |
| **3** | Vision Sensor | **OmniVision OV4689 4MP USB Camera Module**<br>• 1/3" Back-Side Illuminated (BSI) sensor<br>• Driverless UVC compliance via USB Type-C/A (4-pin harness)<br>• Wide-angle M12 lens, high low-light sensitivity | 1 | ₱1,150.00 | ₱1,150.00 | $20.50 | Sourced / Online Electronics Importer | **In Hand & Active** |
| **4** | Pan/Tilt Actuators | **TowerPro MG90S Metal-Gear Micro Servos**<br>• Operating voltage: 4.8V – 6.0V<br>• Stall torque: 2.2 kg·cm @ 6V<br>• Authentic metal gears for pan/tilt mechanical durability<br>• *Includes 2 active units + 2 recommended spares* | 4 | ₱110.00 | ₱440.00 | $7.85 | Makerlab / e-Gizmo / Shopee Preferred | **Active + Spares** |
| **5** | Display Module | **2.42" OLED Display Module (SSD1309, 128×64, SPI)**<br>• High-contrast monochrome white OLED (128×64 pixels)<br>• 7-pin SPI header (GND, VCC, SCL/D0, SDA/D1, RES, DC, CS)<br>• High-speed hardware SPI, no desoldering required | 1 | ₱350.00 | ₱350.00 | $6.25 | Shopee / Lazada / Makerlab | **Procurement Spec** |
| **6** | Ambient Sensor | **GL5528 Light Dependent Resistor (LDR)**<br>• 5mm Photoresistor + 10kΩ 1/4W pull-down resistor<br>• Analog voltage divider for ambient brightness reading | 1 | ₱15.00 | ₱15.00 | $0.27 | Local Electronics Store | **In Hand** |
| **7** | Illumination Module | **5V Auxiliary White LED Strip & Driver Module**<br>• High-efficiency 5V White LED Strip segment<br>• IRLZ44N Logic-Level N-Channel MOSFET (or 2N2222 NPN)<br>• Current-limiting & gate pull-down resistors (10kΩ / 100Ω) | 1 set | ₱110.00 | ₱110.00 | $1.96 | Makerlab / e-Gizmo / Shopee | **Procurement Spec** |
| **8** | Power Source | **18650 Li-ion Cell (3.7V Nominal, 3.0V–4.2V)**<br>• Single high-capacity rechargeable 18650 cell (2600–3000mAh)<br>• Compact footprint for enclosure integration | 1 | ₱120.00 | ₱120.00 | $2.14 | Local Battery Vendor / Shopee | **In Hand** |
| **9** | Power Regulation | **18650 DC-DC Boost Converter (5V / 2A Step-Up)**<br>• Steps single-cell 3.0V–4.2V input up to regulated 5.0V<br>• *Must be BOOST (step-up), not buck; skip if charge module has 5V 2A out* | 1 set | ₱95.00 | ₱95.00 | $1.70 | Makerlab / Shopee / Lazada | **Procurement Spec** |
| **10** | Mechanical Enclosure | **ABS Junction Box Enclosure (150×110×70 mm)**<br>• Waterproof / dustproof flame-retardant ABS enclosure<br>• Houses Pi 3B (in acrylic case with fan), ESP32, & battery with airflow<br>• Pan/tilt bracket mounting platform for MG90S | 1 | ₱220.00 | ₱220.00 | $3.93 | Shopee / Local Hardware Store | **Procurement Spec** |
| **11** | Pan/Tilt Bracket | **Pan/Tilt Camera Platform Bracket Kit**<br>• Dual-axis mechanical bracket fitted for SG90 / MG90S servos<br>• Direct mounting plate for OV4689 camera module | 1 set | ₱95.00 | ₱95.00 | $1.70 | Shopee / Lazada / Makerlab | **Procurement Spec** |
| **12** | Interconnects & Misc | **Wiring, Fasteners & Mounting Hardware**<br>• Dupont jumper wires (M-M, M-F 20cm/10cm ribbon)<br>• M3 nylon/brass standoff screw kit + ceiling-mount screws<br>• Cable ties + short Micro-USB sync cable (Pi ↔ ESP32) | 1 set | ₱180.00 | ₱180.00 | $3.20 | Hardware Supply / Lab Stock | **In Hand / Spec** |

---

## 2. Cost Summary

| Summary Category | Amount (PHP) | Amount (USD) |
|---|:---:|:---:|
| **Compute & Electronics (Pi 3B, ESP32, Camera, Servos + Spares, OLED)** | ₱3,530.00 | $63.00 |
| **Power, Sensing & Illumination System (18650, Boost Converter, LDR, LED Strip + MOSFET)** | ₱340.00 | $6.07 |
| **Enclosure, Pan/Tilt Bracket, Cabling & Fasteners** | ₱495.00 | $8.83 |
| **Total Estimated Hardware Investment** | **₱4,365.00** | **$77.90** |

---

## 3. Pre-Purchase Sourcing & Verification Guide

When purchasing components online (Shopee, Lazada) or through local distributors, use the exact search strings below and verify each critical parameter before completing the order:

| Item | Exact Search String | What to Check Before Buying |
|---|---|---|
| **OLED Display** | `2.42 inch OLED SSD1309 128x64 SPI` | • Listing title MUST explicitly say **SSD1309** (NOT SSD1306 or SH1106).<br>• Module size must be **2.42"** with a **7-pin header** (`GND`, `VCC`, `SCL/D0`, `SDA/D1`, `RES`, `DC`, `CS`).<br>• Many modules ship factory-configured for **SPI**; converting to I2C requires moving surface-mount resistors on the back PCB. Buy as-shipped and wire as SPI (faster refresh rate, zero soldering required).<br>• Verify seller photos confirm the 7-pin header. |
| **Enclosure Box** | `ABS junction box 150x110x70` *(or `waterproof enclosure box`)* | • Internal dimensions must be **at least ~150 × 110 × 70 mm** so the Raspberry Pi 3B (mounted inside its acrylic case with cooling fan), ESP32, and 18650 battery fit with adequate airflow space.<br>• **Pre-order action:** Measure your Pi in its acrylic case first to confirm enclosure internal clearance.<br>• Can also be sourced directly off the shelf from local hardware stores (e.g., Ace Hardware, Handyman, electrical supply). |
| **Pan/Tilt Bracket** | `pan tilt bracket MG90S` *(or `pan tilt platform SG90 MG90S`)* | • Listing must explicitly state compatibility with micro servos (**SG90 / MG90S**).<br>• Skip any listings that bundle unknown or non-branded cheap plastic servos; purchase the bracket standalone. |
| **Spare Servos** | `MG90S servo metal gear` ×2 | • Look for explicit **"metal gear"** specification and inspect customer reviews with disassembly photos showing brass/metal internal gears.<br>• Counterfeit MG90S units with nylon gears are common; avoid unvetted Facebook Marketplace listings unless tested under load. |
| **Power Regulation** | `18650 boost converter 5V 2A` | • A single 18650 cell outputs **3.0V – 4.2V**, which is below the 5.0V system bus requirement. You need a **BOOST (step-up)** converter, **NOT a buck** (step-down) converter.<br>• **Verification check first:** Check whether your existing 18650 charging / protection module already integrates a regulated 5V ≥2A output. If it does, skip purchasing a separate boost converter. |
| **Illumination** | `5V white LED strip`, `IRLZ44N MOSFET` *(or `2N2222`)*, assorted resistors | • The **IRLZ44N** is a logic-level N-channel MOSFET that fully saturates at 3.3V/5V logic levels, preventing thermal throttling.<br>• Ensure total LED strip current draw stays well within the boost converter's rated capacity (e.g., ≤ 500mA for LEDs to leave ≥ 1.5A for Pi and ESP32). |
| **Misc Hardware** | `Dupont jumper wires`, `M3 standoff screw kit`, `cable ties` | • Get assorted 10cm and 20cm Dupont jumpers (M-M and M-F).<br>• Short Micro-USB to USB-A cable for clean Pi ↔ ESP32 communication without excess slack.<br>• Standard M3 nylon/brass standoffs and wood/drywall screws for ceiling mounting. |

---

## 4. Recommended Philippine Electronics Vendors

For servos and semiconductor components where counterfeits are common on open marketplaces, consider dedicated Philippine hobbyist electronics shops:

1. **Makerlab Electronics** (`makerlab-electronics.com` / Shopee Mall / Lazada Mall):
   - Reliable source for genuine MG90S metal-gear servos, IRLZ44N logic-level MOSFETs, ESP32 DevKits, and MT3608/boost modules.
2. **e-Gizmo Mechatronics Central** (`egizmo.net` / Taft Ave, Manila / Online):
   - Proven component quality, authenticated ICs, breakout boards, sensors, and hardware hardware accessories.
3. **Local Hardware Supply Stores (Ace Hardware, Handyman, Wilcon, Electrical Wholesalers):**
   - Excellent for sourcing ABS waterproof junction boxes (150×110×70 mm or larger), cable ties, M3 mounting hardware, and ceiling anchors without shipping delays.

---

## 5. Component Selection Justifications

1. **Raspberry Pi 3B vs. Alternative SBCs:**
   - Provides native quad-core 64-bit ARM CPU capability with mature Linux drivers, official `ai-edge-litert` wheel compatibility, and onboard Wi-Fi without requiring external wireless USB dongles.
2. **ESP32 Microcontroller vs. Direct Pi GPIO Control:**
   - Offloads real-time PWM servo pulse generation and high-frequency ADC sampling from the Pi CPU.
   - Shields the Pi from servo back-EMF spikes and allows independent system failsafe operations.
3. **OV4689 BSI USB Camera vs. Standard Pi Camera v2:**
   - The OmniVision OV4689 sensor utilizes Back-Side Illumination (BSI) architecture, providing superior quantum efficiency and lower read noise under dim fluorescent classroom lighting.
   - Standard USB Video Class (UVC) compliance allows driverless operation across Linux systems via standard OpenCV V4L2 pipelines.
4. **MG90S Metal-Gear Servos vs. Plastic SG90:**
   - Metal gears withstand the mechanical fatigue of continuous automated sweep motions without stripping teeth under the weight of the camera and bracket.
5. **SSD1309 2.42" OLED (SPI) vs. MAX7219 Dot Matrix:**
   - High pixel density (128×64) allows rendering clear numeric counts alongside system status icons, network state, and mode indicators.
   - Crisp emissive white pixels on pure black provide superior wide-angle visibility in varied classroom lighting compared to LED dot matrices.
   - 7-pin SPI interface as shipped provides high-speed, tear-free display updates without requiring delicate SMD solder jumper rework.
6. **Single 18650 with 5V/2A Boost Converter vs. 2S Buck:**
   - A single 18650 cell (3.0V – 4.2V) reduces battery pack weight and volume.
   - A dedicated 5V 2A boost converter provides a stable, regulated 5.0V bus to both the Pi 3B and ESP32.
7. **IRLZ44N Logic-Level MOSFET vs. Standard BJT:**
   - The IRLZ44N features a low gate threshold voltage ($V_{GS(th)} \le 2\text{V}$), allowing it to be fully driven into saturation by the ESP32's 3.3V GPIO without requiring intermediate driver stages or dissipating excessive heat.
8. **ABS Junction Box (150×110×70 mm) Enclosure:**
   - Provides a standardized, flame-retardant, dust-resistant housing that fits the Pi 3B (with its acrylic case and 5V cooling fan), the ESP32 DevKit, and power circuitry with sufficient clearance for thermal convection.
