Put STEP files here with these exact names. Missing ones are drawn as simple blocks.
Check each model's licence and measure the real part with calipers: community models can be off.

  pi3b.step              <- Pi
  esp32_devkit.step      <- ESP32
  charge_module.step     <- Module
  18650_holder.step      <- Cell
  perfboard_5x7.step     <- Perfboard
  mg90s.step             <- servo
  lcd2004_i2c.step       <- lcd
  ov4689_camera.step     <- camera

Where to look:
  Pi 3B     GrabCAD 'Raspberry Pi 3 model B single-board computer' (use the Simplified STEP, ~2.5 MB)
  ESP32     GrabCAD 'ESP32-DevKitC V4' (38-pin) or 'ESP32 38 Pines ESP WROOM 32'
  MG90S, 18650 holder, LCD2004 I2C, TP5100-style charge board, OV4689 board, 4x6/5x7 perfboard:
            search GrabCAD / Printables / Thingiverse / SnapMagic for the exact name; KiCad's packages3D
            library also has pin headers, screw terminals and displays.
After the first run open the STEP and check connector directions; fix with MODEL_OPTS (spin/flip).