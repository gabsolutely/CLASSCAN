#!/usr/bin/env bash
# ============================================================================
# CLASSCAN — Boot-Time Network Bringup
# ============================================================================
# Called by classcan-boot.service on every boot.
# Brings up:
#   1. wlan0 static IP + hostapd (Wi-Fi hotspot at 192.168.20.1)
#   2. usb0 static IP via systemd-networkd   (192.168.7.1, once USB cable plugged in)
#
# Do NOT run this directly — use install_autoconnect.sh to set everything up,
# then just reboot.
# ============================================================================

set -euo pipefail

log()  { echo "[classcan-boot] $*"; }
warn() { echo "[classcan-boot] WARNING: $*" >&2; }

# ── 1. Wi-Fi Hotspot (wlan0) ─────────────────────────────────────────────────

log "Bringing up wlan0 hotspot ..."

# Release wlan0 from NetworkManager (NM runs on Trixie and will conflict with
# hostapd if it keeps hold of the interface). The persistent fix is the NM
# conf.d file written by install_autoconnect.sh; this is a boot-time guard
# for the first boot and any recovery scenario where NM grabbed it anyway.
if command -v nmcli &>/dev/null && systemctl is-active --quiet NetworkManager; then
    nmcli device disconnect wlan0 2>/dev/null || true
    nmcli device set wlan0 managed no 2>/dev/null || true
    sleep 1
    log "  wlan0 released from NetworkManager."
else
    # Legacy fallback (no NM): kill wpa_supplicant directly
    pkill -f "wpa_supplicant.*wlan0" 2>/dev/null && \
        log "  Stopped wpa_supplicant on wlan0." || true
fi

# Bring up the interface and assign static IP.
# Try systemd-networkd first; fall back to explicit ip addr add so this
# script works regardless of whether systemd-networkd is managing wlan0.
ip link set wlan0 up
networkctl reconfigure wlan0 2>/dev/null || true
sleep 1

# Verify the address was actually applied; assign it explicitly if not.
if ! ip addr show wlan0 | grep -q "192.168.20.1"; then
    log "  systemd-networkd did not assign IP — applying manually."
    ip addr flush dev wlan0 2>/dev/null || true
    ip addr add 192.168.20.1/24 dev wlan0
fi


# Start hostapd (uses /etc/hostapd/hostapd.conf written by hotspot.sh / install_autoconnect.sh)
systemctl restart hostapd

# Give it a moment to come up
sleep 2

if systemctl is-active --quiet hostapd; then
    log "  hostapd running OK (SSID: CLASSCAN, 192.168.20.1)"
else
    warn "  hostapd failed to start. Check: sudo journalctl -u hostapd -n 30"
fi

# Restart dnsmasq so it picks up both wlan0 + usb0 DHCP configs
systemctl restart dnsmasq
log "  dnsmasq restarted."

# ── 2. USB gadget (usb0) ─────────────────────────────────────────────────────
# usb0 is configured by /etc/systemd/network/10-classcan-usb0.network and
# brought up automatically by systemd-networkd when the USB cable is plugged in.

sleep 1

if ip link show usb0 &>/dev/null; then
    log "  usb0 interface present (192.168.7.1)."
else
    log "  usb0 not yet present — will appear when a USB data cable is plugged in."
fi

# ── Done ─────────────────────────────────────────────────────────────────────

log "Boot bringup complete."
log "  Hotspot : ssh pi@192.168.20.1  |  http://192.168.20.1:8080"
log "  USB     : ssh pi@192.168.7.1   |  http://192.168.7.1:8080"
