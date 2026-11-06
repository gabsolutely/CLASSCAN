/*
 * CLASSCAN — ESP32 pin & timing configuration
 *
 * Actuators & Sensors:
 *   - Pan Servo:  MG90S 360° Continuous-Rotation Servo (Speed/Direction commands)
 *   - Tilt Servo: MG90S 180° Standard Positional Servo (Absolute Angle in degrees)
 *   - Display:    LCD2004 20×4 Character LCD with PCF8574 I2C Backpack (0x27 / 0x3F)
 *   - Sensor:     LDR Ambient Light Sensor (GL5528) + IRLZ44N LED Strip Driver
 */

#pragma once

// ── Serial ─────────────────────────────────────────────────────────────
#define SERIAL_BAUD        115200

// ── GPIO Pins ──────────────────────────────────────────────────────────
#define PIN_LDR            34    // Analog input (ADC1_CH6) from GL5528 + 10k pull-down divider
#define PIN_ILLUMINATION   25    // Digital output → IRLZ44N logic-level MOSFET gate (5V white LED strip, <=500mA draw)
#define PIN_PAN            18    // PWM output → Pan Servo signal (MG90S 360° continuous)
#define PIN_TILT           13    // PWM output → Tilt Servo signal (MG90S 180° positional)
                                 // NOTE: remapped from GPIO21 to free GPIO21 for LCD SDA

// ── LCD Display (LCD2004, I2C 20×4, PCF8574 backpack) ──────────────────────
// Standard blue-backlight character LCD with soldered PCF8574 I2C backpack.
// 4 wires only: VCC (5V), GND, SDA, SCL.
// Default PCF8574 address is 0x27 (auto-fallbacks to 0x3F if 0x27 does not respond).
#define PIN_LCD_SDA        21    // I2C Bus 1 SDA
#define PIN_LCD_SCL        22    // I2C Bus 1 SCL
#define LCD_I2C_ADDR     0x27   // PCF8574 default (0x3F for PCF8574A)

// ── LDR Thresholds ─────────────────────────────────────────────────────
// ADC reads 0–4095; lower = darker.
#define LDR_DIM_THRESHOLD  1500  // Mid-point ambient threshold
#define LDR_HYSTERESIS      75   // Dead-band on each side — prevents chattering

// How often to send an illumination-state report to the Pi (ms).
#define ILLUMINATION_REPORT_INTERVAL_MS  5000

// ── Pan Servo (MG90S 360° Continuous Rotation) ──────────────────────────
// Commands are speed/direction: 90 is neutral stop, >90 forward/CW, <90 reverse/CCW.
#define SERVO_PAN_STOP          90
#define SERVO_PAN_MIN_US      1000
#define SERVO_PAN_MAX_US      2000
#define SERVO_PAN_SWEEP_SPEED  155    // Forward sweep speed
#define SERVO_PAN_ANGLE_SPEED  155    // Continuous-servo speed for timed angle moves
#define SERVO_MS_PER_DEGREE     12    // Calibrated ms per degree for pan rotation
#define SERVO_SWEEP_MOVE_MS   1500    // Panning duration per sweep stroke
#define SERVO_SWEEP_DWELL_MS   800    // Pause at ends of sweep
#define SERVO_ZONE_MOVE_MS     700    // Panning duration to reach next quadrant

// ── Tilt Servo (MG90S 180° Positional Standard Servo) ───────────────────
// Commands are absolute angles in degrees: 0° to 180°.
// 30° is calibrated downward pitch for classroom ceiling mount.
#define SERVO_TILT_DEFAULT_DEG  30    // Default downward pitch (30° from horizontal)
#define SERVO_TILT_MIN_DEG       0
#define SERVO_TILT_MAX_DEG     180
#define SERVO_TILT_MIN_US      500    // MG90S 180° pulse range: 500 μs = 0°
#define SERVO_TILT_MAX_US     2400    // 2400 μs = 180°

// ── Backward Compatibility Aliases ─────────────────────────────────────
#define SERVO_COMMAND_MIN        0
#define SERVO_COMMAND_MAX      180
#define SERVO_STOP              SERVO_PAN_STOP
#define SERVO_MIN_US          SERVO_PAN_MIN_US
#define SERVO_MAX_US          SERVO_PAN_MAX_US
#define SERVO_SWEEP_SPEED      SERVO_PAN_SWEEP_SPEED
#define SERVO_ANGLE_SPEED      SERVO_PAN_ANGLE_SPEED

// ── Zone Check Dwell ───────────────────────────────────────────────────
#define ZONE_DWELL_MS          800    // ms to hold still for Pi to capture frame

// ── Main loop delay ────────────────────────────────────────────────────
#define LOOP_DELAY_MS           10
