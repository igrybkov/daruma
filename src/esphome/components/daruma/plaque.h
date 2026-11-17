#pragma once

// Geometry of the pomodoro's plaque in the bottom-left corner
// (layout.corner_left). Plain C++, so the host test and the previews use
// the same numbers as the device (tests/test_layout.cpp).
//
// Idle, the plaque holds today's tomatoes (TomatoPlaque). While a focus or
// a break runs or is paused, it holds the timer (TimerPlaque): mm:ss in
// four fixed digit cells, and under it one dot per pomodoro of the goal.
// The timer plaque keeps one size for the whole session, so a tick can
// repaint just its rect. Paused, a tab with a pause sign sits on its top
// edge (pause_tab): above the plaque, never wider, so the digits and the
// colon stay where they are.

#include <algorithm>

#include "layout.h"

namespace Daruma {

// Most slots either plaque shows (goal or done, whichever is more).
static const int PLAQUE_MAX_SLOTS = 15;

struct TomatoPlaque {
  Rect rect;
  int per_row{3};
  int rows{1};
  int step{22};  // Between tomato centers, across and up.
  int r{8};      // Tomato radius.
  int pad{6};

  // Center of tomato i. Rows fill from the bottom up, left to right.
  void center(int i, int *x, int *y) const {
    *x = this->rect.x + this->pad / 2 + this->step / 2 + (i % this->per_row) * this->step;
    *y = this->rect.bottom() - this->pad / 2 - this->step / 2 - (i / this->per_row) * this->step + this->r / 4;
  }

  // Three a row, stacking upward. 22 px apart, so three rows of tomatoes
  // stay clear of the daruma's body and of the eyes persona at rest.
  static TomatoPlaque compute(const Layout &l, int slots) {
    TomatoPlaque p;
    slots = std::min(std::max(slots, 1), PLAQUE_MAX_SLOTS);
    p.step = l.px(22);
    p.r = l.px(8);
    p.pad = l.px(6);
    p.per_row = std::min(slots, 3);
    p.rows = (slots + p.per_row - 1) / p.per_row;
    p.rect = l.corner_left(p.per_row * p.step + p.pad, p.rows * p.step + p.pad);
    return p;
  }
};

struct TimerPlaque {
  Rect rect;
  int pad{6};
  int cell{13};     // Width of one digit cell.
  int sep{8};       // Width of the colon's slot between mm and ss.
  int cap{16};      // Height of the digits.
  int digits_x{0};  // Left of the first digit cell.
  int digits_top{0};
  int baseline{0};  // The digits' baseline.
  int dot_r{3};
  int dot_step{8};
  int per_row{8};
  int rows{1};
  int dots_top{0};  // Top of the first dot row.

  int digits_w() const { return 4 * this->cell + this->sep; }
  // Center x of digit i (0, 1 minutes; 2, 3 seconds).
  int digit_cx(int i) const { return this->digits_x + i * this->cell + (i >= 2 ? this->sep : 0) + this->cell / 2; }
  // Center x of the colon's slot.
  int sep_cx() const { return this->digits_x + 2 * this->cell + this->sep / 2; }
  int digits_cx() const { return this->digits_x + this->digits_w() / 2; }
  // The digits' box, for text that replaces them (minutes on slow screens).
  Rect digits() const { return Rect{this->digits_x, this->digits_top, this->digits_w(), this->cap}; }

  // The pause tab: a pill centered on the top edge, sunk into it a little.
  // Its pause sign: two bars, each tab_bar wide, tab_bar apart, and inset
  // tab_bar from the pill's top and bottom.
  int tab_w{26};
  int tab_h{14};
  int tab_sink{3};
  int tab_bar{3};
  Rect pause_tab() const {
    return Rect{this->rect.cx() - this->tab_w / 2, this->rect.y + this->tab_sink - this->tab_h, this->tab_w,
                this->tab_h};
  }

  // Center of dot i: rows top to bottom, each centered under the digits.
  void dot(int i, int slots, int *x, int *y) const {
    const int row = i / this->per_row;
    const int in_row = std::min(slots - row * this->per_row, this->per_row);
    const int row_w = (in_row - 1) * this->dot_step;
    *x = this->rect.cx() - row_w / 2 + (i % this->per_row) * this->dot_step;
    *y = this->dots_top + this->dot_r + row * this->dot_step;
  }

  // digit_w: the widest digit of the timer font; cap: the digits' height.
  static TimerPlaque compute(const Layout &l, int digit_w, int cap, int slots) {
    TimerPlaque p;
    slots = std::min(std::max(slots, 1), PLAQUE_MAX_SLOTS);
    p.pad = l.px(6);
    p.cell = std::max(digit_w, 1);
    p.sep = l.px(8);
    p.cap = std::max(cap, 1);
    p.dot_r = std::max(l.px(3), 2);
    p.dot_step = 2 * p.dot_r + l.px(2);
    p.per_row = std::min(slots, 8);
    p.rows = (slots + p.per_row - 1) / p.per_row;
    const int dots_w = (p.per_row - 1) * p.dot_step + 2 * p.dot_r + 1;
    const int inner_w = std::max(p.digits_w(), dots_w);
    const int gap = l.px(6);
    const int dots_h = (p.rows - 1) * p.dot_step + 2 * p.dot_r + 1;
    p.rect = l.corner_left(inner_w + 2 * p.pad, p.pad + p.cap + gap + dots_h + p.pad);
    p.digits_x = p.rect.x + (p.rect.w - p.digits_w()) / 2;
    p.digits_top = p.rect.y + p.pad;
    p.baseline = p.digits_top + p.cap;
    p.dots_top = p.digits_top + p.cap + gap;
    p.tab_w = l.px(26);
    p.tab_h = l.px(14);
    p.tab_sink = l.px(3);
    p.tab_bar = std::max(l.px(3), 2);
    return p;
  }
};

}  // namespace Daruma
