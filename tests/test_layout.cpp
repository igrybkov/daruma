// Host test of the screen layout (layout.h), the pomodoro plaque
// (plaque.h), where the eyes persona's looks sit (daruma_eyes/eye_reach.h),
// the focus ring (focus.h) and the frame scheduler (profile.h).
//
//   c++ -std=c++17 -Wall -Wextra -I components/daruma \
//       tests/test_layout.cpp -o /tmp/test_layout && /tmp/test_layout
//
// With --json it prints the layouts of the preview sizes instead, for
// tests/preview_screens.py, so the previews use this same math.
// With --plaque W H SLOTS DIGIT_W CAP it prints both plaques for that
// screen, goal and timer font (tests/preview_line.py). With
// --eyes W H [--before] it prints each look's eyes at both ends of the
// glance (--before: all centered in layout.upper, as they used to be).

#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <cstring>

#include "../daruma_eyes/eye_reach.h"
#include "focus.h"
#include "layout.h"
#include "plaque.h"
#include "profile.h"

using namespace Daruma;

static int failures = 0;

#define CHECK(cond)                                                \
  do {                                                             \
    if (!(cond)) {                                                 \
      std::printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond);  \
      failures++;                                                  \
    }                                                              \
  } while (0)

#define CHECK_RECT(r, X, Y, W, H) CHECK((r) == (Rect{X, Y, W, H}))

// 320x240 must give back every number the UI used before the layout existed.
static void test_design_size() {
  const Layout l = Layout::compute(320, 240);
  CHECK(l.size_class == SizeClass::STANDARD);
  CHECK(l.unit == 1.0f);
  CHECK_RECT(l.stage, 0, 0, 320, 240);
  // Dock: DOCK_TOP 128, 6 from the sides, 4 from the bottom.
  CHECK_RECT(l.dock, 6, 128, 308, 108);
  // HEADER_H 40, the back arrow's tap zone x < 60.
  CHECK_RECT(l.header, 0, 0, 320, 40);
  CHECK_RECT(l.back, 0, 0, 60, 40);
  // App area (14, HEADER_H + 2, W - 28, H - y - 14).
  CHECK_RECT(l.content, 14, 42, 292, 184);
  // The 2x2 board: 140x82 tiles at x 16/164 and y 48/138.
  CHECK(l.grid_cols == 2 && l.grid_rows == 2);
  CHECK_RECT(l.tile(0), 16, 48, 140, 82);
  CHECK_RECT(l.tile(1), 164, 48, 140, 82);
  CHECK_RECT(l.tile(2), 16, 138, 140, 82);
  CHECK_RECT(l.tile(3), 164, 138, 140, 82);
  CHECK(l.dots_y == 226);
  // Bottom band: the info line between the 6 px margins, 6 up; both
  // corners stand 4 above it. The badge is 42 across in the right corner.
  CHECK(l.edge == 6 && l.corner_bottom == 212);
  CHECK_RECT(l.info, 6, 216, 308, 18);
  CHECK_RECT(l.info_top, 60, 4, 254, 18);
  CHECK_RECT(l.upper, 0, 0, 320, 212);
  CHECK_RECT(l.badge(), 272, 170, 42, 42);
  CHECK_RECT(l.corner_left(78, 50), 6, 162, 78, 50);
  // Bubbles at H - 8 and H - 12; captions at H - 36; dock buttons r 26 at
  // dock top + 52.
  CHECK(l.height - l.px(12) == 228 && l.height - l.px(36) == 204);
  CHECK(l.dock.y + l.px(52) == 180 && l.px(26) == 26);
  // Hits: the old board_tile_ and dock_slot_ answers.
  CHECK(l.tile_at(20, 50) == 0 && l.tile_at(200, 200) == 3);
  CHECK(l.tile_at(158, 60) == -1);  // The gap between tiles.
  CHECK(l.tile_at(10, 50) == -1);
}

static void test_other_sizes() {
  const Layout wide = Layout::compute(480, 272);
  CHECK(wide.size_class == SizeClass::WIDE);
  CHECK(wide.grid_cols == 3 && wide.grid_rows == 2);
  CHECK(wide.tiles_per_page() == 6);
  CHECK(wide.dock.bottom() == 272 - wide.px(4));
  CHECK(wide.header.h == 45);
  // Six tiles fit the board and do not overlap.
  for (int i = 0; i < 6; i++) {
    const Rect t = wide.tile(i);
    CHECK(t.x >= wide.board.x && t.right() <= wide.board.right());
    CHECK(t.y >= wide.board.y && t.bottom() <= wide.board.bottom());
    CHECK(t.w > 100 && t.h > 60);
    if (i % 3 != 2)
      CHECK(wide.tile(i + 1).x >= t.right());
  }

  const Layout small_wide = Layout::compute(320, 170);
  CHECK(small_wide.size_class == SizeClass::WIDE);
  CHECK(small_wide.px(40) == 28);
  CHECK(small_wide.content.bottom() <= 170);

  const Layout square = Layout::compute(240, 240);
  CHECK(square.size_class == SizeClass::SQUARE);
  CHECK(square.grid_cols == 2);
  CHECK(square.unit == 1.0f);
  CHECK(square.tile(1).right() <= 240 - square.px(16));

  const Layout tall = Layout::compute(240, 320);
  CHECK(tall.size_class == SizeClass::TALL);
  CHECK(tall.grid_cols == 2 && tall.grid_rows == 3);
  CHECK(tall.tile(5).bottom() <= tall.board.bottom());
}

// The two corners mirror each other and keep clear of each other and of
// the info line, at every preview size and the worst goal.
static void test_corners() {
  static const int SIZES[][2] = {{320, 240}, {480, 272}, {240, 240}, {320, 170}};
  for (const auto &size : SIZES) {
    const Layout l = Layout::compute(size[0], size[1]);
    const Rect badge = l.badge();
    CHECK(badge.bottom() == l.corner_bottom);
    CHECK(badge.x >= 0 && l.width - badge.right() == l.edge);
    CHECK(l.info.x == l.edge && l.width - l.info.right() == l.edge);
    CHECK(l.info.y > l.corner_bottom && l.info.bottom() < l.height);
    CHECK(l.upper.bottom() == l.corner_bottom);
    for (int slots = 1; slots <= PLAQUE_MAX_SLOTS; slots++) {
      const TomatoPlaque t = TomatoPlaque::compute(l, slots);
      CHECK(t.rect.x == l.edge && t.rect.bottom() == badge.bottom());
      CHECK(t.rect.right() < badge.x && t.rect.y > l.header.bottom());
      CHECK(t.rect.intersected(l.info).empty());
      // Every tomato inside its plaque.
      for (int i = 0; i < slots; i++) {
        int x, y;
        t.center(i, &x, &y);
        CHECK(x - t.r >= t.rect.x && x + t.r <= t.rect.right());
        CHECK(y - t.r - t.r / 2 >= t.rect.y && y + t.r <= t.rect.bottom());
      }
      // Timer font metrics as on the BOX-3 (22 px Manrope bold) and larger.
      const TimerPlaque p = TimerPlaque::compute(l, l.px(14), l.px(16), slots);
      CHECK(p.rect.x == l.edge && p.rect.bottom() == badge.bottom());
      CHECK(p.rect.right() < badge.x);
      CHECK(p.digits_x >= p.rect.x + p.pad && p.digits_x + p.digits_w() <= p.rect.right() - p.pad);
      CHECK(p.rows <= 2);
      // The pause tab: on the top edge, inside the plaque's width, clear of
      // the digits, and no higher than three rows of tomatoes.
      const Rect tab = p.pause_tab();
      CHECK(tab.x >= p.rect.x && tab.right() <= p.rect.right());
      CHECK(tab.y < p.rect.y && tab.bottom() > p.rect.y && tab.bottom() <= p.digits_top);
      CHECK(tab.y >= TomatoPlaque::compute(l, Eyes::CLEAR_SLOTS).rect.y && tab.y > l.header.bottom());
      CHECK(tab.h - 2 * p.tab_bar >= 4 && 3 * p.tab_bar <= tab.w - tab.h);
      for (int i = 0; i < slots; i++) {
        int x, y;
        p.dot(i, slots, &x, &y);
        CHECK(x - p.dot_r >= p.rect.x && x + p.dot_r <= p.rect.right());
        CHECK(y - p.dot_r > p.baseline && y + p.dot_r < p.rect.bottom());
      }
    }
  }
  // A goal of 8: three rows of three tomatoes, one row of eight dots. The
  // plaque ends left of x 80, where the eyes persona's left eye rests.
  const Layout l = Layout::compute(320, 240);
  const TomatoPlaque t = TomatoPlaque::compute(l, 8);
  CHECK(t.per_row == 3 && t.rows == 3);
  CHECK_RECT(t.rect, 6, 140, 72, 72);
  CHECK(t.rect.right() < 80);
  const TimerPlaque p = TimerPlaque::compute(l, 14, 16, 8);
  CHECK(p.per_row == 8 && p.rows == 1);
  // Digit cells are fixed: "11:11" and "00:00" put each digit in one place.
  CHECK(p.digit_cx(1) - p.digit_cx(0) == 14 && p.digit_cx(2) - p.digit_cx(1) == 14 + 8);
  CHECK(TimerPlaque::compute(l, 14, 16, 15).rows == 2);
}

// No look of the eyes persona, at either end of its glance, meets a plaque of
// a goal up to 9 (tomatoes or the timer with its pause tab), the badge or
// the info line, and none leaves the top of the screen.
static void test_eyes() {
  static const int SIZES[][2] = {{320, 240}, {480, 272}, {240, 240}, {320, 170}, {240, 320}};
  for (const auto &size : SIZES) {
    const Layout l = Layout::compute(size[0], size[1]);
    Rect corners[2 + 2 * PLAQUE_MAX_SLOTS];
    int n = 0;
    corners[n++] = l.badge();
    corners[n++] = l.info;
    for (int slots = 1; slots <= PLAQUE_MAX_SLOTS; slots++) {
      if (slots <= Eyes::CLEAR_SLOTS)
        corners[n++] = TomatoPlaque::compute(l, slots).rect;
      const TimerPlaque p = TimerPlaque::compute(l, l.px(14), l.px(16), slots);
      corners[n++] = p.rect.united(p.pause_tab());
    }
    for (int i = 0; i < Eyes::LOOK_COUNT; i++) {
      int cx, cy;
      Eyes::center(l, Eyes::LOOKS[i], &cx, &cy);
      Eyes::Span eyes, wink;
      Eyes::look_reach(Eyes::LOOKS[i], &eyes, &wink);
      for (const Eyes::Span &s : {eyes, wink}) {
        const Rect r = Eyes::on_screen(l, s, cx, cy);
        if (r.empty())
          continue;
        CHECK(r.y >= 0);
        for (int k = 0; k < n; k++) {
          if (!r.intersected(corners[k]).empty())
            std::printf("  %dx%d look %d meets corner %d\n", l.width, l.height, i, k);
          CHECK(r.intersected(corners[k]).empty());
        }
      }
    }
  }
  // 320x240: the resting eyes rise 8 + 3 px of room from upper's center
  // (106); wide screens, where no corner is under the eyes, stay put.
  int cx, cy;
  const Layout l = Layout::compute(320, 240);
  Eyes::center(l, Eyes::LOOKS[0], &cx, &cy);
  CHECK(cx == 160 && cy == 106 - 9);
  const Layout wide = Layout::compute(480, 272);
  for (int i = 0; i < Eyes::LOOK_COUNT; i++) {
    Eyes::center(wide, Eyes::LOOKS[i], &cx, &cy);
    CHECK(cy == wide.upper.cy());
  }
}

static void test_rect_cells() {
  const Rect r{10, 20, 100, 50};
  CHECK_RECT(r.inset(5), 15, 25, 90, 40);
  CHECK_RECT(r.cell(0, 2, 2, 10), 10, 20, 45, 20);
  CHECK_RECT(r.cell(3, 2, 2, 10), 65, 50, 45, 20);
  CHECK(r.cell_at(64, 60, 2, 2, 10) == -1);
  CHECK(r.cell_at(66, 60, 2, 2, 10) == 3);
  CHECK(r.contains(10, 20) && !r.contains(110, 20));
  // Delta boxes: the old and new eye boxes, kept on the stage.
  const Rect a{10, 10, 20, 20}, b{25, 5, 10, 10};
  CHECK_RECT(a.united(b), 10, 5, 25, 25);
  CHECK_RECT(a.united(Rect{}), 10, 10, 20, 20);
  CHECK_RECT(a.intersected(b), 25, 10, 5, 5);
  CHECK(a.intersected(Rect{40, 40, 5, 5}).empty());
}

static void test_focus_ring() {
  FocusRing f;
  CHECK(!f.valid() && !f.next());
  f.set_count(3);
  CHECK(f.index() == 0);
  CHECK(f.next() && f.index() == 1);
  f.next();
  CHECK(f.next() && f.index() == 0);  // Wraps.
  CHECK(f.prev() && f.index() == 2);
  f.set_count(2);  // The list shrank: still a valid item.
  CHECK(f.index() == 1);
  f.set_count(0);
  CHECK(f.index() == -1);

  FocusRing list(false);
  list.set_count(5);
  list.set(4);
  CHECK(!list.next() && list.index() == 4);  // No wrap.
  // A window of 3 rows starting at row 0 must move to show row 4.
  CHECK(list.keep_visible(0, 3) == 2);
  list.set(1);
  CHECK(list.keep_visible(2, 3) == 1);
  CHECK(list.keep_visible(0, 3) == 0);

  // Board paging: six apps, four per page.
  FocusRing board;
  board.set_count(6);
  for (int i = 0; i < 4; i++)
    board.next();
  CHECK(board.index() == 4 && board.page(4) == 1);
  board.next();
  board.next();
  CHECK(board.index() == 0 && board.page(4) == 0);
}

static void test_scheduler() {
  DisplayProfile lcd;
  lcd.min_frame_ms = 100;
  FrameScheduler s;
  s.set_profile(lcd);
  CHECK(!s.due(0, false));
  CHECK(s.due(0, true));
  CHECK(s.full_frame());  // The first frame is whole.
  s.drawn(0, true);
  CHECK(!s.due(50, true));  // Too soon.
  s.invalidate();
  s.invalidate();
  CHECK(!s.due(99, false));
  CHECK(s.due(100, false));  // Two requests, one frame.
  CHECK(!s.full_frame());
  s.drawn(100, false);
  CHECK(!s.pending());

  DisplayProfile eink;
  eink.animate = false;
  eink.min_frame_ms = 5000;
  eink.full_refresh_every = 3;
  CHECK(eink.slow() && !lcd.slow());
  FrameScheduler e;
  e.set_profile(eink);
  e.drawn(0, e.full_frame());
  int fulls = 0;
  for (int i = 1; i <= 6; i++) {
    CHECK(e.due(i * 5000, true));
    const bool full = e.full_frame();
    fulls += full ? 1 : 0;
    e.drawn(i * 5000, full);
  }
  CHECK(fulls == 2);  // Every third frame.

  DisplayProfile no_partial;
  no_partial.partial_refresh = false;
  FrameScheduler n;
  n.set_profile(no_partial);
  n.drawn(0, true);
  CHECK(n.full_frame());
}

static void test_gray() {
  CHECK(quantize_gray(ColorMode::FULL, 10, 20, 30) == -1);
  CHECK(quantize_gray(ColorMode::MONO, 255, 255, 255) == 255);
  CHECK(quantize_gray(ColorMode::MONO, 40, 40, 40) == 0);
  CHECK(quantize_gray(ColorMode::GRAY4, 85, 85, 85) == 85);
  CHECK(quantize_gray(ColorMode::GRAY4, 170, 170, 170) == 170);
  CHECK(quantize_gray(ColorMode::GRAY4, 0, 0, 0) == 0);
}

static void print_rect(const char *name, const Rect &r, bool comma = true) {
  std::printf("\"%s\": [%d, %d, %d, %d]%s", name, r.x, r.y, r.w, r.h, comma ? ", " : "");
}

static void dump_json() {
  static const int SIZES[][2] = {{320, 240}, {480, 272}, {240, 240}, {320, 170}, {240, 320}};
  std::printf("{");
  const int n = sizeof(SIZES) / sizeof(SIZES[0]);
  for (int i = 0; i < n; i++) {
    const Layout l = Layout::compute(SIZES[i][0], SIZES[i][1]);
    std::printf("\"%dx%d\": {\"size_class\": \"%s\", \"unit\": %.6f, \"grid\": [%d, %d], \"gap\": %d, \"dots_y\": %d, ",
                l.width, l.height, size_class_name(l.size_class), l.unit, l.grid_cols, l.grid_rows, l.gap, l.dots_y);
    print_rect("stage", l.stage);
    print_rect("dock", l.dock);
    print_rect("header", l.header);
    print_rect("back", l.back);
    print_rect("info", l.info);
    print_rect("info_top", l.info_top);
    print_rect("upper", l.upper);
    print_rect("badge", l.badge());
    std::printf("\"edge\": %d, \"corner_bottom\": %d, ", l.edge, l.corner_bottom);
    print_rect("content", l.content);
    print_rect("board", l.board);
    std::printf("\"tiles\": [");
    for (int t = 0; t < l.tiles_per_page(); t++) {
      const Rect r = l.tile(t);
      std::printf("[%d, %d, %d, %d]%s", r.x, r.y, r.w, r.h, t + 1 < l.tiles_per_page() ? ", " : "");
    }
    std::printf("]}%s", i + 1 < n ? ", " : "");
  }
  std::printf("}\n");
}

static void dump_plaque(int w, int h, int slots, int digit_w, int cap) {
  const Layout l = Layout::compute(w, h);
  const TomatoPlaque t = TomatoPlaque::compute(l, slots);
  std::printf("{\"tomatoes\": {");
  print_rect("rect", t.rect);
  std::printf("\"r\": %d, \"centers\": [", t.r);
  for (int i = 0; i < std::min(std::max(slots, 1), PLAQUE_MAX_SLOTS); i++) {
    int x, y;
    t.center(i, &x, &y);
    std::printf("%s[%d, %d]", i ? ", " : "", x, y);
  }
  const TimerPlaque p = TimerPlaque::compute(l, digit_w, cap, slots);
  std::printf("]}, \"timer\": {");
  print_rect("rect", p.rect);
  print_rect("digits", p.digits());
  print_rect("pause_tab", p.pause_tab());
  std::printf("\"tab_bar\": %d, ", p.tab_bar);
  std::printf("\"baseline\": %d, \"sep_cx\": %d, \"digit_cx\": [%d, %d, %d, %d], \"dot_r\": %d, \"dots\": [",
              p.baseline, p.sep_cx(), p.digit_cx(0), p.digit_cx(1), p.digit_cx(2), p.digit_cx(3), p.dot_r);
  for (int i = 0; i < std::min(std::max(slots, 1), PLAQUE_MAX_SLOTS); i++) {
    int x, y;
    p.dot(i, slots, &x, &y);
    std::printf("%s[%d, %d]", i ? ", " : "", x, y);
  }
  std::printf("]}}\n");
}

// Each look's eyes and wink on screen, glanced fully left and right.
static void dump_eyes(int w, int h, bool before) {
  const Layout l = Layout::compute(w, h);
  std::printf("{\"looks\": [");
  for (int i = 0; i < Eyes::LOOK_COUNT; i++) {
    const Eyes::Look &look = Eyes::LOOKS[i];
    int cx = l.upper.cx(), cy = l.upper.cy();
    if (!before)
      Eyes::center(l, look, &cx, &cy);
    const Eyes::MoodReach &m = Eyes::MOODS[look.mood];
    const int half = (int) std::lround(m.half * look.lid);
    std::printf("%s{\"mood\": %d, \"cx\": %d, \"cy\": %d, \"glances\": [", i ? ", " : "", look.mood, cx, cy);
    for (int g = 0; g < 2; g++) {
      const int dx = m.moves_x ? look.dx + (g ? Eyes::GLANCE : -Eyes::GLANCE) : 0;
      const int dy = m.moves_y ? look.dy : 0;
      const Rect r = Eyes::on_screen(l, Eyes::Span{m.l + dx, m.cy - half + dy, m.r + dx, m.cy + half + dy}, cx, cy);
      std::printf("%s[%d, %d, %d, %d]", g ? ", " : "", r.x, r.y, r.w, r.h);
    }
    std::printf("]}");
  }
  std::printf("]}\n");
}

int main(int argc, char **argv) {
  if (argc > 1 && std::strcmp(argv[1], "--json") == 0) {
    dump_json();
    return 0;
  }
  if (argc > 6 && std::strcmp(argv[1], "--plaque") == 0) {
    dump_plaque(std::atoi(argv[2]), std::atoi(argv[3]), std::atoi(argv[4]), std::atoi(argv[5]), std::atoi(argv[6]));
    return 0;
  }
  if (argc > 3 && std::strcmp(argv[1], "--eyes") == 0) {
    dump_eyes(std::atoi(argv[2]), std::atoi(argv[3]), argc > 4 && std::strcmp(argv[4], "--before") == 0);
    return 0;
  }
  test_design_size();
  test_other_sizes();
  test_corners();
  test_eyes();
  test_rect_cells();
  test_focus_ring();
  test_scheduler();
  test_gray();
  if (failures == 0)
    std::printf("All layout checks passed\n");
  return failures == 0 ? 0 : 1;
}
