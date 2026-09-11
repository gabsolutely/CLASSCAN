#!/usr/bin/env bash
# CLASSCAN Headless Network Watchdog
# Automatically pings target DNS/gateway and reboots if connectivity is lost

TARGET="1.1.1.1"
LOGFILE="/var/log/wifi-watchdog.log"

if ! ping -c 3 -W 5 "$TARGET" > /dev/null 2>&1; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Network unreachable. Cycling wlan0 interface..." >> "$LOGFILE"
    ip link set wlan0 down
    sleep 3
    ip link set wlan0 up
    sleep 10
    if ! ping -c 3 -W 5 "$TARGET" > /dev/null 2>&1; then
        echo "$(date '+%Y-%m-%d %H:%M:%S') - Re-ping failed. Rebooting system..." >> "$LOGFILE"
        /sbin/reboot
    fi
fi
