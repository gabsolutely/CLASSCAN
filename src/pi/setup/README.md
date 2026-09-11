# Raspberry Pi 3B Headless Environment Setup

This directory contains system-level configuration files and deployment scripts required for headless operation of the CLASSCAN vision pipeline on the Raspberry Pi 3B running **Raspberry Pi OS Lite (64-bit, Debian 13 / Trixie)**.

---

## 1. System Dependencies & Python Runtime

Ensure basic tools and compilation headers are installed:
```bash
sudo apt update && sudo apt install -y git python3-pip python3-venv v4l-utils libgl1 iw
```

Clone the repository and set up a dedicated virtual environment:
```bash
cd ~
git clone https://github.com/gabsolutely/CLASSCAN.git
cd CLASSCAN
python3 -m venv .venv --system-site-packages
source .venv/bin/activate
pip install -r src/pi/requirements.txt
```

Verify the software pipeline integrity:
```bash
pytest
```
*Expected: 23 passed unit tests covering detector logic, change trigger, postprocessing, and zone reconciler.*

---

## 2. Wi-Fi Stability & Headless Resilience

Raspberry Pi OS Trixie exhibits a known driver/power-management bug (`brcmfmac`) where the Wi-Fi chip enters a sleep state after extended idle and fails to reconnect, locking out headless SSH access.

Two layers of protection are implemented:

### A. Disable Wi-Fi Power Saving (Systemd)
1. Copy the systemd service unit into place:
   ```bash
   sudo cp src/pi/setup/wifi-powersave-off.service /etc/systemd/system/
   ```
2. Enable and start the service:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable wifi-powersave-off.service
   sudo systemctl start wifi-powersave-off.service
   ```
3. Verify that power saving is off:
   ```bash
   iw dev wlan0 get power_save
   # Should output: Power save: off
   ```

### B. Automated Recovery Watchdog (Cron)
If the connection is lost despite power-saving being disabled, the watchdog attempts to cycle the network interface, and reboots the system as a fail-safe.

1. Install the script:
   ```bash
   sudo cp src/pi/setup/wifi-watchdog.sh /usr/local/bin/
   sudo chmod +x /usr/local/bin/wifi-watchdog.sh
   ```
2. Add a root cron job:
   ```bash
   sudo crontab -e
   ```
   Add the following line:
   ```cron
   */5 * * * * /usr/local/bin/wifi-watchdog.sh
   ```

---

## 3. OV4689 Camera Configuration & Manual Exposure

The OV4689 4MP camera operates as a standard UVC device at `/dev/video0`.

### Device Verification
```bash
v4l2-ctl --list-devices
v4l2-ctl -d /dev/video0 --list-formats-ext
```

### Manual Exposure & Gain Tuning
Default hardware auto-exposure produces underexposed frames under standard indoor classroom lighting, impairing head detector confidence. Adjust settings manually via `v4l2-ctl` or `scripts/camera_verify.py`:

```bash
# Disable auto exposure (1 = Manual Mode, 3 = Aperture Priority / Auto)
v4l2-ctl -d /dev/video0 -c auto_exposure=1

# Adjust exposure time (increase for brighter image)
v4l2-ctl -d /dev/video0 -c exposure_time_absolute=500

# Adjust analog gain
v4l2-ctl -d /dev/video0 -c gain=64
```

Verify camera output visually or via verification script:
```bash
python scripts/camera_verify.py --camera-only --save-raw
```
