/*
 * LDR-triggered illumination module driver.
 *
 * Reads the LDR analog value and drives the illumination output
 * (MOSFET gate or direct LED) high/low based on threshold.
 *
 * Hysteresis:
 *   A dead-band of LDR_HYSTERESIS counts on either side of LDR_DIM_THRESHOLD
 *   prevents rapid on/off chattering when ambient light hovers at the boundary.
 *   Turn ON  threshold : LDR_DIM_THRESHOLD + LDR_HYSTERESIS  (darker)
 *   Turn OFF threshold : LDR_DIM_THRESHOLD - LDR_HYSTERESIS  (brighter)
 *
 * Reporting:
 *   getLdrValue() exposes the last ADC reading so main.cpp can forward the
 *   illumination state to the Pi over serial.
 */

#pragma once
#include <Arduino.h>
#include "config.h"

namespace LdrIllumination {

    static uint8_t _pinLdr;
    static uint8_t _pinIllum;
    static bool    _on    = false;
    static int     _ldrVal = 0;

    inline void begin(uint8_t pinLdr, uint8_t pinIllum) {
        _pinLdr   = pinLdr;
        _pinIllum = pinIllum;
        pinMode(_pinIllum, OUTPUT);
        digitalWrite(_pinIllum, LOW);
    }

    // Returns true if the illumination state changed this call.
    inline bool update() {
        _ldrVal = analogRead(_pinLdr);

        bool shouldBeOn;
        if (_on) {
            // Currently ON: stay on until light rises above (threshold - hysteresis)
            shouldBeOn = (_ldrVal < (LDR_DIM_THRESHOLD - LDR_HYSTERESIS));
        } else {
            // Currently OFF: turn on only when light drops below (threshold + hysteresis)
            shouldBeOn = (_ldrVal < (LDR_DIM_THRESHOLD + LDR_HYSTERESIS));
        }

        if (shouldBeOn != _on) {
            _on = shouldBeOn;
            digitalWrite(_pinIllum, _on ? HIGH : LOW);
            return true;   // state changed
        }
        return false;
    }

    inline bool isOn()      { return _on; }
    inline int  getLdrValue() { return _ldrVal; }
}
