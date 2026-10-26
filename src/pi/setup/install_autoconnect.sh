#!/usr/bin/env bash
# ============================================================================
# CLASSCAN — Auto-Connect Install Script
# ============================================================================
# Run this ONCE on the Pi to permanently enable:
#   • Wi-Fi hotspot  (wlan0 → SSID "CLASSCAN", 192.168.20.1)
#   • USB gadget     (micro-USB port → 192.168.7.1)
#   • Ethernet DHCP  (eth0  → DHCP from any router — SSH recovery fallback)
#
# After this script + one reboot, reach the Pi via ANY of:
#   Wi-Fi  → connect to "CLASSCAN" → ssh pi@192.168.20.1  /  http://192.168.20.1:8080
#   USB    → plug data cable       → ssh pi@192.168.7.1   /  http://192.168.7.1:8080
#   LAN    → plug ethernet cable   → check router for Pi's IP (hostname: raspberrypi)
#
# Usage:
#   sudo bash install_autoconnect.sh
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log()  { echo "[install] $*"; }
warn() { echo "[install] WARNING: $*" >&2; }
die()  { echo "[install] ERROR: $*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "Run as root: sudo bash install_autoconnect.sh"

# ── 1. Install packages ───────────────────────────────────────────────────────

log "Installing required packages (hostapd, dnsmasq) ..."
apt-get update -qq
apt-get install -y hostapd dnsmasq
systemctl unmask hostapd 2>/dev/null || true

# ── 2. USB Gadget (dwc2 + g_ether) ───────────────────────────────────────────

CONFIG_TXT="/boot/config.txt"
MODULES_FILE="/etc/modules"

log "Configuring USB gadget (dwc2 overlay + g_ether module) ..."

grep -qxF "dtoverlay=dwc2" "$CONFIG_TXT" 2>/dev/null \
    || { echo "dtoverlay=dwc2" >> "$CONFIG_TXT"; log "  Added dtoverlay=dwc2 to $CONFIG_TXT"; }

grep -qxF "dwc2" "$MODULES_FILE" 2>/dev/null \
    || { echo "dwc2" >> "$MODULES_FILE"; log "  Added dwc2 to $MODULES_FILE"; }

grep -qxF "g_ether" "$MODULES_FILE" 2>/dev/null \
    || { echo "g_ether" >> "$MODULES_FILE"; log "  Added g_ether to $MODULES_FILE"; }

# ── 3. Static IP for usb0 (systemd-networkd) ────────────────────────────────
# /etc/network/interfaces.d/ may not exist on Trixie (ifupdown not default).
# Use systemd-networkd .network files instead — always present on Pi OS Trixie.

log "Writing usb0 static IP config (/etc/systemd/network/10-classcan-usb0.network) ..."
mkdir -p /etc/systemd/network
cat > /etc/systemd/network/10-classcan-usb0.network <<'EOF'
# CLASSCAN USB gadget network — written by install_autoconnect.sh
[Match]
Name=usb0

[Network]
Address=192.168.7.1/24
EOF
systemctl enable systemd-networkd
log "  usb0 static IP configured via systemd-networkd."

# ── 3b. eth0 DHCP via systemd-networkd (ethernet recovery fallback) ──────────
# If an ethernet cable is plugged into a router the Pi gets a DHCP lease,
# allowing SSH access even when wlan0 hotspot is broken — critical for recovery.

log "Writing eth0 DHCP config (/etc/systemd/network/10-classcan-eth0.network) ..."
cat > /etc/systemd/network/10-classcan-eth0.network <<'EOF'
# CLASSCAN ethernet recovery — written by install_autoconnect.sh
# Enables DHCP on eth0 so the Pi gets a router-assigned IP when a cable is
# plugged in. Check your router's device list for the IP, then ssh pi@<ip>.
[Match]
Name=eth0

[Network]
DHCP=yes
MulticastDNS=yes
EOF
log "  eth0 DHCP configured via systemd-networkd."

# ── 4. dnsmasq: USB DHCP ─────────────────────────────────────────────────────

log "Writing dnsmasq USB DHCP config (/etc/dnsmasq.d/classcan-usb.conf) ..."
cat > /etc/dnsmasq.d/classcan-usb.conf <<'EOF'
# CLASSCAN USB gadget DHCP — written by install_autoconnect.sh
interface=usb0
dhcp-range=192.168.7.2,192.168.7.10,255.255.255.0,24h
EOF

# ── 5. hostapd config (wlan0 hotspot) ────────────────────────────────────────
# IMPORTANT: must be /etc/hostapd/hostapd.conf — the systemd unit has
#   ConditionFileNotEmpty=/etc/hostapd/hostapd.conf which is evaluated before
#   DAEMON_CONF is read. A different filename causes a silent no-op start.

log "Writing hostapd config (/etc/hostapd/hostapd.conf) ..."
mkdir -p /etc/hostapd
cat > /etc/hostapd/hostapd.conf <<'EOF'
# CLASSCAN hotspot — written by install_autoconnect.sh
interface=wlan0
driver=nl80211
ssid=CLASSCAN
hw_mode=g
channel=6
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
# Default passphrase (change before field deployment in /etc/hostapd/hostapd.conf)
wpa_passphrase=classcan2024
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
EOF

# Point hostapd daemon at our config
sed -i 's|^#\?DAEMON_CONF=.*|DAEMON_CONF="/etc/hostapd/hostapd.conf"|' \
    /etc/default/hostapd 2>/dev/null || true

# ── 5b. Tell NetworkManager to leave wlan0 alone ─────────────────────────────
# NM runs on Trixie and will fight hostapd for wlan0 unless explicitly told
# not to. This conf file is the persistent fix that survives reboots.
# To temporarily use wlan0 as a WiFi client (e.g. to install packages),
# run:  sudo bash src/pi/setup/wifi-client.sh on
# Then: sudo bash src/pi/setup/wifi-client.sh off  when done.

log "Telling NetworkManager to leave wlan0 alone (hostapd owns it) ..."
mkdir -p /etc/NetworkManager/conf.d
cat > /etc/NetworkManager/conf.d/classcan-unmanaged.conf <<'EOF'
# CLASSCAN — wlan0 is managed by hostapd (AP mode), not NetworkManager.
# Remove this file and restart NM to temporarily use wlan0 as a WiFi client.
[keyfile]
unmanaged-devices=interface-name:wlan0
EOF
systemctl reload NetworkManager 2>/dev/null || systemctl restart NetworkManager || true
log "  wlan0 unmanaged by NM."

# ── 6. dnsmasq: Wi-Fi DHCP ───────────────────────────────────────────────────

log "Writing dnsmasq hotspot DHCP config (/etc/dnsmasq.d/classcan-hotspot.conf) ..."
cat > /etc/dnsmasq.d/classcan-hotspot.conf <<'EOF'
# CLASSCAN hotspot DHCP — written by install_autoconnect.sh
interface=wlan0
dhcp-range=192.168.20.10,192.168.20.50,255.255.255.0,12h
domain=local
address=/classcan.local/192.168.20.1
EOF

# ── 7. Persist wlan0 static IP (systemd-networkd) ───────────────────────────
# dhcpcd may not be present on Trixie. Use systemd-networkd instead.

log "Writing wlan0 static IP config (/etc/systemd/network/10-classcan-wlan0.network) ..."
mkdir -p /etc/systemd/network
cat > /etc/systemd/network/10-classcan-wlan0.network <<'EOF'
# CLASSCAN hotspot static IP — written by install_autoconnect.sh
[Match]
Name=wlan0

[Network]
Address=192.168.20.1/24
# No DHCP client — hostapd manages this interface
LinkLocalAddressing=no
EOF
systemctl enable systemd-networkd
log "  wlan0 static IP configured via systemd-networkd."

# ── 8. Install the boot runtime script + systemd service ─────────────────────

BOOT_SCRIPT="${SCRIPT_DIR}/classcan-boot.sh"
SERVICE_DST="/etc/systemd/system/classcan-boot.service"

log "Installing systemd service: $SERVICE_DST ..."
cat > "$SERVICE_DST" <<EOF
[Unit]
Description=CLASSCAN Boot — Hotspot + USB Gadget
# Run after systemd-networkd is up so that networkctl reconfigure works
# reliably and eth0 DHCP is not disrupted.
After=systemd-networkd.service
Wants=systemd-networkd.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/bash ${BOOT_SCRIPT}

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable classcan-boot.service
systemctl enable hostapd
systemctl enable dnsmasq
log "classcan-boot.service enabled."

# ── Summary ───────────────────────────────────────────────────────────────────

echo ""
echo "============================================================"
echo "  CLASSCAN Auto-Connect Install Complete"
echo "============================================================"
echo ""
echo "  REBOOT NOW to activate all changes:"
echo "    sudo reboot"
echo ""
echo "  After reboot, reach the Pi via:"
echo ""
echo "  [Wi-Fi Hotspot]"
echo "    Connect to:  CLASSCAN  (default password: classcan2024 — change before deployment)"
echo "    SSH:         ssh pi@192.168.20.1"
echo "    Dashboard:   http://192.168.20.1:8080"
echo "    Also try:    http://classcan.local:8080"
echo ""
echo "  [USB Cable  — micro-USB data cable Pi → laptop]"
echo "    SSH:         ssh pi@192.168.7.1"
echo "    Dashboard:   http://192.168.7.1:8080"
echo "    (Windows: RNDIS adapter appears; may need driver — see usb_gadget.sh)"
echo ""
echo "============================================================"
