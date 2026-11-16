#include "sprite.h"

#include "esphome/components/display/display.h"

#include <utility>
#include <vector>

namespace Daruma {

esphome::Color from_565(uint16_t v) {
  const uint8_t r = (v >> 11) & 0x1F, g = (v >> 5) & 0x3F, b = v & 0x1F;
  return esphome::Color((r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2));
}

void Sprite::draw(esphome::display::Display &display, int ox, int oy, int scale) const {
  // Rectangles still growing down: one per run of the last row.
  struct Block {
    int x, w, y;
    uint8_t index;
  };
  std::vector<Block> open, next;
  auto flush = [&](const Block &b, int bottom) {
    display.filled_rectangle(ox + b.x * scale, oy + b.y * scale, b.w * scale, (bottom - b.y) * scale,
                             from_565(this->palette_[b.index]));
  };

  Rows rows(*this);
  for (int y = 0; y < this->height_; y++) {
    const uint8_t *row = rows.next();
    next.clear();
    size_t o = 0;
    int x = 0;
    while (x < this->width_) {
      const uint8_t index = row[x];
      int run = 1;
      while (x + run < this->width_ && row[x + run] == index)
        run++;
      if (index != this->clear_) {
        // Blocks from the row above that end before this run are done.
        while (o < open.size() && open[o].x < x)
          flush(open[o++], y);
        if (o < open.size() && open[o].x == x && open[o].w == run && open[o].index == index) {
          next.push_back(open[o++]);  // Same run as above: grow it.
        } else {
          next.push_back(Block{x, run, y, index});
        }
      }
      x += run;
    }
    while (o < open.size())
      flush(open[o++], y);
    std::swap(open, next);
  }
  for (const Block &b : open)
    flush(b, this->height_);
}

}  // namespace Daruma
