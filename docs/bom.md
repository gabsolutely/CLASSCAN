# CLASSCAN — Bill of Materials (BOM) & Sourcing Specification

**Project:** Intelligent Classroom Headcount Monitoring System  
**Hardware Revision:** Phase 2 (Post-PoC, Oct 2026)  
**Currency Conversion Baseline:** ~₱56.00 PHP = $1.00 USD  

> [!NOTE]
> **Phase 2 Purchasing Status (Oct 2026):** Lazada cart assembled (15 items, subtotal ₱2,572.69 + ₱466 shipping = **₱3,038.69 total**). Initial order confirmed: **LCD2004 + pan/tilt bracket kit only**. Enclosure, illumination, and battery deferred to next order. Working budget ~₱2k (Jelaine contributing ~₱1,700 now; remaining teammates pending). Tools (soldering iron, etc.) not included in BOM — not yet confirmed.

---

## 1. Itemized Component Breakdown

| Item | Category | Component & Specification | Qty | Unit Cost (PHP) | Total Cost (PHP) | Est. Cost (USD) | Sourcing / Vendor | Hardware Status |
|---|---|---|:---:|:---:|:---:|:---:|---|:---:|
| **1** | Compute Engine | **Raspberry Pi 3 Model B (1GB RAM)**<br>• Quad-core 64-bit ARM Cortex-A53 @ 1.2 GHz<br>• Onboard Wi-Fi (802.11n) & Bluetooth 4.1<br>• 4× USB 2.0, HDMI, CSI, DSI, Micro-SD | 1 | ₱1,400.00 | ₱1,400.00 | $25.00 | Used bundle (incl. 16GB SD card) / Local secondhand | **In Hand & Active** |
| **2** | Microcontroller | **ESP32-WROOM-32 DevKit V1 (30-pin)**<br>• Dual-core Xtensa 32-bit LX6 @ 240 MHz<br>• 520 KB SRAM, 4 MB Flash<br>• Native ADC, PWM timers, Micro-USB UART | 1 | ₱190.00 | ₱190.00 | $3.40 | Shopee / Lazada / Makerlab | **In Hand & Active** |
| **3** | Vision Sensor | **OmniVision OV4689 4MP USB Camera Module**<br>• 1/3" Back-Side Illuminated (BSI) sensor<br>• Driverless UVC compliance via USB Type-C/A<br>• Board footprint ~2×2 cm, ~3 cm tall<br>• Wide-angle M12 lens | 1 | ₱1,150.00 | ₱1,150.00 | $20.50 | Huang Li Electronics / Online Importer | **In Hand & Active** |
| **4** | Pan/Tilt Actuators | **Mini ABS Pan/Tilt Bracket Kit with MG90S Servos**<br>• Fits 28×28 mm cameras (OV4689 board fits)<br>• Shipped unassembled; MG90S included<br>• Concern: MG90S may be underpowered for a hanging enclosure — user also owns a 28BYJ-48 stepper motor as backup<br>• *Package B set (₱1,027) also in cart as alternative* | 1 set | ₱1,000.00 | ₱1,000.00 | $17.86 | Lazada (mini ABS kit) | **Procurement — Phase 2 (initial order)** |
| **5** | Display Module | **LCD2004 I2C Character LCD (20×4, Blue Backlight)**<br>• 20 columns × 4 rows character LCD<br>• I2C interface (4 pins: VCC, GND, SDA, SCL) — no complex soldering for logic<br>• Blue backlight, white text<br>• *Replaces originally planned SSD1309 OLED (2.42" ~₱700 too expensive; 12864B dropped: too many pins, no photo of back)* | 1 | ₱273.58 | ₱273.58 | $4.88 | Lazada | **Procurement — Phase 2 (initial order)** |
| **6** | Ambient Sensor | **GL5528 Light Dependent Resistor (LDR)**<br>• 5mm Photoresistor + 10kΩ 1/4W pull-down resistor<br>• Analog voltage divider for ambient brightness reading | 1 | ₱15.00 | ₱15.00 | $0.27 | Local Electronics Store | **In Hand** |
| **7** | Illumination Module | **2W 5V USB COB LED Bar + IRLZ44N MOSFET Driver**<br>• 2W 5V USB COB LED bar (white) — 81.91 PHP<br>• IRLZ44N Logic-Level N-Channel MOSFET — 99.88 PHP<br>• 2× 1000µF electrolytic capacitors — 25 PHP<br>• 2× screw terminals — 30 PHP<br>• Current-limiting & gate pull-down resistors | 1 set | ₱236.79 | ₱236.79 | $4.23 | Lazada | **Procurement — Phase 2 (deferred)** |
| **8** | Power Cells | **LG HG2 18650 Li-ion Cells (3.7V, ~3000mAh)**<br>• High-drain rechargeable 18650 cells<br>• Swappable: pull out depleted cell, swap in charged cell<br>• *USB power banks ruled out as too expensive* | 1 set | ₱198.00 | ₱198.00 | $3.54 | Lazada | **Procurement — Phase 2 (deferred)** |
| **9** | Power Regulation | **18650 Charge/Boost Module (Dual USB, 5V 2.4A, with Display)**<br>• Charges 18650 cell and outputs regulated 5V 2.4A<br>• Dual USB output; onboard battery level display<br>• 1-slot 18650 holder — 25 PHP<br>• 5A fuse holder — 45 PHP<br>• 2-pin rocker switch 5-pack — 50.53 PHP | 1 set | ₱216.56 | ₱216.56 | $3.87 | Lazada | **Procurement — Phase 2 (deferred)** |
| **10** | Mechanical Enclosure | **Plain Box Screwed to Ceiling (Camera Moves Only)**<br>• Box mounted fixed to ceiling; only camera module moves via pan/tilt<br>• 3D-printed dome ruled out (too expensive)<br>• IP68 174×174×73 mm box (inner 160×160×63 mm, no cutouts) — ₱572.76 in cart<br>• Estimated total with cutting/modification: ₱500–600<br>• 2× 5×7 cm double-sided perfboards — 48 PHP | 1 | ₱620.76 | ₱620.76 | $11.08 | Lazada | **Procurement — Phase 2 (deferred)** |
| **11** | Interconnects & Misc | **Wiring, Fasteners & Mounting Hardware**<br>• Dupont jumper wires (M-M, M-F), M3 nylon/brass standoffs<br>• Cable ties, short Micro-USB sync cable (Pi ↔ ESP32)<br>• Expansion/breakout boards, resistors — already owned | 1 set | ₱180.00 | ₱180.00 | $3.20 | Hardware Supply / Lab Stock / Owned | **In Hand / Spec** |

---

## 2. Cost Summary

| Summary Category | Amount (PHP) | Amount (USD) |
|---|:---:|:---:|
| **In Hand (Pi 3B, ESP32, Camera, LDR)** | ₱2,755.00 | $49.20 |
| **Phase 2 Initial Order (LCD2004 + Pan/Tilt, confirmed)** | ₱1,273.58 | $22.74 |
| **Phase 2 Deferred (Illumination, Battery, Enclosure, Misc)** | ₱1,253.11 | $22.38 |
| **Lazada Cart Total (Phase 2 items only, not yet confirmed)** | **₱3,038.69** (incl. ₱466 shipping) | **$54.26** |
| **Total Estimated Hardware Investment (all phases)** | **~₱4,261.69** | **~$76.10** |

> [!TIP]
> Phase 2 initial order (LCD2004 + pan/tilt kit) is the priority purchase. Enclosure, COB LED, and battery components can be deferred until the initial order arrives and is tested.

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
| **Box/Enclosure** | `IP68 waterproof enclosure junction box 174x174` or `plastic project box ceiling mount` | Confirm inner dimensions fit the Pi (in acrylic case), ESP32, and wiring. IP68 174×174×73 mm (inner 160×160×63 mm) is the reference size. Check if cutouts are pre-drilled or if you'll need to cut. |
| **COB LED Bar** | `2W 5V USB COB LED strip white bar` | Confirm 5V USB input, white light, COB type. Draw should stay ≤400mA so the charge/boost module can power everything. |
| **18650 Cells** | `LG HG2 18650 3000mAh 20A` | Look for LG HG2 or Samsung 25R. Avoid no-name 18650s that claim 6000+ mAh (physically impossible). Buy from reputable Lazada/Shopee sellers with reviews. |
| **Charge/Boost Module** | `18650 charge boost module dual USB 5V 2.4A display` | Must output 5V ≥2A for the Pi 3B. Dual USB preferred. A display showing battery % is helpful. Confirm it can charge AND output simultaneously (pass-through charging). |
| **IRLZ44N MOSFET** | `IRLZ44N N-channel MOSFET TO-220` | Logic-level gate threshold ≤2V so ESP32 3.3V GPIO fully drives it. Don't substitute with IRF44N (higher $V_{GS(th)}$, won't saturate from 3.3V). |
| **Misc** | `Dupont jumper wires`, `1000uF 25V electrolytic capacitor`, `screw terminal 2-pin`, `5x7 perfboard` | Standard components. Confirm capacitor voltage rating ≥10V. |

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
   - MG90S metal gears provide durability. Note: concern that MG90S may be underpowered for a heavy hanging enclosure — the 28BYJ-48 stepper motor (already owned) is an available fallback.
5. **LCD2004 I2C (20×4) vs. SSD1309 OLED:**
   - SSD1309 2.42" OLED (~₱700) and 12864B graphic LCD (too many pins, no back photo) were ruled out on cost/complexity grounds.
   - LCD2004 with I2C backpack requires only 4 wires (VCC, GND, SDA, SCL) — no additional soldering for logic connections.
   - Sufficient for displaying a headcount number, zone status, and mode indicator in a classroom setting.
6. **18650 Cells + Charge/Boost Module vs. USB Power Banks:**
   - USB power banks were ruled out as too expensive for this use case.
   - Swappable 18650 cells allow quick battery swap during testing without waiting for a full recharge cycle.
   - Charge/boost module with dual USB output and display provides a clean, self-contained power solution.
7. **Plain Box (Ceiling-Mounted, Camera Moves) vs. Full Enclosure:**
   - 3D-printed dome enclosure ruled out (too expensive).
   - Plain ABS/IP68 box screwed to the ceiling keeps the expensive electronics stationary; only the camera module on the pan/tilt bracket moves.
   - Simpler mechanically and easier to access for maintenance.
8. **IRLZ44N Logic-Level MOSFET vs. Standard BJT:**
   - The IRLZ44N features a low gate threshold voltage ($V_{GS(th)} \le 2\text{V}$), allowing it to be fully driven into saturation by the ESP32's 3.3V GPIO without requiring intermediate driver stages or dissipating excessive heat.
