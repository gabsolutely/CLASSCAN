# CLASSCAN — Connecting to the Pi Without Wi-Fi

You have two options. Both give you the dashboard at an IP address in your browser — no router, no Wi-Fi needed.

---

## Option A — Direct Ethernet Cable (Recommended)

Plug an ethernet cable straight from the Pi's ethernet port → your laptop.  
Any cable works (modern NICs auto-MDI, no crossover cable needed).

### On the Pi

```bash
sudo bash src/pi/setup/direct_connect.sh
# Or make it survive reboots:
sudo bash src/pi/setup/direct_connect.sh --persistent
```

Pi IP will be **`192.168.10.1`**.

### On your laptop (Windows)

1. Open **Control Panel → Network and Internet → Network Connections**
2. Right-click your **Ethernet** adapter → **Properties**
3. Select **Internet Protocol Version 4 (TCP/IPv4)** → **Properties**
4. Choose **Use the following IP address:**
   - IP address: `192.168.10.2`
   - Subnet mask: `255.255.255.0`
   - Default gateway: *(leave blank)*
5. Click **OK** twice.

### On your laptop (macOS)

1. **System Settings → Network → Ethernet → Details → TCP/IP**
2. Configure IPv4: **Manually**
3. IP: `192.168.10.2` / Subnet: `255.255.255.0`

### Access the dashboard

```
http://192.168.10.1:8080
```

SSH if needed:
```bash
ssh pi@192.168.10.1
```

---

## Option B — USB Cable (USB Gadget / RNDIS)

Turns the Pi's micro-USB power port into a USB network adapter. One cable does power + network.

> [!IMPORTANT]
> This uses the Pi 3B's **micro-USB port** (the power port, J1). You need a **data** cable — charge-only cables don't have the D+/D− data lines. The 4 full-size USB-A ports on the Pi do **not** support this.

### On the Pi — one-time setup

```bash
sudo bash src/pi/setup/usb_gadget.sh
sudo reboot
```

After reboot, plug a data USB cable: **Pi micro-USB → laptop USB-A**.

Pi IP will be **`192.168.7.1`**.

### On Windows — RNDIS driver (first time only)

Windows may not auto-install the RNDIS driver. If the adapter shows as "Unknown Device":

1. Open **Device Manager**
2. Find **Unknown Device** under Network Adapters (or Other Devices)
3. Right-click → **Update Driver** → **Browse my computer**
4. → **Let me pick from a list**
5. Select **Network Adapters** → **Microsoft** → **Remote NDIS Compatible Device**
6. Click **Next** → **Yes** on any warning

The adapter will appear as **"Remote NDIS Internet Sharing Device"** or similar.

> [!TIP]
> On Windows 10/11 you can alternatively use the **RNDIS driver from the Raspberry Pi USB Driver package** — search "Raspberry Pi RNDIS driver" if the Microsoft built-in driver doesn't work.

### On macOS / Linux

No driver install needed. A new network interface (`en5`, `usb0`, or similar) appears automatically after plugging in. It will receive an IP from the Pi's dnsmasq DHCP server.

### Access the dashboard

```
http://192.168.7.1:8080
```

SSH if needed:
```bash
ssh pi@192.168.7.1
```

---

## Option C — Wi-Fi Hotspot (No cables needed)

Configure the Pi to broadcast its own Wi-Fi network. Your laptop/phone connects directly to it — no school router needed.

> [!IMPORTANT]
> The Pi 3B has **one Wi-Fi chip**. While the hotspot is active it **cannot** also connect to another Wi-Fi network. Use ethernet for SSH if you need a shell while the hotspot is running.

### On the Pi

```bash
# Start hotspot now (lost on reboot)
sudo bash src/pi/setup/hotspot.sh

# Or — install as a boot service (survives reboots)
sudo bash src/pi/setup/hotspot.sh --persistent

# Stop the hotspot and release wlan0
sudo bash src/pi/setup/hotspot.sh --stop

# Check status
sudo bash src/pi/setup/hotspot.sh --status
```

Default credentials (edit the top of `hotspot.sh` to change):
- **SSID**: `CLASSCAN`
- **Password**: `classcan2024`
- **Pi IP**: `192.168.20.1`

### On your device (any OS)

1. Go to Wi-Fi settings and connect to **`CLASSCAN`**
2. Enter password **`classcan2024`**
3. Open browser → `http://192.168.20.1:8080`
   - Or try the mDNS alias: `http://classcan.local:8080`

No static IP configuration needed — the Pi's DHCP server handles it automatically.

---

## Side-by-side comparison

| | Ethernet cable (Option A) | USB cable (Option B) | Wi-Fi Hotspot (Option C) |
|---|---|---|---|
| **Cable** | Ethernet patch cable | Micro-USB data cable | None |
| **Pi port used** | Ethernet jack | Micro-USB (power port) | Built-in wlan0 |
| **Device setup** | Set static IP manually | RNDIS driver (once) | None (DHCP) |
| **Pi IP** | `192.168.10.1` | `192.168.7.1` | `192.168.20.1` |
| **Also powers Pi?** | No (need separate power) | Yes (if laptop USB supplies 900 mA+) | No |
| **Speed** | 100 Mbps | ~12 Mbps (USB 2.0 FS) | ~50 Mbps (802.11n) |
| **Multiple viewers?** | No | No | Yes (up to ~5 concurrent) |
| **Recommended for** | Normal use / bench | Bench testing / no spare cables | **Demo / no-cable scenario** |

> [!NOTE]
> The Pi 3B's micro-USB port can power the board *and* act as a USB gadget simultaneously, but it is fussy about current. If the Pi browncounts under load, use a dedicated 5 V / 2.5 A power supply for power and use the ethernet option for connectivity.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Browser says "refused to connect" | Check `python main.py` is running on the Pi; check port 8080 is not firewalled (`sudo ufw allow 8080`) |
| Can't ping Pi | Verify laptop static IP is set correctly; try `ping 192.168.10.1` |
| Windows shows "Unidentified network" | Normal for a direct link with no gateway — the dashboard still works |
| RNDIS adapter shown but no IP | Reboot the Pi; unplug/replug USB; confirm dnsmasq is running (`systemctl status dnsmasq`) |
| USB gadget mode not appearing | Double-check you have a **data** cable (not charge-only); confirm `dtoverlay=dwc2` is in `/boot/config.txt` after running the script |
| CLASSCAN hotspot not visible | Run `sudo bash hotspot.sh --status`; check `journalctl -u hostapd -n 30` for errors |
| Hotspot visible but no IP assigned | dnsmasq may have failed — run `sudo systemctl restart dnsmasq` then reconnect |
| `hostapd: nl80211: Could not configure driver` | Another process owns wlan0 (e.g. wpa_supplicant) — run `sudo systemctl stop wpa_supplicant` then retry |
