#pragma once

#include <vector>
#include <string>

#include "esphome/core/component.h"
#include "esphome/components/daruma/persona.h"
#include "esphome/components/daruma/sprite.h"

namespace Daruma {

class ImagePersona : public esphome::Component, public Persona {
 public:
  explicit ImagePersona(const std::string &name) : Persona(name) {}

  // Around the picture. Without one, each picture's corner color.
  void set_background(uint8_t r, uint8_t g, uint8_t b) {
    this->background_ = esphome::Color(r, g, b);
    this->has_background_ = true;
  }
  // Pictures in the order the build lists them; behaviors refer to them by
  // that index.
  void add_frames(const Sprite *main, const Sprite *blink, const Sprite *wink) {
    this->frames_.push_back(Frames{main, blink, wink});
  }

  void draw(esphome::display::Display &display, StateId state, float look_y) override;
  void draw_still(esphome::display::Display &display, StateId state) override;
  bool needs_redraw(StateId state) override;
  // A blink or wink repaints only the box where it differs from the picture
  // on screen, not the whole screen.
  bool draw_delta(esphome::display::Display &display, StateId state) override;
  Rect delta_area() const override { return this->delta_; }

  void blink() override;
  void wink() override;

 protected:
  struct Frames {
    const Sprite *main;
    const Sprite *blink;
    const Sprite *wink;
  };

  const Frames &frames_for_(StateId state) const;
  const Sprite *pick_(const Frames &frames);
  void show_(esphome::display::Display &display, const Sprite *image);
  esphome::Color fill_for_(const Sprite *image);
  // Where two pictures of the same size differ, in picture coordinates.
  // Empty (w = 0) when they are the same. Worked out once per pair.
  Rect diff_box_(const Sprite *a, const Sprite *b);

  struct Diff {
    const Sprite *a;
    const Sprite *b;
    Rect box;
  };
  std::vector<Diff> diffs_;

  std::vector<Frames> frames_;
  esphome::Color background_{0, 0, 0};
  bool has_background_{false};
  const Sprite *corner_of_{nullptr};
  esphome::Color corner_;
  uint32_t blink_until_{0};
  uint32_t wink_until_{0};
  const Sprite *drawn_{nullptr};
  Rect delta_;  // What the last draw_delta() repainted.
};

}  // namespace Daruma
