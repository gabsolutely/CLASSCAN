/*
 * LED matrix display driver stub.
 *
 * Renders the current headcount on the LED matrix.
 * Replace the body of showCount() with calls to your specific
 * matrix library (MAX7219 / HT16K33 / custom) once hardware is confirmed.
 *
 * Placeholder uses Serial.println for bench-testing without hardware.
 */

#pragma once
#include <Arduino.h>

namespace LedMatrix {

    inline void begin() {
        // TODO: initialise matrix library here (e.g. MD_Parola, Adafruit_LEDBackpack)
        // Example (MAX7219):
        //   display.begin(MD_MAX72XX::FC16_HW, CS_PIN, NUM_DEVICES);
        //   display.setIntensity(5);
        //   display.displayClear();
    }

    inline void showCount(int count) {
        // TODO: replace with actual matrix draw calls
        // Example (MAX7219 / MD_Parola):
        //   display.setTextAlignment(PA_CENTER);
        //   display.print(count);

        // Bench-test fallback:
        Serial.print("[LedMatrix] Displaying count: ");
        Serial.println(count);
    }
}
