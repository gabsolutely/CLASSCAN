# CLASSCAN — Prototype Deployment Checklist
> **Hard deadline: September 28, 2026**  
> Work through this list top-to-bottom before the demo. Tick each box as you go.

---

## 0 · Code & Tests (do once, on dev machine)

- [ ] **All 27 unit tests pass** — `python -m pytest tests/ -v`
- [ ] **No uncommitted changes** — `git status` is clean
- [ ] **Push to remote** — `git push origin main` (backup before physical demo)

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
- [ ] Pi is on the **same Wi-Fi network** as the demo laptop
- [ ] Pi IP address is known — `hostname -I` (write it here: `_____________`)
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
- [ ] Servo mechanism physically attached and free to rotate without obstruction
- [ ] LDR and illumination LED circuit wired per `hardware/wiring_guide.md`
- [ ] LED matrix wired and powered

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

- [ ] Camera mounted and pointed at the room area of interest
- [ ] Pi powered from stable supply (not laptop USB); active fan spinning
- [ ] ESP32 connected to Pi via USB serial cable
- [ ] Servo bracket pointing in default center position; free to sweep
- [ ] LED matrix displays received headcount
- [ ] LDR / illumination circuit responds to ambient light changes

---

## 7 · Demo Run

- [ ] At least **one live run** with real people in frame before the actual demo
- [ ] Confirm count updates when people enter/leave the frame
- [ ] Expected accuracy: MAE ≈ 2.77 people on moderate-density scenes; ±3 is normal

---

## 8 · Known Limitations (state at defense)

| Issue | Status |
|---|---|
| Ensemble `.tflite` files not in repo | Too large for git; export from Colab Drive before deploy (see `models/README.md`) |
| Camera baseline not auto-applied on boot | Run `v4l2-ctl` block manually after each reboot (ROADMAP open item) |
| INT8 quantization broken | XNNPack fails on `UpSampling2D(bilinear)`; float32 only; ~1.4 s/scan — within budget |
| Not validated at 5+ people | Data-domain gap (SCUT-HEAD vs Filipino classroom); real-footage r ceiling = 0.586 |
| `line1` clip weakest (r=0.455) | Students moving in a line; static seated scenes perform better |

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
