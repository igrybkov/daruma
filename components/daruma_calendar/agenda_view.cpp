#include "agenda_view.h"

#include <algorithm>

#include "esphome/components/daruma/draw.h"
#include "esphome/components/daruma/text.h"

namespace Daruma {

using esphome::Color;
using esphome::display::TextAlign;

// a blended toward b by k (0..1).
static Color mix(Color a, Color b, float k) {
  auto ch = [k](uint8_t x, uint8_t y) { return (uint8_t) (x + (y - x) * k); };
  return Color(ch(a.r, b.r), ch(a.g, b.g), ch(a.b, b.b));
}

void AgendaView::draw(AppView &v, const AgendaViewState &state) {
  const Theme &t = v.theme;
  this->pad_ = v.px(10);
  this->time_w_ = v.px(54);
  this->top_ = v.px(2);
  // As many rows of at least 26 design pixels as fit, then share out the
  // rest so the last row ends at the bottom.
  const int room = v.h - 2 * this->top_;
  this->fit_ = std::max(1, room / std::max(1, v.px(26)));
  this->row_h_ = room / this->fit_;

  if (state.span == nullptr) {
    this->count_ = 0;
    this->focus_.set_count(0);
    const bool show_error = !state.loading && !state.error.empty();
    this->draw_message_(v, show_error ? state.error : state.loading_text);
    return;
  }

  const int count = state.rows.size();
  this->count_ = count;
  this->focus_.set_count(count);
  if (v.focus)
    this->scroll_ = this->focus_.keep_visible(this->scroll_, this->fit_);
  this->scroll_ = std::max(0, std::min(this->scroll_, count - this->fit_));
  const bool scrolls = count > this->fit_;
  const int right = v.x + v.w - this->pad_ - (scrolls ? v.px(6) : 0);
  const int last = std::min(count, this->scroll_ + this->fit_);

  for (int i = this->scroll_; i < last; i++) {
    const AgendaRow &row = state.rows[i];
    const int top = v.y + this->top_ + (i - this->scroll_) * this->row_h_;
    const int mid = top + this->row_h_ / 2;
    switch (row.kind) {
      case AgendaRowKind::HEADING: {
        const std::string text = row.day < (int) state.headings.size() ? state.headings[row.day] : "";
        this->draw_heading_(v, text, top, right);
        break;
      }
      case AgendaRowKind::EVENT:
        this->draw_event_(v, state, state.span->events[row.event], top, right);
        break;
      case AgendaRowKind::NOTHING:
        v.display.print(v.x + this->pad_ + this->time_w_, mid, v.text, t.muted, TextAlign::CENTER_LEFT,
                        state.nothing_text.c_str(), t.panel);
        break;
      case AgendaRowKind::MORE: {
        const std::string more = "+" + std::to_string(state.span->hidden()) + " " + state.more_text;
        v.display.print(v.x + this->pad_ + 2, mid, v.small, t.muted, TextAlign::CENTER_LEFT, more.c_str(), t.panel);
        break;
      }
    }
    if (v.focus && i == this->focus_.index()) {
      // A ring around the row, in the focus color.
      const int ring = std::max(2, v.px(2));
      const Color c = t.on(t.panel, t.focus_color());
      const int x0 = v.x + this->pad_ - v.px(5), w = right - x0 + v.px(3);
      for (int k = 0; k < ring; k++) {
        v.display.rectangle(x0 + k, top + k, w - 2 * k, this->row_h_ - 2 * k, c);
      }
    }
  }

  if (scrolls) {
    const Color line = mix(t.panel, t.muted, 0.2f);
    const int top = v.y + this->top_;
    const int track_x = v.x + v.w - this->pad_ - 2, track_h = this->fit_ * this->row_h_ - 4;
    const int thumb_h = std::max(10, track_h * this->fit_ / count);
    const int thumb_y = top + 2 + (track_h - thumb_h) * this->scroll_ / std::max(1, count - this->fit_);
    v.display.filled_rectangle(track_x, top + 2, 3, track_h, line);
    v.display.filled_rectangle(track_x, thumb_y, 3, thumb_h, mix(t.panel, t.muted, 0.7f));
  }
}

void AgendaView::draw_heading_(AppView &v, const std::string &text, int top, int right) {
  const Theme &t = v.theme;
  const int left = v.x + this->pad_;
  const int baseline = top + this->row_h_ - v.px(7);
  const std::string label = fit_text(v.display, v.text, text, right - left);
  v.display.print(left, baseline, v.text, t.ink, TextAlign::BASELINE_LEFT, label.c_str(), t.panel);
  v.display.horizontal_line(left, top + this->row_h_ - v.px(3), right - left, mix(t.panel, t.muted, 0.35f));
}

void AgendaView::draw_event_(AppView &v, const AgendaViewState &state, const CalendarEvent &event, int top, int right) {
  const Theme &t = v.theme;
  const bool today = event.start < state.today_end;
  const bool now = event.is_now(state.now);
  const bool past = today && event.is_past(state.now);
  const int mid = top + this->row_h_ / 2;
  const int left = v.x + this->pad_;

  Color bg = t.panel;
  if (now) {
    bg = mix(t.panel, t.accent, 0.2f);
    Utilities::Draw::roundedRectangle(&v.display, left - v.px(4), top + 1, right - left + v.px(6), this->row_h_ - 2,
                                      v.px(5), bg);
    v.display.filled_rectangle(left - v.px(4), top + 3, 3, this->row_h_ - 6, t.accent);
  }

  // The start time; "…" for one that began before today.
  std::string time;
  if (event.all_day) {
    time = state.all_day_text;
  } else {
    time = state.span != nullptr && event.start < state.span->start ? "…" : local_hhmm(event.start);
  }
  const Color time_color = now ? t.accent : (past || event.all_day ? t.muted : t.ink);
  time = fit_text(v.display, v.small, time, this->time_w_ - v.px(4));
  v.display.print(left + 2, mid, v.small, time_color, TextAlign::CENTER_LEFT, time.c_str(), bg);

  const int title_x = left + this->time_w_;
  std::string title = drawable_text(v.text, event.title);
  if (title.empty())
    title = state.untitled_text;
  title = fit_text(v.display, v.text, title, right - title_x);
  v.display.print(title_x, mid, v.text, past ? t.muted : t.ink, TextAlign::CENTER_LEFT, title.c_str(), bg);
}

void AgendaView::draw_message_(AppView &v, const std::string &text) {
  const int width = v.w - 4 * this->pad_;
  std::vector<std::string> lines = Utilities::Text::wrap(v.display, v.text, text, width);
  if (lines.size() > 3)
    lines.resize(3);
  const int line_h = v.px(22);
  int y = v.y + v.h / 2 - (int) (lines.size() - 1) * line_h / 2;
  for (const std::string &line : lines) {
    v.display.print(v.x + v.w / 2, y, v.text, v.theme.muted, TextAlign::CENTER,
                    fit_text(v.display, v.text, line, width).c_str(), v.theme.panel);
    y += line_h;
  }
}

int AgendaView::row_at(int x, int y) const {
  if (x < 0 || y < this->top_)
    return -1;
  const int i = (y - this->top_) / this->row_h_;
  if (i >= this->fit_)
    return -1;
  const int row = this->scroll_ + i;
  return row < this->count_ ? row : -1;
}

bool AgendaView::move_focus(bool forward) {
  if (this->count_ == 0)
    return false;
  if (forward) {
    this->focus_.next();
  } else {
    this->focus_.prev();
  }
  this->scroll_ = this->focus_.keep_visible(this->scroll_, this->fit_);
  return true;
}

}  // namespace Daruma
