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

> [!IMPORTANT]
> **Why No Direct Marketplace Links?**  
> Direct marketplace links are intentionally not hardcoded: search results often default to overseas retailers (Waveshare, EU, Canadian shops) that incur high shipping overhead and customs delay. Furthermore, Shopee, Lazada, and Facebook Marketplace links frequently break, point to differing variants, or lead to counterfeit items and scams.  
> Instead, use the exact search strings below and verify every specification on candidate listings before purchasing. Send shortlisted listings to verify their hardware specs against this guide.

| Item | Search this | Check before buying |
|---|---|---|
| **OLED** | `2.42 inch OLED SSD1309 128x64 SPI` | Title says **SSD1309** (not SSD1306 or SH1106) and 2.42" with 7 pins. Many of these ship set to SPI, and the I2C version needs resistors moved on the back. Buy it as shipped and wire it as SPI (faster, no soldering). Check the seller photos show a 7-pin header. |
| **Box** | `ABS junction box 150x110x70` *(or `waterproof enclosure box`)* | At least ~150x110 mm so the Pi (in its acrylic case), ESP32, and battery fit with airflow. A hardware store also sells these. **Pre-order action:** Measure your Pi in its acrylic case first so the box size is right. |
| **Pan/tilt** | `pan tilt bracket MG90S` *(or `pan tilt platform SG90 MG90S`)* | Listing says it fits micro servos (SG90/MG90S). Skip any that bundle fake servos; source the bracket standalone or with authenticated servos. |
| **Spare servos** | `MG90S servo metal gear` ×2 | Look for "metal gear" and reviews with photos. Counterfeit MG90S are common, so don't buy from FB Marketplace without testing under load. |
| **Power** | `18650 boost converter 5V 2A` | Your single 18650 is only 3–4.2V, so you need a **boost** converter, not a buck. First check whether your charging module already has a 5V ≥2A output, and if so skip this. |
| **Illumination** | `5V white LED strip`, `IRLZ44N MOSFET` *(or `2N2222`)*, assorted resistors | Total current stays within what the boost output can supply (keep LED draw ≤500mA so ≥1.5A remains for Pi 3B and ESP32). |
| **Misc** | `Dupont jumper wires`, `M3 standoff screw kit`, `cable ties` | Short USB cables for Pi to ESP32, plus ceiling-mount screws and standoffs. |

---

## 4. Recommended Philippine Electronics Vendors

For electronics specifically, **Makerlab Electronics** and **e-Gizmo** are PH shops worth checking:

1. **Makerlab Electronics** (`makerlab-electronics.com` / Shopee Mall / Lazada Mall):
   - Proven local stock for authentic MG90S metal-gear servos, IRLZ44N logic-level MOSFETs, ESP32 DevKit V1, and step-up boost converters.
2. **e-Gizmo Mechatronics Central** (`egizmo.net` / Taft Ave, Manila / Online):
   - Dedicated Philippine robotics and mechatronics distributor. Buying servos and discrete ICs from a dedicated electronics shop often beats open Shopee/Lazada listings for authenticity on servos.
3. **Local Hardware Supply Stores (Ace Hardware, Handyman, Wilcon, Electrical Wholesalers):**
   - Ideal for sourcing ABS waterproof junction boxes (150×110×70 mm or larger), cable ties, M3 mounting hardware, and ceiling anchors locally without waiting on shipping.

> [!TIP]
> **Pre-Ordering Action:** Before ordering the enclosure, physically measure your Raspberry Pi 3B inside its assembled acrylic case (including standoff height and top-mounted 5V fan) to ensure the junction box provides ample headroom for wiring bends and convective airflow.

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
