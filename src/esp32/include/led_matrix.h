/*
 * CLASSCAN — Display Driver Wrapper / Backward Compatibility
 *
 * Forwards to oled_display.h (SSD1309 OLED display driver).
 * Kept so existing main.cpp and references continue to work seamlessly.
 */

#pragma once
#include "oled_display.h"

namespace LedMatrix = OledDisplay;
