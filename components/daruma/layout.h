#pragma once

// Where things go on the screen, for any display size. The hub computes one
// Layout from the display at setup (Hub::layout()) and everything draws
// into its regions, so no part of the UI assumes 320x240.
//
// Sizes are designed in "design pixels" for a 320x240 screen and scaled by
// `unit` (min(width, height) / 240). On 320x240 every region comes out at
// the same pixel numbers the UI always used. px(v) turns a design size
// into screen pixels.
//
//   stage    where the persona draws (the whole screen)
//   dock     the menu's dock panel, over the bottom of the stage
//   header   the title bar of the app board and of apps
//   content  the app area under the header (AppView x, y, w, h)
//   board    the app board's tile area: grid_cols x grid_rows tiles a page
//   back     the tap zone of the header's back arrow
//   info     a thin line of short text on the device's own screen (the next
//            calendar event): the bottom strip between the side margins,
//            under both bottom corners
//   info_top the same line at the top, right of the voice timer, for a
//            persona that wants it there
//   upper    the stage above the bottom corners; a persona that centers
//            itself (the eyes) centers here, so the corners stay clear
//   corner_left(w, h), corner_right(w, h)
//            a w x h box in a bottom corner (the tomato plaque, the
//            temperature badge). Both share one bottom edge (corner_bottom)
//            and one side margin (edge), and sit above the info line
//            whether it shows or not, so nothing moves when it comes or goes
//
// Plain C++ with no ESPHome includes, so a host test can check the numbers
// (tests/test_layout.cpp).
//
// Using it in a module or app:
//
//   const Layout &l = hub.layout();
//   Rect card = l.content.inset(l.px(8));      // a card inside the app area
//   Rect cell = card.cell(i, 2, 2, l.gap);     // one of a 2x2 grid of answers
//   if (cell.contains(x, y)) ...               // a tap on it
//   int cols = l.grid_cols;                    // 2 on 4:3 and square, 3 on 16:9

#include <algorithm>
#include <cmath>
#include <cstdint>

namespace Daruma {

struct Rect {
  int x{0};
  int y{0};
  int w{0};
  int h{0};

  int right() const { return this->x + this->w; }
  int bottom() const { return this->y + this->h; }
  int cx() const { return this->x + this->w / 2; }
  int cy() const { return this->y + this->h / 2; }
  bool empty() const { return this->w <= 0 || this->h <= 0; }
  bool contains(int px, int py) const {
    return px >= this->x && px < this->right() && py >= this->y && py < this->bottom();
  }
  bool operator==(const Rect &o) const { return x == o.x && y == o.y && w == o.w && h == o.h; }
  bool operator!=(const Rect &o) const { return !(*this == o); }

  // The smallest rect holding both (an empty one adds nothing).
  Rect united(const Rect &o) const {
    if (o.empty())
      return *this;
    if (this->empty())
      return o;
    const int l = std::min(x, o.x), t = std::min(y, o.y);
    return Rect{l, t, std::max(right(), o.right()) - l, std::max(bottom(), o.bottom()) - t};
  }
  // The part inside both (empty when they do not meet).
  Rect intersected(const Rect &o) const {
    const int l = std::max(x, o.x), t = std::max(y, o.y);
    const int r = std::min(right(), o.right()), b = std::min(bottom(), o.bottom());
    return r > l && b > t ? Rect{l, t, r - l, b - t} : Rect{};
  }

  // Smaller by d on every side (or dx left and right, dy top and bottom).
  Rect inset(int d) const { return this->inset(d, d); }
  Rect inset(int dx, int dy) const { return Rect{x + dx, y + dy, w - 2 * dx, h - 2 * dy}; }
  // Cell i (row by row) of a cols x rows grid with `gap` between cells. The
  // cells share the width and height evenly; leftover pixels stay at the end.
  Rect cell(int i, int cols, int rows, int gap) const {
    cols = std::max(cols, 1);
    rows = std::max(rows, 1);
    const int cw = (this->w - gap * (cols - 1)) / cols;
    const int ch = (this->h - gap * (rows - 1)) / rows;
    return Rect{this->x + (i % cols) * (cw + gap), this->y + (i / cols) % rows * (ch + gap), cw, ch};
  }
  // Index of the cell that holds (px, py), or -1 (also for the gaps).
  int cell_at(int px, int py, int cols, int rows, int gap) const {
    for (int i = 0; i < cols * rows; i++) {
      if (this->cell(i, cols, rows, gap).contains(px, py))
        return i;
    }
    return -1;
  }
};

// The screen's shape.
enum class SizeClass : uint8_t {
  STANDARD,  // About 4:3 (320x240): the design shape.
  WIDE,      // 16:9 and wider (480x272, 320x170).
  SQUARE,    // About 1:1 (240x240).
  TALL,      // Portrait (240x320).
};

inline const char *size_class_name(SizeClass c) {
  switch (c) {
    case SizeClass::WIDE:
      return "wide";
    case SizeClass::SQUARE:
      return "square";
    case SizeClass::TALL:
      return "tall";
    default:
      return "standard";
  }
}

struct Layout {
  int width{0};
  int height{0};
  SizeClass size_class{SizeClass::STANDARD};
  float unit{1.0f};  // Screen pixels per design pixel.

  Rect screen;
  Rect stage;
  Rect dock;
  Rect header;
  Rect content;
  Rect board;
  Rect back;
  Rect info;
  Rect info_top;
  Rect upper;
  int edge{6};           // Side margin of the bottom corners and the info line.
  int corner_bottom{0};  // Shared bottom edge of the two bottom corners.
  int grid_cols{2};
  int grid_rows{2};
  int gap{8};     // Between board tiles and other grid cells.
  int dots_y{0};  // Center line of the board's page dots.

  // A design size in screen pixels, rounded.
  int px(float v) const { return (int) std::lround(v * this->unit); }
  int tiles_per_page() const { return this->grid_cols * this->grid_rows; }
  // Tile i of a board page.
  Rect tile(int i) const { return this->board.cell(i, this->grid_cols, this->grid_rows, this->gap); }
  // The tile under (x, y), or -1.
  int tile_at(int x, int y) const { return this->board.cell_at(x, y, this->grid_cols, this->grid_rows, this->gap); }
  // A w x h box in the bottom-left or bottom-right corner.
  Rect corner_left(int w, int h) const { return Rect{this->edge, this->corner_bottom - h, w, h}; }
  Rect corner_right(int w, int h) const { return Rect{this->width - this->edge - w, this->corner_bottom - h, w, h}; }
  // The temperature badge: a circle in the bottom-right corner.
  Rect badge() const { return this->corner_right(this->px(42), this->px(42)); }

  static SizeClass classify(int w, int h) {
    if (w <= 0 || h <= 0)
      return SizeClass::STANDARD;
    const float aspect = (float) w / (float) h;
    if (aspect >= 1.6f)
      return SizeClass::WIDE;
    if (aspect >= 1.2f)
      return SizeClass::STANDARD;
    if (aspect >= 0.84f)
      return SizeClass::SQUARE;
    return SizeClass::TALL;
  }

  static Layout compute(int w, int h) {
    Layout l;
    l.width = w;
    l.height = h;
    l.size_class = classify(w, h);
    l.unit = std::max(1, std::min(w, h)) / 240.0f;
    l.screen = Rect{0, 0, w, h};
    l.stage = l.screen;

    // Dock: a panel over the bottom of the stage, 108 tall, 6 in from the
    // sides and 4 up from the bottom.
    const int dock_h = l.px(108);
    l.dock = Rect{l.px(6), h - l.px(4) - dock_h, w - 2 * l.px(6), dock_h};

    l.header = Rect{0, 0, w, l.px(40)};
    l.back = Rect{0, 0, l.px(60), l.header.h};
    const int app_y = l.header.h + l.px(2);
    l.content = Rect{l.px(14), app_y, w - 2 * l.px(14), h - app_y - l.px(14)};

    l.grid_cols = l.size_class == SizeClass::WIDE ? 3 : 2;
    l.grid_rows = l.size_class == SizeClass::TALL ? 3 : 2;
    l.gap = l.px(8);
    const int board_y = l.header.h + l.px(8);
    l.board = Rect{l.px(16), board_y, w - 2 * l.px(16), h - board_y - l.px(20)};
    l.dots_y = h - l.px(14);

    // Bottom band: the info line, 18 high and 6 up from the bottom, runs
    // between the side margins. The two corners stand on one line 4 above
    // it. This stays the same with the line off, empty or at the top.
    l.edge = l.px(6);
    const int info_h = l.px(18);
    l.info = Rect{l.edge, h - l.px(6) - info_h, w - 2 * l.edge, info_h};
    // At the top: right of the voice timer, to the right margin.
    l.info_top = Rect{l.px(60), l.px(4), w - l.px(60) - l.edge, info_h};
    l.corner_bottom = l.info.y - l.px(4);
    l.upper = Rect{0, 0, w, l.corner_bottom};
    return l;
  }
};

}  // namespace Daruma
