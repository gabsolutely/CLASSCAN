#!/usr/bin/env bash
# ============================================================================
# CLASSCAN — Pi Direct Ethernet Connection Setup
# ============================================================================
# Configures eth0 on the Pi with a static IP so you can reach the dashboard
# from a laptop over a plain ethernet cable (no router, no Wi-Fi needed).
#
# Laptop end: set your ethernet adapter to a static IP in the same subnet:
#   Windows: Control Panel → Network Adapters → Ethernet → IPv4 Properties
#              IP: 192.168.10.2  |  Mask: 255.255.255.0  |  GW: (leave blank)
#   macOS:   System Settings → Network → Ethernet → Manual
#              IP: 192.168.10.2  |  Mask: 255.255.255.0
#
# Then open:  http://192.168.10.1:8080   in your browser.
#
# Usage (run on the Pi):
#   bash direct_connect.sh              # apply once (lost on reboot)
#   bash direct_connect.sh --persistent # write to /etc/network/interfaces.d/
#                                       # so it survives reboots
# ============================================================================

set -euo pipefail

PI_IP="192.168.10.1"
PI_MASK="255.255.255.0"
IFACE="eth0"
DASHBOARD_PORT="8080"
PERSISTENT_FILE="/etc/network/interfaces.d/classcan-eth-static.conf"

# ── helpers ──────────────────────────────────────────────────────────────────

log()  { echo "[direct_connect] $*"; }
warn() { echo "[direct_connect] WARNING: $*" >&2; }

require_root() {
    if [[ $EUID -ne 0 ]]; then
        echo "ERROR: This script must be run as root (sudo bash direct_connect.sh)"
        exit 1
    fi
}

check_iface() {
    if ! ip link show "$IFACE" &>/dev/null; then
        warn "Interface $IFACE not found. Is the ethernet cable plugged in?"
        warn "Available interfaces:"
        ip link show | grep -E '^[0-9]+:' | awk '{print "  " $2}' | tr -d ':'
        exit 1
    fi
}

apply_ip() {
    log "Bringing up $IFACE with static IP $PI_IP ..."
    ip link set "$IFACE" up
    # Flush any existing IP first to avoid duplicate-address warnings
    ip addr flush dev "$IFACE" 2>/dev/null || true
    ip addr add "${PI_IP}/24" dev "$IFACE"
    log "Done. eth0 is now $PI_IP"
}

write_persistent() {
    log "Writing persistent config to $PERSISTENT_FILE ..."
    cat > "$PERSISTENT_FILE" <<EOF
# CLASSCAN static ethernet — written by direct_connect.sh
# Remove this file to restore DHCP on eth0.
auto $IFACE
iface $IFACE inet static
    address $PI_IP
    netmask $PI_MASK
EOF
    log "Persistent config written."
    log "Restart networking to activate: sudo systemctl restart networking"
}

print_summary() {
    echo ""
    echo "============================================================"
    echo "  CLASSCAN — Direct Ethernet Connection Ready"
    echo "============================================================"
    echo "  Pi IP  : $PI_IP"
    echo "  Laptop : set your ethernet adapter to 192.168.10.2 / 255.255.255.0"
    echo ""
    echo "  Dashboard : http://${PI_IP}:${DASHBOARD_PORT}"
    echo "  SSH       : ssh pi@${PI_IP}"
    echo "============================================================"
}

# ── main ─────────────────────────────────────────────────────────────────────

require_root
check_iface
apply_ip

if [[ "${1:-}" == "--persistent" ]]; then
    write_persistent
fi

print_summary
