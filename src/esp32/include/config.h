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
#define PIN_TILT           21    // PWM output → tilt servo signal
#define PIN_OLED_SDA       16    // I2C SDA → SSD1309 OLED display
#define PIN_OLED_SCL       17    // I2C SCL → SSD1309 OLED display

// ── OLED Display (2.42" SSD1309, 128×64, I2C) ────────────────────────────
// SSD1309 is electrically identical to SSD1306; Adafruit SSD1306 lib works as-is.
#define OLED_I2C_ADDR   0x3C    // Most common address (try 0x3D if blank)
#define OLED_WIDTH       128
#define OLED_HEIGHT       64

// ── LDR Thresholds ─────────────────────────────────────────────────────
// ADC reads 0–4095; lower = darker. Tune once illumination module is built.
#define LDR_DIM_THRESHOLD  1500  // Below this → enable illumination
#define LDR_HYSTERESIS      75   // Dead-band on each side — prevents chattering
                                 // ON  when ldrVal < (LDR_DIM_THRESHOLD + LDR_HYSTERESIS)
                                 // OFF when ldrVal > (LDR_DIM_THRESHOLD - LDR_HYSTERESIS)

// How often to send an illumination-state report to the Pi (ms).
// Set 0 to disable periodic reporting (state changes are always reported).
#define ILLUMINATION_REPORT_INTERVAL_MS  5000

// ── MG90S 360 continuous-rotation servos ────────────────────────────────
// These values are speed commands, not positions.  90 is neutral/stop.
#define SERVO_COMMAND_MIN       0
#define SERVO_COMMAND_MAX     180
#define SERVO_STOP              90
#define SERVO_MIN_US          1000
#define SERVO_MAX_US          2000
#define SERVO_SWEEP_SPEED     155
#define SERVO_ANGLE_SPEED     155    // Continuous-servo command used for angle moves
#define SERVO_MS_PER_DEGREE    12    // Calibrate for the mounted servo speed
#define SERVO_SWEEP_MOVE_MS  1500
#define SERVO_SWEEP_DWELL_MS  800
#define SERVO_ZONE_MOVE_MS    700

// ── Zone Check Dwell ───────────────────────────────────────────────────
#define ZONE_DWELL_MS       800    // ms to hold still for Pi to detect

// ── Main loop delay ────────────────────────────────────────────────────
#define LOOP_DELAY_MS      10
