# Raspberry Pi 3B Headless Environment Setup

This directory contains system-level configuration files and deployment scripts required for headless operation of the CLASSCAN vision pipeline on the Raspberry Pi 3B running **Raspberry Pi OS Lite (64-bit, Debian 13 / Trixie)**.

---

## 0. Auto-Connect on Boot (Hotspot + USB) — **Do This First**

Run **once** on the Pi to permanently enable zero-config access from any device:

```bash
sudo bash src/pi/setup/install_autoconnect.sh
sudo reboot
```

After reboot, you can always reach the Pi — no ethernet, no router, no prior Wi-Fi setup:

| Method | Connect | SSH | Dashboard |
|---|---|---|---|
| **Wi-Fi hotspot** | Join `CLASSCAN` (pw: `classcan2024`) | `ssh pi@192.168.20.1` | `http://192.168.20.1:8080` |
| **USB data cable** | Plug micro-USB → laptop | `ssh pi@192.168.7.1` | `http://192.168.7.1:8080` |

> **Windows USB note:** A "Remote NDIS" adapter appears in Device Manager. If it shows as unknown, update the driver: Device Manager → right-click → Update Driver → Browse → Let me pick → **Remote NDIS Compatible Device**.

### What the install script does
- Installs `hostapd` + `dnsmasq`
- Enables `dwc2` USB OTG overlay and `g_ether` module (USB gadget networking)
- Writes all config files for hostapd, dnsmasq, dhcpcd, and network interfaces
- Installs and enables `classcan-boot.service` (systemd) — runs [`classcan-boot.sh`](classcan-boot.sh) on every boot to bring up wlan0 hotspot and verify USB gadget

### Files added by this feature
| File | Purpose |
|---|---|
| [`install_autoconnect.sh`](install_autoconnect.sh) | One-time install — run once, then reboot |
| [`classcan-boot.sh`](classcan-boot.sh) | Boot-time bringup script (called by systemd) |

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
