#pragma once

// The Settings page's rows without drawing: how many fit, which row a tap
// hits, how far a swipe scrolls and what each row says. Plain C++ with no
// ESPHome includes, so a host test can check it (tests/test_settings.cpp).

#include <algorithm>
#include <string>

namespace Daruma {

// Where the rows go inside the app area, in app-area coordinates.
struct SettingsRows {
  int top{0};    // The first row's top.
  int row_h{0};  // One row.
  int rows{0};   // Rows that fit.
};

// As many rows as fit with air around the text (at least `min_row_h` each),
// then the rest shared out so the last row ends at the bottom.
inline SettingsRows settings_rows(int height, int pad, int min_row_h) {
  SettingsRows r;
  const int inner = std::max(0, height - 2 * pad);
  r.top = pad;
  r.rows = std::max(1, inner / std::max(1, min_row_h));
  r.row_h = inner / r.rows;
  return r;
}

// The first row shown, kept inside the list: no blank rows at the end.
inline int settings_clamp_first(int first, int count, int rows) { return std::max(0, std::min(first, count - rows)); }

// The row index under app-area `y`, or -1 for none.
inline int settings_row_at(int y, const SettingsRows &r, int first, int count) {
  if (r.row_h <= 0 || y < r.top)
    return -1;
  const int k = (y - r.top) / r.row_h;
  if (k >= r.rows)
    return -1;
  const int index = first + k;
  return index < count ? index : -1;
}

// One swipe moves a page less one row, so the last row stays in sight.
inline int settings_page_step(int rows) { return std::max(1, rows - 1); }

// The theme word a row's value shows: "on", "off", or "held" while
// something else keeps it off.
inline const char *settings_value_word(bool on, bool held) {
  if (held && !on)
    return "held";
  return on ? "on" : "off";
}

}  // namespace Daruma
