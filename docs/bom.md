# CLASSCAN — Bill of Materials (BOM) & Sourcing Specification

**Project:** Intelligent Classroom Headcount Monitoring System  
**Hardware Revision:** Phase 2 — Trial Build (Nov 2026)  
**Currency Conversion Baseline:** ~₱56.00 PHP = $1.00 USD  

> [!NOTE]
> **Hardware Status (Nov 2026):** Core compute (Pi 3B, ESP32, OV4689 camera) is active and integrated. **Battery/charge-boost modules and perfboard are retired** — the unit runs on **tethered 5V wall power** (for 12h+ school-day reliability without battery drop-out). **ESP32 and LCD2004 part-side terminal leads are hot-glued** directly at the pins/backpacks; mid-span wire-to-wire joints are **electrical-taped (not glued)** so wiring can still be opened for troubleshooting. Remaining purchases: **soft data-carrying Type-C cable** (lightweight camera lead for servos), **soft high-current Type-C power cable** (+ Micro-USB 5.1kΩ adapter/tap), and illumination/enclosure finalization.

---

## 1. Itemized Component Breakdown

| Item | Category | Component & Specification | Qty | Unit Cost (PHP) | Total Cost (PHP) | Est. Cost (USD) | Sourcing / Vendor | Hardware Status |
|---|---|---|:---:|:---:|:---:|:---:|---|:---:|
| **1** | Compute Engine | **Raspberry Pi 3 Model B (1GB RAM)**<br>• Quad-core 64-bit ARM Cortex-A53 @ 1.2 GHz<br>• Onboard Wi-Fi (802.11n) & Bluetooth 4.1<br>• 4× USB 2.0, HDMI, CSI, DSI, Micro-SD | 1 | ₱1,400.00 | ₱1,400.00 | $25.00 | Used bundle (incl. 16GB SD card) / Local secondhand | **In Hand & Active** |
| **2** | Microcontroller | **ESP32-WROOM-32 DevKit V1 (30-pin)**<br>• Dual-core Xtensa 32-bit LX6 @ 240 MHz<br>• 520 KB SRAM, 4 MB Flash<br>• Terminal leads **hot-glued directly** (no perfboard) | 1 | ₱190.00 | ₱190.00 | $3.40 | Shopee / Lazada / Makerlab | **Active & Glued at Terminals** |
| **3** | Vision Sensor | **OmniVision OV4689 4MP USB Camera Module**<br>• 1/3" Back-Side Illuminated (BSI) sensor<br>• Driverless UVC compliance via USB Type-C/A<br>• Board footprint ~2×2 cm, ~3 cm tall<br>• Requires lightweight **soft data Type-C cable** for pan/tilt sweep | 1 | ₱1,150.00 | ₱1,150.00 | $20.50 | Huang Li Electronics / Online Importer | **In Hand & Active** |
| **4** | Pan/Tilt Actuators | **Mini ABS Pan/Tilt Bracket Kit with MG90S Servos**<br>• Fits 28×28 mm cameras (OV4689 board fits)<br>• Dual-axis bracket with MG90S metal-gear servos | 1 set | ₱1,000.00 | ₱1,000.00 | $17.86 | Electronics Distributor / Online | **In Hand** |
| **5** | Display Module | **LCD2004 I2C Character LCD (20×4, Blue Backlight)**<br>• 20 columns × 4 rows character LCD<br>• I2C interface (4 pins: VCC, GND, SDA, SCL) — **backpack leads glued, mid-span taped**<br>• Blue backlight, white text | 1 | ₱273.58 | ₱273.58 | $4.88 | Electronics Distributor / Online | **In Hand (Terminals Glued)** |
| **6** | Ambient Sensor | **GL5528 Light Dependent Resistor (LDR)**<br>• 5mm Photoresistor + 10kΩ 1/4W pull-down resistor<br>• Inline-wired to ESP32 GPIO 34 (no perfboard) | 1 | ₱15.00 | ₱15.00 | $0.27 | Local Electronics Store | **In Hand** |
| **7** | Illumination Module | **2W 5V USB COB LED Bar + IRLZ44N MOSFET Driver**<br>• 2W 5V USB COB LED bar (white) — 81.91 PHP<br>• IRLZ44N Logic-Level N-Channel MOSFET — 99.88 PHP<br>• Electrolytic cap (100–1000µF) + 100Ω & 10kΩ resistors (inline taped/glued, no perfboard) | 1 set | ₱236.79 | ₱236.79 | $4.23 | Electronics Distributor / Online | **Procurement — Phase 2** |
| **8** | Wall Power Supply | **External 5V Wall Power Adapter + Soft Power Cable Path**<br>• Existing **45W USB-C wall charger** (or ≥5V 3A wall adapter)<br>• Feeds Pi 3B Micro-USB (via USB-C→Micro-USB 5.1kΩ CC adapter / 5V tap) & inline taped 5V/GND servo+LED bus<br>• Enters enclosure through repurposed `15×10 mm` pass-through slot | 1 | ₱0.00 | ₱0.00 | $0.00 | On Hand (45W PSU); cable itemized in Item 11 | **Wall PSU On Hand** |
| **9** | Retired Battery System | ~~**18650 Cell + Charge/Boost Power Modules + Rocker Switch**~~<br>• **RETIRED:** Dropped due to cell retention failure, 2.4A boost ceiling brownout risk, and 12h+ daily school-day duty cycle<br>• Previous switch cutout repurposed as wall power cable pass-through; old charger hole removed | — | *(₱414.56 sunk)* | — | — | Retired from active build | **Retired / Removed** |
| **10** | Mechanical Enclosure | **Weather-Resistant Ceiling Junction Box**<br>• Fixed to ceiling; camera moves externally on pan/tilt head<br>• ABS junction enclosure (approx. 174×174×73 mm, inner 160×160×63 mm)<br>• Single `15×10 mm` pass-through slot (ex-switch hole) for wall power cable; unused USB-C charger slot omitted<br>• ~~Perfboards~~ **omitted** — ESP32 & LCD leads glued, wire-to-wire splices taped | 1 | ₱572.76 | ₱572.76 | $10.23 | Hardware Supply / Online | **Procurement — Phase 2** |
| **11** | Interconnects & Soft Cables | **Soft Type-C Cables, Harness Tape & Fasteners**<br>• **1× Soft flexible data-carrying USB-C cable** (OV4689 camera → Pi USB-A; thin/lightweight so MG90S servos don't stall)<br>• **1× Soft high-current USB-C power cable** (+ USB-C→Micro-USB 5.1kΩ adapter or 5V breakout for Pi 3B)<br>• Short Micro-USB sync cable (Pi ↔ ESP32), Dupont leads, hot glue (terminals) + electrical tape (serviceable mid-span splices) | 1 set | ₱280.00 | ₱280.00 | $5.00 | Shopee / Hardware Supply | **To Acquire (Soft Cables)** |

---

## 2. Cost Summary

| Summary Category | Amount (PHP) | Amount (USD) |
|---|:---:|:---:|
| **Active Hardware In Hand (Pi 3B, ESP32, Camera, LDR, Bracket Kit + Servos, LCD2004, Wall PSU)** | ₱4,028.58 | $71.94 |
| **Remaining Active Purchases (Soft Data + Power Type-C Cables, Illumination, Enclosure)** | ₱1,089.55 | $19.46 |
| **Total Active Build Cost (excl. retired battery/perfboard parts)** | **~₱5,118.13** | **~$91.40** |

---

## 3. Pre-Purchase Sourcing & Verification Guide

> [!IMPORTANT]
> **Why No Direct Marketplace Links?**  
> Direct marketplace links are intentionally not hardcoded: search results often default to overseas retailers (Waveshare, EU, Canadian shops) that incur high shipping overhead and customs delay. Furthermore, Shopee, Lazada, and Facebook Marketplace links frequently break, point to differing variants, or lead to counterfeit items and scams.  
> Instead, use the exact search strings below and verify every specification on candidate listings before purchasing. Send shortlisted listings to verify their hardware specs against this guide.

| Item | Search this | Check before buying |
|---|---|---|
| **LCD2004** | `LCD2004 I2C 20x4 character LCD blue` | Title says **I2C** (not parallel). Must have the I2C backpack module soldered on (4-pin: VCC GND SDA SCL). Blue backlight with white text is the standard. Avoid listings that show the 16-pin parallel version only. |
| **Pan/Tilt Kit** | `mini ABS pan tilt bracket 28x28 camera MG90S` or `pan tilt platform MG90S kit` | Confirm it fits a ~28×28 mm camera board. Check that MG90S servos are included or sold alongside. Skip kits with obviously fake/plastic-gear "MG90S" clones. Package B sets on Lazada are an alternative. |
| **Box/Enclosure** | `IP68 waterproof enclosure junction box 174x174` or `plastic project box ceiling mount` | Confirm inner dimensions fit the Pi (in acrylic case), ESP32, and taped wire splices. IP68 174×174×73 mm (inner 160×160×63 mm) is the reference size. Drill one `15×10 mm` pass-through slot for wall power (repurposing the former switch hole). |
| **Soft Data Type-C Cable (Camera)** | `soft silicone USB C data cable flexible` or `FPC soft USB-A to Type-C data` | **Must be DATA-CARRYING** (USB 2.0 `D+`/`D-` wires — NOT "charging-only") so OV4689 UVC video transmits. Must be thin, limp/silicone-jacketed so MG90S servos do not stall from cable stiffness. |
| **Soft Power Type-C Cable (Wall PSU)** | `soft silicone 60W 100W USB C cable` + `USB C female to Micro USB male OTG power adapter 5.1k` (or `soft silicone USB-A to Micro-USB 3A`) | Use a thick-gauge soft silicone cable rated **≥3A**. **Pi 3B note:** Pi 3B power input is **Micro-USB** (not Type-C), so ensure either a **USB-C→Micro-USB adapter/5V breakout with 5.1kΩ CC pulldown resistors** or a **USB-A→Micro-USB 3A soft cable** is used so a 45W USB-C charger outputs clean 5V. |
| **COB LED Bar** | `2W 5V USB COB LED strip white bar` | Confirm 5V USB input, white light, COB type, draw ≤400mA so it stays well within wall PSU headroom. |
| **IRLZ44N MOSFET** | `IRLZ44N N-channel MOSFET TO-220` | Logic-level gate threshold ≤2V so ESP32 3.3V GPIO fully drives it. Don't substitute with IRF44N (higher $V_{GS(th)}$, won't saturate from 3.3V). |
| **Misc** | `Dupont jumper wires`, `100uF 25V electrolytic capacitor`, `electrical tape`, `hot glue sticks` | Standard components. Hot-glue wires only at part terminals (ESP32/LCD); use electrical tape at mid-span wire-to-wire splices so components stay serviceable. |

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
   - Chosen as bare module (not pre-cased webcam) for pan/tilt turret mounting flexibility.
4. **Mini ABS Pan/Tilt Kit with MG90S vs. Separate Bracket + Servos:**
   - All-in-one kit simplifies sourcing. Fits 28×28 mm camera boards (OV4689 footprint matches).
   - MG90S metal gears provide durability and torque stability for camera positioning.
5. **LCD2004 I2C (20×4) vs. Alternative Displays:**
   - Evaluated against graphic OLED modules; selected for high character legibility from classroom distances and simple 4-wire I2C interface.
   - Sufficient for displaying headcount, zone status, and mode indicators.
6. **Tethered 5V Wall Power vs. 18650 Battery Pack:**
   - Initial prototyping tested 18650 Li-ion cells + a 5V/2.4A boost module, which proved physically fragile (cell retention failures), current-limited during simultaneous servo actuation, and impractical for 12+ hour daily classroom sessions.
   - Switching directly to an external 5V ≥3A wall PSU via a soft high-current power cable eliminates onboard power/boost PCBs, frees internal enclosure volume, and guarantees stable voltage without recharging downtime.
7. **Ceiling-Mounted Junction Box vs. Fully Articulated Enclosure:**
   - Enclosing compute stationary while actuating the camera module only minimizes moving mass and servo fatigue.
   - Rigid ABS construction offers reliable mounting and ample internal volume for convection.
8. **IRLZ44N Logic-Level MOSFET vs. Standard BJT:**
   - The IRLZ44N features a low gate threshold voltage ($V_{GS(th)} \le 2\text{V}$), allowing it to be fully driven into saturation by the ESP32's 3.3V GPIO without requiring intermediate driver stages or dissipating excessive heat.
