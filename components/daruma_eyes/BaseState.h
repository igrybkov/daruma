#pragma once
#include "esphome/components/display/display.h"
#include <cmath>
#include <string>

namespace Daruma {
    namespace States {
        class BaseState {
        public:
            virtual ~BaseState() = default;

            virtual std::string getName() const {
                return "Unknown";
            }

            // True when the state moves on its own and needs periodic redraws.
            virtual bool isAnimated() const {
                return false;
            }

            virtual void render(esphome::display::Display* display, float x, float y, float blinkPercentage, esphome::Color eyeColor, esphome::Color backgroundColor) = 0;

            // Where the eyes sit: the stage's center, and screen pixels per
            // design pixel (sizes are designed for a 240-pixel-high stage).
            void setGeometry(int cx, int cy, float unit) {
                this->cx_ = cx;
                this->cy_ = cy;
                this->unit_ = unit;
            }

        protected:
            int u(float v) const { return (int) std::lround(v * this->unit_); }

            int cx_{160};
            int cy_{120};
            float unit_{1.0f};
        };
    }
}
