#include "Sleepy.h"

namespace Daruma {
    namespace States {
        Sleepy::Sleepy() {
            this->sleepyAnimator = ::Daruma::Utilities::FloatAnimator();
        }

        std::string Sleepy::getName() const {
            return "Sleepy";
        }

        void Sleepy::render(esphome::display::Display* display, float x, float y, float blinkPercentage, esphome::Color eyeColor, esphome::Color backgroundColor) {
            int spacing = this->u(20);
            int width = this->u(60);
            int height = this->u(60);
            int centerX = this->cx_;
            int centerY = this->cy_;
            int leftX = centerX - spacing - width;
            int rightX = centerX + spacing;

            if (sleepyAnimator.isDone()) {
                sleepyAnimator.startAnimation(0.0f, 5.0f, 5000);
            }
            float animationValue = sleepyAnimator.update();
            float yOffset = 0.0f;
            float heightOffset = 0.0f;

            if (animationValue <= 3.0f) {
                animationValue = animationValue / 3.0f;
                yOffset = this->u(20) * animationValue;
                heightOffset = height * animationValue;
            } else if (animationValue <= 3.05f) {
                animationValue = (animationValue - 3.0f) * 20.0f;
                yOffset = this->u(20) * (1.0f - animationValue);
                heightOffset = height * (1.0f - animationValue);
            }

            ::Daruma::Utilities::Draw::roundedRectangle(display, leftX, centerY - height / 2 + (int)heightOffset + (int)yOffset, width, height - (int)heightOffset, this->u(15), eyeColor);
            ::Daruma::Utilities::Draw::roundedRectangle(display, rightX, centerY - height / 2 + (int)heightOffset + (int)yOffset, width, height - (int)heightOffset, this->u(15), eyeColor);
        }
    }
}
