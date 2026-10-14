#!/usr/bin/env bash
# ============================================================================
# CLASSCAN — Wi-Fi Client Mode Toggle
# ============================================================================
# Normally wlan0 is owned by hostapd (hotspot mode). Use this script to
# temporarily hand wlan0 back to NetworkManager so you can connect to a
# Wi-Fi network (e.g. to run apt install, git pull, etc.).
#
# Usage:
#   sudo bash wifi-client.sh on           # switch to WiFi client mode
#   sudo bash wifi-client.sh off          # switch back to hotspot mode
#   sudo bash wifi-client.sh status       # show current mode
#
# "on" stops the hotspot, lets NM connect to the last saved Wi-Fi network.
# "off" disconnects NM from Wi-Fi and restarts the hotspot.
# ============================================================================

set -euo pipefail

NM_CONF="/etc/NetworkManager/conf.d/classcan-unmanaged.conf"

log()  { echo "[wifi-client] $*"; }
die()  { echo "[wifi-client] ERROR: $*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "Run as root: sudo bash wifi-client.sh [on|off|status]"

case "${1:-}" in

    on)
        log "Switching to Wi-Fi CLIENT mode ..."

        # Stop hotspot
        systemctl stop hostapd  2>/dev/null && log "  hostapd stopped." || true
        systemctl stop classcan-boot.service 2>/dev/null || true

        # Flush static IP assigned by boot script so NM starts clean
        ip addr flush dev wlan0 2>/dev/null || true

        # Remove the NM unmanaged conf so NM takes over wlan0
        if [[ -f "$NM_CONF" ]]; then
            rm "$NM_CONF"
            log "  Removed NM unmanaged config."
        fi
        systemctl reload NetworkManager 2>/dev/null || systemctl restart NetworkManager

        # Give NM a moment, then connect to the last saved WiFi connection
        sleep 2
        SAVED=$(nmcli -t -f NAME,TYPE connection show | grep wireless | head -1 | cut -d: -f1)
        if [[ -n "$SAVED" ]]; then
            log "  Connecting to saved network: $SAVED ..."
            nmcli con up "$SAVED" 2>/dev/null && log "  Connected." || \
                log "  Auto-connect failed — run: sudo nmcli dev wifi connect \"SSID\" password \"PASS\""
        else
            log "  No saved Wi-Fi connections found."
            log "  Run: sudo nmcli dev wifi connect \"SSID\" password \"PASS\""
        fi

        echo ""
        echo "  Wi-Fi client mode ON. wlan0 is managed by NetworkManager."
        echo "  When done, run:  sudo bash src/pi/setup/wifi-client.sh off"
        echo ""
        ;;

    off)
        log "Switching back to HOTSPOT mode ..."

        # Disconnect NM from wlan0
        nmcli device disconnect wlan0 2>/dev/null || true
        nmcli device set wlan0 managed no  2>/dev/null || true

        # Restore the NM unmanaged conf
        mkdir -p /etc/NetworkManager/conf.d
        cat > "$NM_CONF" <<'EOF'
# CLASSCAN — wlan0 is managed by hostapd (AP mode), not NetworkManager.
# Remove this file and restart NM to temporarily use wlan0 as a WiFi client.
[keyfile]
unmanaged-devices=interface-name:wlan0
EOF
        systemctl reload NetworkManager 2>/dev/null || systemctl restart NetworkManager || true
        sleep 1

        # Restart the hotspot via the boot script
        log "  Starting hotspot ..."
        bash "$(dirname "$(realpath "$0")")/classcan-boot.sh"

        echo ""
        echo "  Hotspot mode ON. Devices can connect to: CLASSCAN (classcan2024)"
        echo "  Dashboard: http://192.168.20.1:8080"
        echo ""
        ;;

    status)
        echo ""
        if [[ -f "$NM_CONF" ]]; then
            echo "  Mode   : HOTSPOT (NM unmanaged conf present)"
        else
            echo "  Mode   : Wi-Fi CLIENT (NM manages wlan0)"
        fi
        echo ""
        echo "  wlan0:"
        ip addr show wlan0 2>/dev/null | grep -E "state|inet" | sed 's/^/    /'
        echo ""
        echo "  hostapd: $(systemctl is-active hostapd 2>/dev/null || echo not-running)"
        echo "  NM wlan0: $(nmcli -t -f DEVICE,STATE device status 2>/dev/null | grep wlan0 | cut -d: -f2 || echo unknown)"
        echo ""
        ;;

    *)
        die "Usage: sudo bash wifi-client.sh [on | off | status]"
        ;;
esac
