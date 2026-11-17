#include "task_view.h"

#include <algorithm>
#include <vector>

#include "esphome/components/daruma/draw.h"
#include "esphome/components/daruma/text.h"
#include "esphome/components/daruma/ui_tree.h"
#include "esphome/core/helpers.h"

namespace Daruma {

using esphome::Color;
using esphome::display::BaseFont;
using esphome::display::Display;
using esphome::display::TextAlign;

// Marks keep their meaning on every theme, so they do not follow it.
static const Color DONE_COLOR(46, 160, 87);
static const Color FLAG_COLOR(245, 124, 0);
static const Color OVERDUE_COLOR(211, 47, 47);
static const Color DUE_TODAY_COLOR(230, 160, 0);

static const int MARK_W = 14;   // One mark (flag or due dot) at the row's end.
static const int SCROLL_W = 4;  // Scroll bar width.

static int text_height(Display &display, BaseFont *font) {
  int x1, y1, width, height;
  display.get_text_bounds(0, 0, "Ag", font, TextAlign::TOP_LEFT, &x1, &y1, &width, &height);
  return height;
}

std::string TaskView::status() const {
  const int open = this->list_->open_count();
  if (open < 0)
    return "";
  if (open == 0)
    return "All done";
  return esphome::str_sprintf("%d left", open);
}

TaskView::Layout TaskView::layout_(const AppView &v, int text_h) const {
  Layout l;
  const int pad = std::max(4, v.w / 48);
  l.left = v.x + pad;
  l.top = v.y + pad;
  l.width = v.w - 2 * pad - SCROLL_W - 4;
  l.height = v.h - 2 * pad;
  // As many rows as fit with a little air around the text, then share out
  // the rest so the last row ends at the bottom.
  l.rows = std::max(1, l.height / (text_h + 14));
  l.row_h = l.height / l.rows;
  return l;
}

int TaskView::total_rows_() const {
  const int extra = this->list_->hidden_open() > 0 ? 1 : 0;  // The "+N more" row.
  return (int) this->list_->items().size() + extra;
}

void TaskView::clamp_scroll_() {
  this->first_ = std::max(0, std::min(this->first_, this->total_rows_() - this->rows_));
}

void TaskView::draw(AppView &v) {
  const int text_h = text_height(v.display, v.text);
  const Layout l = this->layout_(v, text_h);
  this->list_top_ = l.top - v.y;
  this->row_h_ = l.row_h;
  this->rows_ = l.rows;
  this->clamp_scroll_();
  this->focus_.set_count(this->list_->items().size());

  const std::string dots = this->list_->has_glyph(0x2026) ? "…" : "...";
  switch (this->list_->state()) {
    case TaskList::State::EMPTY:
    case TaskList::State::LOADING:
      this->draw_message_(v, "Loading" + dots, text_h);
      break;
    case TaskList::State::FAILED:
      this->draw_message_(v, this->list_->error() + "\nTap to try again", text_h);
      break;
    case TaskList::State::READY: {
      const auto &items = this->list_->items();
      const int hidden = this->list_->hidden_open();
      if (items.empty() && hidden == 0) {
        // Nothing at all today: a big check.
        TaskItem done;
        done.done = true;
        const int r = std::max(12, std::min(v.h / 7, 24));
        const int cy = v.y + v.h / 2 - r / 2;
        this->draw_check_(v, v.x + v.w / 2, cy, r, done);
        v.display.print(v.x + v.w / 2, cy + r + 6 + text_h / 2, v.text, v.theme.ink, TextAlign::CENTER, "All done",
                        v.theme.panel);
        break;
      }
      const int total = this->total_rows_();
      for (int k = 0; k < l.rows && this->first_ + k < total; k++) {
        const int index = this->first_ + k;
        const int y = l.top + k * l.row_h;
        if (index < (int) items.size()) {
          this->draw_row_(v, l, y, items[index], v.focus && index == this->focus_.index());
        } else {
          v.display.print(l.left + l.row_h, y + l.row_h / 2, v.text, v.theme.muted, TextAlign::CENTER_LEFT,
                          esphome::str_sprintf("+%d more", hidden).c_str(), v.theme.panel);
        }
        if (k + 1 < l.rows && index + 1 < total)
          v.display.horizontal_line(l.left + 4, y + l.row_h - 1, l.width - 8, shade(v.theme.panel, 0.88f));
      }
      this->draw_scroll_bar_(v, l);
      break;
    }
  }
  this->draw_notice_(v, text_h);
}

void TaskView::draw_row_(AppView &v, const Layout &l, int y, const TaskItem &item, bool focused) {
  const Theme &t = v.theme;
  const int cy = y + l.row_h / 2;
  UiTree::add("row", item.title, Rect{l.left, y, l.width, l.row_h}, focused, item.done ? "done" : "");
  if (focused) {
    // A ring around the row, in the focus color.
    const int ring = std::max(2, v.px(2));
    const int r = std::min(l.row_h / 2 - 1, v.px(8));
    Utilities::Draw::roundedRectangle(&v.display, l.left, y + 1, l.width, l.row_h - 2, r,
                                      t.on(t.panel, t.focus_color()));
    Utilities::Draw::roundedRectangle(&v.display, l.left + ring, y + 1 + ring, l.width - 2 * ring,
                                      l.row_h - 2 - 2 * ring, std::max(1, r - ring), t.panel);
  }
  const int r = std::max(7, std::min(l.row_h * 27 / 100, 12));
  const int cx = l.left + r + 4;
  this->draw_check_(v, cx, cy, r, item);

  const int marks = (item.flagged ? 1 : 0) + (item.overdue || item.due_today ? 1 : 0);
  const int right = l.left + l.width;
  this->draw_marks_(v, right, cy, item);

  const int tx = cx + r + 10;
  const int max_w = right - marks * MARK_W - tx - 4;
  const std::string title = fit_text(v.display, v.text, item.title, max_w);
  const Color ink = item.done ? t.muted : t.ink;
  v.display.print(tx, cy, v.text, ink, TextAlign::CENTER_LEFT, title.c_str(), t.panel);
  if (item.done) {
    const int w = text_width(v.display, v.text, title);
    v.display.horizontal_line(tx, cy, w, t.muted);
    v.display.horizontal_line(tx, cy + 1, w, t.muted);
  }
}

void TaskView::draw_check_(AppView &v, int cx, int cy, int r, const TaskItem &item) {
  Display &d = v.display;
  const Theme &t = v.theme;
  if (!item.done) {
    // A read-only list gets a lighter ring: tapping it does nothing.
    const Color ring = item.pending || !this->list_->can_check() ? t.muted : t.ink;
    d.circle(cx, cy, r, ring);
    d.circle(cx, cy, r - 1, ring);
    return;
  }
  // Waiting for HA: the check shows, a little faded.
  const Color fill = item.pending ? shade(DONE_COLOR, 0.7f) : DONE_COLOR;
  d.filled_circle(cx, cy, r, fill);
  const int x0 = cx - r * 45 / 100, y0 = cy;
  const int x1 = cx - r * 10 / 100, y1 = cy + r * 38 / 100;
  const int x2 = cx + r * 50 / 100, y2 = cy - r * 35 / 100;
  for (int dy = 0; dy < 2; dy++) {
    d.line(x0, y0 + dy, x1, y1 + dy, Color::WHITE);
    d.line(x1, y1 + dy, x2, y2 + dy, Color::WHITE);
  }
}

void TaskView::draw_marks_(AppView &v, int right, int cy, const TaskItem &item) {
  Display &d = v.display;
  int x = right - MARK_W / 2;
  if (item.overdue || item.due_today) {
    d.filled_circle(x, cy, 4, item.overdue ? OVERDUE_COLOR : DUE_TODAY_COLOR);
    x -= MARK_W;
  }
  if (item.flagged) {
    const int pole = x - 3;
    d.vertical_line(pole, cy - 6, 13, FLAG_COLOR);
    d.filled_triangle(pole + 1, cy - 6, pole + 8, cy - 3, pole + 1, cy, FLAG_COLOR);
  }
}

void TaskView::draw_scroll_bar_(AppView &v, const Layout &l) {
  const int total = this->total_rows_();
  if (total <= l.rows)
    return;
  const int x = l.left + l.width + 4;
  const Color track = shade(v.theme.panel, 0.9f);
  Utilities::Draw::roundedRectangle(&v.display, x, l.top, SCROLL_W, l.height, SCROLL_W / 2, track);
  const int thumb_h = std::max(12, l.height * l.rows / total);
  const int thumb_y = l.top + (l.height - thumb_h) * this->first_ / (total - l.rows);
  Utilities::Draw::roundedRectangle(&v.display, x, thumb_y, SCROLL_W, thumb_h, SCROLL_W / 2, v.theme.muted);
}

void TaskView::draw_message_(AppView &v, const std::string &text, int text_h) {
  const std::vector<std::string> lines = Utilities::Text::wrap(v.display, v.text, text, v.w - 24);
  const int count = std::min((int) lines.size(), 4);
  const int line_h = text_h + 4;
  int y = v.y + v.h / 2 - count * line_h / 2 + line_h / 2;
  for (int i = 0; i < count; i++, y += line_h) {
    v.display.print(v.x + v.w / 2, y, v.text, i == 0 ? v.theme.ink : v.theme.muted, TextAlign::CENTER, lines[i].c_str(),
                    v.theme.panel);
  }
}

// A small pill at the bottom of the app, in the theme's colors swapped.
void TaskView::draw_notice_(AppView &v, int text_h) {
  const std::string &notice = this->list_->notice();
  if (notice.empty())
    return;
  BaseFont *font = v.small != nullptr ? v.small : v.text;
  const std::string text = fit_text(v.display, font, notice, v.w - 36);
  const int h = std::min(text_h + 8, v.h / 4);
  const int w = std::min(text_width(v.display, font, text) + 20, v.w - 16);
  const int x = v.x + (v.w - w) / 2;
  const int y = v.y + v.h - h - 6;
  Utilities::Draw::roundedRectangle(&v.display, x, y, w, h, h / 2, v.theme.ink);
  v.display.print(x + w / 2, y + h / 2, font, v.theme.panel, TextAlign::CENTER, text.c_str(), v.theme.ink);
}

bool TaskView::move_focus_(bool forward) {
  if (this->list_->state() != TaskList::State::READY || this->list_->items().empty())
    return false;  // Nothing to focus: the menu scrolls instead.
  this->focus_.set_count(this->list_->items().size());
  if (forward) {
    this->focus_.next();
  } else {
    this->focus_.prev();
  }
  this->first_ = this->focus_.keep_visible(this->first_, this->rows_);
  this->clamp_scroll_();
  return true;
}

bool TaskView::input(Input input, int /*x*/, int y) {
  switch (input) {
    case Input::NEXT:
      return this->move_focus_(true);
    case Input::PREV:
      return this->move_focus_(false);
    case Input::SELECT: {
      const TaskList::State state = this->list_->state();
      if (state == TaskList::State::FAILED || state == TaskList::State::EMPTY) {
        this->list_->refresh();
        return true;
      }
      this->focus_.set_count(this->list_->items().size());
      if (state == TaskList::State::READY && this->focus_.valid())
        this->list_->toggle(this->focus_.index());
      return true;
    }
    case Input::SWIPE_UP:  // Finger moves up: show what is below.
      this->first_ += std::max(1, this->rows_ - 1);
      this->clamp_scroll_();
      return true;
    case Input::SWIPE_DOWN:
      this->first_ -= std::max(1, this->rows_ - 1);
      this->clamp_scroll_();
      return true;
    case Input::TAP: {
      const TaskList::State state = this->list_->state();
      if (state == TaskList::State::FAILED || state == TaskList::State::EMPTY) {
        this->list_->refresh();
        return true;
      }
      if (state != TaskList::State::READY || this->row_h_ <= 0 || y < this->list_top_)
        return true;
      const int row = (y - this->list_top_) / this->row_h_;
      if (row >= this->rows_)
        return true;
      const size_t index = this->first_ + row;
      if (index < this->list_->items().size())
        this->list_->toggle(index);
      return true;
    }
    default:
      return false;
  }
}

}  // namespace Daruma
