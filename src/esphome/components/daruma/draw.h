#pragma once
#include <algorithm>
#include <cmath>
#include "esphome/components/display/display.h"

namespace Daruma {
namespace Utilities {
class Draw {
 public:
  static void roundedRectangle(esphome::display::Display *display, float x, float y, float width, float height,
                               float cornerRadius, esphome::Color color);
  static void roundedRectangleWithOverlayTriangle(esphome::display::Display *display, float x, float y, float width,
                                                  float height, float cornerRadius, esphome::Color baseColor,
                                                  esphome::Color overlayColor, float targetX, float targetY,
                                                  bool fromRight = false);

  static void heart(esphome::display::Display *display, float x, float y, float size, esphome::Color color);

  static void topHalfOval(esphome::display::Display *display, float x, float y, float width, float height,
                          esphome::Color color);

  static void topHalfDonut(esphome::display::Display *display, float x, float y, float width, float height,
                           float thickness, esphome::Color color);

  // Filled five-point star centered on (x, y), point up.
  static void star(esphome::display::Display *display, int x, int y, int outerRadius, int innerRadius,
                   esphome::Color color);

  // Small tomato centered on (x, y). Body is 2r wide, 1.5r tall,
  // with a stem and leaves on top. shine adds a light highlight.
  static void tomato(esphome::display::Display *display, int x, int y, int r, esphome::Color bodyColor,
                     esphome::Color leafColor, bool shine);
};
}  // namespace Utilities
}  // namespace Daruma
