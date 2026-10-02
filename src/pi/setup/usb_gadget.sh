#!/usr/bin/env bash
# ============================================================================
# CLASSCAN — Pi USB Gadget Networking Setup
# ============================================================================
# Makes the Pi 3B appear as a USB network adapter when plugged into your
# laptop over a USB cable. No ethernet cable, no Wi-Fi, no router needed —
# just the USB cable you already use for power/serial.
#
# ── How it works ────────────────────────────────────────────────────────────
# The Pi's USB OTG port (the micro-USB power port on Pi 3B) can be switched
# into "gadget" mode, presenting itself as a RNDIS (Windows) / ECM (macOS/
# Linux) USB network interface. The Pi gets a fixed IP; the laptop's OS
# assigns itself an address via DHCP on the virtual adapter.
#
# ── Pi 3B note ───────────────────────────────────────────────────────────────
# The Pi 3B uses the dwc2 USB controller which supports gadget mode, but ONLY
# through the board's micro-USB port (J1). The 4 full-size USB-A ports do NOT
# support OTG. You need a micro-USB data cable (not a charge-only cable).
#
# ── What this script does ────────────────────────────────────────────────────
# 1. Enables dwc2 overlay and g_ether module in config.txt and /etc/modules
# 2. Configures usb0 with a static IP (192.168.7.1)
# 3. Optionally sets up dnsmasq to hand the laptop an IP via DHCP
#
# After running + rebooting, plug a data USB cable from Pi micro-USB → laptop.
# On Windows: a "Remote NDIS" or "USB Ethernet" adapter appears. It may need
#             the RNDIS driver: Device Manager → update driver → browse →
#             pick "Remote NDIS Compatible Device" from the list.
# On macOS/Linux: a network interface (e.g. en5 or usb0) appears automatically.
#
# Then open:  http://192.168.7.1:8080   in your browser.
#
# Usage (run on the Pi):
#   sudo bash usb_gadget.sh
# ============================================================================

set -euo pipefail

GADGET_IP="192.168.7.1"
IFACE="usb0"
DASHBOARD_PORT="8080"
CONFIG_TXT="/boot/config.txt"
MODULES_FILE="/etc/modules"
INTERFACES_DIR="/etc/network/interfaces.d"
DNSMASQ_CONF="/etc/dnsmasq.d/classcan-usb.conf"

# ── helpers ──────────────────────────────────────────────────────────────────

log()  { echo "[usb_gadget] $*"; }
warn() { echo "[usb_gadget] WARNING: $*" >&2; }

require_root() {
    if [[ $EUID -ne 0 ]]; then
        echo "ERROR: This script must be run as root (sudo bash usb_gadget.sh)"
        exit 1
    fi
}

line_in_file() {
    # Return 0 if the exact line $1 is in file $2, else 1
    grep -qxF "$1" "$2" 2>/dev/null
}

# ── step 1 — enable dwc2 overlay ─────────────────────────────────────────────

enable_dwc2() {
    log "Checking $CONFIG_TXT for dwc2 overlay ..."
    if ! line_in_file "dtoverlay=dwc2" "$CONFIG_TXT"; then
        echo "dtoverlay=dwc2" >> "$CONFIG_TXT"
        log "Added: dtoverlay=dwc2"
    else
        log "Already present: dtoverlay=dwc2"
    fi
}

# ── step 2 — load g_ether module ─────────────────────────────────────────────

enable_gether() {
    log "Checking $MODULES_FILE for dwc2 + g_ether ..."
    if ! line_in_file "dwc2" "$MODULES_FILE"; then
        echo "dwc2" >> "$MODULES_FILE"
        log "Added: dwc2"
    fi
    if ! line_in_file "g_ether" "$MODULES_FILE"; then
        echo "g_ether" >> "$MODULES_FILE"
        log "Added: g_ether"
    fi
}

# ── step 3 — static IP for usb0 ──────────────────────────────────────────────

configure_usb0_ip() {
    local conf="${INTERFACES_DIR}/classcan-usb0.conf"
    log "Writing $conf ..."
    cat > "$conf" <<EOF
# CLASSCAN USB gadget network — written by usb_gadget.sh
auto $IFACE
allow-hotplug $IFACE
iface $IFACE inet static
    address $GADGET_IP
    netmask 255.255.255.0
EOF
    log "usb0 static IP configured: $GADGET_IP"
}

# ── step 4 — dnsmasq for laptop DHCP (optional but convenient on Windows) ──

configure_dnsmasq() {
    if ! command -v dnsmasq &>/dev/null; then
        log "dnsmasq not installed — skipping DHCP setup (install with: apt install dnsmasq)"
        return
    fi
    log "Writing $DNSMASQ_CONF ..."
    cat > "$DNSMASQ_CONF" <<EOF
# CLASSCAN USB gadget DHCP — written by usb_gadget.sh
interface=$IFACE
dhcp-range=192.168.7.2,192.168.7.10,255.255.255.0,24h
EOF
    systemctl enable dnsmasq --quiet
    log "dnsmasq configured. Laptop will receive 192.168.7.2 via DHCP."
}

# ── summary ───────────────────────────────────────────────────────────────────

print_summary() {
    echo ""
    echo "============================================================"
    echo "  CLASSCAN — USB Gadget Networking Configured"
    echo "============================================================"
    echo "  REBOOT THE PI NOW for changes to take effect."
    echo ""
    echo "  Then plug a data USB cable: Pi micro-USB → laptop."
    echo ""
    echo "  Pi IP     : $GADGET_IP"
    echo "  Dashboard : http://${GADGET_IP}:${DASHBOARD_PORT}"
    echo "  SSH       : ssh pi@${GADGET_IP}"
    echo ""
    echo "  Windows: A 'Remote NDIS' adapter will appear in Device Manager."
    echo "           If it shows as unknown device, install RNDIS driver:"
    echo "           Device Manager → right-click → Update Driver →"
    echo "           Browse → Let me pick → Remote NDIS Compatible Device"
    echo ""
    echo "  macOS / Linux: a usb0 / en* interface appears automatically."
    echo "============================================================"
}

# ── main ─────────────────────────────────────────────────────────────────────

require_root
enable_dwc2
enable_gether
configure_usb0_ip
configure_dnsmasq
print_summary
