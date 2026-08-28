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
#define PIN_TILT           19    // PWM output → tilt servo signal

// ── LDR Thresholds ─────────────────────────────────────────────────────
// ADC reads 0–4095; lower = darker. Tune once illumination module is built.
#define LDR_DIM_THRESHOLD  1500  // Below this → enable illumination

// ── Servo Sweep ─────────────────────────────────────────────────────────
#define SERVO_PAN_MIN       0    // Degrees
#define SERVO_PAN_MAX     180    // Degrees
#define SERVO_TILT_DEFAULT 30    // Fixed tilt during sweep
#define SERVO_STEP          5    // Degrees per loop iteration
#define SERVO_STEP_DELAY   20    // ms between steps during sweep

// ── Zone Check Dwell ───────────────────────────────────────────────────
#define ZONE_DWELL_MS     800    // ms to hold at each zone position for Pi to detect

// ── Main loop delay ────────────────────────────────────────────────────
#define LOOP_DELAY_MS      10
