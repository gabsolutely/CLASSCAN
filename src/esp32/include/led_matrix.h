/*
 * CLASSCAN — Display Driver Wrapper / Backward Compatibility
 *
 * Forwards to lcd_display.h (LCD2004 I2C 20×4 character LCD driver).
 * Kept so existing main.cpp and references continue to work seamlessly.
 * (Previously forwarded to oled_display.h — SSD1309 OLED — now replaced.)
 */

#pragma once
#include "lcd_display.h"

namespace LedMatrix = LcdDisplay;
