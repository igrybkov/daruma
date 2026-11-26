#include "settings_app.h"

#include <algorithm>

#include "esphome/components/daruma/draw.h"
#include "esphome/components/daruma/text.h"
#include "esphome/components/daruma/ui_tree.h"

namespace Daruma {

using esphome::Color;
using esphome::display::BaseFont;
using esphome::display::Display;
using esphome::display::TextAlign;

static const int SCROLL_W = 4;  // Scroll bar width.

static int text_height(Display &display, BaseFont *font) {
  int x1, y1, width, height;
  display.get_text_bounds(0, 0, "Ag", font, TextAlign::TOP_LEFT, &x1, &y1, &width, &height);
  return height;
}

std::string SettingsApp::word_(const Theme &theme, const char *key) const {
  return theme.word(this->prefix_ + "." + key);
}

void SettingsApp::on_open() {
  this->first_ = 0;
  this->focus_.set_count(this->count_());
  this->focus_.reset();
}

void SettingsApp::flip_(int index) {
  if (index < 0 || index >= this->count_())
    return;
  Setting &s = this->hub_->settings()[index];
  if (s.set)
    s.set(!s.is_on());
  this->hub_->request_redraw();
}

void SettingsApp::scroll_(int rows) {
  this->first_ = settings_clamp_first(this->first_ + rows, this->count_(), this->rows_.rows);
}

bool SettingsApp::move_focus_(bool forward) {
  if (this->count_() == 0)
    return false;  // Nothing to focus: the menu scrolls instead.
  this->focus_.set_count(this->count_());
  if (forward) {
    this->focus_.next();
  } else {
    this->focus_.prev();
  }
  this->first_ =
      settings_clamp_first(this->focus_.keep_visible(this->first_, this->rows_.rows), this->count_(), this->rows_.rows);
  return true;
}

bool SettingsApp::input(Input input, int /*x*/, int y) {
  switch (input) {
    case Input::NEXT:
      return this->move_focus_(true);
    case Input::PREV:
      return this->move_focus_(false);
    case Input::SELECT:
      this->focus_.set_count(this->count_());
      if (this->focus_.valid())
        this->flip_(this->focus_.index());
      return true;
    case Input::SWIPE_UP:  // Finger moves up: show what is below.
      this->scroll_(settings_page_step(this->rows_.rows));
      return true;
    case Input::SWIPE_DOWN:
      this->scroll_(-settings_page_step(this->rows_.rows));
      return true;
    case Input::TAP:
      this->flip_(settings_row_at(y, this->rows_, this->first_, this->count_()));
      return true;
    default:
      return false;
  }
}

void SettingsApp::draw(AppView &v) {
  const int text_h = text_height(v.display, v.text);
  const int pad = std::max(4, v.w / 48);
  this->rows_ = settings_rows(v.h, pad, text_h + v.px(18));
  const int count = this->count_();
  this->focus_.set_count(count);
  this->first_ = settings_clamp_first(this->first_, count, this->rows_.rows);

  if (count == 0) {
    const std::string text = this->word_(v.theme, "empty");
    UiTree::add("text", text, v.area());
    v.display.print(v.x + v.w / 2, v.y + v.h / 2, v.text, v.theme.muted, TextAlign::CENTER, text.c_str(),
                    v.theme.panel);
    return;
  }
  auto &settings = this->hub_->settings();
  for (int k = 0; k < this->rows_.rows && this->first_ + k < count; k++) {
    const int index = this->first_ + k;
    const int y = v.y + this->rows_.top + k * this->rows_.row_h;
    this->draw_row_(v, settings[index], y, v.focus && index == this->focus_.index());
    if (k + 1 < this->rows_.rows && index + 1 < count)
      v.display.horizontal_line(v.x + pad + 4, y + this->rows_.row_h - 1, v.w - 2 * pad - 8 - SCROLL_W,
                                shade(v.theme.panel, 0.88f));
  }
  this->draw_scroll_bar_(v);
}

void SettingsApp::draw_row_(AppView &v, const Setting &s, int y, bool focused) {
  const Theme &t = v.theme;
  const int pad = std::max(4, v.w / 48);
  const int left = v.x + pad;
  const int width = v.w - 2 * pad - SCROLL_W - 4;
  const int row_h = this->rows_.row_h;
  const int cy = y + row_h / 2;
  const bool on = s.is_on();
  const bool held = s.is_held();
  UiTree::add("switch", s.label, Rect{left, y, width, row_h}, focused, settings_value_word(on, held));
  if (focused) {
    const int ring = std::max(2, v.px(2));
    const int r = std::min(row_h / 2 - 1, v.px(8));
    Utilities::Draw::roundedRectangle(&v.display, left, y + 1, width, row_h - 2, r, t.on(t.panel, t.focus_color()));
    Utilities::Draw::roundedRectangle(&v.display, left + ring, y + 1 + ring, width - 2 * ring, row_h - 2 - 2 * ring,
                                      std::max(1, r - ring), t.panel);
  }
  const Color lit = t.on(t.panel, t.color(this->prefix_ + ".on"));
  const int icon_x = left + v.px(18);
  if (v.icons != nullptr)
    v.display.print(icon_x, cy, v.icons, on ? lit : t.muted, TextAlign::CENTER, s.icon.c_str(), t.panel);

  const int right = left + width - v.px(8);
  const int switch_w = v.px(36);
  this->draw_switch_(v, right, cy, on, held);

  const int tx = icon_x + v.px(18);
  int text_right = right - switch_w - v.px(8);
  if (held) {
    // "Held" before the switch: it is off for now, not by the person.
    BaseFont *font = v.small != nullptr ? v.small : v.text;
    const std::string word = this->word_(t, "held");
    v.display.print(text_right, cy, font, t.muted, TextAlign::CENTER_RIGHT, word.c_str(), t.panel);
    text_right -= text_width(v.display, font, word) + v.px(6);
  }
  const std::string label = fit_text(v.display, v.text, s.label, std::max(0, text_right - tx));
  v.display.print(tx, cy, v.text, t.ink, TextAlign::CENTER_LEFT, label.c_str(), t.panel);
}

// A pill with a knob: right and lit while on, left and grey while off.
void SettingsApp::draw_switch_(AppView &v, int right, int cy, bool on, bool held) {
  const Theme &t = v.theme;
  const int w = v.px(36), h = v.px(20);
  const int x = right - w, y = cy - h / 2;
  const Color lit = t.on(t.panel, t.color(this->prefix_ + ".on"));
  const Color track = on ? lit : shade(t.panel, 0.7f);
  Utilities::Draw::roundedRectangle(&v.display, x, y, w, h, h / 2, track);
  const int r = h / 2 - v.px(3);
  const int kx = on ? x + w - h / 2 : x + h / 2;
  v.display.filled_circle(kx, cy, r, on ? t.on(lit, Color::WHITE) : (held ? t.muted : t.ink));
}

void SettingsApp::draw_scroll_bar_(AppView &v) {
  const int count = this->count_();
  const SettingsRows &r = this->rows_;
  if (count <= r.rows)
    return;
  const int pad = std::max(4, v.w / 48);
  const int x = v.x + v.w - pad - SCROLL_W;
  const int top = v.y + r.top;
  const int height = r.rows * r.row_h;
  Utilities::Draw::roundedRectangle(&v.display, x, top, SCROLL_W, height, SCROLL_W / 2, shade(v.theme.panel, 0.9f));
  const int thumb_h = std::max(12, height * r.rows / count);
  const int thumb_y = top + (height - thumb_h) * this->first_ / (count - r.rows);
  Utilities::Draw::roundedRectangle(&v.display, x, thumb_y, SCROLL_W, thumb_h, SCROLL_W / 2, v.theme.muted);
}

}  // namespace Daruma
