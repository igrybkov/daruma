#include "Sleeping.h"

namespace Daruma {
    namespace States {
        Sleeping::Sleeping() {
            this->sleepAnimator = ::Daruma::Utilities::FloatAnimator();
        }

        std::string Sleeping::getName() const {
            return "Sleeping";
        }

        void Sleeping::render(esphome::display::Display* display, float x, float y, float blinkPercentage, esphome::Color eyeColor, esphome::Color backgroundColor) {
            int spacing = this->u(20);
            int width = this->u(60);
            int height = this->u(3);
            int centerX = this->cx_;
            int centerY = this->cy_;
            int leftX = centerX - spacing - width;
            int rightX = centerX + spacing;

            if (sleepAnimator.isDone()) {
                sleepAnimator.startAnimation(0.0f, 2.0f, 3000);
            }
            float animationValue = sleepAnimator.update();
            float yOffset = (float) this->u(20);
            if (animationValue <= 1.0f) {
                yOffset += sleepAnimator.calculateV(animationValue) * this->u(5);
            } else {
                yOffset += this->u(5);
            }

            display->filled_rectangle(leftX, centerY - height / 2 + yOffset, width, height, eyeColor);
            display->filled_rectangle(rightX, centerY - height / 2 + yOffset, width, height, eyeColor);
        }
    }
}
