#pragma once

#include <cstdint>

#include "esphome/components/daruma/persona.h"

namespace Daruma {

// The glass of a window in a sprite scene, in native (unscaled) pixels.
struct Pane {
  int x{0};
  int y{0};
  int w{0};
  int h{0};
};

// Animation step of the view for `sky` at `now`. The view only changes when
// the step does, so the persona can skip redraws in between.
uint32_t window_step(Sky sky, uint32_t now);

// Paints the view through the glass into an RGB565 frame `stride` pixels wide.
// Paints every pixel of the pane; the room drawn on top hides the bars.
void paint_window(uint16_t *frame, int stride, const Pane &pane, Sky sky, uint32_t step);

}  // namespace Daruma
