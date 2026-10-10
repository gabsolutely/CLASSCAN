/*
 * CLASSCAN — OLED display driver (SSD1309, 2.42", 128×64, I2C)
 *
 * Shows the current headcount in a large font centred on the screen,
 * with a small "CLASSCAN" label at the top and "students" beneath the count.
 *
 * Hardware:  2.42" SSD1309 OLED module
 *            (electrically identical to SSD1306 — Adafruit SSD1306 lib works as-is)
 * Interface: I2C on GPIO16 (SDA) / GPIO17 (SCL)   ← free pins per pinout doc
 * Libraries: Adafruit SSD1306 + Adafruit GFX (declared in platformio.ini)
 *
 * File renamed conceptually to "display" but kept as led_matrix.h so
 * main.cpp needs no changes.
 */

#pragma once
#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include "config.h"

namespace LedMatrix {

    static Adafruit_SSD1306 _display(OLED_WIDTH, OLED_HEIGHT, nullptr, -1);
    static TwoWire           _i2c    = TwoWire(1);   // I2C bus 1 (bus 0 reserved)

    // ── Helpers ────────────────────────────────────────────────────────────

    // Draw the static chrome that never changes.
    inline void _drawChrome() {
        // Top label: "CLASSCAN"
        _display.setTextSize(1);
        _display.setTextColor(SSD1306_WHITE);
        _display.setCursor(32, 2);
        _display.print(F("CLASSCAN"));

        // Thin separator line under the label
        _display.drawFastHLine(0, 12, OLED_WIDTH, SSD1306_WHITE);

        // Bottom label: "students"
        _display.setTextSize(1);
        _display.setCursor(38, 54);
        _display.print(F("students"));
    }

    // ── Public API ─────────────────────────────────────────────────────────

    inline void begin() {
        _i2c.begin(PIN_OLED_SDA, PIN_OLED_SCL, 400000UL);   // 400 kHz fast mode

        if (!_display.begin(SSD1306_SWITCHCAPVCC, OLED_I2C_ADDR, false, false, _i2c)) {
            // OLED not found — degrade gracefully, Serial fallback still available
            Serial.println(F("[OLED] SSD1306 init failed — check wiring / address"));
            return;
        }

        _display.clearDisplay();
        _display.cp437(true);   // Use CP437 character set
        _drawChrome();
        _display.display();
    }

    inline void showCount(int count) {
        _display.clearDisplay();
        _drawChrome();

        // Large centred count (text size 4 = 24px tall, 14px wide per digit)
        char buf[8];
        snprintf(buf, sizeof(buf), "%d", count);
        const int charW   = 6 * 4;   // 6px base × scale 4
        const int charH   = 8 * 4;
        const int strLen  = (int)strlen(buf);
        const int x       = (OLED_WIDTH  - charW * strLen) / 2;
        const int y       = 14 + (64 - 14 - 10 - charH) / 2;   // vertically centred in body

        _display.setTextSize(4);
        _display.setTextColor(SSD1306_WHITE);
        _display.setCursor(x, y);
        _display.print(buf);

        _display.display();
    }
}
