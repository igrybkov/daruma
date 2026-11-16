#include "Loved.h"

namespace Daruma {
    namespace States {
        Loved::Loved() {}

        std::string Loved::getName() const {
            return "Loved";
        }

        void Loved::render(esphome::display::Display* display, float x, float y, float blinkPercentage, esphome::Color eyeColor, esphome::Color backgroundColor) {
            int spacing = this->u(20);
            int size = this->u(60);

            int centerX = this->cx_;
            int centerY = this->cy_;

            int leftX = centerX - spacing - size + x;
            int rightX = centerX + spacing + x;

            ::Daruma::Utilities::Draw::heart(display, leftX, centerY - size / 2 + y, size, esphome::Color(255, 0, 0));
            ::Daruma::Utilities::Draw::heart(display, rightX, centerY - size / 2 + y, size, esphome::Color(255, 0, 0));
        }
    }
}
