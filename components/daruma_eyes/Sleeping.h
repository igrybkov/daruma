#pragma once
#include "BaseState.h"
#include "esphome/components/daruma/draw.h"
#include "FloatAnimator.h"

namespace Daruma {
    namespace States {
        class Sleeping : public BaseState {
        public:
            Sleeping();

            std::string getName() const override;
            bool isAnimated() const override { return true; }
            void render(
                esphome::display::Display* display,
                float x, float y,
                float blinkPercentage,
                esphome::Color eyeColor,
                esphome::Color backgroundColor
            ) override;
        private:
            ::Daruma::Utilities::FloatAnimator sleepAnimator;
        };
    }
}
