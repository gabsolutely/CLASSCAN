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
    static unsigned long _manualStopAt = 0;
    static bool _manualTimed = false;
    static bool _manualMoving = false;
    static int _panAngle = 90;
    static int _tiltAngle = 90;
    static int _panStartAngle = 90;
    static int _tiltStartAngle = 90;
    static int _panTargetAngle = 90;
    static int _tiltTargetAngle = 90;
    static unsigned long _angleMoveStarted = 0;
    static unsigned long _panMoveMs = 0;
    static unsigned long _tiltMoveMs = 0;

    inline void writeCommand(Servo& servo, int command) {
        command = constrain(command, SERVO_COMMAND_MIN, SERVO_COMMAND_MAX);
        servo.writeMicroseconds(map(command, SERVO_COMMAND_MIN, SERVO_COMMAND_MAX,
                                    SERVO_MIN_US, SERVO_MAX_US));
    }

    inline void stop() {
        writeCommand(_pan, SERVO_STOP);
        writeCommand(_tilt, SERVO_STOP);
    }

    inline void startManual(int panCommand, int tiltCommand, unsigned long durationMs = 0) {
        writeCommand(_pan, panCommand);
        writeCommand(_tilt, tiltCommand);
        _manualTimed = durationMs > 0;
        _manualMoving = panCommand != SERVO_STOP || tiltCommand != SERVO_STOP;
        _manualStopAt = millis() + durationMs;
    }

    inline void startAngleMove(int panAngle, int tiltAngle, int speedCommand = SERVO_ANGLE_SPEED) {
        _panTargetAngle = constrain(panAngle, 0, 180);
        _tiltTargetAngle = constrain(tiltAngle, 0, 180);
        speedCommand = constrain(speedCommand, SERVO_STOP + 1, SERVO_COMMAND_MAX);

        _panStartAngle = _panAngle;
        _tiltStartAngle = _tiltAngle;
        _panMoveMs = abs(_panTargetAngle - _panStartAngle) * SERVO_MS_PER_DEGREE;
        _tiltMoveMs = abs(_tiltTargetAngle - _tiltStartAngle) * SERVO_MS_PER_DEGREE;

        if (_panMoveMs > 0) {
            writeCommand(_pan, _panTargetAngle > _panStartAngle
                ? speedCommand : SERVO_COMMAND_MAX - speedCommand);
        } else {
            writeCommand(_pan, SERVO_STOP);
        }
        if (_tiltMoveMs > 0) {
            writeCommand(_tilt, _tiltTargetAngle > _tiltStartAngle
                ? speedCommand : SERVO_COMMAND_MAX - speedCommand);
        } else {
            writeCommand(_tilt, SERVO_STOP);
        }

        _angleMoveStarted = millis();
        _manualTimed = _panMoveMs > 0 || _tiltMoveMs > 0;
        _manualMoving = _manualTimed;
        _manualStopAt = _angleMoveStarted + max(_panMoveMs, _tiltMoveMs);
    }

    inline bool manual() {
        if (_manualTimed) {
            const unsigned long elapsed = millis() - _angleMoveStarted;
            if (_panMoveMs > 0) {
                const float progress = min(1.0f, static_cast<float>(elapsed) / _panMoveMs);
                _panAngle = _panStartAngle + (_panTargetAngle - _panStartAngle) * progress;
            }
            if (_tiltMoveMs > 0) {
                const float progress = min(1.0f, static_cast<float>(elapsed) / _tiltMoveMs);
                _tiltAngle = _tiltStartAngle + (_tiltTargetAngle - _tiltStartAngle) * progress;
            }
        }
        if (_manualTimed && millis() >= _manualStopAt) {
            stop();
            _panAngle = _panTargetAngle;
            _tiltAngle = _tiltTargetAngle;
            _manualTimed = false;
            _manualMoving = false;
            return false;
        }
        return _manualMoving;
    }

    inline void setAngleReference(int panAngle = 90, int tiltAngle = 90) {
        _panAngle = constrain(panAngle, 0, 180);
        _tiltAngle = constrain(tiltAngle, 0, 180);
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
