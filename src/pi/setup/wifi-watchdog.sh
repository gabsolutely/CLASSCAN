#!/usr/bin/env bash
# ============================================================================
# CLASSCAN Headless Network Watchdog
# ============================================================================
# Runs every 5 minutes via root cron. Checks that the wlan0 hotspot is alive
# (correct IP assigned + hostapd running). If not, restarts classcan-boot.
# If it still fails, reboots as a last resort.
#
# IMPORTANT: Do NOT ping an external address (e.g. 1.1.1.1) here. In hotspot
# mode the Pi is the AP and has no upstream internet route, so an external
# ping always fails and would cause a reboot loop.
#
# Cron install (run as root):
#   (crontab -l; echo "*/5 * * * * /usr/local/bin/wifi-watchdog.sh") | crontab -
# ============================================================================

EXPECTED_IP="192.168.20.1"
LOGFILE="/var/log/wifi-watchdog.log"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$LOGFILE"; }

# ── Check 1: wlan0 has the hotspot IP ────────────────────────────────────────

if ! ip addr show wlan0 2>/dev/null | grep -q "$EXPECTED_IP"; then
    log "wlan0 missing $EXPECTED_IP. Restarting classcan-boot.service ..."
    systemctl restart classcan-boot.service 2>/dev/null || true
    sleep 15

    if ! ip addr show wlan0 2>/dev/null | grep -q "$EXPECTED_IP"; then
        log "Still no IP after restart. Rebooting ..."
        /sbin/reboot
    else
        log "wlan0 IP restored OK."
    fi
    exit 0
fi

# ── Check 2: hostapd is running ───────────────────────────────────────────────

if ! systemctl is-active --quiet hostapd; then
    log "hostapd not running. Restarting classcan-boot.service ..."
    systemctl restart classcan-boot.service 2>/dev/null || true
    sleep 10

    if ! systemctl is-active --quiet hostapd; then
        log "hostapd still dead after restart. Rebooting ..."
        /sbin/reboot
    else
        log "hostapd restarted OK."
    fi
fi

# All good — no log entry needed (keeps log clean)
