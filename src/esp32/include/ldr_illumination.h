/*
 * LDR-triggered illumination module driver.
 *
 * Reads the LDR analog value and drives the illumination output
 * (MOSFET gate or direct LED) high/low based on threshold.
 */

#pragma once
#include <Arduino.h>
#include "config.h"

namespace LdrIllumination {

    static uint8_t _pinLdr;
    static uint8_t _pinIllum;
    static bool    _on = false;

    inline void begin(uint8_t pinLdr, uint8_t pinIllum) {
        _pinLdr   = pinLdr;
        _pinIllum = pinIllum;
        pinMode(_pinIllum, OUTPUT);
        digitalWrite(_pinIllum, LOW);
    }

    inline void update() {
        int ldrVal = analogRead(_pinLdr);
        bool shouldBeOn = (ldrVal < LDR_DIM_THRESHOLD);
        if (shouldBeOn != _on) {
            _on = shouldBeOn;
            digitalWrite(_pinIllum, _on ? HIGH : LOW);
        }
    }

    inline bool isOn() { return _on; }
}
