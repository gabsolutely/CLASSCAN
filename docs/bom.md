# CLASSCAN — Bill of Materials (BOM)

**Project:** Intelligent Classroom Headcount Monitoring System  
**Hardware Revision:** Prototype v1.0  
**Currency Conversion Baseline:** ~₱56.00 PHP = $1.00 USD  

---

## 1. Itemized Component Breakdown

| Item | Category | Component & Specification | Qty | Unit Cost (PHP) | Total Cost (PHP) | Est. Cost (USD) | Sourcing / Vendor | Hardware Status |
|---|---|---|:---:|:---:|:---:|:---:|---|:---:|
| **1** | Compute Engine | **Raspberry Pi 3 Model B (1GB RAM)**<br>• Quad-core 64-bit ARM Cortex-A53 @ 1.2 GHz<br>• Onboard Wi-Fi (802.11n) & Bluetooth 4.1<br>• 4× USB 2.0, HDMI, CSI, DSI, Micro-SD | 1 | ₱2,100.00 | ₱2,100.00 | $37.50 | Local Electronics / Authorized Reseller | **In Hand & Active** |
| **2** | Microcontroller | **ESP32-WROOM-32 DevKit V1 (30-pin)**<br>• Dual-core Xtensa 32-bit LX6 @ 240 MHz<br>• 520 KB SRAM, 4 MB Flash<br>• Native ADC, PWM timers, Micro-USB UART | 1 | ₱190.00 | ₱190.00 | $3.40 | Shopee / Lazada | **In Hand & Active** |
| **3** | Vision Sensor | **OmniVision OV4689 4MP USB Camera Module**<br>• 1/3" Back-Side Illuminated (BSI) sensor<br>• Driverless UVC compliance via USB Type-C/A (4-pin harness)<br>• Wide-angle M12 lens, high low-light sensitivity | 1 | ₱1,150.00 | ₱1,150.00 | $20.50 | Sourced / Online Electronics Importer | **In Hand & Active** |
| **4** | Pan/Tilt Actuators | **TowerPro MG90S Metal-Gear Micro Servos**<br>• Operating voltage: 4.8V – 6.0V<br>• Stall torque: 2.2 kg·cm @ 6V<br>• Metal gearing for continuous pan/tilt durability | 2 | ₱110.00 | ₱220.00 | $3.90 | Shopee / Lazada | **In Hand** |
| **5** | Display Module | **MAX7219 8×32 Dot Matrix 4-in-1 LED Module**<br>• Red LED dot matrix display (32×8 pixels)<br>• SPI 3-wire interface (DIN, CS, CLK)<br>• High visibility across standard classroom lengths | 1 | ₱145.00 | ₱145.00 | $2.60 | Shopee / Lazada | **In Hand** |
| **6** | Ambient Sensor | **GL5528 Light Dependent Resistor (LDR)**<br>• 5mm Photoresistor + 10kΩ 1/4W pull-down resistor<br>• Analog voltage divider for ambient brightness reading | 1 | ₱15.00 | ₱15.00 | $0.27 | Local Electronics Store | **In Hand** |
| **7** | Illumination Module | **Custom Auxiliary LED Illumination Array**<br>• 4× 5mm 0.5W Ultra-Bright White LEDs (15000 mcd)<br>• 1× 2N2222 NPN Transistor / 2N7000 N-MOSFET switch<br>• 4× 47Ω current-limiting resistors + 1kΩ base resistor | 1 set | ₱65.00 | ₱65.00 | $1.15 | Custom In-House Assembly | **In Hand / Assembly** |
| **8** | Power Source | **18650 Li-ion Cells (3.7V, 2600mAh each)**<br>• 2S configuration (7.4V nominal) or dual parallel<br>• Rechargeable, high-drain capacity | 2 | ₱120.00 | ₱240.00 | $4.30 | Shopee / Local Battery Vendor | **In Hand** |
| **9** | Power Regulation | **Dual-Power Step-Up/BMS Module**<br>• TP4056 Dual-Cell USB Charging Module with Protection<br>• MT3608 / XL6009 5V/3A DC-DC Step-Up Boost Converter | 1 set | ₱95.00 | ₱95.00 | $1.70 | Shopee / Lazada | **In Hand** |
| **10** | Mechanical Enclosure | **Custom 3D-Printed Dome Turret Enclosure**<br>• PLA/PETG filament material (~180g)<br>• 2-axis servo bracket, camera housing, ceiling baseplate<br>• Pi enclosed in clear acrylic case + 5V brushless cooling fan | 1 | ₱250.00 | ₱250.00 | $4.50 | In-House 3D Printing / Bench Case | **In Hand & Active** |
| **11** | Interconnects & Misc | **Wiring, Cables & Fasteners**<br>• 1× Micro-USB to USB-A data sync cable (Pi ↔ ESP32)<br>• 1× 4-pin JST to USB-A camera harness cable<br>• Dupont ribbon jumpers (M-M, M-F), breadboard/perfboard<br>• M2/M3 mounting screws and nuts | 1 set | ₱180.00 | ₱180.00 | $3.20 | Hardware Supply / Lab Stock | **In Hand** |

---

## 2. Cost Summary

| Summary Category | Amount (PHP) | Amount (USD) |
|---|:---:|:---:|
| **Compute & Electronics (Pi 3B, ESP32, Camera, Servos, Display)** | ₱3,820.00 | $68.20 |
| **Power, Sensing & Illumination System** | ₱415.00 | $7.40 |
| **Enclosure, Cabling & Hardware Fasteners** | ₱430.00 | $7.70 |
| **Total Estimated Hardware Investment** | **₱4,665.00** | **$83.30** |

---

## 3. Component Selection Justifications

1. **Raspberry Pi 3B vs. Alternative SBCs:**
   - Provides native quad-core 64-bit ARM CPU capability with mature Linux drivers, official `ai-edge-litert` wheel compatibility, and onboard Wi-Fi/Bluetooth without requiring external wireless USB dongles.
2. **ESP32 Microcontroller vs. Direct Pi GPIO Control:**
   - Offloads real-time PWM servo pulse generation and high-frequency ADC sampling from the Pi CPU.
   - Shields the Pi from servo back-EMF spikes and allows independent system failsafe operations.
3. **OV4689 BSI USB Camera vs. Standard Pi Camera v2:**
   - The OmniVision OV4689 sensor utilizes Back-Side Illumination (BSI) architecture, providing superior quantum efficiency and lower read noise under dim fluorescent classroom lighting.
   - Standard USB Video Class (UVC) compliance allows driverless operation across Linux systems via standard OpenCV V4L2 pipelines.
4. **MG90S Metal-Gear Servos vs. Plastic SG90:**
   - Metal gears withstand the mechanical fatigue of continuous automated sweep motions without stripping teeth under the weight of the camera and bracket.
