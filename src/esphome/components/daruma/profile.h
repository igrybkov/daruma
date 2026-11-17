#pragma once

// What the screen can do, as the board declares it (`display_profile:`),
// and the frame scheduler that paces drawing to it.
//
// Plain C++ with no ESPHome includes, so a host test can check it
// (tests/test_layout.cpp).

#include <cstdint>

namespace Daruma {

enum class ColorMode : uint8_t {
  FULL,   // Color LCD.
  GRAY4,  // Four gray levels.
  MONO,   // Black and white.
};

struct DisplayProfile {
  ColorMode colors{ColorMode::FULL};
  // False: personas show still frames only; blinks, wags and drift stop.
  bool animate{true};
  // The shortest time between two frames. Changes in between wait and are
  // drawn together.
  uint32_t min_frame_ms{100};
  // The screen can update part of itself (personas repaint only what moved).
  bool partial_refresh{true};
  // With partial_refresh: every Nth frame repaints everything (e-ink ghosting).
  // 0 = never.
  uint16_t full_refresh_every{0};

  // A slow screen (e-ink): clocks and countdowns show minutes and redraw
  // once a minute.
  bool slow() const { return this->min_frame_ms >= 1000; }
};

// Perceived brightness, 0..255 (Rec. 601 weights).
inline uint8_t luminance(uint8_t r, uint8_t g, uint8_t b) {
  return (uint8_t) ((r * 299u + g * 587u + b * 114u) / 1000u);
}

// A gray level for the mode: 0/255 for mono, 0/85/170/255 for gray4.
// FULL returns -1 (keep the color).
inline int quantize_gray(ColorMode mode, uint8_t r, uint8_t g, uint8_t b) {
  const uint8_t y = luminance(r, g, b);
  switch (mode) {
    case ColorMode::MONO:
      return y >= 128 ? 255 : 0;
    case ColorMode::GRAY4:
      return ((y + 42) / 85) * 85;
    default:
      return -1;
  }
}

// Paces frames: no closer together than min_frame, and only when something
// asked for one. Several requests inside one min_frame make one frame.
//
//   loop:  if (sched.due(now, wants_motion)) { draw(sched.full_frame()); sched.drawn(now); }
class FrameScheduler {
 public:
  void set_profile(const DisplayProfile &profile) { this->profile_ = profile; }
  const DisplayProfile &profile() const { return this->profile_; }

  // Something changed that must reach the screen, even while motion is held
  // back (a voice phase changed, a menu opened).
  void invalidate() { this->forced_ = true; }
  bool pending() const { return this->forced_; }

  // min_frame has passed since the last frame (or none was drawn yet).
  bool ready(uint32_t now) const {
    return !this->any_ || (uint32_t) (now - this->last_ms_) >= this->profile_.min_frame_ms;
  }
  // True when a frame should be drawn now. `motion`: the idle screen would
  // look different (a persona frame is due, a value ticked).
  bool due(uint32_t now, bool motion) const { return (this->forced_ || motion) && this->ready(now); }

  // The frame about to be drawn must repaint the whole screen: no partial
  // refresh, the first frame, or every full_refresh_every-th one.
  bool full_frame() const {
    if (!this->profile_.partial_refresh || !this->any_)
      return true;
    const uint16_t every = this->profile_.full_refresh_every;
    return every > 0 && this->partial_ + 1 >= every;
  }

  // A frame went out at `now`.
  void drawn(uint32_t now, bool full) {
    this->any_ = true;
    this->last_ms_ = now;
    this->forced_ = false;
    this->partial_ = full ? 0 : (uint16_t) (this->partial_ + 1);
    this->frames_++;
  }

  uint32_t frames() const { return this->frames_; }

 protected:
  DisplayProfile profile_;
  bool forced_{false};
  bool any_{false};
  uint32_t last_ms_{0};
  uint16_t partial_{0};
  uint32_t frames_{0};
};

}  // namespace Daruma
