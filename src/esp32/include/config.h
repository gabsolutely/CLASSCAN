/*
 * CLASSCAN — ESP32 pin & timing configuration
 */

#pragma once

// ── Serial ─────────────────────────────────────────────────────────────
#define SERIAL_BAUD        115200

// ── GPIO Pins ──────────────────────────────────────────────────────────
#define PIN_LDR            34    // Analog input (ADC1_CH6) from GL5528 + 10k pull-down divider
#define PIN_ILLUMINATION   25    // Digital output → IRLZ44N logic-level MOSFET gate (5V white LED strip, <=500mA draw)
#define PIN_PAN            18    // PWM output → pan servo signal (MG90S metal-gear)
#define PIN_TILT           13    // PWM output → tilt servo signal (MG90S metal-gear)
                                 // NOTE: moved from GPIO21 to free it for LCD SDA
// ── LCD Display (LCD2004, I2C 20×4, PCF8574 backpack) ──────────────────────
// Standard blue-backlight character LCD with soldered PCF8574 I2C backpack.
// 4 wires only: VCC (5V), GND, SDA, SCL.
// Default PCF8574 address is 0x27; try 0x3F if the display stays blank.
#define PIN_LCD_SDA        21    // I2C Bus 1 SDA
#define PIN_LCD_SCL        22    // I2C Bus 1 SCL
#define LCD_I2C_ADDR     0x27   // PCF8574 default (try 0x3F if blank)

// ── LDR Thresholds ─────────────────────────────────────────────────────
// ADC reads 0–4095; lower = darker. Tune once illumination module is built.
#define LDR_DIM_THRESHOLD  1500  // Mid-point ambient threshold
#define LDR_HYSTERESIS      75   // Dead-band on each side — prevents chattering
                                 // Turn ON  when ldrVal < (LDR_DIM_THRESHOLD - LDR_HYSTERESIS)  (darker)
                                 // Turn OFF when ldrVal > (LDR_DIM_THRESHOLD + LDR_HYSTERESIS)  (brighter)

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
