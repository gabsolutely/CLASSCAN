/*
 * CLASSCAN — ESP32 Firmware
 * main.cpp (PlatformIO / Arduino Framework)
 *
 * Responsibilities:
 *   - Read LDR and toggle illumination module (with hysteresis — see ldr_illumination.h)
 *   - Drive pan servo (MG90S 360° continuous) and tilt servo (MG90S 180° positional)
 *   - Drive LCD2004 (I2C 20×4) with current headcount via led_matrix.h / lcd_display.h
 *   - Receive commands from Pi 3B over USB serial (JSON, newline-delimited)
 *   - Report state ("idle" | "moving") back over serial
 *   - Report illumination state changes + periodic LDR value over serial
 *
 * ── Inbound protocol (Pi → ESP32): ─────────────────────────────────────────
 *   {"type": "count",   "value": <int>}
 *   {"type": "command", "value": "<cmd>"}
 *       Commands: MODE_SWEEP | MODE_ZONE | MODE_MANUAL |
 *                 STOP_SERVOS | SET_CENTER |
 *                 ZONE_Q1 | ZONE_Q2 | ZONE_Q3 | ZONE_Q4
 *   {"type": "servo",   "pan": <0-180 speed>, "tilt": <0-180 deg>, "duration_ms": <optional>}
 *   {"type": "servo",   "pan_angle": <0-180 deg>, "tilt_angle": <0-180 deg>, "speed": <91-180>}
 *   {"type": "zones",   "Q1": <int>, "Q2": <int>, "Q3": <int>, "Q4": <int>, "total": <int>}
 *
 * ── Outbound protocol (ESP32 → Pi): ─────────────────────────────────────────
 *   {"type": "state",   "value": "idle" | "moving"}
 *   {"type": "ldr",     "value": <adc 0-4095>, "illumination": true | false}
 *   {"type": "pan_pos", "pct": <0-100>, "moving": <bool>}   // SWEEP mode only, every 500 ms
 */

#include <Arduino.h>
#include <ArduinoJson.h>
#include <ESP32Servo.h>

#include "config.h"
#include "ldr_illumination.h"
#include "servo_controller.h"
#include "led_matrix.h"

// ── State ──────────────────────────────────────────────────────────────────
enum class Mode { SWEEP, ZONE_CHECK, MANUAL };

Mode    currentMode  = Mode::SWEEP;
int     headcount    = 0;
bool    servoMoving  = false;

unsigned long _lastIllumReport = 0;   // millis() of last periodic LDR report
unsigned long _lastPanReport   = 0;   // millis() of last pan_pos broadcast

// ── Serial helpers ──────────────────────────────────────────────────────────

void reportState(const char* state) {
    StaticJsonDocument<64> doc;
    doc["type"]  = "state";
    doc["value"] = state;
    serializeJson(doc, Serial);
    Serial.println();
}

/**
 * Send illumination status to Pi.
 *   {"type": "ldr", "value": <adc>, "illumination": <bool>}
 */
void reportIllumination() {
    StaticJsonDocument<96> doc;
    doc["type"]          = "ldr";
    doc["value"]         = LdrIllumination::getLdrValue();
    doc["illumination"]  = LdrIllumination::isOn();
    serializeJson(doc, Serial);
    Serial.println();
}

void handleIncoming(const String& line) {
    StaticJsonDocument<256> doc;
    DeserializationError err = deserializeJson(doc, line);
    if (err) return;

    const char* type = doc["type"];
    if (!type) return;

    // ── count ──────────────────────────────────────────────────────────────
    if (strcmp(type, "count") == 0) {
        headcount = doc["value"].as<int>();
        LedMatrix::showCount(headcount);

    // ── zones (per-quadrant counts in ZONE_CHECK mode) ─────────────────────
    } else if (strcmp(type, "zones") == 0) {
        int q1    = doc["Q1"]    | 0;
        int q2    = doc["Q2"]    | 0;
        int q3    = doc["Q3"]    | 0;
        int q4    = doc["Q4"]    | 0;
        int total = doc["total"] | 0;
        LedMatrix::showZones(q1, q2, q3, q4, total);

    // ── servo (pan 360 speed, tilt 180 angle) ──────────────────────────────
    } else if (strcmp(type, "servo") == 0) {
        currentMode = Mode::MANUAL;
        if (doc.containsKey("pan_angle") || doc.containsKey("tilt_angle")) {
            // Angle-move: pan uses timed rotation, tilt sets absolute angle (180 servo)
            const int panAngle  = doc["pan_angle"]  | 90;
            const int tiltAngle = doc["tilt_angle"] | SERVO_TILT_DEFAULT_DEG;
            const int speed     = doc["speed"]      | SERVO_PAN_ANGLE_SPEED;
            ServoController::startAngleMove(panAngle, tiltAngle, speed);
            reportState("moving");
        } else {
            // Raw command: pan speed (0-180), tilt angle (0-180)
            const int          pan        = doc["pan"]         | SERVO_PAN_STOP;
            const int          tilt       = doc["tilt"]        | SERVO_TILT_DEFAULT_DEG;
            const unsigned long durationMs = doc["duration_ms"] | 0UL;
            ServoController::startManual(pan, tilt, durationMs);
            reportState(pan != SERVO_PAN_STOP ? "moving" : "idle");
        }

    // ── command ────────────────────────────────────────────────────────────
    } else if (strcmp(type, "command") == 0) {
        const char* cmd = doc["value"];
        if (!cmd) return;

        if (strcmp(cmd, "MODE_SWEEP") == 0) {
            currentMode = Mode::SWEEP;
            ServoController::startSweep();

        } else if (strcmp(cmd, "MODE_ZONE") == 0) {
            currentMode = Mode::ZONE_CHECK;
            ServoController::startZone();

        } else if (strcmp(cmd, "MODE_MANUAL") == 0) {
            currentMode = Mode::MANUAL;
            ServoController::stop();
            reportState("idle");

        } else if (strcmp(cmd, "STOP_SERVOS") == 0) {
            currentMode = Mode::MANUAL;
            ServoController::stop();
            reportState("idle");

        } else if (strcmp(cmd, "SET_CENTER") == 0) {
            currentMode = Mode::MANUAL;
            ServoController::startManual(SERVO_PAN_STOP, SERVO_TILT_DEFAULT_DEG);
            ServoController::setAngleReference(90, SERVO_TILT_DEFAULT_DEG);
            reportState("idle");

        } else if (strncmp(cmd, "ZONE_", 5) == 0) {
            // e.g. "ZONE_Q1" → move servo to quadrant Q1
            ServoController::moveTo(cmd + 5);   // pass zone name past the "ZONE_" prefix
        }
    }
}

// ── Setup ──────────────────────────────────────────────────────────────────
void setup() {
    Serial.begin(SERIAL_BAUD);
    while (!Serial) delay(10);

    LdrIllumination::begin(PIN_LDR, PIN_ILLUMINATION);
    ServoController::begin(PIN_PAN, PIN_TILT);
    LedMatrix::begin();   // init I2C + LCD; prints "== CLASSCAN ==" splash

    // Debug: report active LCD I2C address so Pi can confirm it over serial
    {
        StaticJsonDocument<96> dbg;
        dbg["type"]  = "debug";
        dbg["msg"]   = "boot";
        dbg["lcd"]   = LcdDisplay::_activeAddr;
        dbg["pan"]   = PIN_PAN;
        dbg["tilt"]  = PIN_TILT;
        serializeJson(dbg, Serial);
        Serial.println();
    }

    reportState("idle");
    reportIllumination();   // send initial LDR reading to Pi
}

// ── Main loop ──────────────────────────────────────────────────────────────
void loop() {
    // 1. LDR → illumination (returns true if state changed)
    bool illumChanged = LdrIllumination::update();
    if (illumChanged) {
        reportIllumination();   // immediate notification on state change
    } else if (ILLUMINATION_REPORT_INTERVAL_MS > 0) {
        // Periodic heartbeat so Pi knows LDR is still alive
        unsigned long now = millis();
        if (now - _lastIllumReport >= ILLUMINATION_REPORT_INTERVAL_MS) {
            _lastIllumReport = now;
            reportIllumination();
        }
    }

    // 2. Servo sweep / zone-check / manual
    bool wasMoving = servoMoving;
    if (currentMode == Mode::SWEEP) {
        servoMoving = ServoController::sweep();
    } else if (currentMode == Mode::ZONE_CHECK) {
        servoMoving = ServoController::stepZone();
    } else {
        servoMoving = ServoController::manual();
    }
    if (wasMoving != servoMoving) {
        reportState(servoMoving ? "moving" : "idle");
    }

    // 2a. Pan position dead-reckoning broadcast (SWEEP mode, every 500 ms)
    if (currentMode == Mode::SWEEP) {
        unsigned long now = millis();
        if (now - _lastPanReport >= 500) {
            _lastPanReport = now;
            StaticJsonDocument<96> pdoc;
            pdoc["type"]   = "pan_pos";
            pdoc["pct"]    = static_cast<int>(ServoController::getPanProgressPct());
            pdoc["moving"] = servoMoving;
            serializeJson(pdoc, Serial);
            Serial.println();
        }
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
