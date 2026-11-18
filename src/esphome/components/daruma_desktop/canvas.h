#pragma once

#ifdef USE_HOST

#include "esphome/components/daruma_desktop/pixel_buffer.h"
#include "esphome/components/display/display.h"
#include "esphome/components/display/display_color_utils.h"

namespace Daruma {

// The desktop build's screen in RAM. The hub draws into it, and flush_to()
// then hands what changed to the real display in one draw_pixels_at() call.
// The sdl display uploads its picture once for each pixel it is given one
// at a time, so drawing into it straight is slow.
//
// It stores each pixel as the sdl display does (RGB565, RGB order), so the
// picture on screen is the same either way. Like any display, it honors the
// clipping rectangle. ESPHome never sets it up or updates it: it only holds
// pixels.
class Canvas final : public esphome::display::Display {
 public:
  // Matches the canvas to a display's size. A new size starts all black.
  void fit(int width, int height) {
    if (width != this->buffer_.width() || height != this->buffer_.height())
      this->buffer_.resize(width, height);
  }

  // Ends any clipping a frame left open. A display does this after each
  // frame it draws itself; nothing does it for the canvas.
  void reset_clipping() { this->clear_clipping_(); }

  esphome::display::DisplayType get_display_type() override { return esphome::display::DISPLAY_TYPE_COLOR; }
  void update() override {}

  void draw_pixel_at(int x, int y, esphome::Color color) override {
    if (this->is_point_clipped(x, y))
      return;
    this->buffer_.set(x, y, esphome::display::ColorUtil::color_to_565(color, esphome::display::COLOR_ORDER_RGB));
  }

  // Draws the pixels that changed since the last flush onto `display`.
  void flush_to(esphome::display::Display &display) {
    const PixelBuffer::Area a = this->buffer_.take_dirty();
    if (a.w == 0)
      return;
    // The values are in the host's byte order.
    const bool big_endian = __BYTE_ORDER__ == __ORDER_BIG_ENDIAN__;
    display.draw_pixels_at(a.x, a.y, a.w, a.h, reinterpret_cast<const uint8_t *>(this->buffer_.data()),
                           esphome::display::COLOR_ORDER_RGB, esphome::display::COLOR_BITNESS_565, big_endian, a.x, a.y,
                           this->buffer_.width() - a.x - a.w);
  }

 protected:
  int get_width_internal() override { return this->buffer_.width(); }
  int get_height_internal() override { return this->buffer_.height(); }

  PixelBuffer buffer_;
};

}  // namespace Daruma

#endif
