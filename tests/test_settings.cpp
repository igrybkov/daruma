// Host test of the Settings page's rows (daruma_settings/settings_rows.h).
//
//   c++ -std=c++17 -Wall -Wextra -I src tests/test_settings.cpp -o /tmp/test_settings && /tmp/test_settings

#include <cstdio>
#include <cstring>

#include "esphome/components/daruma_settings/settings_rows.h"

using namespace Daruma;

static int failures = 0;

#define CHECK(cond) \
  do { \
    if (!(cond)) { \
      std::printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond); \
      failures++; \
    } \
  } while (0)

static void layout() {
  // 180 px of app area, 6 px pad, rows of at least 40: four rows of 42.
  const SettingsRows r = settings_rows(180, 6, 40);
  CHECK(r.top == 6);
  CHECK(r.rows == 4);
  CHECK(r.row_h == 42);
  // Too short for one row: still one, the whole height.
  const SettingsRows tiny = settings_rows(30, 5, 40);
  CHECK(tiny.rows == 1);
  CHECK(tiny.row_h == 20);
  // Rows of at least one pixel: ten of them in ten pixels.
  CHECK(settings_rows(10, 0, 1).rows == 10);
  // Nothing at all: one empty row, no division by zero.
  const SettingsRows none = settings_rows(0, 5, 0);
  CHECK(none.rows == 1);
  CHECK(none.row_h == 0);
}

static void taps() {
  const SettingsRows r = settings_rows(180, 6, 40);
  CHECK(settings_row_at(5, r, 0, 6) == -1);  // The pad above the rows.
  CHECK(settings_row_at(6, r, 0, 6) == 0);
  CHECK(settings_row_at(47, r, 0, 6) == 0);
  CHECK(settings_row_at(48, r, 0, 6) == 1);
  CHECK(settings_row_at(173, r, 0, 6) == 3);
  CHECK(settings_row_at(174, r, 0, 6) == -1);  // Below the last row that fits.
  // Scrolled by two: the top row is the third setting.
  CHECK(settings_row_at(10, r, 2, 6) == 2);
  // Past the last setting: nothing.
  CHECK(settings_row_at(100, r, 0, 2) == -1);
  CHECK(settings_row_at(50, r, 0, 2) == 1);
  // Before the first draw: all zero, and no row anywhere.
  SettingsRows flat;
  CHECK(flat.top == 0);
  CHECK(flat.row_h == 0);
  CHECK(flat.rows == 0);
  CHECK(settings_row_at(10, flat, 0, 6) == -1);
  // Rows of no height: no row, whatever the count says.
  const SettingsRows zero{0, 0, 3};
  CHECK(settings_row_at(10, zero, 0, 6) == -1);
  // Rows one pixel high: each pixel its own row.
  const SettingsRows thin{0, 1, 10};
  CHECK(settings_row_at(3, thin, 0, 6) == 3);
}

static void scrolling() {
  // Six rows, four fit: the first row shown runs from 0 to 2.
  CHECK(settings_clamp_first(-1, 6, 4) == 0);
  CHECK(settings_clamp_first(1, 6, 4) == 1);
  CHECK(settings_clamp_first(2, 6, 4) == 2);
  CHECK(settings_clamp_first(3, 6, 4) == 2);
  // Fewer rows than fit: always the top.
  CHECK(settings_clamp_first(3, 2, 4) == 0);
  // A swipe keeps one row in sight.
  CHECK(settings_page_step(4) == 3);
  CHECK(settings_page_step(1) == 1);
  CHECK(settings_page_step(0) == 1);
}

static void words() {
  CHECK(std::strcmp(settings_value_word(true, false), "on") == 0);
  CHECK(std::strcmp(settings_value_word(false, false), "off") == 0);
  // Off because something else holds it.
  CHECK(std::strcmp(settings_value_word(false, true), "held") == 0);
  // Turned back on by hand: on, whatever holds it.
  CHECK(std::strcmp(settings_value_word(true, true), "on") == 0);
}

int main() {
  layout();
  taps();
  scrolling();
  words();
  if (failures) {
    std::printf("%d failure(s)\n", failures);
    return 1;
  }
  std::printf("ok\n");
  return 0;
}
