/*
 * CLASSCAN — ESP32 Firmware
 * main.cpp (PlatformIO / Arduino Framework)
 *
 * Responsibilities:
 *   - Read LDR and toggle illumination module
 *   - Drive pan/tilt servos (SWEEP or ZONE_CHECK mode)
 *   - Drive LED matrix display with current headcount
 *   - Receive commands from Pi 3B over USB serial (JSON, newline-delimited)
 *   - Report state ("idle" | "moving") back over serial
 *
 * Protocol (same as serial_bridge.py):
 *   Inbound  (Pi → ESP32):
 *     {"type": "count",   "value": <int>}
 *     {"type": "command", "value": "<cmd>"}
 *
 *   Outbound (ESP32 → Pi):
 *     {"type": "state", "value": "idle"}
 *     {"type": "state", "value": "moving"}
 */

#include <Arduino.h>
#include <ArduinoJson.h>
#include <ESP32Servo.h>

#include "config.h"
#include "ldr_illumination.h"
#include "servo_controller.h"
#include "led_matrix.h"

// ── State ─────────────────────────────────────────────────────────────────
enum class Mode { SWEEP, ZONE_CHECK };

Mode    currentMode   = Mode::SWEEP;
int     headcount     = 0;
bool    servoMoving   = false;

// ── Serial helpers ────────────────────────────────────────────────────────
void reportState(const char* state) {
    StaticJsonDocument<64> doc;
    doc["type"]  = "state";
    doc["value"] = state;
    serializeJson(doc, Serial);
    Serial.println();
}

void handleIncoming(const String& line) {
    StaticJsonDocument<128> doc;
    DeserializationError err = deserializeJson(doc, line);
    if (err) return;

    const char* type = doc["type"];
    if (!type) return;

    if (strcmp(type, "count") == 0) {
        headcount = doc["value"].as<int>();
        LedMatrix::showCount(headcount);

    } else if (strcmp(type, "command") == 0) {
        const char* cmd = doc["value"];
        if (!cmd) return;

        if (strcmp(cmd, "MODE_SWEEP") == 0) {
            currentMode = Mode::SWEEP;
            ServoController::startSweep();
        } else if (strcmp(cmd, "MODE_ZONE") == 0) {
            currentMode = Mode::ZONE_CHECK;
            ServoController::startZone();
        } else if (strncmp(cmd, "ZONE_", 5) == 0) {
            // e.g. "ZONE_Q1" → move to quadrant Q1
            ServoController::moveTo(cmd + 5);  // pass zone name
        }
    }
}

// ── Setup ─────────────────────────────────────────────────────────────────
void setup() {
    Serial.begin(SERIAL_BAUD);
    while (!Serial) delay(10);

    LdrIllumination::begin(PIN_LDR, PIN_ILLUMINATION);
    ServoController::begin(PIN_PAN, PIN_TILT);
    LedMatrix::begin();

    reportState("idle");
}

// ── Main loop ─────────────────────────────────────────────────────────────
void loop() {
    // 1. LDR → illumination
    LdrIllumination::update();

    // 2. Servo sweep / zone-check
    bool wasMoving = servoMoving;
    if (currentMode == Mode::SWEEP) {
        servoMoving = ServoController::sweep();
    } else {
        servoMoving = ServoController::stepZone();
    }
    if (wasMoving != servoMoving) {
        reportState(servoMoving ? "moving" : "idle");
    }

    // 3. Read serial command from Pi 3B
    if (Serial.available()) {
        String line = Serial.readStringUntil('\n');
        line.trim();
        if (line.length() > 0) {
            handleIncoming(line);
        }
    }

    delay(LOOP_DELAY_MS);
}
