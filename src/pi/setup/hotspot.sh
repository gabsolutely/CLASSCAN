#!/usr/bin/env bash
# ============================================================================
# CLASSCAN — Pi 3B Wi-Fi Hotspot Setup
# ============================================================================
# Turns the Pi's built-in wlan0 into a standalone Wi-Fi access point.
# Devices connect to the "CLASSCAN" network and reach the dashboard at:
#
#   http://192.168.20.1:8080
#
# The Pi 3B has a single Wi-Fi chip — while hotspot is active it CANNOT
# simultaneously connect to another Wi-Fi network. Use ethernet for SSH
# if you need a terminal while the hotspot is running.
#
# Usage (run on the Pi):
#   sudo bash hotspot.sh              # start hotspot (until next reboot)
#   sudo bash hotspot.sh --persistent # install & enable as systemd services
#   sudo bash hotspot.sh --stop       # tear down the hotspot
#   sudo bash hotspot.sh --status     # show current state
#
# Requirements (installed automatically if missing):
#   hostapd   — manages the Wi-Fi access point
#   dnsmasq   — DHCP server so connected devices get an IP
# ============================================================================

set -euo pipefail

# ── Config ────────────────────────────────────────────────────────────────────
SSID="CLASSCAN"
PASSPHRASE="classcan2024"      # WPA2, min 8 chars — change before demo if wanted
CHANNEL="6"                   # 2.4 GHz ch6 — works on all devices, avoids ch1/11 crowding
IFACE="wlan0"
PI_IP="192.168.20.1"
DHCP_RANGE_START="192.168.20.10"
DHCP_RANGE_END="192.168.20.50"
DHCP_MASK="255.255.255.0"
DHCP_LEASE="12h"
DASHBOARD_PORT="8080"

HOSTAPD_CONF="/etc/hostapd/classcan-hotspot.conf"
DNSMASQ_CONF="/etc/dnsmasq.d/classcan-hotspot.conf"

# ── Helpers ───────────────────────────────────────────────────────────────────

log()  { echo "[hotspot] $*"; }
warn() { echo "[hotspot] WARNING: $*" >&2; }
die()  { echo "[hotspot] ERROR: $*" >&2; exit 1; }

require_root() {
    [[ $EUID -eq 0 ]] || die "Run as root: sudo bash hotspot.sh"
}

check_iface() {
    ip link show "$IFACE" &>/dev/null || \
        die "Interface $IFACE not found. Is this a Pi 3B?"
}

install_deps() {
    log "Checking dependencies ..."
    local missing=()
    command -v hostapd  &>/dev/null || missing+=(hostapd)
    command -v dnsmasq  &>/dev/null || missing+=(dnsmasq)

    if [[ ${#missing[@]} -gt 0 ]]; then
        log "Installing: ${missing[*]}"
        apt-get update -qq
        apt-get install -y "${missing[@]}"
    else
        log "hostapd and dnsmasq already installed."
    fi
}

write_hostapd_conf() {
    log "Writing hostapd config -> $HOSTAPD_CONF"
    cat > "$HOSTAPD_CONF" <<EOF
# CLASSCAN hotspot — written by hotspot.sh
interface=$IFACE
driver=nl80211
ssid=$SSID
hw_mode=g
channel=$CHANNEL
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=$PASSPHRASE
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
EOF
    # Tell hostapd which config to use
    sed -i 's|^#\?DAEMON_CONF=.*|DAEMON_CONF="'"$HOSTAPD_CONF"'"|' /etc/default/hostapd 2>/dev/null || true
}

write_dnsmasq_conf() {
    log "Writing dnsmasq config -> $DNSMASQ_CONF"
    cat > "$DNSMASQ_CONF" <<EOF
# CLASSCAN hotspot DHCP — written by hotspot.sh
interface=$IFACE
dhcp-range=$DHCP_RANGE_START,$DHCP_RANGE_END,$DHCP_MASK,$DHCP_LEASE
domain=local
address=/classcan.local/$PI_IP
EOF
}

assign_static_ip() {
    log "Assigning static IP $PI_IP to $IFACE ..."
    ip link set "$IFACE" up
    ip addr flush dev "$IFACE" 2>/dev/null || true
    ip addr add "${PI_IP}/24" dev "$IFACE"
}

start_services() {
    log "Starting hostapd ..."
    systemctl unmask hostapd 2>/dev/null || true
    systemctl start hostapd

    log "Starting dnsmasq ..."
    systemctl restart dnsmasq

    # Give hostapd a moment to come up
    sleep 2

    if systemctl is-active --quiet hostapd; then
        log "hostapd running OK"
    else
        warn "hostapd failed to start. Run: sudo journalctl -u hostapd -n 30"
    fi
}

enable_persistent() {
    log "Enabling services on boot ..."
    systemctl enable hostapd
    systemctl enable dnsmasq

    # Persist static IP via dhcpcd (Pi OS default network manager)
    local DHCPCD_CONF="/etc/dhcpcd.conf"
    if ! grep -q "classcan-hotspot" "$DHCPCD_CONF" 2>/dev/null; then
        log "Appending static IP to $DHCPCD_CONF ..."
        cat >> "$DHCPCD_CONF" <<EOF

# CLASSCAN hotspot static IP — written by hotspot.sh
interface $IFACE
    static ip_address=${PI_IP}/24
    nohook wpa_supplicant
EOF
    else
        log "dhcpcd.conf already has CLASSCAN entry — skipping."
    fi
    log "Hotspot will start automatically on boot."
}

stop_hotspot() {
    log "Stopping hotspot ..."
    systemctl stop hostapd  2>/dev/null && log "hostapd stopped." || warn "hostapd was not running."
    systemctl stop dnsmasq  2>/dev/null && log "dnsmasq stopped."  || warn "dnsmasq was not running."
    ip addr flush dev "$IFACE" 2>/dev/null || true
    log "Done. wlan0 released — reconnect to your normal Wi-Fi if needed."
}

show_status() {
    echo ""
    echo "── hostapd ─────────────────────────────────────────"
    systemctl status hostapd --no-pager -n 5 2>/dev/null || echo "  (not running)"
    echo ""
    echo "── dnsmasq ─────────────────────────────────────────"
    systemctl status dnsmasq --no-pager -n 5 2>/dev/null || echo "  (not running)"
    echo ""
    echo "── wlan0 IP ─────────────────────────────────────────"
    ip addr show "$IFACE" 2>/dev/null || echo "  (no address)"
    echo ""
}

print_summary() {
    echo ""
    echo "============================================================"
    echo "  CLASSCAN Hotspot Active"
    echo "============================================================"
    echo "  Network   : $SSID"
    echo "  Password  : $PASSPHRASE"
    echo "  Pi IP     : $PI_IP"
    echo ""
    echo "  1. Connect your device to Wi-Fi: \"$SSID\""
    echo "  2. Open in browser: http://${PI_IP}:${DASHBOARD_PORT}"
    echo "     (or try: http://classcan.local:${DASHBOARD_PORT})"
    echo ""
    echo "  SSH while on hotspot: ssh pi@${PI_IP}"
    echo "============================================================"
}

# ── Main ──────────────────────────────────────────────────────────────────────

require_root
check_iface

case "${1:-}" in
    --stop)
        stop_hotspot
        exit 0
        ;;
    --status)
        show_status
        exit 0
        ;;
    --persistent)
        install_deps
        write_hostapd_conf
        write_dnsmasq_conf
        assign_static_ip
        start_services
        enable_persistent
        print_summary
        ;;
    "")
        install_deps
        write_hostapd_conf
        write_dnsmasq_conf
        assign_static_ip
        start_services
        print_summary
        ;;
    *)
        die "Unknown option: ${1}. Usage: sudo bash hotspot.sh [--persistent | --stop | --status]"
        ;;
esac
