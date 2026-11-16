#pragma once
#include "BaseState.h"
#include "esphome/components/daruma/draw.h"

namespace Daruma {
    namespace States {
        class Loved : public BaseState {
        public:
            Loved();

            std::string getName() const override;
            void render(
                esphome::display::Display* display,
                float x, float y,
                float blinkPercentage,
                esphome::Color eyeColor,
                esphome::Color backgroundColor
            ) override;
        };
    }
}
