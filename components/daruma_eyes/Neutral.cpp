#include "Neutral.h"

namespace Daruma {
    namespace States {
        Neutral::Neutral() {}

        std::string Neutral::getName() const {
            return "Neutral";
        }

        void Neutral::render(esphome::display::Display* display, float x, float y, float blinkPercentage, esphome::Color eyeColor, esphome::Color backgroundColor) {
            int spacing = this->u(20);
            int width = this->u(60);
            int height = this->u(80) * blinkPercentage;
            int centerX = this->cx_;
            int centerY = this->cy_;

            int leftX = centerX - spacing - width + (int)x;
            int rightX = centerX + spacing + (int)x;

            ::Daruma::Utilities::Draw::roundedRectangle(display, leftX, centerY - height / 2 + (int)y, width, height, this->u(15), eyeColor);
            ::Daruma::Utilities::Draw::roundedRectangle(display, rightX, centerY - height / 2 + (int)y, width, height, this->u(15), eyeColor);
        }
    }
}
