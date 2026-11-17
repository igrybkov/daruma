#include "Scared.h"
#include "esphome/core/hal.h"

namespace Daruma {
namespace States {
Scared::Scared() {}

std::string Scared::getName() const { return "Scared"; }

void Scared::render(esphome::display::Display *display, float x, float y, float blinkPercentage,
                    esphome::Color eyeColor, esphome::Color backgroundColor) {
  int spacing = this->u(35);
  int radius = this->u(10);

  int jitterX = (esphome::millis() % 12) - 6;
  int jitterY = (esphome::millis() % 8) - 4;

  int centerX = this->cx_ + jitterX;
  int centerY = this->cy_ + jitterY;

  int leftX = centerX - spacing - radius + x;
  int rightX = centerX + spacing + radius + x;

  display->filled_circle(leftX, centerY, radius, eyeColor);
  display->filled_circle(rightX, centerY, radius, eyeColor);
}
}  // namespace States
}  // namespace Daruma
