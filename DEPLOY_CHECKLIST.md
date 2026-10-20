# CLASSCAN — Prototype Deployment Checklist
> **Hard deadline: September 28, 2026** (passed — project continues for polish and real-classroom validation)  
> Work through this list top-to-bottom before the demo. Tick each box as you go.

---

## 0 · Code & Tests (do once, on dev machine)

- [ ] **All 31 unit tests pass** — `python -m pytest tests/ -v`
- [ ] **No uncommitted changes** — `git status` is clean
- [ ] **Push to remote** — `git push origin main` (backup before physical demo)

### 0b · Runtime Free-Win Verification (Zero Retraining)
- [ ] `MAX_ROOM_CAPACITY = 45` and `MAX_ZONE_CAPACITY = 15` active in `src/pi/config.py`
- [ ] `MULTI_CAPTURE_COUNT = 3` configured (takes 3 snapshots per quadrant and uses median)
- [ ] `COUNT_HYSTERESIS_DELTA = 0.6` active (dead-band filtering prevents OLED integer jitter)
- [ ] `ZONE_EXCLUSION_MASKS` configured per quadrant to mask non-floor regions (doors, whiteboard, ceiling)
- [ ] Verified via reconciler tests: `pytest tests/test_reconciler.py -v` (passes 100%)

---

## 1 · Model Files  _(Raspberry Pi — `models/` directory)_

> Without the ensemble `.tflite` files the system falls back to COCO SSD which badly undercounts.

- [ ] `models/classcan_density_round4_ep8.tflite` — **present on Pi** (~13 MB)
- [ ] `models/classcan_density_style_aug_ep8.tflite` — **present on Pi** (~13 MB)
- [ ] `models/mobilenet_v2_ssd_classcan.tflite` — present as smoke-test fallback (already committed)
- [ ] Verify both ensemble files load:
  ```bash
  python scripts/run_on_image.py <any_jpg> models/classcan_density_round4_ep8.tflite
  python scripts/run_on_image.py <any_jpg> models/classcan_density_style_aug_ep8.tflite
  ```

**Export from Colab if files are missing:**
```bash
python scripts/export_to_tflite.py --mode density \
    --weights /content/drive/MyDrive/models/classcan_density_v4_round4_ft_epoch8.weights.h5 \
    --output models/classcan_density_round4_ep8.tflite --quant float32

python scripts/export_to_tflite.py --mode density \
    --weights /content/drive/MyDrive/models/classcan_density_style_aug_ft_lowLR_epoch8.weights.h5 \
    --output models/classcan_density_style_aug_ep8.tflite --quant float32
```

---

## 2 · Raspberry Pi 3B Setup

### 2a · OS & Network
- [ ] Pi boots to Raspberry Pi OS Lite 64-bit (Trixie)
- [ ] Pi has a path to the demo laptop — **choose one connectivity option:**
  - **Option A — same Wi-Fi router:** Pi and laptop on the same network; Pi IP via `hostname -I`
  - **Option B — direct ethernet cable:** run `sudo bash src/pi/setup/direct_connect.sh`; Pi IP `192.168.10.1`; set laptop to `192.168.10.2 / 255.255.255.0`
  - **Option C — USB gadget (RNDIS):** run `sudo bash src/pi/setup/usb_gadget.sh` + reboot; Pi IP `192.168.7.1`
  - **Option D — Wi-Fi Hotspot (no cables):** run `sudo bash src/pi/setup/hotspot.sh`; connect laptop to SSID `CLASSCAN` (pw: `classcan2024`); Pi IP `192.168.20.1`
- [ ] Pi IP address is known (write it here: `_____________`)
- [ ] SSH access confirmed — `ssh pi@<ip>` responds

### 2b · Wi-Fi Resilience Services
- [ ] `wifi-powersave-off.service` is **enabled & active**
  ```bash
  sudo systemctl status wifi-powersave-off.service
  # Should show: active (exited)
  ```
- [ ] `wifi-watchdog.sh` is installed in cron
  ```bash
  crontab -l | grep wifi-watchdog
  # Should show: */5 * * * * /path/to/wifi-watchdog.sh
  ```
  If missing:
  ```bash
  sudo cp src/pi/setup/wifi-watchdog.sh /usr/local/bin/wifi-watchdog.sh
  sudo chmod +x /usr/local/bin/wifi-watchdog.sh
  (crontab -l; echo "*/5 * * * * /usr/local/bin/wifi-watchdog.sh") | crontab -
  ```

### 2c · Python Environment
- [ ] `pip list` on Pi shows: `opencv-python-headless`, `ai-edge-litert`, `pyserial`
  ```bash
  pip install -r src/pi/requirements.txt
  ```

### 2d · Camera (OV4689)
- [ ] Camera appears at `/dev/video0` — `ls /dev/video*`
- [ ] `quirks=128` set for uvcvideo:
  ```bash
  cat /etc/modprobe.d/uvcvideo.conf
  # Should contain: options uvcvideo quirks=128
  ```
  If missing:
  ```bash
  echo "options uvcvideo quirks=128" | sudo tee /etc/modprobe.d/uvcvideo.conf
  sudo modprobe -r uvcvideo && sudo modprobe uvcvideo
  ```
- [ ] Apply known-good camera config baseline:
  ```bash
  v4l2-ctl -d /dev/video0 \
    --set-ctrl=auto_exposure=1 \
    --set-ctrl=exposure_time_absolute=500 \
    --set-ctrl=gain=192 \
    --set-ctrl=brightness=64 \
    --set-ctrl=gamma=300 \
    --set-ctrl=saturation=100 \
    --set-ctrl=white_balance_automatic=0 \
    --set-ctrl=white_balance_temperature=4600
  ```
- [ ] Camera feed is live and correctly exposed — `python scripts/camera_verify.py`

---

## 3 · ESP32 Firmware

- [ ] ESP32 is **flashed** with latest firmware (`src/esp32/src/main.cpp` via PlatformIO)
- [ ] ESP32 appears as serial device on Pi — `ls /dev/ttyUSB*` or `/dev/ttyACM*`
- [ ] Serial port in `src/pi/config.py` matches actual device:
  ```python
  SERIAL_PORT = "/dev/ttyUSB0"   # <- update if different
  ```
- [ ] Servo mechanism physically attached to pan/tilt bracket (genuine MG90S metal-gear servos) and free to rotate without obstruction
- [ ] LDR and illumination LED circuit wired per `hardware/wiring_guide.md` (IRLZ44N logic-level MOSFET, 5V LED strip, 10k pulldown)
- [ ] OLED display (SSD1309 2.42" 7-pin SPI) wired to ESP32 (GPIO 14, 27, 4, 2, 5) in factory SPI mode (no SMD soldering)

---

## 4 · End-to-End Boot Test _(on Pi)_

Run with `--mock` first to confirm software loads, then full hardware boot:

```bash
# Quick software smoke-test (no hardware gate)
cd ~/CLASSCAN/src/pi
python main.py --mock --mock-count 7

# Full hardware boot (runs self-test sequence)
python main.py
```

- [ ] Boot sequence runs without abort
- [ ] Console shows: `[EnsembleDensityDetector] Ensemble loaded:` (not COCO SSD fallback)
- [ ] Dashboard URL printed: `http://0.0.0.0:8080`
- [ ] Headcount updates printed in the console as camera frames are scanned

---

## 5 · Dashboard (on demo laptop)

- [ ] Open browser to `http://<pi-ip>:8080`
- [ ] Click **Connect** — status pill turns green ("Connected")
- [ ] Headcount hero number updates every ~2 s poll cycle
- [ ] Live snapshot updates with HUD overlay (bounding boxes + FPS bar)
- [ ] **Mode buttons** (Sweep / Zone Check) send commands — check Pi console for `[CLASSCAN] Command received`
- [ ] **Zone Q1–Q4 buttons** send `ZONE_Qx` commands — visible in Event Log
- [ ] Event log populates with timestamped entries
- [ ] Responsive layout works at 1080p and at ≤900px width (single-column)

---

## 6 · Physical Integration Check

- [ ] **Pre-order enclosure measurement:** Pi measured inside acrylic case (~90×60×30 mm + fan); ABS junction box (≥150×110×70 mm) confirmed to fit Pi, ESP32, and 18650 battery with convective airflow
- [ ] **Power verification:** 18650 cell connected through 5V/2A boost converter (or charging module with integrated 5V ≥2A output); confirms stable 5.0V bus without undervoltage
- [ ] **Pan/tilt servos:** Dual-axis bracket platform fitted with verified metal-gear MG90S units (tested under load, 2 spares available)
- [ ] Camera mounted to pan/tilt bracket and pointed at the classroom area of interest
- [ ] ESP32 connected to Pi via short USB serial cable; reports `{"type":"state","value":"idle"}`
- [ ] OLED display (SSD1309 2.42") shows received headcount locally in crisp monochrome text
- [ ] LDR / illumination circuit responds to ambient light changes (LED strip activates in darkness, total draw ≤500mA)

---

## 7 · Demo Run

- [ ] At least **one live run** with real people in frame before the actual demo
- [ ] Confirm count updates when people enter/leave the frame
- [ ] Expected accuracy: MAE ≈ 2.77 people on moderate-density scenes; ±3 is normal

---

## 8 · Known Limitations (state at defense)

| Issue | Status & Remediation Path |
|---|---|
| Ensemble `.tflite` files not in repo | Too large for git; export from Colab Drive before deploy (see `models/README.md`) |
| Camera baseline not auto-applied on boot | Run `v4l2-ctl` block manually after each reboot (ROADMAP open item) |
| INT8 quantization (bilinear issue) | `UpSampling2D(bilinear)` unsupported in XNNPack INT8; resolved by transitioning to `Conv2DTranspose` in `scripts/train_density.py` and `scripts/adabn.py` |
| Domain shift / SCUT-HEAD Part A | SCUT-HEAD Part A was sampled from a single university (homogeneous rooms); real deployment addressed via 6-Pillar Plan: whole-session holdouts (`eval_harness.py`), AdaBN (`adabn.py`), and model-assisted annotation (`annotate_assisted.py`) |
| `line1` clip weakest (r=0.455) | Students moving in a line; static seated scenes perform better; multi-capture median (`MULTI_CAPTURE_COUNT=3`) smooths transient line movement |
| Hotspot mutual-exclusion | Pi 3B has one Wi-Fi chip: hotspot active = no simultaneous router Wi-Fi; use ethernet for SSH |

---

## Quick Reference — Key Commands

| Task | Command (run from `src/pi/`) |
|---|---|
| Run with real hardware | `python main.py` |
| Run in mock/sim mode | `python main.py --mock --mock-count 8` |
| Skip boot self-test | `python main.py --skip-boot-check` |
| Change dashboard port | `python main.py --port 9090` |
| Smoke-test a model | `python ../../scripts/run_on_image.py img.jpg ../../models/model.tflite` |
| Run unit tests | `python -m pytest tests/ -v` _(from project root)_ |
| Benchmark Pi inference | `python ../../scripts/pi_benchmark.py` |
