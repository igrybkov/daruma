#pragma once

// Gestures of one button, or of taps on a touch screen: press (tap), double,
// hold and long hold. Plain C++ with no ESPHome parts, so a host test can
// check the timing (tests/test_input.cpp).
//
// No delay unless it is needed. The caller passes the gestures bound in the
// current context as a bit mask (gesture_bit()):
// - Neither a double nor a hold bound: the press fires at once, on press-down.
// - A hold bound: the press fires on release, if released before hold time.
// - A double bound: a release waits up to the double window for a second
//   press-down, which fires DOUBLE. Without one, PRESS fires when it ends.
// - Hold and long hold both bound: HOLD fires on a release between the two
//   times, LONG_HOLD as soon as the long time is reached. Only one bound:
//   it fires as soon as its time is reached.
// Touch can't know at touch-down whether a swipe follows, so a tap never
// fires before lift-off (`on_release`); it then fires at once unless a
// double is bound. A touch held past hold time is never a tap. A swipe or
// stroke calls cancel(). TouchTracker below tells a tap from a swipe or a
// stroke.

#include <algorithm>
#include <cstdint>
#include <cstdlib>
#include <vector>

namespace Daruma {

enum class Gesture : uint8_t {
  PRESS,
  DOUBLE,
  HOLD,
  LONG_HOLD,
  TAP,
  SWIPE_LEFT,
  SWIPE_RIGHT,
  SWIPE_UP,
  SWIPE_DOWN,
  STROKE,
  NONE,
};

inline constexpr uint16_t gesture_bit(Gesture g) { return (uint16_t) (1u << static_cast<uint8_t>(g)); }

inline const char *gesture_name(Gesture g) {
  static const char *const NAMES[] = {"press",       "double",   "hold",       "long_hold", "tap", "swipe_left",
                                      "swipe_right", "swipe_up", "swipe_down", "stroke",    "none"};
  return NAMES[static_cast<uint8_t>(g)];
}

struct PressTiming {
  uint32_t double_window_ms{300};
  uint32_t hold_ms{1000};
  uint32_t long_hold_ms{3000};
};

class PressRecognizer {
 public:
  // `press` is what a single press is called: PRESS for buttons, TAP for touch.
  // `on_release`: a single press never fires before release (touch).
  explicit PressRecognizer(Gesture press = Gesture::PRESS, bool on_release = false)
      : press_(press), on_release_(on_release) {}

  void set_timing(const PressTiming &timing) { this->timing_ = timing; }
  const PressTiming &timing() const { return this->timing_; }

  Gesture down(uint32_t now, uint16_t bound) {
    if (this->waiting_) {
      this->waiting_ = false;
      if ((bound & gesture_bit(Gesture::DOUBLE)) != 0 && now - this->up_at_ < this->timing_.double_window_ms) {
        this->start_(now, true);
        return Gesture::DOUBLE;
      }
    }
    const bool wait = this->on_release_ || (bound & (gesture_bit(Gesture::DOUBLE) | holds_())) != 0;
    this->start_(now, !wait);
    return wait ? Gesture::NONE : this->press_;
  }

  Gesture up(uint32_t now, uint16_t bound) {
    if (!this->held_)
      return Gesture::NONE;
    this->held_ = false;
    if (this->done_)
      return Gesture::NONE;
    this->done_ = true;
    const uint32_t held = now - this->down_at_;
    // A press held past hold time is no tap, even with no hold bound.
    if (((bound & holds_()) != 0 || this->on_release_) && held >= this->timing_.hold_ms)
      return (bound & gesture_bit(Gesture::HOLD)) != 0 ? Gesture::HOLD : Gesture::NONE;
    if ((bound & gesture_bit(Gesture::DOUBLE)) != 0) {
      this->waiting_ = true;
      this->up_at_ = now;
      return Gesture::NONE;
    }
    return this->press_;
  }

  Gesture tick(uint32_t now, uint16_t bound) {
    if (this->waiting_ && now - this->up_at_ >= this->timing_.double_window_ms) {
      this->waiting_ = false;
      return this->press_;
    }
    if (!this->held_ || this->done_)
      return Gesture::NONE;
    const uint32_t held = now - this->down_at_;
    const bool hold = (bound & gesture_bit(Gesture::HOLD)) != 0;
    const bool long_hold = (bound & gesture_bit(Gesture::LONG_HOLD)) != 0;
    if (long_hold && held >= this->timing_.long_hold_ms) {
      this->done_ = true;
      return Gesture::LONG_HOLD;
    }
    if (hold && !long_hold && held >= this->timing_.hold_ms) {
      this->done_ = true;
      return Gesture::HOLD;
    }
    return Gesture::NONE;
  }

  // The current press turned into something else (a swipe): it fires nothing.
  void cancel() {
    this->done_ = true;
    this->waiting_ = false;
  }
  // True while a press is held or a double may still come.
  bool busy() const { return this->held_ || this->waiting_; }

 protected:
  static constexpr uint16_t holds_() { return gesture_bit(Gesture::HOLD) | gesture_bit(Gesture::LONG_HOLD); }
  void start_(uint32_t now, bool done) {
    this->held_ = true;
    this->done_ = done;
    this->down_at_ = now;
  }

  Gesture press_;
  bool on_release_;
  PressTiming timing_;
  bool held_{false};
  bool done_{false};  // This press already fired, or never will.
  bool waiting_{false};
  uint32_t down_at_{0};
  uint32_t up_at_{0};
};

// Swipe tuning, in screen pixels and milliseconds.
struct SwipeTuning {
  int move_slop{20};           // moved less than this: still a tap
  int swipe_min{60};           // shortest swipe
  uint32_t swipe_max_ms{700};  // slower than this: a drag, ignored
  int stroke_step{25};         // back-and-forth leg length
  int stroke_turns{2};         // direction changes for a stroke
};

// One finger on a touch screen, from touch-down to lift-off, in screen
// pixels and milliseconds.
struct TouchTrack {
  static constexpr uint32_t NO_DRAG = UINT32_MAX;
  int x0{0};  // Where the finger came down.
  int y0{0};
  int x{0};  // Where it is now, or where it lifted.
  int y{0};
  int travel_x{0};  // The farthest it went from (x0, y0), per axis.
  int travel_y{0};
  uint32_t down_ms{0};
  uint32_t up_ms{0};
  // From the lift-off of the last touch that moved past the slop (a swipe,
  // a stroke, a drag) to this touch-down; NO_DRAG when there was none.
  uint32_t after_drag_ms{NO_DRAG};
};

// Follows the finger and names what it did: nothing past the slop (a tap,
// left to the PressRecognizer), a swipe, or a stroke (petting: two or more
// turns back and forth). A drag that is neither does nothing.
class TouchTracker {
 public:
  void set_tuning(const SwipeTuning &tuning) { this->tuning_ = tuning; }
  const SwipeTuning &tuning() const { return this->tuning_; }

  void start(uint32_t now, int x, int y) {
    TouchTrack t;
    t.x0 = t.x = x;
    t.y0 = t.y = y;
    t.down_ms = now;
    if (this->dragged_)
      t.after_drag_ms = now - this->drag_end_ms_;
    this->track_ = t;
    this->moved_ = false;
    this->down_ = true;
    this->axis_x_.reset(x);
    this->axis_y_.reset(y);
  }

  // True when this sample is the first past the slop: the touch is no tap.
  bool move(int x, int y) {
    if (!this->down_)
      return false;
    TouchTrack &t = this->track_;
    t.x = x;
    t.y = y;
    t.travel_x = std::max(t.travel_x, std::abs(x - t.x0));
    t.travel_y = std::max(t.travel_y, std::abs(y - t.y0));
    this->axis_x_.track(x, this->tuning_);
    this->axis_y_.track(y, this->tuning_);
    if (this->moved_ || (t.travel_x <= this->tuning_.move_slop && t.travel_y <= this->tuning_.move_slop))
      return false;
    this->moved_ = true;
    return true;
  }

  // Lift-off: the swipe or stroke the touch made, or NONE.
  Gesture end(uint32_t now) {
    if (!this->down_)
      return Gesture::NONE;
    this->down_ = false;
    TouchTrack &t = this->track_;
    t.up_ms = now;
    if (!this->moved_)
      return Gesture::NONE;
    this->dragged_ = true;
    this->drag_end_ms_ = now;
    const int dx = t.x - t.x0;
    const int dy = t.y - t.y0;
    const int ax = std::abs(dx);
    const int ay = std::abs(dy);
    if (std::max(this->axis_x_.turns, this->axis_y_.turns) >= this->tuning_.stroke_turns)
      return Gesture::STROKE;
    if (now - t.down_ms > this->tuning_.swipe_max_ms)
      return Gesture::NONE;
    if (ax >= this->tuning_.swipe_min && ax >= 2 * ay)
      return dx < 0 ? Gesture::SWIPE_LEFT : Gesture::SWIPE_RIGHT;
    if (ay >= this->tuning_.swipe_min && ay >= 2 * ax)
      return dy < 0 ? Gesture::SWIPE_UP : Gesture::SWIPE_DOWN;
    return Gesture::NONE;
  }

  bool down() const { return this->down_; }
  // Past the slop: no tap.
  bool moved() const { return this->moved_; }
  // The touch going on, or the last one.
  const TouchTrack &track() const { return this->track_; }

 protected:
  // Turns back and forth along one axis, for strokes.
  struct Axis {
    int pivot{0};
    int dir{0};
    int turns{0};
    void reset(int v) { *this = Axis{v, 0, 0}; }
    void track(int v, const SwipeTuning &tuning) {
      const int d = v - this->pivot;
      if (this->dir == 0) {
        if (std::abs(d) >= tuning.stroke_step) {
          this->dir = d > 0 ? 1 : -1;
          this->pivot = v;
        }
      } else if (d * this->dir > 0) {
        this->pivot = v;  // Further the same way: new turning point.
      } else if (-d * this->dir >= tuning.stroke_step) {
        this->turns++;
        this->dir = -this->dir;
        this->pivot = v;
      }
    }
  };

  SwipeTuning tuning_;
  TouchTrack track_;
  bool down_{false};
  bool moved_{false};
  bool dragged_{false};  // A touch moved past the slop since start-up.
  uint32_t drag_end_ms_{0};
  Axis axis_x_;
  Axis axis_y_;
};

// The finger to follow among a touch screen's points: the one that came down
// (`*id`) while it is on the glass, else another one that is. `on_glass(p)`
// tells them apart. A screen driver keeps a lifted point in its list until
// every finger is off; following the list's first point would then freeze
// the finger in place when the screen gives it a new id mid-swipe, and a
// swipe would end as a tap. Returns nullptr when no point is on the glass.
template<class Point, class OnGlass>
const Point *follow_finger(const std::vector<Point> &points, int *id, OnGlass on_glass) {
  const Point *other = nullptr;
  for (const Point &p : points) {
    if (!on_glass(p))
      continue;
    if ((int) p.id == *id)
      return &p;
    if (other == nullptr)
      other = &p;
  }
  if (other != nullptr)
    *id = other->id;
  return other;
}

}  // namespace Daruma
