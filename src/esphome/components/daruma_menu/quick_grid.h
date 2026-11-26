#pragma once

// The quick panel's grid without drawing: how many tiles fit in a row, how
// tall the panel is, which tile a tap hits and where each tile goes. Plain
// C++ with no ESPHome includes, so a host test can check it
// (tests/test_quick_grid.cpp).

#include <algorithm>
#include <string>
#include <vector>

namespace Daruma {

// The panel hangs from the top of the screen. All sizes in screen pixels.
// quick_grid() fills every field.
struct QuickGrid {
  int pad;     // Space at the left, the right and above the first row.
  int cols;    // Tiles in a row.
  int rows;    // Rows on a page.
  int cell_w;  // One tile's slot.
  int cell_h;
  int height;  // The whole panel, with the room left under the rows.

  int per_page() const { return this->cols * this->rows; }
};

// As many columns as fit cells of at least `min_cell_w`, and as many rows
// as the tiles need, `max_rows` at most. Every page keeps the first page's
// rows, so the panel stays one height while it pages. `bottom` is the room
// under the rows (the handle).
inline QuickGrid quick_grid(int width, int count, int min_cell_w, int cell_h, int pad, int max_rows, int bottom) {
  QuickGrid g;
  g.pad = pad;
  const int inner = std::max(0, width - 2 * pad);
  g.cols = std::max(1, inner / std::max(1, min_cell_w));
  g.cell_w = inner / g.cols;
  g.cell_h = cell_h;
  const int first_page = std::min(count, g.cols * max_rows);
  g.rows = std::max(1, (first_page + g.cols - 1) / g.cols);
  g.height = pad + g.rows * cell_h + bottom;
  return g;
}

// `per_page` comes from QuickGrid::per_page(), always 1 or more.
inline int quick_pages(int count, int per_page) { return std::max(1, (count + per_page - 1) / per_page); }

// The slot on the page under (x, y), or -1 for none. A tap under the rows
// (on the handle) hits no tile.
inline int quick_slot_at(const QuickGrid &g, int x, int y) {
  if (g.cell_w <= 0 || g.cell_h <= 0 || x < g.pad || y < g.pad)
    return -1;
  const int col = (x - g.pad) / g.cell_w;
  const int row = (y - g.pad) / g.cell_h;
  if (col >= g.cols || row >= g.rows)
    return -1;
  return row * g.cols + col;
}

// A slot's center column and its top.
inline int quick_slot_cx(const QuickGrid &g, int slot) { return g.pad + (slot % g.cols) * g.cell_w + g.cell_w / 2; }
inline int quick_slot_top(const QuickGrid &g, int slot) { return g.pad + (slot / g.cols) * g.cell_h; }

// The room a tile's label may take: its slot, plus what both neighbours in
// the row leave free, as the dock does. `left` and `right` are the spare
// room on each side: quick_spare() of a neighbour (an empty slot has a
// label 0 wide), or the pad at the edge.
inline int quick_spare(int cell_w, int label_w) { return std::max(0, (cell_w - label_w) / 2); }
inline int quick_label_room(int cell_w, int left, int right, int gap) {
  return std::max(0, cell_w + 2 * std::min(left, right) - gap);
}

// A label on one line when it fits `room`, else split at the last space
// that lets the first line fit ("Do not" / "disturb"). A single long word
// stays one line; the caller shortens it. `width` measures a string.
template<typename Width> std::vector<std::string> quick_label_lines(const std::string &label, int room, Width width) {
  if (width(label) <= room)
    return {label};
  for (size_t i = label.rfind(' '); i != std::string::npos && i > 0; i = label.rfind(' ', i - 1)) {
    std::string first = label.substr(0, i);
    if (width(first) <= room)
      return {first, label.substr(i + 1)};
  }
  return {label};
}

// The theme word a tile's value shows: "on", "off", or "held" while
// something else keeps it off (Do not disturb holds Sounds).
inline const char *quick_value_word(bool on, bool held) {
  if (held && !on)
    return "held";
  return on ? "on" : "off";
}

}  // namespace Daruma
