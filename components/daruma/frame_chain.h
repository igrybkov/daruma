#pragma once

// Animation frames stored as keyframes and patches (sprite_codec.py), and a
// canvas that shows one of them. Plain C++, host-tested
// (tests/test_frames.cpp).
//
// A frame is either a whole picture, or a patch on an earlier frame (its
// base): only the box where the two differ. To show a frame, the canvas
// draws its base chain from the keyframe up. When the canvas already holds
// a frame on that chain, it applies only the patches after it. So playing
// an animation in order draws one small patch per frame.

#include <algorithm>
#include <cstdint>
#include <memory>
#include <vector>

#include "layout.h"
#include "sprite.h"

namespace Daruma {

struct FrameRef {
  const Sprite *image{nullptr};
  int16_t base{-1};  // The frame this patch goes on, or -1 for a whole picture.
  int16_t x{0};      // Where the patch goes on its base.
  int16_t y{0};
};

// The union of two boxes; an empty box adds nothing.
inline Rect unite(const Rect &a, const Rect &b) {
  if (a.empty())
    return b;
  if (b.empty())
    return a;
  const int x = std::min(a.x, b.x), y = std::min(a.y, b.y);
  return Rect{x, y, std::max(a.right(), b.right()) - x, std::max(a.bottom(), b.bottom()) - y};
}

// `Alloc` places the pixels: the device passes one that can use PSRAM.
template<template<class> class Alloc = std::allocator> class BasicFrameCanvas {
 public:
  // The longest chain followed: a guard against bad data.
  static const int MAX_CHAIN = 16;

  int width() const { return this->w_; }
  int height() const { return this->h_; }
  // The frame shown, or -1.
  int held() const { return this->held_; }
  void forget() { this->held_ = -1; }
  bool is_clear(int x, int y) const { return this->clear_[(size_t) y * this->w_ + x] != 0; }
  uint16_t at(int x, int y) const { return this->px_[(size_t) y * this->w_ + x]; }

  // Brings the canvas to `target`. Returns the box that may have changed,
  // in canvas pixels; empty when the canvas already showed it.
  Rect show(const std::vector<FrameRef> &frames, int target) {
    if (target < 0 || target >= (int) frames.size() || target == this->held_)
      return Rect{};
    // The chain from the target down to its keyframe, or to the frame held.
    int chain[MAX_CHAIN];
    int n = 0;
    int at = target;
    bool from_held = false;
    while (n < MAX_CHAIN) {
      chain[n++] = at;
      const int base = frames[at].base;
      if (base < 0 || base >= (int) frames.size())
        break;
      if (base == this->held_) {
        from_held = true;
        break;
      }
      at = base;
    }
    if (!from_held && frames[chain[n - 1]].base >= 0)
      return Rect{};  // Too deep, or no keyframe: bad data; keep what is shown.
    Rect box;
    for (int i = n - 1; i >= 0; i--)
      box = unite(box, this->apply_(frames[chain[i]]));
    this->held_ = target;
    return box;
  }

 protected:
  Rect apply_(const FrameRef &frame) {
    const Sprite &s = *frame.image;
    if (!s.is_patch()) {
      if (s.width() != this->w_ || s.height() != this->h_) {
        this->w_ = s.width();
        this->h_ = s.height();
        this->px_.assign((size_t) this->w_ * this->h_, 0);
        this->clear_.assign((size_t) this->w_ * this->h_, 1);
      }
    }
    const int ox = s.is_patch() ? frame.x : 0;
    const int oy = s.is_patch() ? frame.y : 0;
    Sprite::Rows rows(s);
    for (int y = 0; y < s.height(); y++) {
      const uint8_t *row = rows.next();
      const int cy = oy + y;
      if (cy < 0 || cy >= this->h_)
        continue;
      for (int x = 0; x < s.width(); x++) {
        const int cx = ox + x;
        if (cx < 0 || cx >= this->w_ || s.is_keep(row[x]))
          continue;
        const size_t i = (size_t) cy * this->w_ + cx;
        this->clear_[i] = s.is_clear(row[x]) ? 1 : 0;
        this->px_[i] = s.is_clear(row[x]) ? 0 : s.color(row[x]);
      }
    }
    const Rect area{ox, oy, s.width(), s.height()};
    const int x0 = std::max(area.x, 0), y0 = std::max(area.y, 0);
    return Rect{x0, y0, std::min(area.right(), this->w_) - x0, std::min(area.bottom(), this->h_) - y0};
  }

  int w_{0};
  int h_{0};
  int held_{-1};
  std::vector<uint16_t, Alloc<uint16_t>> px_;  // RGB565
  std::vector<uint8_t, Alloc<uint8_t>> clear_;  // 1 where the frame is see-through.
};

using FrameCanvas = BasicFrameCanvas<>;

}  // namespace Daruma
