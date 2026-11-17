#pragma once

// Where each part of a prompt card goes, from the hub's Layout and the
// fonts' line heights, and what a tap on it does. Plain C++, so a host test
// and the preview tool use the same rectangles as the device
// (tests/test_prompts.cpp, prompt_geometry.cpp).
//
// The card starts as the app area inset by 8 design pixels
// (layout.content.inset(px(8))), so a tap around it dismisses. When the
// text and buttons need more height, it grows evenly up and down, at most
// to 6 design pixels from the screen's edges.

#include <algorithm>
#include <vector>

#include "esphome/components/daruma/gesture.h"
#include "esphome/components/daruma/layout.h"
#include "prompt_stack.h"

namespace Daruma {

struct PromptGeometry {
  int unit_px{1};             // A scaled step, for paddings and radii.
  int border{2};              // Card border thickness.
  Rect card;                  // The card. A tap outside it dismisses.
  Rect title;                 // Title line; h = 0 without a title.
  Rect body;                  // Wrapped text goes here; h may be 0.
  Rect bar;                   // Countdown bar; h = 0 without a countdown.
  std::vector<Rect> options;  // One per option on screen (list: per visible row).
  int first{0};               // List: the option in the first row.
  Rect scroll;                // List: the scroll track; w = 0 when all rows fit.
};

struct PromptMetrics {
  int title_line{27};  // Line height of the title font.
  int text_line{23};   // Line height of the text font.
};

namespace prompt_layout {

// The card's sides and padding. Width does not depend on the content, so
// the controller can wrap the body to inner_width() before asking for a card.
struct Frame {
  int border;
  int pad;
};
inline Frame frame_of(const Layout &l, bool urgent) {
  const int border = urgent ? l.px(5) : l.px(3);
  return Frame{border, border + l.px(8)};
}
inline Rect base_card(const Layout &l) { return l.content.inset(l.px(8)); }
inline int inner_width(const Layout &l, bool urgent) { return base_card(l).w - 2 * frame_of(l, urgent).pad; }

// A card `inner_h` tall inside, centered on the base card, kept on screen.
inline PromptGeometry card(const Layout &l, bool urgent, int inner_h, int *top, int *bottom, int *left, int *right) {
  PromptGeometry g;
  g.unit_px = std::max(1, l.px(6));
  const Frame f = frame_of(l, urgent);
  g.border = f.border;
  Rect c = base_card(l);
  const int want = inner_h + 2 * f.pad;
  if (want > c.h) {
    const Rect most = l.screen.inset(c.x, l.px(6));
    const int h = std::min(want, most.h);
    c.y = std::max(most.y, std::min(c.cy() - h / 2, most.bottom() - h));
    c.h = h;
  }
  g.card = c;
  *left = c.x + f.pad;
  *right = c.right() - f.pad;
  *top = c.y + f.pad;
  *bottom = c.bottom() - f.pad;
  return g;
}

// The title line at the top, the countdown bar at the bottom.
struct Chrome {
  int title_h;  // Title line plus the gap under it; 0 without.
  int bar_h;    // Bar plus the gap over it; 0 without.
};
inline Chrome chrome(const Layout &l, int title_line, bool has_title, bool has_bar) {
  return Chrome{has_title ? title_line + l.px(3) : 0, has_bar ? l.px(5) + l.px(6) : 0};
}
inline void place_chrome(const Layout &l, PromptGeometry &g, int title_line, bool has_title, bool has_bar, int *top,
                         int *bottom, int left, int right) {
  if (has_bar) {
    const int bar_h = l.px(5);
    g.bar = Rect{left, *bottom - bar_h, right - left, bar_h};
    *bottom = g.bar.y - l.px(6);
  }
  if (has_title) {
    g.title = Rect{left, *top, right - left, title_line};
    *top = g.title.bottom() + l.px(3);
  }
}

// A row of n equal buttons across [left, right), ending at `bottom`.
inline void button_row(std::vector<Rect> &out, int n, int left, int right, int bottom, int h, int gap, int max_w) {
  if (n <= 0)
    return;
  int w = (right - left - gap * (n - 1)) / n;
  w = std::min(w, max_w);
  const int total = w * n + gap * (n - 1);
  const int x0 = left + (right - left - total) / 2;
  for (int i = 0; i < n; i++)
    out.push_back(Rect{x0 + i * (w + gap), bottom - h, w, h});
}

// Title, wrapped body (body_lines lines of the text font), and 0-3 buttons
// in a row at the bottom.
inline PromptGeometry message(const Layout &l, const PromptMetrics &m, int n_options, int body_lines, bool urgent,
                              bool has_title, bool has_bar) {
  const Chrome ch = chrome(l, m.title_line, has_title, has_bar);
  const int button_h = m.text_line + l.px(18);
  const int buttons = n_options > 0 ? button_h + l.px(8) : 0;
  const int need = ch.title_h + body_lines * m.text_line + buttons + ch.bar_h;
  int top, bottom, left, right;
  PromptGeometry g = card(l, urgent, need, &top, &bottom, &left, &right);
  place_chrome(l, g, m.title_line, has_title, has_bar, &top, &bottom, left, right);
  if (n_options > 0) {
    button_row(g.options, n_options, left, right, bottom, button_h, l.px(8), right - left);
    bottom -= buttons;
  }
  g.body = Rect{left, top, right - left, std::max(0, bottom - top)};
  return g;
}

// A question (body_lines lines of the text font) over a 2x2 grid of
// answers, then a row of small extra buttons for options past the fourth.
// The title is a small header line in the text font, so the question gets
// the room.
inline PromptGeometry choice(const Layout &l, const PromptMetrics &m, int n_options, int body_lines, bool urgent,
                             bool has_title, bool has_bar) {
  const Chrome ch = chrome(l, m.text_line, has_title, has_bar);
  const int gap = l.px(6);
  const int extras = std::max(0, n_options - 4);
  const int extra_h = m.text_line + l.px(6);
  const int cells = std::min(n_options, 4);
  const int rows = (cells + 1) / 2;
  const int cell_h = m.text_line + l.px(10);
  const int grid_h = rows * cell_h + (rows - 1) * gap;
  const int need =
      ch.title_h + std::max(1, body_lines) * m.text_line + gap + grid_h + (extras > 0 ? extra_h + gap : 0) + ch.bar_h;
  int top, bottom, left, right;
  PromptGeometry g = card(l, urgent, need, &top, &bottom, &left, &right);
  place_chrome(l, g, m.text_line, has_title, has_bar, &top, &bottom, left, right);
  std::vector<Rect> extra;
  if (extras > 0) {
    button_row(extra, extras, left, right, bottom, extra_h, gap, l.px(110));
    bottom -= extra_h + gap;
  }
  const Rect grid{left, bottom - grid_h, right - left, grid_h};
  for (int i = 0; i < cells; i++)
    g.options.push_back(grid.cell(i, 2, rows, gap));
  for (const auto &r : extra)
    g.options.push_back(r);
  g.body = Rect{left, top, right - left, std::max(0, grid.y - gap - top)};
  return g;
}

// Rows of options that scroll. The body, when there is one, takes up to
// `body_lines` lines under the title.
inline PromptGeometry list(const Layout &l, const PromptMetrics &m, int n_options, int focus, int first, int body_lines,
                           bool urgent, bool has_title, bool has_bar) {
  const Chrome ch = chrome(l, m.title_line, has_title, has_bar);
  const int gap = l.px(4);
  const int row_h = m.text_line + l.px(8);
  const int body_h = body_lines > 0 ? body_lines * m.text_line + l.px(6) : 0;
  const int need = ch.title_h + body_h + n_options * (row_h + gap) - gap + ch.bar_h;
  int top, bottom, left, right;
  PromptGeometry g = card(l, urgent, need, &top, &bottom, &left, &right);
  place_chrome(l, g, m.title_line, has_title, has_bar, &top, &bottom, left, right);
  if (body_lines > 0) {
    g.body = Rect{left, top, right - left, body_lines * m.text_line};
    top = g.body.bottom() + l.px(6);
  }
  const int fit = std::max(1, (bottom - top + gap) / (row_h + gap));
  if (n_options > fit) {
    const int track = l.px(4);
    g.scroll = Rect{right - track, top, track, bottom - top};
    right -= track + l.px(6);
  }
  // Keep the focused row on screen, and the last page full.
  if (focus >= 0) {
    if (focus < first)
      first = focus;
    if (focus >= first + fit)
      first = focus - fit + 1;
  }
  first = std::max(0, std::min(first, n_options - fit));
  g.first = first;
  for (int i = first; i < std::min(n_options, first + fit); i++)
    g.options.push_back(Rect{left, top + (i - first) * (row_h + gap), right - left, row_h});
  return g;
}

}  // namespace prompt_layout

// What a tap at (x, y) does to prompt p, drawn as g.
enum class TapAction : uint8_t { NOTHING, CHOOSE, DISMISS };
struct Tap {
  TapAction action{TapAction::NOTHING};
  int index{-1};  // CHOOSE: the option.
};

// - A quiet prompt (an info message with at most one button): any tap
//   dismisses, its button included.
// - A tap on a visible option chooses it.
// - A tap outside the card dismisses.
// - A tap on the card, not on an option, does nothing.
// - Not dismissable: only options count. An answered choice waits for HA,
//   so it may always go.
inline Tap tap_result(const Prompt &p, const PromptGeometry &g, int x, int y) {
  const bool may_dismiss = p.dismissable || p.answered;
  if (p.quiet() && may_dismiss)
    return Tap{TapAction::DISMISS, -1};
  const int first = p.layout == PromptLayout::LIST ? g.first : 0;
  for (size_t r = 0; r < g.options.size(); r++) {
    const int i = first + (int) r;
    if (g.options[r].contains(x, y) && p.mark(i) != Mark::HIDDEN)
      return p.choosable(i) ? Tap{TapAction::CHOOSE, i} : Tap{};
  }
  if (!g.card.contains(x, y) && may_dismiss)
    return Tap{TapAction::DISMISS, -1};
  return Tap{};
}

// When a list last changed page, for the tap rules below.
struct ListScroll {
  bool paged{false};
  uint32_t paged_ms{0};
};

// Taps on a list that scrolls. Scrolling must never choose. The hub calls a
// touch a tap when it saw the finger move less than its slop (20 px), but on
// the device a quick flick can reach it as just touch-down and lift-off: the
// main loop reads the touch screen between frames, and drawing a new page
// keeps it busy for tens of milliseconds. So a flick right after a page
// looked like a tap on the row under it. In a list that scrolls, a tap
// counts only when:
// - it came down LIST_SETTLE_MS or more after the last page change and after
//   the last touch that moved (a swipe that paged, or one that did not),
// - the list did not page while the finger was down,
// - the finger moved LIST_TAP_SLOP or less up or down (the screen's jitter
//   is a pixel or two),
// - it lifted in the row where it came down.
// A list that fits, and the other layouts, take taps as before.
static const uint32_t LIST_SETTLE_MS = 350;
static const int LIST_TAP_SLOP = 10;

// The row (index into g.options) at (x, y), or -1.
inline int row_at(const PromptGeometry &g, int x, int y) {
  for (size_t r = 0; r < g.options.size(); r++) {
    if (g.options[r].contains(x, y))
      return (int) r;
  }
  return -1;
}

inline bool list_tap_holds(const PromptGeometry &g, const TouchTrack &touch, const ListScroll &scroll) {
  if (g.scroll.w == 0)
    return true;
  if (touch.after_drag_ms < LIST_SETTLE_MS)
    return false;
  // Signed: a page change after touch-down comes out negative.
  if (scroll.paged && (int32_t) (touch.down_ms - scroll.paged_ms) < (int32_t) LIST_SETTLE_MS)
    return false;
  if (touch.travel_y > LIST_TAP_SLOP)
    return false;
  return row_at(g, touch.x0, touch.y0) == row_at(g, touch.x, touch.y);
}

// What a finished touch that did not move past the hub's slop does: the tap
// rules above for a list that scrolls, then tap_result() at the point where
// the finger came down.
inline Tap tap_result(const Prompt &p, const PromptGeometry &g, const TouchTrack &touch, const ListScroll &scroll) {
  if (p.layout == PromptLayout::LIST && !list_tap_holds(g, touch, scroll))
    return Tap{};
  return tap_result(p, g, touch.x0, touch.y0);
}

}  // namespace Daruma
