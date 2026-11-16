#pragma once

// Eyes drawn from shapes. Based on https://github.com/FamousWolf/daruma
// (MIT, see LICENSE): one renderer per mood, plus blink, glance and wink.
// A look is a mood's eyes, shifted and maybe half closed; the build lists
// the looks in __init__.py (LOOKS) in the order of the table in
// eye_reach.h.

#include <vector>
#include <string>

#include "esphome/core/component.h"
#include "esphome/components/daruma/persona.h"
#include "BaseState.h"
#include "FloatAnimator.h"
#include "eye_reach.h"

namespace Daruma {

class EyesPersona : public esphome::Component, public Persona {
 public:
  // A mood's eyes, shifted and maybe half closed; mood indexes states_.
  using Look = Eyes::Look;

  explicit EyesPersona(const std::string &name);

  void draw(esphome::display::Display &display, StateId state, float look_y) override;
  void draw_still(esphome::display::Display &display, StateId state) override;
  bool needs_redraw(StateId state) override;
  // Blinks, glances, winks and moving moods repaint only the box the eyes
  // were and are in, so the screen sends that box instead of every pixel.
  bool draw_delta(esphome::display::Display &display, StateId state) override;
  Rect delta_area() const override { return this->delta_; }

  void blink() override;
  void wink() override;
  void look_around() override;

 protected:
  const Look &look_(StateId state) const;
  esphome::Color eye_color_() const;
  void draw_wink_(esphome::display::Display &display, uint8_t mood, float x, float y);
  // Places a look's eyes above the bottom corners (eye_reach.h) and sets
  // their scale.
  void place_(esphome::display::Display &display, const Look &look);
  // Paints the eyes for a state (no background) and returns their box on
  // screen; empty for a mood without one.
  Rect paint_(esphome::display::Display &display, StateId state, float look_y);
  Rect box_(uint8_t mood, float x, float y) const;
  Rect drawn_box_;  // The eyes' box at the last draw.
  Rect delta_;      // What the last draw_delta() repainted.
  float unit_now_{1.0f};
  int cx_{160};
  int cy_{120};

  std::vector<States::BaseState *> states_;
  Utilities::FloatAnimator blink_animator_;
  Utilities::FloatAnimator move_animator_;
  Utilities::FloatAnimator wink_animator_;
  esphome::Color background_{0, 0, 0};
  int drawn_look_{-1};
  float drawn_look_y_{0.0f};
  uint32_t last_draw_{0};
};

}  // namespace Daruma
