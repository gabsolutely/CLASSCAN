/*
 * CLASSCAN — LCD Display Driver (LCD2004, I2C 20×4, PCF8574 backpack)
 *
 * Driver for 20-column × 4-row character LCD with PCF8574 I2C backpack.
 * 4 wires only: VCC (5V), GND, SDA, SCL.
 *
 * Pin assignments (from config.h):
 *   SDA → PIN_LCD_SDA  (GPIO 14)
 *   SCL → PIN_LCD_SCL  (GPIO 27)
 *   VCC → 5V
 *   GND → GND
 *
 * I2C Address: 0x27 default (auto-detects 0x3F for PCF8574A).
 * Library: marcoschwartz/LiquidCrystal_I2C @ ^1.1.4
 *
 * Implementation note:
 *   The driver uses a pointer (_lcdPtr) rather than a static instance so
 *   that the auto-detected I2C address is used to construct the object
 *   exactly once inside begin(). Constructing at namespace scope and later
 *   copy-assigning is unreliable with this library.
 */

#pragma once
#include <Arduino.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include "config.h"

namespace LcdDisplay {

    static LiquidCrystal_I2C* _lcdPtr = nullptr;
    static uint8_t _activeAddr = LCD_I2C_ADDR;

    // State flags to avoid full-screen clears on every update
    static int  _lastCount      = -1;
    static bool _headerWritten  = false;
    static bool _inZoneMode     = false;

    // ── Helpers ────────────────────────────────────────────────────────────

    // Centre a string in a 20-char field; prints to current _lcdPtr.
    inline void _printCentred(const char* str, int row) {
        if (!_lcdPtr) return;
        int len = strlen(str);
        int pad = (20 - len) / 2;
        _lcdPtr->setCursor(0, row);
        for (int i = 0; i < 20; i++) _lcdPtr->print(' ');   // clear row
        _lcdPtr->setCursor(pad < 0 ? 0 : pad, row);
        _lcdPtr->print(str);
    }

    // ── Public API ─────────────────────────────────────────────────────────

    inline void begin() {
        Wire.begin(PIN_LCD_SDA, PIN_LCD_SCL);

        // Auto-detect PCF8574 (0x27) vs PCF8574A (0x3F)
        _activeAddr = LCD_I2C_ADDR;
        Wire.beginTransmission(_activeAddr);
        if (Wire.endTransmission() != 0) {
            Wire.beginTransmission(0x3F);
            if (Wire.endTransmission() == 0) {
                _activeAddr = 0x3F;
            }
        }

        // Construct LCD object with the confirmed address (pointer avoids
        // copy-assignment issues with LiquidCrystal_I2C).
        delete _lcdPtr;
        _lcdPtr = new LiquidCrystal_I2C(_activeAddr, 20, 4);
        _lcdPtr->init();
        _lcdPtr->backlight();

        // Write splash without clear() so servo PWM noise can't corrupt it
        // (clear() causes a ~1.5ms I2C blackout that is bridged by servo noise)
        _printCentred("== CLASSCAN ==", 0);
        _printCentred("",              1);
        _printCentred("Initializing...", 2);
        _printCentred("",              3);

        _headerWritten = false;
        _lastCount     = -1;
        _inZoneMode    = false;
    }

    // ── Sweep mode: show headcount.  Redraws only changed rows. ────────────
    inline void showCount(int count) {
        if (!_lcdPtr) return;

        // If we were in zone mode, force full redraw of the sweep layout
        if (_inZoneMode) {
            _inZoneMode    = false;
            _headerWritten = false;
            _lastCount     = -1;
        }

        // Write static rows once per mode-entry (never use clear())
        if (!_headerWritten) {
            _printCentred("== CLASSCAN ==", 0);
            _printCentred("",              1);   // blank spacer
            _printCentred("students",      3);
            _headerWritten = true;
        }

        // Update count row only when value changed
        if (count != _lastCount) {
            _lastCount = count;
            char countLine[21];
            snprintf(countLine, sizeof(countLine), "Count: %d", count);
            _printCentred(countLine, 2);
        }
    }

    // ── Zone-check mode: show per-quadrant counts + total. ─────────────────
    // Layout (20×4):
    //   Row 0: "CLASSCAN  Total: 42"
    //   Row 1: "Q1:07       Q2:05  "
    //   Row 2: "Q3:03       Q4:04  "
    //   Row 3: "    Zone Check     "
    inline void showZones(int q1, int q2, int q3, int q4, int total, const char* activeZone = nullptr) {
        if (!_lcdPtr) return;

        // If entering zone mode from sweep, invalidate header so row 0 redraws
        if (!_inZoneMode) {
            _inZoneMode    = true;
            _headerWritten = false;
            _lastCount     = -1;
        }

        // Row 0: title + total (always redraw — total updates after each quadrant scan)
        {
            char row0[21];
            snprintf(row0, sizeof(row0), "CLASSCAN  Total:%3d ", total);
            _lcdPtr->setCursor(0, 0);
            _lcdPtr->print(row0);
        }

        // Row 1: Q1 / Q2
        {
            char row1[21];
            snprintf(row1, sizeof(row1), "Q1:%02d       Q2:%02d   ", q1, q2);
            _lcdPtr->setCursor(0, 1);
            _lcdPtr->print(row1);
        }

        // Row 2: Q3 / Q4
        {
            char row2[21];
            snprintf(row2, sizeof(row2), "Q3:%02d       Q4:%02d   ", q3, q4);
            _lcdPtr->setCursor(0, 2);
            _lcdPtr->print(row2);
        }

        // Row 3: status / current quadrant scan
        if (activeZone && strlen(activeZone) > 0) {
            char row3[21];
            snprintf(row3, sizeof(row3), " Scanning: %-9s", activeZone);
            _lcdPtr->setCursor(0, 3);
            _lcdPtr->print(row3);
            _headerWritten = true;
        } else if (!_headerWritten) {
            _printCentred("Zone Accumulator", 3);
            _headerWritten = true;
        }
    }

    // ── Generic status (splash / boot messages) ─────────────────────────────
    inline void showStatus(const char* line2, const char* line3 = nullptr) {
        if (!_lcdPtr) return;
        // Reset state so the next showCount/showZones does a full redraw
        _headerWritten = false;
        _lastCount     = -1;
        _inZoneMode    = false;
        _printCentred("== CLASSCAN ==", 0);
        _printCentred(line2, 1);
        if (line3) _printCentred(line3, 2);
        else       _printCentred("", 2);
        _printCentred("", 3);
    }
}
