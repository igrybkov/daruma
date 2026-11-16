#include "Sad.h"

namespace Daruma {
    namespace States {
        Sad::Sad() {}

        std::string Sad::getName() const {
            return "Sad";
        }

        void Sad::render(esphome::display::Display* display, float x, float y, float blinkPercentage, esphome::Color eyeColor, esphome::Color backgroundColor) {
            int spacing = this->u(20);
            int width = this->u(60);
            int height = this->u(60) * blinkPercentage;
            int centerX = this->cx_;
            int centerY = this->cy_ + this->u(40);

            int leftX = centerX - spacing - width + x;
            int rightX = centerX + spacing + x;

            ::Daruma::Utilities::Draw::roundedRectangleWithOverlayTriangle(display, leftX, centerY - height / 2 + y, width, height, this->u(15),
                                                    eyeColor, backgroundColor, leftX, centerY + y, true);
            ::Daruma::Utilities::Draw::roundedRectangleWithOverlayTriangle(display, rightX, centerY - height / 2 + y, width, height, this->u(15),
                                                    eyeColor, backgroundColor, rightX + width, centerY + y, false);
        }
    }
}
