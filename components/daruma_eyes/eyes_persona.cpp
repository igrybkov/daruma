#include "eyes_persona.h"

#include <cmath>

#include "esphome/core/hal.h"
#include "esphome/core/helpers.h"
#include "esphome/components/daruma/draw.h"
#include "Happy.h"
#include "Loved.h"
#include "Neutral.h"
#include "Sad.h"
#include "Scared.h"
#include "Sleeping.h"
#include "Sleepy.h"

namespace Daruma {

// Minimum gap between redraws for moods that move on their own
// (Scared jitter, Sleepy droop, Sleeping breath). About 8 fps.
static const uint32_t ANIMATED_MOOD_FRAME_MS = 125;
static const int WINK_DURATION_MS = 450;

// The moods and the looks (eye_reach.h).
using namespace Eyes;

// Param `color`, in the order of PARAMS in __init__.py.
static const esphome::Color EYE_COLORS[] = {{0, 255, 255}, {60, 255, 120}, {255, 190, 40}, {255, 120, 200},
                                            {240, 240, 240}};

EyesPersona::EyesPersona(const std::string &name) : Persona(name) {
  this->states_ = {new States::Neutral(), new States::Happy(),  new States::Sad(),     new States::Loved(),
                   new States::Scared(),  new States::Sleepy(), new States::Sleeping()};
}

const EyesPersona::Look &EyesPersona::look_(StateId state) const {
  const int index = this->animation_for(state);
  return LOOKS[index >= 0 && index < LOOK_COUNT ? index : 0];
}

esphome::Color EyesPersona::eye_color_() const {
  const int index = this->param("color");
  return EYE_COLORS[index >= 0 && index < (int) (sizeof(EYE_COLORS) / sizeof(EYE_COLORS[0])) ? index : 0];
}

void EyesPersona::place_(esphome::display::Display &display, const Look &look) {
  // Above the bottom corners (the pomodoro plaque, the badge), as high as
  // this look needs to keep clear of them (eye_reach.h); the whole stage's
  // center before a layout exists.
  this->unit_now_ = this->unit_(display);
  if (this->layout_ != nullptr && this->layout_->width > 0) {
    Eyes::center(*this->layout_, look, &this->cx_, &this->cy_);
  } else {
    const Rect stage = this->stage_(display);
    this->cx_ = stage.cx();
    this->cy_ = stage.cy();
  }
  this->states_[look.mood]->setGeometry(this->cx_, this->cy_, this->unit_now_);
}

// Where a mood's eyes can reach, its wink box included, in design pixels
// around the stage center: left, top, right, bottom. Blinks only shrink
// them. Loved draws hearts, which have no fixed box: it always redraws all.
struct EyeBox {
  int16_t l, t, r, b;
  bool moves_x, moves_y;  // The mood follows the glance / the look offset.
};
static const EyeBox BOXES[] = {
    {-84, -48, 84, 48, true, true},   // NEUTRAL
    {-84, -76, 84, -16, true, true},  // HAPPY: a donut top half; the wink box above it.
    {-84, 2, 84, 78, true, true},     // SAD
    {0, 0, 0, 0, false, false},       // LOVED
    {-65, -18, 65, 18, true, false},  // SCARED: jittering dots.
    {-84, -34, 84, 54, false, false}, // SLEEPY: drooping lids.
    {-84, 14, 84, 32, false, false},  // SLEEPING: breathing lines.
};

Rect EyesPersona::box_(uint8_t mood, float x, float y) const {
  if (mood >= sizeof(BOXES) / sizeof(BOXES[0]) || mood == LOVED)
    return Rect{};
  const EyeBox &e = BOXES[mood];
  auto u = [this](int v) { return (int) std::lround(v * this->unit_now_); };
  const int dx = e.moves_x ? (int) std::floor(x) : 0;
  const int dy = e.moves_y ? (int) std::floor(y) : 0;
  return Rect{this->cx_ + u(e.l) + dx, this->cy_ + u(e.t) + dy, u(e.r - e.l) + 2, u(e.b - e.t) + 2};
}

Rect EyesPersona::paint_(esphome::display::Display &display, StateId state, float look_y) {
  const Look &look = this->look_(state);
  this->place_(display, look);

  float blink = 1.0f;
  if (!this->blink_animator_.isDone()) {
    blink = Utilities::FloatAnimator::calculateV(this->blink_animator_.update());
  }
  // Offsets are design pixels; the eyes scale with the stage.
  const float x = (this->move_animator_.update() + look.dx) * this->unit_now_;
  const float y = (look_y + look.dy) * this->unit_now_;

  this->states_[look.mood]->render(&display, x, y, blink * look.lid, this->eye_color_(), this->background_);

  // A narrowed look does not wink: the wink is a whole eye's height.
  if (!this->wink_animator_.isDone()) {
    this->wink_animator_.update();
    if (!this->wink_animator_.isDone() && look.lid >= 1.0f) {
      this->draw_wink_(display, look.mood, x, y);
    }
  }

  this->drawn_look_ = this->animation_for(state);
  this->drawn_look_y_ = look_y;
  this->last_draw_ = esphome::millis();
  return this->box_(look.mood, x, y);
}

void EyesPersona::draw(esphome::display::Display &display, StateId state, float look_y) {
  display.fill(this->background_);
  this->drawn_box_ = this->paint_(display, state, look_y);
}

bool EyesPersona::draw_delta(esphome::display::Display &display, StateId state) {
  // Same look, no bubble lift, and a mood with a known box: repaint only the
  // old and the new box. Anything else is a full frame.
  const Look &look = this->look_(state);
  if (this->animation_for(state) != this->drawn_look_ || this->drawn_look_y_ != 0.0f || this->drawn_box_.empty() ||
      look.mood == LOVED)
    return false;
  // Where the eyes go now: the box needs the offsets paint_() will use.
  this->place_(display, look);
  const float x = (this->move_animator_.update() + look.dx) * this->unit_now_;
  const float y = look.dy * this->unit_now_;
  // A little slack: the glance may move on between here and the paint.
  const Rect next = this->box_(look.mood, x, y).inset(-(int) std::lround(4 * this->unit_now_));
  const Rect area = this->drawn_box_.united(next).intersected(this->stage_(display));
  if (area.empty())
    return false;
  display.start_clipping(esphome::display::Rect(area.x, area.y, area.w, area.h));
  display.filled_rectangle(area.x, area.y, area.w, area.h, this->background_);
  this->drawn_box_ = this->paint_(display, state, 0.0f);
  display.end_clipping();
  this->delta_ = area;
  return true;
}

void EyesPersona::draw_still(esphome::display::Display &display, StateId state) {
  this->drawn_box_ = Rect{};
  const Look &look = this->look_(state);
  display.fill(this->background_);
  this->place_(display, look);
  this->states_[look.mood]->render(&display, look.dx * this->unit_now_, look.dy * this->unit_now_, look.lid,
                                   this->eye_color_(), this->background_);
  this->drawn_look_ = -1;  // Force the next idle frame.
}

bool EyesPersona::needs_redraw(StateId state) {
  if (this->animation_for(state) != this->drawn_look_)
    return true;
  if (!this->blink_animator_.isDone() || !this->move_animator_.isDone() || !this->wink_animator_.isDone())
    return true;
  return this->states_[this->look_(state).mood]->isAnimated() &&
         esphome::millis() - this->last_draw_ >= ANIMATED_MOOD_FRAME_MS;
}

void EyesPersona::blink() {
  if (this->blink_animator_.isDone())
    this->blink_animator_.startAnimation(1.0f, 0.0f, 200);
}

void EyesPersona::wink() {
  if (this->wink_animator_.isDone())
    this->wink_animator_.startAnimation(0.0f, 1.0f, WINK_DURATION_MS);
}

void EyesPersona::look_around() {
  if (this->move_animator_.isDone()) {
    this->move_animator_.startAnimation(this->move_animator_.update(),
                                        (float) (esphome::random_uint32() % (2 * GLANCE + 1)) - GLANCE, 500);
  }
}

void EyesPersona::draw_wink_(esphome::display::Display &display, uint8_t mood, float x, float y) {
  // Right eye box per mood, matching the geometry in each state's render().
  int top, height;
  if (mood == NEUTRAL) {
    top = 80;
    height = 80;
  } else if (mood == HAPPY) {
    top = 56;
    height = 40;
  } else if (mood == SAD) {
    top = 130;
    height = 60;
  } else {
    return;  // Wink looks wrong on hearts, dots and closed eyes.
  }

  // The boxes above are for a 240-high stage centered at y = 120.
  auto u = [this](int v) { return (int) std::lround(v * this->unit_now_); };
  height = u(height);
  const int right_x = this->cx_ + u(20) + (int) x;
  const int eye_top = this->cy_ + u(top - 120) + (int) y;
  display.filled_rectangle(right_x - u(4), eye_top - u(4), u(68), height + u(8), this->background_);
  Utilities::Draw::roundedRectangle(&display, right_x, eye_top + height / 2 - u(5), u(60), u(10), u(5),
                                    this->eye_color_());
}

}  // namespace Daruma
