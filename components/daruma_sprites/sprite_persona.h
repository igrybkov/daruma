#pragma once

#include <string>
#include <vector>

#include "esphome/core/component.h"
#include "esphome/core/helpers.h"
#include "esphome/components/daruma/persona.h"
#include "esphome/components/daruma/frame_chain.h"
#include "esphome/components/daruma/sprite.h"
#include "window.h"

namespace Daruma {

// Two ways to draw:
// - Flat: each frame is the whole scene.
// - Layered (a backdrop is set): every frame is put together in a buffer,
//   back to front: the window view (if any), the backdrop (the room, with a
//   see-through hole where the glass is), then the persona frame at a fixed
//   offset. Only pixels that changed since the last frame go to the screen.
//
// Frames are stored as keyframes and patches (frame_chain.h). A layered persona
// keeps the persona in a canvas: playing frames in order applies one small
// patch each, and only that box is composed and sent to the screen.
//
// The scene takes the largest whole-number scale that fits the stage. On a
// stage of another shape, a layered room fills the rest from its edge
// strips (daruma_sprites/extend.py): the wall goes on sideways and upward,
// the floor sideways. The room sits on the bottom of the stage, centered.
// Without strips, the rest is the background color.
class SpritePersona : public esphome::Component, public Persona {
 public:
  explicit SpritePersona(const std::string &name) : Persona(name) {}

  // The largest scale to use (0: no limit).
  void set_scale(int scale) { this->max_scale_ = scale; }
  void set_background(uint8_t r, uint8_t g, uint8_t b) { this->background_ = esphome::Color(r, g, b); }
  // The stored frames, in order: a whole picture (base -1), or a patch at
  // (x, y) on an earlier one. Animations refer to them by that index.
  void add_image(const Sprite *image, int base, int x, int y) {
    this->frames_.push_back(FrameRef{image, (int16_t) base, (int16_t) x, (int16_t) y});
  }
  // The build emits the frames, animation names and steps as constant
  // tables, so setup() runs one call per table instead of one per entry.
  struct FrameStep {
    uint16_t anim;
    int16_t frame;
    uint32_t ms;
  };
  void add_image_table(const FrameRef *table, size_t n) { this->frames_.insert(this->frames_.end(), table, table + n); }
  void add_animation_table(const char *const *names, size_t n) {
    for (size_t i = 0; i < n; i++)
      this->add_animation(names[i]);
  }
  void add_frame_table(const FrameStep *steps, size_t n) {
    for (size_t i = 0; i < n; i++)
      this->add_frame(steps[i].anim, steps[i].frame, steps[i].ms);
  }
  // Animations in the order the build lists them; behaviors refer to them
  // by that index (through the goal map below, if any).
  void add_animation(const std::string &name) {
    this->anims_.emplace_back();
    this->anims_.back().name = name;
  }
  void add_frame(int anim, int frame, uint32_t ms);
  void set_blink(int anim, int frame) { this->anims_[anim].blink = (int16_t) frame; }
  void set_wink(int anim, int frame) { this->anims_[anim].wink = (int16_t) frame; }
  // Plays once and holds its last frame, instead of looping.
  void set_play_once(int anim) { this->anims_[anim].once = true; }
  // A look per goal stage (the goal signal: none, started, done). Each map
  // turns a behavior's animation index into the one for that stage. Without
  // maps, the index is used as it is.
  void add_goal_map(std::vector<int16_t> map) { this->goal_maps_.push_back(std::move(map)); }
  void set_backdrop(const Sprite *image) { this->backdrop_ = image; }
  // Edge strips of the backdrop (any may be null): left and right as tall
  // as the backdrop, top as wide.
  void set_strips(const Sprite *left, const Sprite *right, const Sprite *top) {
    this->strip_sprites_[0] = left;
    this->strip_sprites_[1] = right;
    this->strip_sprites_[2] = top;
  }
  void set_sprite_offset(int x, int y) {
    this->sprite_x_ = x;
    this->sprite_y_ = y;
  }
  void set_window(int x, int y, int w, int h) {
    this->window_ = Pane{x, y, w, h};
    this->has_window_ = true;
  }
  // Plant sprites, one per growth stage (healthy and wilted), drawn between
  // the backdrop and the persona. The stage follows the progress signal.
  void set_plant_offset(int x, int y) {
    this->plant_x_ = x;
    this->plant_y_ = y;
  }
  // Backdrop colors swapped for a per-weekday set (Sunday first), e.g. a rug.
  void set_recolor(std::vector<uint32_t> colors, std::vector<std::vector<uint32_t>> by_weekday);
  void add_plant_stage(const Sprite *healthy, const Sprite *wilted) {
    this->plant_.push_back(healthy);
    this->plant_wilted_img_.push_back(wilted);
  }

  void draw(esphome::display::Display &display, StateId state, float look_y) override;
  void draw_still(esphome::display::Display &display, StateId state) override;
  bool needs_redraw(StateId state) override;
  bool draw_delta(esphome::display::Display &display, StateId state) override;

  Rect delta_area() const override { return this->delta_area_; }

  void blink() override;
  void wink() override;

 protected:
  struct Frame {
    int16_t frame;  // Index into frames_.
    uint32_t ms;
  };
  struct Animation {
    std::string name;
    std::vector<Frame> frames;
    int16_t blink{-1};
    int16_t wink{-1};
    uint32_t total_ms{0};
    bool once{false};
  };

  // Where the scene goes on the stage, in scene pixels: the backdrop (or a
  // flat frame) of w x h, with `left`, `right` and `top` scene pixels of
  // extension around it, at `scale`, the view's top-left at (sx, sy).
  struct View {
    int scale{1};
    int left{0}, right{0}, top{0};
    int w{0}, h{0};    // The view, extension included.
    int sx{0}, sy{0};  // Screen position of the view's top-left.
    Rect stage;
    bool covers{false};  // The view covers the whole stage.
  };
  View view_(esphome::display::Display &display, int w, int h, bool extend) const;
  // A strip decoded to RGB565 (clear pixels as the background).
  struct Strip {
    int w{0}, h{0};
    std::vector<uint16_t> px;
    bool valid() const { return this->w > 0 && this->h > 0; }
    uint16_t at(int x, int y) const { return this->px[(size_t) y * this->w + x]; }
  };
  void decode_strips_();
  bool has_strips_() const { return this->strips_[0].valid() || this->strips_[2].valid(); }

  const Animation &animation_(StateId state) const;
  // The frame to show now (an index into frames_).
  int current_(StateId state);
  // Flat drawing: frames are whole pictures there.
  void blit_(esphome::display::Display &display, const Sprite *image);
  // Paint only the pixels where `image` differs from `previous`.
  void blit_diff_(esphome::display::Display &display, const Sprite *image, const Sprite *previous);

  // --- Layered drawing ---
  bool layered_() const { return this->backdrop_ != nullptr; }
  uint32_t window_step_() const;
  // What the room behind the persona depends on. The room is composed
  // again only when this changes.
  struct Under {
    uint32_t step{0};
    uint8_t sky{0};
    uint8_t plant{0};
    bool wilted{false};
    uint8_t day{0};
    bool operator==(const Under &o) const {
      return step == o.step && sky == o.sky && plant == o.plant && wilted == o.wilted && day == o.day;
    }
  };
  Under under_now_() const;
  // Frame buffers for the view; false when out of memory.
  bool buffers_();
  // The window, the room and the plant into under_, in the screen's colors.
  void compose_under_(const Under &under);
  // under_ with the canvas on top into frame_.
  void compose_frame_();
  // Sends frame_ to the screen (only what differs from shown_ unless `full`),
  // then keeps it as the shown frame.
  void present_(esphome::display::Display &display, bool full);
  // Sends the canvas box `box` (canvas pixels) over under_, where it differs
  // from shown_, and updates shown_.
  void present_box_(esphome::display::Display &display, const Rect &box);
  // A screen rectangle in the view's scene pixels, clipped to the stage.
  Rect screen_rect_(int x, int y, int w, int h) const;
  void draw_layered_(esphome::display::Display &display, int frame, bool idle);
  // Out of memory: the persona alone, on the background.
  void draw_canvas_flat_(esphome::display::Display &display);

  std::vector<FrameRef> frames_;
  std::vector<Animation> anims_;
  std::vector<std::vector<int16_t>> goal_maps_;
  BasicFrameCanvas<esphome::RAMAllocator> canvas_;  // In PSRAM when there is some.
  int max_scale_{0};
  esphome::Color background_{0, 0, 0};
  const Animation *playing_{nullptr};
  uint32_t epoch_{0};
  uint32_t blink_until_{0};
  uint32_t wink_until_{0};
  int drawn_{-1};
  Rect delta_area_;

  const Sprite *backdrop_{nullptr};
  const Sprite *strip_sprites_[3]{nullptr, nullptr, nullptr};
  Strip strips_[3];  // left, right, top
  bool strips_decoded_{false};
  View view_now_;    // The view of the frame being built.
  int buf_size_{0};  // Pixels in frame_ and shown_.
  int sprite_x_{0};
  int sprite_y_{0};
  bool has_window_{false};
  Pane window_;
  std::vector<uint16_t> recolor_from_;
  std::vector<std::vector<uint16_t>> recolor_by_day_;  // [weekday - 1][i]
  std::vector<const Sprite *> plant_;
  std::vector<const Sprite *> plant_wilted_img_;
  int plant_x_{0};
  int plant_y_{0};
  uint16_t *under_{nullptr};  // The room behind the persona.
  uint16_t *frame_{nullptr};  // Being built.
  uint16_t *shown_{nullptr};  // On screen now, for the diff.
  bool shown_valid_{false};
  bool under_valid_{false};
  bool no_memory_{false};
  Under under_key_;
};

}  // namespace Daruma
