#include "next_line.h"

#include <algorithm>

#include "calendar_app.h"
#include "esphome/components/daruma/draw.h"
#include "esphome/components/daruma/text.h"
#include "esphome/core/log.h"

namespace Daruma {

static const char *const TAG = "daruma_calendar";
// Above the voice timer (10), under the pomodoro plaque (20). The line has
// a strip of its own under the bottom corners, so nothing else depends on
// it being drawn first.
static const int LAYER_ORDER = 15;

NextEventLine &NextEventLine::get() {
  static NextEventLine line;
  return line;
}

void NextEventLine::add(Hub &hub, CalendarApp *app, esphome::display::BaseFont *font) {
  this->apps_.push_back(app);
  this->dirty_ = true;
  if (this->hub_ != nullptr)
    return;
  this->hub_ = &hub;
  this->font_ = font;
  hub.add_layer(LAYER_ORDER, [this](esphome::display::Display &display) { this->draw_(display); });
  // The pill leads somewhere (the module's targets: next_event).
  hub.add_tap_area("next_event", [this]() {
    if (this->text_.empty() || !this->hub_->message().empty())
      return Rect{};
    return this->drawn_;
  });
}

LineText NextEventLine::compute_(const esphome::ESPTime &now) const {
  const time_t t = now.timestamp;
  const time_t day_end = local_day_start(now, 1);
  const CalendarApp *best_app = nullptr;
  const CalendarEvent *best = nullptr;
  NextEventKind kind = NextEventKind::NONE;
  for (const CalendarApp *app : this->apps_) {
    NextEventKind k;
    const CalendarEvent *e = app->line_pick(t, day_end, &k);
    if (e != nullptr && (best == nullptr || next_event_better(k, *e, kind, *best))) {
      best_app = app;
      best = e;
      kind = k;
    }
  }
  if (best == nullptr)
    return LineText{};
  // Words of the copy the event came from (its theme keys).
  const char *key = kind == NextEventKind::NEXT ? "line_next" : (best->end <= day_end ? "line_now" : "line_now_open");
  std::string title = drawable_text(this->font_, best->title);
  if (title.empty())
    title = best_app->word("untitled");
  return line_text(best_app->word(key), title, local_hhmm(best->start), local_hhmm(best->end));
}

void NextEventLine::tick() {
  if (this->hub_ == nullptr)
    return;
  const esphome::ESPTime now = this->apps_.front()->clock_now();
  if (!now.is_valid())
    return;
  // Another persona may use other words.
  if (this->hub_->persona() != this->persona_) {
    this->persona_ = this->hub_->persona();
    this->dirty_ = true;
  }
  if (!this->dirty_ && now.minute == this->minute_)
    return;
  this->dirty_ = false;
  this->minute_ = now.minute;

  // Used while any copy may show something (Hub::info_line() is then
  // the persona's place for it).
  const bool used = std::any_of(this->apps_.begin(), this->apps_.end(), [](CalendarApp *a) { return a->line_on(); });
  this->hub_->set_info_line_used(used);

  const LineText text = used ? this->compute_(now) : LineText{};
  if (text == this->text_)
    return;
  this->text_ = text;
  this->fitted_for_ = -1;
  ESP_LOGD(TAG, "Next event line: %s", text.empty() ? "off" : "changed");  // Never the title.

  esphome::display::Display *display = this->hub_->display();
  const Rect region = this->hub_->info_line();
  if (text.empty() || display == nullptr || region.empty()) {
    if (!this->drawn_.empty())
      this->hub_->request_redraw();  // The persona shows again under it.
    return;
  }
  Rect pill = this->measure_(*display, region);
  if (!this->drawn_.empty())
    pill.w = std::max(pill.w, this->drawn_.w);
  this->hub_->request_area(pill);
}

Rect NextEventLine::measure_(esphome::display::Display &display, const Rect &region) {
  if (this->fitted_for_ != region.w) {
    const int pad = this->hub_->layout().px(6);
    const int before = text_width(display, this->font_, this->text_.before);
    const int after = text_width(display, this->font_, this->text_.after);
    const int room = region.w - 2 * pad - before - after;
    this->fitted_ = room > 0 ? fit_text(display, this->font_, this->text_.title, room) : std::string();
    this->fitted_w_ = std::min(2 * pad + before + after + text_width(display, this->font_, this->fitted_), region.w);
    this->fitted_for_ = region.w;
  }
  return Rect{region.x, region.y, this->fitted_w_, region.h};
}

void NextEventLine::draw_(esphome::display::Display &display) {
  // Hidden under a message bubble, like the plaque; the menu and prompts
  // cover the layers anyway. At the top it would meet "muted".
  const Rect region = this->hub_->info_line();
  const bool top = region.y < this->hub_->layout().height / 2;
  const bool clipped = display.is_clipping();
  if (this->text_.empty() || region.empty() || !this->hub_->message().empty() || (top && this->hub_->muted())) {
    if (!clipped)
      this->drawn_ = Rect{};
    return;
  }
  Rect pill = this->measure_(display, region);
  // A clipped pass (request_area, or the persona's own delta) repaints over
  // what is on screen: never narrower than the pill already there. One
  // that does not reach the pill leaves it be.
  if (clipped) {
    if (!this->drawn_.empty())
      pill.w = std::max(pill.w, this->drawn_.w);
    const esphome::display::Rect clip = display.get_clipping();
    if (pill.intersected(Rect{clip.x, clip.y, clip.w, clip.h}).empty())
      return;
  }
  const std::string &title = this->fitted_;

  const Theme &theme = this->hub_->theme();
  const Layout &l = this->hub_->layout();
  const esphome::Color bg = theme.dock;
  Utilities::Draw::roundedRectangle(&display, pill.x, pill.y, pill.w, pill.h, l.px(6), bg);
  const esphome::Color ink = theme.on(bg, theme.dock_ink);
  const esphome::Color muted = theme.on(bg, theme.dock_muted);
  int x = pill.x + l.px(6);
  const int cy = pill.cy();
  auto print = [&](const std::string &s, esphome::Color c) {
    if (s.empty())
      return;
    display.print(x, cy, this->font_, c, esphome::display::TextAlign::CENTER_LEFT, s.c_str(), bg);
    x += text_width(display, this->font_, s);
  };
  print(this->text_.before, muted);
  print(title, ink);
  print(this->text_.after, muted);
  this->drawn_ = pill;
}

}  // namespace Daruma
