/*
 * CLASSCAN — OLED Display Driver (SSD1309, 2.42", 128×64)
 *
 * Shows the current headcount in a large font centred on the screen,
 * with a "CLASSCAN" header at the top and "students" beneath the count.
 *
 * Supports both:
 *   - Option A (Primary / As-Shipped): 7-Pin SPI Mode (OLED_USE_SPI = 1)
 *   - Option B (Alternative / Modded): 4-Pin I2C Mode (OLED_USE_SPI = 0)
 *
 * Configured in config.h to match hardware/esp32_pinout.md & hardware/wiring_guide.md.
 */

#pragma once
#include <Arduino.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include "config.h"

#if OLED_USE_SPI
#include <SPI.h>
#else
#include <Wire.h>
#endif

namespace OledDisplay {

#if OLED_USE_SPI
    static SPIClass         _spi(HSPI);
    static Adafruit_SSD1306 _display(OLED_WIDTH, OLED_HEIGHT, &_spi,
                                     PIN_OLED_DC, PIN_OLED_RES, PIN_OLED_CS);
#else
    static TwoWire          _i2c(1);
    static Adafruit_SSD1306 _display(OLED_WIDTH, OLED_HEIGHT, &_i2c, -1);
#endif

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
#if OLED_USE_SPI
        // Explicit hardware reset strobe for 7-pin SSD1309 breakout boards
        if (PIN_OLED_RES >= 0) {
            pinMode(PIN_OLED_RES, OUTPUT);
            digitalWrite(PIN_OLED_RES, HIGH);
            delay(10);
            digitalWrite(PIN_OLED_RES, LOW);
            delay(15);
            digitalWrite(PIN_OLED_RES, HIGH);
            delay(20);
        }
        _spi.begin(PIN_OLED_SCK, -1, PIN_OLED_MOSI, PIN_OLED_CS);
        if (!_display.begin(SSD1306_SWITCHCAPVCC, 0, true, false)) {
            Serial.println(F("[OLED] SSD1309 SPI init failed — check wiring / CS / RES"));
            return;
        }
#else
        _i2c.begin(PIN_OLED_SDA, PIN_OLED_SCL, 400000UL);   // 400 kHz fast mode
        if (!_display.begin(SSD1306_SWITCHCAPVCC, OLED_I2C_ADDR, false, false)) {
            Serial.println(F("[OLED] SSD1309 I2C init failed — check wiring / address"));
            return;
        }
#endif

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
