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
PASSPHRASE="classcan2024"      # WPA2, min 8 chars — CHANGE THIS BEFORE DEPLOYMENT
CHANNEL="6"                   # 2.4 GHz ch6 — works on all devices, avoids ch1/11 crowding
IFACE="wlan0"
PI_IP="192.168.20.1"
DHCP_RANGE_START="192.168.20.10"
DHCP_RANGE_END="192.168.20.50"
DHCP_MASK="255.255.255.0"
DHCP_LEASE="12h"
DASHBOARD_PORT="8080"

# NOTE: must be hostapd.conf (not a custom name) — the systemd unit has
#   ConditionFileNotEmpty=/etc/hostapd/hostapd.conf which fires before DAEMON_CONF is read.
HOSTAPD_CONF="/etc/hostapd/hostapd.conf"
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
    mkdir -p /etc/default
    if grep -q "DAEMON_CONF" /etc/default/hostapd 2>/dev/null; then
        sed -i 's|^#\?DAEMON_CONF=.*|DAEMON_CONF="'"$HOSTAPD_CONF"'"|' /etc/default/hostapd 2>/dev/null || true
    else
        echo "DAEMON_CONF=\"$HOSTAPD_CONF\"" >> /etc/default/hostapd
    fi
}

write_dnsmasq_conf() {
    log "Writing dnsmasq config -> $DNSMASQ_CONF"
    cat > "$DNSMASQ_CONF" <<EOF
# CLASSCAN hotspot DHCP — written by hotspot.sh
interface=$IFACE
except-interface=lo
bind-dynamic
dhcp-range=$DHCP_RANGE_START,$DHCP_RANGE_END,$DHCP_MASK,$DHCP_LEASE
dhcp-option=3,$PI_IP
dhcp-option=6,$PI_IP
domain=local
address=/classcan.local/$PI_IP
EOF
}

release_from_nm() {
    if command -v nmcli &>/dev/null && systemctl is-active --quiet NetworkManager; then
        log "NetworkManager is running — unmanaging $IFACE so hostapd can own it ..."
        nmcli device disconnect "$IFACE" 2>/dev/null || true
        nmcli device set "$IFACE" managed no
        sleep 1
        log "  $IFACE released from NetworkManager."
    else
        # Legacy: kill wpa_supplicant directly
        pkill -f "wpa_supplicant.*$IFACE" 2>/dev/null && \
            log "  Stopped wpa_supplicant on $IFACE." || true
    fi
}

restore_to_nm() {
    if command -v nmcli &>/dev/null && systemctl is-active --quiet NetworkManager; then
        log "Returning $IFACE to NetworkManager ..."
        nmcli device set "$IFACE" managed yes
    fi
}

assign_static_ip() {
    log "Assigning static IP $PI_IP to $IFACE ..."
    rfkill unblock wifi 2>/dev/null || true
    ip link set "$IFACE" up
    # Flush ALL addresses (including any DHCP lease from a school router)
    # so wlan0 ends up with only our static AP address.
    ip addr flush dev "$IFACE" 2>/dev/null || true
    ip addr add "${PI_IP}/24" dev "$IFACE"
    log "  $IFACE now has ${PI_IP}/24"
}

start_services() {
    log "Starting hostapd ..."
    rfkill unblock wifi 2>/dev/null || true
    systemctl unmask hostapd 2>/dev/null || true
    # Reload unit files so systemd re-evaluates ConditionFileNotEmpty
    systemctl daemon-reload 2>/dev/null || true
    systemctl restart hostapd

    # Give hostapd a moment to switch interface to AP mode
    sleep 2

    # Re-apply static IP in case hostapd bounced the interface into AP mode
    ip link set "$IFACE" up
    if ! ip addr show "$IFACE" | grep -q "$PI_IP"; then
        log "Re-asserting static IP $PI_IP on $IFACE ..."
        ip addr add "${PI_IP}/24" dev "$IFACE" 2>/dev/null || true
    fi

    log "Starting dnsmasq ..."
    systemctl restart dnsmasq
    sleep 1

    if systemctl is-active --quiet hostapd; then
        log "hostapd running OK"
    else
        warn "hostapd failed to start. Run: sudo journalctl -u hostapd -n 30"
        warn "Trying to start hostapd directly for diagnostics ..."
        hostapd -dd "$HOSTAPD_CONF" &
        sleep 2
        kill %1 2>/dev/null || true
    fi

    if systemctl is-active --quiet dnsmasq; then
        log "dnsmasq running OK"
    else
        warn "dnsmasq failed to start. Run: sudo journalctl -u dnsmasq -n 30"
    fi
}

enable_persistent() {
    log "Enabling services on boot ..."
    systemctl unmask hostapd 2>/dev/null || true
    systemctl enable hostapd
    systemctl enable dnsmasq

    # Clean up any legacy or deadlock-prone units
    systemctl stop classcan-hotspot.service 2>/dev/null || true
    systemctl disable classcan-hotspot.service 2>/dev/null || true
    rm -f /etc/systemd/system/classcan-hotspot.service 2>/dev/null || true

    # 1. Prevent NetworkManager from grabbing wlan0 on boot
    if command -v nmcli &>/dev/null || [ -d /etc/NetworkManager ]; then
        log "Writing NetworkManager unmanaged rule for $IFACE ..."
        mkdir -p /etc/NetworkManager/conf.d
        cat > /etc/NetworkManager/conf.d/classcan-unmanaged.conf <<EOF
# CLASSCAN — $IFACE is managed by hostapd (AP mode), not NetworkManager.
[keyfile]
unmanaged-devices=interface-name:$IFACE
EOF
        systemctl reload NetworkManager 2>/dev/null || true
        log "  $IFACE permanently unmanaged by NetworkManager."
    fi

    # 2. Configure hostapd systemd drop-in override (prepares wlan0 interface cleanly before hostapd starts)
    log "Configuring systemd drop-in overrides ..."
    mkdir -p /etc/systemd/system/hostapd.service.d
    cat > /etc/systemd/system/hostapd.service.d/override.conf <<EOF
[Unit]
After=network.target

[Service]
ExecStartPre=-/usr/sbin/rfkill unblock wifi
ExecStartPre=-/usr/bin/nmcli device set $IFACE managed no
ExecStartPre=-/sbin/ip link set $IFACE up
ExecStartPre=-/sbin/ip addr replace ${PI_IP}/24 dev $IFACE
EOF

    # 3. Configure dnsmasq drop-in override (starts only AFTER hostapd brings up AP mode)
    mkdir -p /etc/systemd/system/dnsmasq.service.d
    cat > /etc/systemd/system/dnsmasq.service.d/override.conf <<EOF
[Unit]
After=hostapd.service
Wants=hostapd.service
EOF

    systemctl daemon-reload
    log "Hotspot persistence configured (hostapd & dnsmasq enabled via systemd drop-ins)."
}

stop_hotspot() {
    log "Stopping hotspot ..."
    systemctl stop hostapd  2>/dev/null && log "hostapd stopped." || warn "hostapd was not running."
    systemctl stop dnsmasq  2>/dev/null && log "dnsmasq stopped."  || warn "dnsmasq was not running."
    systemctl disable classcan-hotspot.service 2>/dev/null || true
    rm -f /etc/systemd/system/classcan-hotspot.service 2>/dev/null || true
    rm -f /etc/NetworkManager/conf.d/classcan-unmanaged.conf 2>/dev/null || true
    rm -rf /etc/systemd/system/hostapd.service.d /etc/systemd/system/dnsmasq.service.d 2>/dev/null || true
    systemctl daemon-reload 2>/dev/null || true
    ip addr flush dev "$IFACE" 2>/dev/null || true
    restore_to_nm
    systemctl reload NetworkManager 2>/dev/null || true
    log "Done. wlan0 released — NetworkManager will reconnect to your normal Wi-Fi."
}

show_status() {
    echo ""
    echo "── hostapd ─────────────────────────────────────────"
    systemctl status hostapd --no-pager -n 5 2>/dev/null || echo "  (not running)"
    echo ""
    echo "── dnsmasq ─────────────────────────────────────────"
    systemctl status dnsmasq --no-pager -n 5 2>/dev/null || echo "  (not running)"
    echo ""
    echo "── $IFACE IP ─────────────────────────────────────────"
    ip addr show "$IFACE" 2>/dev/null || echo "  (no address)"
    echo ""
    echo "── DHCP Leases (connected devices) ─────────────────"
    cat /var/lib/misc/dnsmasq.leases 2>/dev/null || echo "  (no active leases recorded)"
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
        release_from_nm
        assign_static_ip
        start_services
        enable_persistent
        print_summary
        ;;
    "")
        install_deps
        write_hostapd_conf
        write_dnsmasq_conf
        release_from_nm
        assign_static_ip
        start_services
        print_summary
        ;;
    *)
        die "Unknown option: ${1}. Usage: sudo bash hotspot.sh [--persistent | --stop | --status]"
        ;;
esac
