/*
 * Timed controller for MG90S 360 continuous-rotation servos.
 *
 * These servos accept a speed/direction command rather than an angle. There
 * is no position feedback, so movement is controlled by calibrated timings.
 */

#pragma once

#include <Arduino.h>
#include <ESP32Servo.h>
#include "config.h"

namespace ServoController {

    static Servo _pan;
    static Servo _tilt;

    enum class Phase { MOVING, DWELLING };
    static Phase _sweepPhase = Phase::MOVING;
    static bool _sweepForward = true;
    static unsigned long _phaseStarted = 0;

    struct ZoneEntry {
        const char* name;
        int panCommand;
        int tiltCommand;
    };

    // Commands are speeds/directions, not positions. Calibrate timings after mounting.
    static const ZoneEntry ZONE_TABLE[] = {
        {"Q1",  70, 105},
        {"Q2", 110, 105},
        {"Q3", 110,  75},
        {"Q4",  70,  75},
    };
    static const int ZONE_COUNT = sizeof(ZONE_TABLE) / sizeof(ZONE_TABLE[0]);
    static int _zoneIdx = 0;
    static unsigned long _zonePhaseStarted = 0;
    static bool _zoneMoving = false;

    inline void writeCommand(Servo& servo, int command) {
        command = constrain(command, SERVO_COMMAND_MIN, SERVO_COMMAND_MAX);
        servo.writeMicroseconds(map(command, SERVO_COMMAND_MIN, SERVO_COMMAND_MAX,
                                    SERVO_MIN_US, SERVO_MAX_US));
    }

    inline void stop() {
        writeCommand(_pan, SERVO_STOP);
        writeCommand(_tilt, SERVO_STOP);
    }

    inline void begin(uint8_t pinPan, uint8_t pinTilt) {
        _pan.setPeriodHertz(50);
        _tilt.setPeriodHertz(50);
        _pan.attach(pinPan, SERVO_MIN_US, SERVO_MAX_US);
        _tilt.attach(pinTilt, SERVO_MIN_US, SERVO_MAX_US);
        writeCommand(_pan, SERVO_SWEEP_SPEED);
        writeCommand(_tilt, SERVO_STOP);
        _phaseStarted = millis();
        _zonePhaseStarted = millis();
    }

    inline void startSweep() {
        _sweepForward = true;
        _sweepPhase = Phase::MOVING;
        _phaseStarted = millis();
        writeCommand(_pan, SERVO_SWEEP_SPEED);
        writeCommand(_tilt, SERVO_STOP);
    }

    inline void startZone() {
        _zoneIdx = 0;
        _zoneMoving = true;
        _zonePhaseStarted = millis();
        writeCommand(_pan, ZONE_TABLE[_zoneIdx].panCommand);
        writeCommand(_tilt, ZONE_TABLE[_zoneIdx].tiltCommand);
    }

    inline bool sweep() {
        const unsigned long now = millis();
        const unsigned long phaseLength = _sweepPhase == Phase::MOVING
            ? SERVO_SWEEP_MOVE_MS : SERVO_SWEEP_DWELL_MS;

        if (now - _phaseStarted < phaseLength) {
            return _sweepPhase == Phase::MOVING;
        }

        _phaseStarted = now;
        if (_sweepPhase == Phase::MOVING) {
            stop();
            _sweepPhase = Phase::DWELLING;
            return false;
        }

        _sweepForward = !_sweepForward;
        writeCommand(_pan, _sweepForward ? SERVO_SWEEP_SPEED
                          : SERVO_COMMAND_MAX - SERVO_SWEEP_SPEED);
        _sweepPhase = Phase::MOVING;
        return true;
    }

    inline bool stepZone() {
        const unsigned long now = millis();

        if (_zoneMoving) {
            if (now - _zonePhaseStarted < SERVO_ZONE_MOVE_MS) return true;
            stop();
            _zoneMoving = false;
            _zonePhaseStarted = now;
            return false;
        }

        if (now - _zonePhaseStarted < ZONE_DWELL_MS) return false;

        _zoneIdx = (_zoneIdx + 1) % ZONE_COUNT;
        writeCommand(_pan, ZONE_TABLE[_zoneIdx].panCommand);
        writeCommand(_tilt, ZONE_TABLE[_zoneIdx].tiltCommand);
        _zoneMoving = true;
        _zonePhaseStarted = now;
        return true;
    }

    inline void moveTo(const char* zoneName) {
        for (int i = 0; i < ZONE_COUNT; i++) {
            if (strcmp(ZONE_TABLE[i].name, zoneName) == 0) {
                _zoneIdx = i;
                writeCommand(_pan, ZONE_TABLE[i].panCommand);
                writeCommand(_tilt, ZONE_TABLE[i].tiltCommand);
                _zoneMoving = true;
                _zonePhaseStarted = millis();
                return;
            }
        }
    }
}
