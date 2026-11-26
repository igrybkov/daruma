// Host test of the quick panel's grid (daruma_menu/quick_grid.h).
//
//   c++ -std=c++17 -Wall -Wextra -I src tests/test_quick_grid.cpp -o /tmp/test_quick_grid && /tmp/test_quick_grid

#include <cstdio>
#include <cstring>

#include "esphome/components/daruma_menu/quick_grid.h"

using namespace Daruma;

static int failures = 0;

#define CHECK(cond) \
  do { \
    if (!(cond)) { \
      std::printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond); \
      failures++; \
    } \
  } while (0)

static void grid() {
  // 320 wide, 8 px pad, cells of at least 74: four columns of 76.
  const QuickGrid g = quick_grid(320, 5, 74, 70, 8, 2, 14);
  CHECK(g.pad == 8);
  CHECK(g.cols == 4);
  CHECK(g.cell_w == 76);
  CHECK(g.cell_h == 70);
  // Five tiles need two rows: 8 + 2 * 70 + 14.
  CHECK(g.rows == 2);
  CHECK(g.height == 162);
  CHECK(g.per_page() == 8);
  // Four tiles fit one row: the panel is one row tall.
  const QuickGrid one = quick_grid(320, 4, 74, 70, 8, 2, 14);
  CHECK(one.rows == 1);
  CHECK(one.height == 92);
  // Twenty tiles still stop at max_rows; the rest go on more pages.
  const QuickGrid many = quick_grid(320, 20, 74, 70, 8, 2, 14);
  CHECK(many.rows == 2);
  CHECK(many.per_page() == 8);
  // Nothing to show: one empty row, no division by zero.
  const QuickGrid none = quick_grid(0, 0, 0, 70, 8, 0, 0);
  CHECK(none.cols == 1);
  CHECK(none.rows == 1);
  CHECK(none.cell_w == 0);
  CHECK(none.height == 78);
  // A wide screen fits more columns.
  CHECK(quick_grid(480, 5, 74, 70, 8, 2, 14).cols == 6);
  // Cells one pixel wide: one column per pixel.
  CHECK(quick_grid(10, 3, 1, 70, 0, 2, 0).cols == 10);
}

static void pages() {
  CHECK(quick_pages(0, 8) == 1);
  CHECK(quick_pages(8, 8) == 1);
  CHECK(quick_pages(9, 8) == 2);
  CHECK(quick_pages(16, 8) == 2);
  CHECK(quick_pages(17, 8) == 3);
  // One tile a page: a page per tile.
  CHECK(quick_pages(3, 1) == 3);
}

static void taps() {
  const QuickGrid g = quick_grid(320, 5, 74, 70, 8, 2, 14);
  // The first cell starts at the pad.
  CHECK(quick_slot_at(g, 8, 8) == 0);
  CHECK(quick_slot_at(g, 7, 20) == -1);
  CHECK(quick_slot_at(g, 20, 7) == -1);
  CHECK(quick_slot_at(g, 83, 77) == 0);
  CHECK(quick_slot_at(g, 84, 8) == 1);
  CHECK(quick_slot_at(g, 8, 78) == 4);
  CHECK(quick_slot_at(g, 311, 147) == 7);
  // Past the last column, or under the rows on the handle: no tile.
  CHECK(quick_slot_at(g, 312, 20) == -1);
  CHECK(quick_slot_at(g, 20, 148) == -1);
  // A grid with no width hits nothing.
  CHECK(quick_slot_at(quick_grid(0, 3, 74, 70, 8, 2, 14), 8, 8) == -1);
  CHECK(quick_slot_at(quick_grid(320, 3, 74, 0, 8, 2, 14), 8, 8) == -1);
  // Cells of one pixel still hit.
  const QuickGrid tiny = quick_grid(3, 6, 1, 1, 0, 2, 0);
  CHECK(tiny.cell_w == 1);
  CHECK(quick_slot_at(tiny, 1, 0) == 1);
  CHECK(quick_slot_at(tiny, 2, 1) == 5);
}

static void places() {
  const QuickGrid g = quick_grid(320, 5, 74, 70, 8, 2, 14);
  CHECK(quick_slot_cx(g, 0) == 46);
  CHECK(quick_slot_cx(g, 3) == 274);
  CHECK(quick_slot_cx(g, 4) == 46);
  CHECK(quick_slot_top(g, 3) == 8);
  CHECK(quick_slot_top(g, 4) == 78);
}

static void label_room() {
  // A neighbour with a short label leaves half of what it does not use.
  CHECK(quick_spare(76, 40) == 18);
  CHECK(quick_spare(76, 90) == 0);
  // An empty slot: the whole half slot.
  CHECK(quick_spare(76, 0) == 38);
  // The smaller side counts twice, less the gap.
  CHECK(quick_label_room(76, 18, 8, 4) == 88);
  CHECK(quick_label_room(76, 8, 18, 4) == 88);
  CHECK(quick_label_room(0, 0, 0, 4) == 0);
}

static void label_lines() {
  // Ten pixels a letter.
  auto width = [](const std::string &s) { return (int) s.size() * 10; };
  auto lines = quick_label_lines("Sounds", 60, width);
  CHECK(lines.size() == 1);
  CHECK(lines[0] == "Sounds");
  // Too wide: split at the last space whose first line fits.
  lines = quick_label_lines("Do not disturb", 80, width);
  CHECK(lines.size() == 2);
  CHECK(lines[0] == "Do not");
  CHECK(lines[1] == "disturb");
  lines = quick_label_lines("Do not disturb", 50, width);
  CHECK(lines.size() == 2);
  CHECK(lines[0] == "Do");
  CHECK(lines[1] == "not disturb");
  // Exactly the room: still one line.
  lines = quick_label_lines("Do not", 60, width);
  CHECK(lines.size() == 1);
  // A first line exactly the room fits.
  lines = quick_label_lines("Do not disturb", 60, width);
  CHECK(lines.size() == 2);
  CHECK(lines[0] == "Do not");
  // A one-letter first word.
  lines = quick_label_lines("A bcdef", 30, width);
  CHECK(lines.size() == 2);
  CHECK(lines[0] == "A");
  // Two spaces in a row: each one is tried.
  lines = quick_label_lines("ab  cdefgh", 25, width);
  CHECK(lines.size() == 2);
  CHECK(lines[0] == "ab");
  // One long word, or no first line that fits: one line, for the caller to shorten.
  CHECK(quick_label_lines("Temperature", 60, width).size() == 1);
  CHECK(quick_label_lines("Doing it", 30, width).size() == 1);
  CHECK(quick_label_lines(" lead", 30, width).size() == 1);
}

static void words() {
  CHECK(std::strcmp(quick_value_word(true, false), "on") == 0);
  CHECK(std::strcmp(quick_value_word(false, false), "off") == 0);
  CHECK(std::strcmp(quick_value_word(false, true), "held") == 0);
  // Turned on again during Do not disturb: on wins.
  CHECK(std::strcmp(quick_value_word(true, true), "on") == 0);
}

int main() {
  grid();
  pages();
  taps();
  places();
  label_room();
  label_lines();
  words();
  if (failures == 0)
    std::printf("ok\n");
  return failures == 0 ? 0 : 1;
}
