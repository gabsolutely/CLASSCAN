/*
 * CLASSCAN — ESP32 pin & timing configuration
 */

#pragma once

// ── Serial ─────────────────────────────────────────────────────────────
#define SERIAL_BAUD        115200

// ── GPIO Pins ──────────────────────────────────────────────────────────
#define PIN_LDR            34    // Analog input (ADC1_CH6)
#define PIN_ILLUMINATION   25    // Digital output → MOSFET gate / LED driver
#define PIN_PAN            18    // PWM output → pan servo signal
#define PIN_TILT           21    // PWM output -> tilt servo signal

// ── LDR Thresholds ─────────────────────────────────────────────────────
// ADC reads 0–4095; lower = darker. Tune once illumination module is built.
#define LDR_DIM_THRESHOLD  1500  // Below this → enable illumination

// ── MG90S 360 continuous-rotation servos ────────────────────────────────
// These values are speed commands, not positions.  90 is neutral/stop.
#define SERVO_COMMAND_MIN       0
#define SERVO_COMMAND_MAX     180
#define SERVO_STOP              90
#define SERVO_MIN_US          1000
#define SERVO_MAX_US          2000
#define SERVO_SWEEP_SPEED     155
#define SERVO_SWEEP_MOVE_MS  1500
#define SERVO_SWEEP_DWELL_MS  800
#define SERVO_ZONE_MOVE_MS    700

// ── Zone Check Dwell ───────────────────────────────────────────────────
#define ZONE_DWELL_MS       800    // ms to hold still for Pi to detect

// ── Main loop delay ────────────────────────────────────────────────────
#define LOOP_DELAY_MS      10
