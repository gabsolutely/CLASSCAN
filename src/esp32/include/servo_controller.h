/*
 * Pan/Tilt servo controller.
 *
 * Two modes:
 *   SWEEP     — continuously sweeps pan from min to max and back
 *   ZONE      — steps through a calibrated quadrant lookup table;
 *               reports moving/idle per step for Pi's change-trigger
 *
 * Quadrant lookup table: fill in actual pan/tilt degree values
 * after physical calibration once the turret is mounted.
 */

#pragma once
#include <Arduino.h>
#include <ESP32Servo.h>
#include "config.h"

namespace ServoController {

    static Servo _pan;
    static Servo _tilt;

    // ── Sweep state ──────────────────────────────────────────────────────
    static int  _panPos    = SERVO_PAN_MIN;
    static int  _sweepDir  = 1;  // +1 or -1
    static unsigned long _lastStep = 0;

    // ── Zone table ───────────────────────────────────────────────────────
    // {name, pan_deg, tilt_deg}
    struct ZoneEntry { const char* name; int pan; int tilt; };
    static const ZoneEntry ZONE_TABLE[] = {
        {"Q1",   0, 30},
        {"Q2",  60, 30},
        {"Q3", 120, 30},
        {"Q4", 180, 30},
        // Add/adjust after calibration
    };
    static const int ZONE_COUNT = sizeof(ZONE_TABLE) / sizeof(ZONE_TABLE[0]);
    static int  _zoneIdx   = 0;
    static unsigned long _zoneDwellStart = 0;
    static bool _dwelling  = false;

    inline void begin(uint8_t pinPan, uint8_t pinTilt) {
        _pan.attach(pinPan);
        _tilt.attach(pinTilt);
        _pan.write(SERVO_PAN_MIN);
        _tilt.write(SERVO_TILT_DEFAULT);
    }

    // Returns true while moving (for state reporting)
    inline bool sweep() {
        unsigned long now = millis();
        if (now - _lastStep < SERVO_STEP_DELAY) return true;  // still stepping
        _lastStep = now;

        _panPos += _sweepDir * SERVO_STEP;
        if (_panPos >= SERVO_PAN_MAX) { _panPos = SERVO_PAN_MAX; _sweepDir = -1; }
        if (_panPos <= SERVO_PAN_MIN) { _panPos = SERVO_PAN_MIN; _sweepDir =  1; }

        _pan.write(_panPos);
        _tilt.write(SERVO_TILT_DEFAULT);
        return true;  // always "moving" in sweep mode
    }

    // Step through zone table; returns true while moving/dwelling
    inline bool stepZone() {
        unsigned long now = millis();

        if (!_dwelling) {
            // Move to current zone
            _pan.write(ZONE_TABLE[_zoneIdx].pan);
            _tilt.write(ZONE_TABLE[_zoneIdx].tilt);
            _dwelling        = true;
            _zoneDwellStart  = now;
            return true;  // moving
        }

        if (now - _zoneDwellStart >= ZONE_DWELL_MS) {
            // Dwell complete — advance
            _dwelling = false;
            _zoneIdx  = (_zoneIdx + 1) % ZONE_COUNT;
            return false;  // briefly idle between zones (triggers Pi detect)
        }

        return true;  // still dwelling
    }

    // Move directly to a named zone (e.g. "Q2")
    inline void moveTo(const char* zoneName) {
        for (int i = 0; i < ZONE_COUNT; i++) {
            if (strcmp(ZONE_TABLE[i].name, zoneName) == 0) {
                _pan.write(ZONE_TABLE[i].pan);
                _tilt.write(ZONE_TABLE[i].tilt);
                return;
            }
        }
    }
}
