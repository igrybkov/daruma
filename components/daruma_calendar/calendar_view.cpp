#include "calendar_view.h"

#include <algorithm>

#include "esphome/components/daruma/draw.h"
#include "esphome/components/daruma/text.h"

namespace Daruma {

using esphome::Color;
using esphome::display::Display;
using esphome::display::TextAlign;

// a blended toward b by k (0..1).
static Color mix(Color a, Color b, float k) {
  auto ch = [k](uint8_t x, uint8_t y) { return (uint8_t) (x + (y - x) * k); };
  return Color(ch(a.r, b.r), ch(a.g, b.g), ch(a.b, b.b));
}

// A thick "<" (dir -1) or ">" (dir 1) centered on (cx, cy).
static void chevron(Display &display, int cx, int cy, int half, int dir, Color color) {
  for (int t = -1; t <= 1; t++) {
    const int tip = cx + t + dir * half / 2, tail = cx + t - dir * half / 2;
    display.line(tail, cy - half, tip, cy, color);
    display.line(tip, cy, tail, cy + half, color);
  }
}

void CalendarView::draw(AppView &v, const CalendarViewState &state) {
  this->w_ = v.w;
  this->h_ = v.h;
  this->pad_ = v.px(10);
  this->bar_h_ = v.px(34);
  this->row_h_ = v.px(28);
  this->time_w_ = v.px(54);
  this->arrow_w_ = v.px(46);
  this->draw_bar_(v, state);
  v.display.horizontal_line(v.x + this->pad_, v.y + this->bar_h_, v.w - 2 * this->pad_, mix(v.theme.panel, v.theme.muted, 0.35f));
  this->draw_list_(v, state);
}

CalendarHit CalendarView::hit(int x, int y) const {
  if (x < 0 || y < 0 || x >= this->w_ || y >= this->h_)
    return CalendarHit::NONE;
  if (y < this->bar_h_) {
    if (x < this->arrow_w_)
      return CalendarHit::PREVIOUS;
    if (x >= this->w_ - this->arrow_w_)
      return CalendarHit::NEXT;
    return CalendarHit::LABEL;
  }
  return CalendarHit::LIST;
}

void CalendarView::draw_bar_(AppView &v, const CalendarViewState &state) {
  const Theme &t = v.theme;
  const int cy = v.y + this->bar_h_ / 2;
  const Color off = mix(t.panel, t.muted, 0.4f);
  chevron(v.display, v.x + this->pad_ + v.px(8), cy, v.px(7), -1, state.can_go_back ? t.ink : off);
  chevron(v.display, v.x + v.w - this->pad_ - v.px(8), cy, v.px(7), 1, state.can_go_forward ? t.ink : off);

  // "Today  Sun 15", centered between the arrows on one baseline.
  const int room = v.w - 2 * this->arrow_w_;
  const int gap = 6;
  const std::string label = fit_text(v.display, v.text, state.label, room);
  const int label_w = text_width(v.display, v.text, label);
  std::string date = state.date;
  int date_w = date.empty() ? 0 : text_width(v.display, v.small, date);
  if (label_w + gap + date_w > room) {
    date.clear();
    date_w = 0;
  }
  const int total = label_w + (date.empty() ? 0 : gap + date_w);
  const int left = v.x + (v.w - total) / 2;
  const int baseline = cy + v.px(6);
  v.display.print(left, baseline, v.text, t.ink, TextAlign::BASELINE_LEFT, label.c_str(), t.panel);
  if (!date.empty()) {
    v.display.print(left + label_w + gap, baseline, v.small, t.muted, TextAlign::BASELINE_LEFT, date.c_str(),
                    t.panel);
  }
}

void CalendarView::draw_message_(AppView &v, const std::string &text, int top) {
  const int width = v.w - 4 * this->pad_;
  std::vector<std::string> lines = Utilities::Text::wrap(v.display, v.text, text, width);
  if (lines.size() > 3)
    lines.resize(3);
  const int line_h = v.px(22);
  const int mid = top + (v.y + v.h - top) / 2;
  int y = mid - (int) (lines.size() - 1) * line_h / 2;
  for (const std::string &line : lines) {
    v.display.print(v.x + v.w / 2, y, v.text, v.theme.muted, TextAlign::CENTER,
                    fit_text(v.display, v.text, line, width).c_str(), v.theme.panel);
    y += line_h;
  }
}

void CalendarView::draw_list_(AppView &v, const CalendarViewState &state) {
  const Theme &t = v.theme;
  const int top = v.y + this->bar_h_ + 2;
  this->rows_ = std::max(1, (v.h - this->bar_h_ - 6) / this->row_h_);
  this->items_ = 0;

  if (state.day == nullptr) {
    const bool show_error = !state.loading && !state.error.empty();
    this->draw_message_(v, show_error ? state.error : state.loading_text, top);
    return;
  }
  const CalendarDay &day = *state.day;
  if (day.events.empty()) {
    this->draw_message_(v, state.empty_text, top);
    return;
  }

  const int events = day.events.size();
  const int items = events + (day.total > events ? 1 : 0);
  this->items_ = items;
  this->scroll_ = std::max(0, std::min(this->scroll_, items - this->rows_));
  const bool scrolls = items > this->rows_;
  const int right = v.x + v.w - this->pad_ - (scrolls ? 6 : 0);
  const Color line = mix(t.panel, t.muted, 0.2f);

  // The first event still to start is the "next" one; it gets the accent.
  int next = -1, first_timed = -1;
  bool busy = false;
  if (state.is_today) {
    for (int i = 0; i < events; i++) {
      const CalendarEvent &event = day.events[i];
      if (event.all_day)
        continue;
      if (first_timed < 0)
        first_timed = i;
      busy = busy || event.is_now(state.now);
      if (next < 0 && event.start > state.now)
        next = i;
    }
  }

  const int last = std::min(items, this->scroll_ + this->rows_);
  for (int i = this->scroll_; i < last; i++) {
    const int row_top = top + (i - this->scroll_) * this->row_h_;
    if (i < events) {
      this->draw_row_(v, state, day.events[i], i == next, row_top, right);
    } else {
      const std::string more = "+" + std::to_string(day.total - events) + " " + state.more_text;
      v.display.print(v.x + this->pad_ + 2, row_top + this->row_h_ / 2, v.small, t.muted, TextAlign::CENTER_LEFT, more.c_str(),
                      t.panel);
    }
    if (i + 1 < last)
      v.display.horizontal_line(v.x + this->pad_, row_top + this->row_h_ - 1, right - v.x - this->pad_, line);
  }

  // The current time, as a line between the past and the next event, when
  // nothing is going on right now.
  if (state.is_today && first_timed >= 0 && !busy) {
    const int at = next >= 0 ? next : events;
    if (at >= this->scroll_ && at <= last && !(at == last && last < items)) {
      const int y = top + (at - this->scroll_) * this->row_h_ - (at == this->scroll_ ? 0 : 1);
      v.display.filled_rectangle(v.x + this->pad_ + 4, y - 1, right - v.x - this->pad_ - 4, 2, t.accent);
      v.display.filled_circle(v.x + this->pad_ + 3, y, 3, t.accent);
    }
  }

  if (scrolls) {
    const int track_x = v.x + v.w - this->pad_ - 2, track_h = this->rows_ * this->row_h_ - 4;
    const int thumb_h = std::max(10, track_h * this->rows_ / items);
    const int thumb_y = top + 2 + (track_h - thumb_h) * this->scroll_ / std::max(1, items - this->rows_);
    v.display.filled_rectangle(track_x, top + 2, 3, track_h, line);
    v.display.filled_rectangle(track_x, thumb_y, 3, thumb_h, mix(t.panel, t.muted, 0.7f));
  }
}

void CalendarView::draw_row_(AppView &v, const CalendarViewState &state, const CalendarEvent &event, bool next,
                             int top, int right) {
  const Theme &t = v.theme;
  const bool now = state.is_today && event.is_now(state.now);
  const bool past = state.is_today && event.is_past(state.now);
  const int mid = top + this->row_h_ / 2;

  Color bg = t.panel;
  if (now) {
    bg = mix(t.panel, t.accent, 0.2f);
    Utilities::Draw::roundedRectangle(&v.display, v.x + this->pad_ - 4, top + 1, right - v.x - this->pad_ + 6, this->row_h_ - 3, 5, bg);
    v.display.filled_rectangle(v.x + this->pad_ - 4, top + 3, 3, this->row_h_ - 7, t.accent);
  }

  const int time_x = v.x + this->pad_ + 2;
  if (event.all_day) {
    v.display.print(time_x, mid, v.small, t.muted, TextAlign::CENTER_LEFT, state.all_day_text.c_str(), bg);
  } else {
    // Times outside this day (an event from last night, or one that runs
    // past midnight) show as "…".
        const std::string from = event.start < state.day->start ? "…" : local_hhmm(event.start);
    const std::string to = event.end > state.day->end ? "…" : local_hhmm(event.end);
    const Color from_color = (now || next) ? t.accent : (past ? t.muted : t.ink);
    v.display.print(time_x, mid - v.px(7), v.small, from_color, TextAlign::CENTER_LEFT, from.c_str(), bg);
    v.display.print(time_x, mid + v.px(7), v.small, t.muted, TextAlign::CENTER_LEFT, to.c_str(), bg);
  }

  const int title_x = v.x + this->pad_ + this->time_w_;
  std::string title = drawable_text(v.text, event.title);
  if (title.empty())
    title = state.untitled_text;
  title = fit_text(v.display, v.text, title, right - title_x);
  v.display.print(title_x, mid, v.text, past ? t.muted : t.ink, TextAlign::CENTER_LEFT, title.c_str(), bg);
}

}  // namespace Daruma
