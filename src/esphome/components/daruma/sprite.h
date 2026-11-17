#pragma once

// Plain C++ apart from draw() and from_565(), which sprite.cpp defines with
// the display. So host tests can decode pictures (tests).

#include <cstdint>
#include <memory>

namespace esphome {
struct Color;
namespace display {
class Display;
}  // namespace display
}  // namespace esphome

namespace Daruma {

// A compressed picture: runs of palette colors row by row, where a run can
// also mean "same as the row above". Built at compile time by sprite.py;
// sprite_codec.py describes the byte format.
//
// A patch is a picture of what changed between two animation frames: the
// index right after the palette means "keep what is there" (frame_chain.h
// applies it).
class Sprite {
 public:
  constexpr Sprite(int width, int height, int bits, int clear, int colors, const uint16_t *palette, const uint8_t *data,
                   bool patch = false)
      : width_(width),
        height_(height),
        bits_(bits),
        clear_(clear),
        colors_(colors),
        palette_(palette),
        data_(data),
        patch_(patch) {}

  int width() const { return this->width_; }
  int height() const { return this->height_; }
  bool is_patch() const { return this->patch_; }
  bool is_clear(uint8_t index) const { return index == this->clear_; }
  // A patch pixel that keeps the frame below.
  bool is_keep(uint8_t index) const { return this->patch_ && index == this->colors_; }
  // RGB565 of a palette index.
  uint16_t color(uint8_t index) const { return this->palette_[index]; }

  // Reads the picture one row at a time, top to bottom.
  class Rows {
   public:
    explicit Rows(const Sprite &sprite) : sprite_(sprite), at_(sprite.data_), row_(new uint8_t[sprite.width_]()) {}
    // Palette indices of the next row, width() of them. Valid until the next call.
    const uint8_t *next() {
      const Sprite &s = this->sprite_;
      const int shift = 8 - s.bits_;
      const int mask = (1 << shift) - 1;
      const int copy = s.colors_ + (s.patch_ ? 1 : 0);
      int x = 0;
      while (x < s.width_) {
        const uint8_t b = *this->at_++;
        int index, run;
        if (s.bits_ == 8) {
          index = b;
          run = *this->at_++ + 1;
        } else {
          index = b >> shift;
          run = b & mask;
          if (run == 0)
            run = mask + 1 + *this->at_++;
        }
        if (x + run > s.width_)
          run = s.width_ - x;  // Bad data; stay inside the row.
        if (index != copy) {   // Otherwise the row above stays in place.
          for (int i = 0; i < run; i++)
            this->row_[x + i] = (uint8_t) index;
        }
        x += run;
      }
      return this->row_.get();
    }

   private:
    const Sprite &sprite_;
    const uint8_t *at_;
    std::unique_ptr<uint8_t[]> row_;
  };

  // Draws the picture with its top-left at (x, y), each pixel scale x scale.
  // Clear pixels are skipped. Same-colored pixels go out as rectangles, grown
  // down while the rows below repeat them, so a stripe or block is one call.
  // Not for patches.
  void draw(esphome::display::Display &display, int x, int y, int scale) const;

 protected:
  int width_;
  int height_;
  int bits_;
  int clear_;   // Palette index of see-through pixels, or -1.
  int colors_;  // Palette size; the codes after it: see sprite_codec.py.
  const uint16_t *palette_;
  const uint8_t *data_;
  bool patch_;
};

// RGB565 to a display color, the way the screen shows it.
esphome::Color from_565(uint16_t value);

}  // namespace Daruma
