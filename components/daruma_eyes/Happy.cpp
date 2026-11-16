#include "Happy.h"

namespace Daruma {
    namespace States {
        Happy::Happy() {}

        std::string Happy::getName() const {
            return "Happy";
        }

        void Happy::render(esphome::display::Display* display, float x, float y, float blinkPercentage, esphome::Color eyeColor, esphome::Color backgroundColor) {
            int spacing = this->u(20);
            int width = this->u(60);
            int height = this->u(20) * blinkPercentage;
            int centerX = this->cx_;
            int centerY = this->cy_ - this->u(40);

            int leftX = centerX - spacing - width + x;
            int rightX = centerX + spacing + x;

            if (height <= 7) {
                ::Daruma::Utilities::Draw::topHalfOval(display, leftX, centerY - height / 2 + y, width, height, eyeColor);
                ::Daruma::Utilities::Draw::topHalfOval(display, rightX, centerY - height / 2 + y, width, height, eyeColor);
            } else {
                ::Daruma::Utilities::Draw::topHalfDonut(display, leftX, centerY - height / 2 + y, width, height, this->u(7), eyeColor);
                ::Daruma::Utilities::Draw::topHalfDonut(display, rightX, centerY - height / 2 + y, width, height, this->u(7), eyeColor);
            }
        }
    }
}
