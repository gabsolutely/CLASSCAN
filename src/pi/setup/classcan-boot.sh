#!/usr/bin/env bash
# ============================================================================
# CLASSCAN — Boot-Time Network Bringup
# ============================================================================
# Called by classcan-boot.service on every boot.
# Brings up:
#   1. wlan0 static IP + hostapd (Wi-Fi hotspot)
#   2. usb0 static IP via interfaces.d (happens automatically; we just verify)
#
# Do NOT run this directly — use install_autoconnect.sh to set everything up,
# then just reboot.
# ============================================================================

set -euo pipefail

log()  { echo "[classcan-boot] $*"; }
warn() { echo "[classcan-boot] WARNING: $*" >&2; }

# ── 1. Wi-Fi Hotspot (wlan0) ─────────────────────────────────────────────────

log "Bringing up wlan0 hotspot ..."

# Kill wpa_supplicant on wlan0 if it's running (conflicts with hostapd)
pkill -f "wpa_supplicant.*wlan0" 2>/dev/null && \
    log "  Stopped wpa_supplicant on wlan0." || true

# Bring up the interface; systemd-networkd applies the static IP from
# /etc/systemd/network/10-classcan-wlan0.network (written by install_autoconnect.sh)
ip link set wlan0 up
networkctl reconfigure wlan0 2>/dev/null || true
sleep 1


# Start hostapd (uses /etc/hostapd/classcan-hotspot.conf set by install script)
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
# usb0 is brought up automatically by /etc/network/interfaces.d/classcan-usb0.conf
# on allow-hotplug, so we just log whether the interface is already present.

sleep 1

if ip link show usb0 &>/dev/null; then
    log "  usb0 interface present (192.168.7.1)."
else
    log "  usb0 not yet present — it will appear when a USB data cable is plugged in."
fi

# ── Done ─────────────────────────────────────────────────────────────────────

log "Boot bringup complete."
log "  Hotspot : ssh pi@192.168.20.1  |  http://192.168.20.1:8080"
log "  USB     : ssh pi@192.168.7.1   |  http://192.168.7.1:8080"
