/*
 * CLASSCAN — LCD Display Driver (LCD2004, I2C 20×4, PCF8574 backpack)
 *
 * Driver for 20-column × 4-row character LCD with PCF8574 I2C backpack.
 * 4 wires only: VCC (5V), GND, SDA, SCL.
 *
 * Pin assignments (from config.h):
 *   SDA → PIN_LCD_SDA  (GPIO 21)
 *   SCL → PIN_LCD_SCL  (GPIO 22)
 *   VCC → 5V
 *   GND → GND
 *
 * I2C Address: 0x27 default (auto-detects 0x3F for PCF8574A).
 * Library: marcoschwartz/LiquidCrystal_I2C @ ^1.1.4
 */

#pragma once
#include <Arduino.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include "config.h"

namespace LcdDisplay {

    static LiquidCrystal_I2C _lcd(LCD_I2C_ADDR, 20, 4);   // 20 cols, 4 rows
    static uint8_t _activeAddr = LCD_I2C_ADDR;

    // ── Helpers ────────────────────────────────────────────────────────────

    // Centre a string in a 20-char field; returns left-padded string.
    inline void _printCentred(const char* str, int row) {
        int len = strlen(str);
        int pad = (20 - len) / 2;
        _lcd.setCursor(0, row);
        for (int i = 0; i < 20; i++) _lcd.print(' ');   // clear row
        _lcd.setCursor(pad < 0 ? 0 : pad, row);
        _lcd.print(str);
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

        _lcd = LiquidCrystal_I2C(_activeAddr, 20, 4);
        _lcd.init();
        _lcd.backlight();

        _lcd.clear();
        _printCentred("== CLASSCAN ==", 0);
        _printCentred("Initializing...", 2);
    }

    inline void showCount(int count) {
        _lcd.clear();

        // Row 0: header
        _printCentred("== CLASSCAN ==", 0);

        // Row 1: blank spacer
        _lcd.setCursor(0, 1);
        for (int i = 0; i < 20; i++) _lcd.print(' ');

        // Row 2: centered count
        char countLine[21];
        snprintf(countLine, sizeof(countLine), "Count: %d", count);
        _printCentred(countLine, 2);

        // Row 3: "students"
        _printCentred("students", 3);
    }

    inline void showStatus(const char* line2, const char* line3 = nullptr) {
        _lcd.clear();
        _printCentred("== CLASSCAN ==", 0);
        _printCentred(line2, 1);
        if (line3) _printCentred(line3, 2);
    }
}
