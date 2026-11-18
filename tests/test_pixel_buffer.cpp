// Host test of the desktop build's RAM screen (daruma_desktop/pixel_buffer.h):
// which pixels it keeps, and the rectangle it reports as changed.
//
//   c++ -std=c++17 -Wall -Wextra -I src tests/test_pixel_buffer.cpp \
//       -o /tmp/test_pixel_buffer && /tmp/test_pixel_buffer

#include <cstdio>

#include "esphome/components/daruma_desktop/pixel_buffer.h"

using Daruma::PixelBuffer;

static int failures = 0;

#define CHECK(cond) \
  do { \
    if (!(cond)) { \
      std::printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond); \
      failures++; \
    } \
  } while (0)

static bool area_is(const PixelBuffer::Area &a, int x, int y, int w, int h) {
  return a.x == x && a.y == y && a.w == w && a.h == h;
}

static void test_empty() {
  PixelBuffer none;
  CHECK(none.width() == 0);
  CHECK(none.height() == 0);
  CHECK(area_is(none.take_dirty(), 0, 0, 0, 0));

  PixelBuffer b;
  b.resize(4, 3);
  CHECK(b.width() == 4);
  CHECK(b.height() == 3);
  CHECK(area_is(b.take_dirty(), 0, 0, 0, 0));
  for (int y = 0; y < 3; y++)
    for (int x = 0; x < 4; x++)
      CHECK(b.at(x, y) == 0);
}

static void test_one_pixel() {
  PixelBuffer b;
  b.resize(4, 3);
  b.set(2, 1, 0xF800);
  CHECK(b.at(2, 1) == 0xF800);
  // Row-major: the pixel is at 1 * 4 + 2.
  CHECK(b.data()[6] == 0xF800);
  CHECK(area_is(b.take_dirty(), 2, 1, 1, 1));
  // Taken: nothing is left.
  CHECK(area_is(b.take_dirty(), 0, 0, 0, 0));
  // The pixel stays.
  CHECK(b.at(2, 1) == 0xF800);
}

static void test_corners() {
  PixelBuffer b;
  b.resize(4, 3);
  b.set(0, 0, 1);
  CHECK(area_is(b.take_dirty(), 0, 0, 1, 1));
  b.set(3, 2, 2);
  CHECK(area_is(b.take_dirty(), 3, 2, 1, 1));
  b.set(3, 0, 3);
  b.set(0, 2, 4);
  CHECK(area_is(b.take_dirty(), 0, 0, 4, 3));
  CHECK(b.at(0, 0) == 1);
  CHECK(b.at(3, 2) == 2);
  CHECK(b.at(3, 0) == 3);
  CHECK(b.at(0, 2) == 4);
}

static void test_grows_each_way() {
  PixelBuffer b;
  b.resize(8, 8);
  b.set(4, 4, 1);
  b.set(5, 4, 1);
  CHECK(area_is(b.take_dirty(), 4, 4, 2, 1));
  b.set(4, 4, 1);
  b.set(3, 4, 1);
  CHECK(area_is(b.take_dirty(), 3, 4, 2, 1));
  b.set(4, 4, 1);
  b.set(4, 6, 1);
  CHECK(area_is(b.take_dirty(), 4, 4, 1, 3));
  b.set(4, 4, 1);
  b.set(4, 1, 1);
  CHECK(area_is(b.take_dirty(), 4, 1, 1, 4));
}

static void test_outside_is_dropped() {
  PixelBuffer b;
  b.resize(4, 3);
  b.set(-1, 0, 7);
  b.set(0, -1, 7);
  b.set(4, 0, 7);
  b.set(0, 3, 7);
  CHECK(area_is(b.take_dirty(), 0, 0, 0, 0));
  for (int y = 0; y < 3; y++)
    for (int x = 0; x < 4; x++)
      CHECK(b.at(x, y) == 0);
}

static void test_resize_clears() {
  PixelBuffer b;
  b.resize(2, 2);
  b.set(1, 1, 9);
  b.resize(3, 2);
  CHECK(area_is(b.take_dirty(), 0, 0, 0, 0));
  CHECK(b.at(1, 1) == 0);
}

int main() {
  test_empty();
  test_one_pixel();
  test_corners();
  test_grows_each_way();
  test_outside_is_dropped();
  test_resize_clears();
  if (failures)
    std::printf("%d failures\n", failures);
  return failures ? 1 : 0;
}
