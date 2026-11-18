#pragma once

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <vector>

namespace Daruma {

// A screen's pixels in RAM, as RGB565 values in the host's byte order, and
// the rectangle that changed since the last take_dirty(). Pixels keep their
// value until they are drawn again, like a screen does.
class PixelBuffer {
 public:
  // A rectangle of pixels. Empty when w is 0.
  struct Area {
    int x;
    int y;
    int w;
    int h;
  };

  // All pixels black (0), nothing changed.
  void resize(int width, int height) {
    this->width_ = width;
    this->height_ = height;
    this->pixels_.assign(static_cast<size_t>(width) * height, 0);
    this->dirty_ = false;
  }

  int width() const { return this->width_; }
  int height() const { return this->height_; }
  const uint16_t *data() const { return this->pixels_.data(); }
  uint16_t at(int x, int y) const { return this->pixels_[this->index_(x, y)]; }

  // A pixel outside the buffer is dropped.
  void set(int x, int y, uint16_t value) {
    if (x < 0 || y < 0 || x >= this->width_ || y >= this->height_)
      return;
    this->pixels_[this->index_(x, y)] = value;
    if (!this->dirty_) {
      this->dirty_ = true;
      this->x_low_ = this->x_high_ = x;
      this->y_low_ = this->y_high_ = y;
      return;
    }
    this->x_low_ = std::min(this->x_low_, x);
    this->x_high_ = std::max(this->x_high_, x);
    this->y_low_ = std::min(this->y_low_, y);
    this->y_high_ = std::max(this->y_high_, y);
  }

  // The smallest rectangle around every pixel set since the last call.
  Area take_dirty() {
    if (!this->dirty_)
      return Area{0, 0, 0, 0};
    this->dirty_ = false;
    return Area{this->x_low_, this->y_low_, this->x_high_ + 1 - this->x_low_, this->y_high_ + 1 - this->y_low_};
  }

 protected:
  size_t index_(int x, int y) const { return static_cast<size_t>(y) * this->width_ + x; }

  int width_{0};
  int height_{0};
  std::vector<uint16_t> pixels_;
  bool dirty_{false};
  // Read only while dirty_ is true: set() gives them their first values.
  int x_low_{0};   // pragma: no mutate
  int y_low_{0};   // pragma: no mutate
  int x_high_{0};  // pragma: no mutate
  int y_high_{0};  // pragma: no mutate
};

}  // namespace Daruma
