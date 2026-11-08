/*
 * CLASSCAN — Dual-Axis Servo Controller
 *
 * Actuator Configuration:
 *   - Pan Servo:  TowerPro MG90S 360° Continuous Rotation (Speed/Direction commands)
 *   - Tilt Servo: TowerPro MG90S 180° Positional Servo (Absolute Angle 0°–180°)
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
        int panSpeed;   // Continuous-rotation speed (70 = CCW, 110 = CW)
        int tiltAngle;  // Positional tilt angle (0° to 180°, calibrated 25°–35°)
    };

    // Quadrant positions: pan speeds for timed movement, tilt absolute angles
    // Speeds kept close to neutral (90) to minimise current draw on Pi USB power.
    static const ZoneEntry ZONE_TABLE[] = {
        {"Q1",  75, 35},   // Q1: Pan CCW slow, Tilt 35° downward
        {"Q2", 105, 35},   // Q2: Pan CW  slow, Tilt 35° downward
        {"Q3", 105, 25},   // Q3: Pan CW  slow, Tilt 25° downward
        {"Q4",  75, 25},   // Q4: Pan CCW slow, Tilt 25° downward
    };
    static const int ZONE_COUNT = sizeof(ZONE_TABLE) / sizeof(ZONE_TABLE[0]);
    static int _zoneIdx = 0;
    static unsigned long _zonePhaseStarted = 0;
    static bool _zoneMoving = false;

    // Manual / Angle move state
    static unsigned long _manualStopAt = 0;
    static bool _manualTimed = false;
    static bool _manualMoving = false;

    static int _panAngle = 90;
    static int _tiltAngle = SERVO_TILT_DEFAULT_DEG;
    static int _panStartAngle = 90;
    static int _panTargetAngle = 90;
    static int _tiltTargetAngle = SERVO_TILT_DEFAULT_DEG;
    static unsigned long _angleMoveStarted = 0;
    static unsigned long _panMoveMs = 0;

    // ── Low-Level Servo Writes ─────────────────────────────────────────────

    // Write speed/direction to Pan Servo (MG90S 360° continuous)
    inline void writePanSpeed(int speed) {
        speed = constrain(speed, 0, 180);
        _pan.writeMicroseconds(map(speed, 0, 180, SERVO_PAN_MIN_US, SERVO_PAN_MAX_US));
    }

    // Write absolute angle to Tilt Servo (MG90S 180° positional)
    inline void writeTiltAngle(int angle) {
        angle = constrain(angle, SERVO_TILT_MIN_DEG, SERVO_TILT_MAX_DEG);
        _tilt.writeMicroseconds(map(angle, 0, 180, SERVO_TILT_MIN_US, SERVO_TILT_MAX_US));
        _tiltAngle = angle;
    }

    // Backward-compatible writeCommand (routes by servo)
    inline void writeCommand(Servo& servo, int val) {
        if (&servo == &_pan) {
            writePanSpeed(val);
        } else {
            writeTiltAngle(val);
        }
    }

    // Stop pan rotation (continuous servo); tilt holds its position
    inline void stop() {
        writePanSpeed(SERVO_PAN_STOP);
    }

    // ── Manual Control ─────────────────────────────────────────────────────

    inline void startManual(int panSpeed, int tiltAngle = SERVO_TILT_DEFAULT_DEG, unsigned long durationMs = 0) {
        writePanSpeed(panSpeed);
        writeTiltAngle(tiltAngle);
        _manualTimed = durationMs > 0;
        _manualMoving = (panSpeed != SERVO_PAN_STOP);
        _manualStopAt = millis() + durationMs;
    }

    inline void startAngleMove(int panAngle, int tiltAngle = SERVO_TILT_DEFAULT_DEG, int speedCommand = SERVO_PAN_ANGLE_SPEED) {
        _panTargetAngle = constrain(panAngle, 0, 180);
        _tiltTargetAngle = constrain(tiltAngle, SERVO_TILT_MIN_DEG, SERVO_TILT_MAX_DEG);
        speedCommand = constrain(speedCommand, SERVO_PAN_STOP + 1, 180);

        _panStartAngle = _panAngle;
        _panMoveMs = abs(_panTargetAngle - _panStartAngle) * SERVO_MS_PER_DEGREE;

        // Set Tilt position immediately (standard 180° servo moves directly)
        writeTiltAngle(_tiltTargetAngle);

        // Run Pan servo for timed duration (continuous 360° servo)
        if (_panMoveMs > 0) {
            writePanSpeed(_panTargetAngle > _panStartAngle ? speedCommand : 180 - speedCommand);
        } else {
            writePanSpeed(SERVO_PAN_STOP);
        }

        _angleMoveStarted = millis();
        _manualTimed = (_panMoveMs > 0);
        _manualMoving = _manualTimed;
        _manualStopAt = _angleMoveStarted + _panMoveMs;
    }

    inline bool manual() {
        if (_manualTimed) {
            const unsigned long elapsed = millis() - _angleMoveStarted;
            if (_panMoveMs > 0) {
                const float progress = min(1.0f, static_cast<float>(elapsed) / _panMoveMs);
                _panAngle = _panStartAngle + (_panTargetAngle - _panStartAngle) * progress;
            }
            if (millis() >= _manualStopAt) {
                writePanSpeed(SERVO_PAN_STOP);
                _panAngle = _panTargetAngle;
                _manualTimed = false;
                _manualMoving = false;
                return false;
            }
        }
        return _manualMoving;
    }

    inline void setAngleReference(int panAngle = 90, int tiltAngle = SERVO_TILT_DEFAULT_DEG) {
        _panAngle = constrain(panAngle, 0, 180);
        writeTiltAngle(tiltAngle);
    }

    // ── Initialization ─────────────────────────────────────────────────────

    inline void begin(uint8_t pinPan, uint8_t pinTilt) {
        _pan.setPeriodHertz(50);
        _tilt.setPeriodHertz(50);
        _pan.attach(pinPan, SERVO_PAN_MIN_US, SERVO_PAN_MAX_US);
        _tilt.attach(pinTilt, SERVO_TILT_MIN_US, SERVO_TILT_MAX_US);

        // Write tilt first, stagger 150 ms, then write pan stop.
        // This avoids both servos pulling inrush current simultaneously,
        // which can brown out the ESP32 when powered from Pi USB alone.
        writeTiltAngle(SERVO_TILT_DEFAULT_DEG);
        delay(150);
        writePanSpeed(SERVO_PAN_STOP);

        _phaseStarted = millis();
        _zonePhaseStarted = millis();
    }

    // ── Sweep Mode ─────────────────────────────────────────────────────────

    inline void startSweep() {
        _sweepForward = true;
        _sweepPhase = Phase::MOVING;
        _phaseStarted = millis();
        writeTiltAngle(SERVO_TILT_DEFAULT_DEG);
        writePanSpeed(SERVO_PAN_SWEEP_SPEED);
    }

    inline bool sweep() {
        const unsigned long now = millis();
        const unsigned long phaseLength = (_sweepPhase == Phase::MOVING)
            ? SERVO_SWEEP_MOVE_MS : SERVO_SWEEP_DWELL_MS;

        if (now - _phaseStarted < phaseLength) {
            return (_sweepPhase == Phase::MOVING);
        }

        _phaseStarted = now;
        if (_sweepPhase == Phase::MOVING) {
            writePanSpeed(SERVO_PAN_STOP);
            _sweepPhase = Phase::DWELLING;
            return false;
        }

        _sweepForward = !_sweepForward;
        writePanSpeed(_sweepForward ? SERVO_PAN_SWEEP_SPEED : 180 - SERVO_PAN_SWEEP_SPEED);
        _sweepPhase = Phase::MOVING;
        return true;
    }

    // ── Quadrant / Zone Check Mode ─────────────────────────────────────────

    inline void startZone() {
        _zoneIdx = 0;
        _zoneMoving = true;
        _zonePhaseStarted = millis();
        writePanSpeed(ZONE_TABLE[_zoneIdx].panSpeed);
        writeTiltAngle(ZONE_TABLE[_zoneIdx].tiltAngle);
    }

    inline bool stepZone() {
        const unsigned long now = millis();

        if (_zoneMoving) {
            if (now - _zonePhaseStarted < SERVO_ZONE_MOVE_MS) return true;
            writePanSpeed(SERVO_PAN_STOP);
            _zoneMoving = false;
            _zonePhaseStarted = now;
            return false;
        }

        if (now - _zonePhaseStarted < ZONE_DWELL_MS) return false;

        _zoneIdx = (_zoneIdx + 1) % ZONE_COUNT;
        writePanSpeed(ZONE_TABLE[_zoneIdx].panSpeed);
        writeTiltAngle(ZONE_TABLE[_zoneIdx].tiltAngle);
        _zoneMoving = true;
        _zonePhaseStarted = now;
        return true;
    }

    inline void moveTo(const char* zoneName) {
        for (int i = 0; i < ZONE_COUNT; i++) {
            if (strcmp(ZONE_TABLE[i].name, zoneName) == 0) {
                _zoneIdx = i;
                writePanSpeed(ZONE_TABLE[i].panSpeed);
                writeTiltAngle(ZONE_TABLE[i].tiltAngle);
                _zoneMoving = true;
                _zonePhaseStarted = millis();
                return;
            }
        }
    }
}
