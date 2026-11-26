#include "habits_app.h"

#include <algorithm>

#include "esphome/components/daruma/draw.h"
#include "esphome/components/daruma/text.h"
#include "esphome/components/daruma/ui_tree.h"
#include "esphome/core/hal.h"
#include "esphome/core/log.h"

namespace Daruma {

using esphome::Color;
using esphome::display::TextAlign;

static const char *const TAG = "daruma_habits";
static const std::string PREFIX = "habits.";
// Theme colors for Habitica's value bands, worst to best (habit_value_band).
// How long a drop or quest progress stays in the notice line.
static const uint32_t NEWS_MS = 5000;
static const char *const BANDS[] = {"worst", "worse", "bad", "neutral", "good", "better", "best"};

// The rendered text HA sends under "response".
static std::string reply_text(ArduinoJson::JsonObjectConst reply) {
  const char *text = reply["response"].as<const char *>();
  return text != nullptr ? text : "";
}

void HabitsApp::setup() {
  this->list_.set_on_reply([this](const HabitReply &r) {
    const std::string news = habit_news(r, this->word_("quest"));
    if (!news.empty()) {
      this->news_ = news;
      this->news_at_ = esphome::millis();
    }
    for (auto &listener : this->listeners_)
      listener(r);
  });
}

void HabitsApp::set_source(const std::string &entity) {
  const bool ok = entity.rfind("script.", 0) == 0 && entity.size() > 7;
  this->list_.set_source(ok ? entity : "");
  if (!ok)
    ESP_LOGW(TAG, "'%s' is not a script entity", entity.c_str());
  if (this->open_)
    this->list_.refresh(esphome::millis());
  this->changed_();
}

void HabitsApp::loop() {
  const uint32_t now = esphome::millis();
  this->list_.tick(now);
  this->select_(now);
  // The notice line comes and goes on its own.
  const std::string notice = this->notice_text_(now);
  if (notice != this->shown_notice_) {
    this->shown_notice_ = notice;
    this->changed_();
  }
}

// What the notice line says now: a problem, else a reply's news for a while.
std::string HabitsApp::notice_text_(uint32_t now) const {
  const HabitList::Notice notice = this->list_.notice(now);
  if (notice != HabitList::Notice::NONE)
    return this->word_(notice == HabitList::Notice::BUSY ? "busy" : "failed");
  return now - this->news_at_ < NEWS_MS ? this->news_ : "";
}

void HabitsApp::changed_() {
  if (this->hub_ != nullptr)
    this->hub_->request_redraw();
}

void HabitsApp::on_list(int generation, ArduinoJson::JsonObjectConst reply) {
  this->list_.on_list(generation, reply_text(reply));
  this->changed_();
}

void HabitsApp::on_score(int seq, ArduinoJson::JsonObjectConst reply) {
  this->list_.on_score(seq, reply_text(reply), esphome::millis());
  this->changed_();
}

void HabitsApp::on_score_error(int seq, const std::string &error) {
  ESP_LOGW(TAG, "Score failed: %s", error.c_str());
  this->list_.on_score_error(seq, error, esphome::millis());
  this->changed_();
}

void HabitsApp::refresh_idle() {
  if (this->enabled_ && !this->list_.sending() && this->list_.waiting() == 0)
    this->list_.refresh(esphome::millis());
}

void HabitsApp::on_open() {
  this->open_ = true;
  this->first_ = 0;
  this->focus_.set_count((int) this->list_.habits().size());
  this->focus_.reset();
  this->select_timer_.cancel();
  this->list_.refresh(esphome::millis());
}

std::string HabitsApp::word_(const char *key) const { return this->hub_->theme().word(PREFIX + key); }

// "+4 today": the daily habits' ups less downs.
std::string HabitsApp::status() {
  const auto &habits = this->list_.habits();
  const bool daily = std::any_of(habits.begin(), habits.end(), [](const Habit &h) { return h.period == 'd'; });
  if (this->list_.state() != HabitList::State::READY || !daily)
    return "";
  return fill(this->word_("status"), "net", habit_signed(habit_today_net(habits)));
}

void HabitsApp::score_(size_t index, bool up) {
  const HabitList::Tap tap = this->list_.score(index, up, esphome::millis());
  if (tap == HabitList::Tap::QUEUED)
    this->hub_->react(up ? StateId::HABIT_UP : StateId::HABIT_DOWN);
  this->changed_();
}

// SELECT on a habit with both sides waits for a second press.
void HabitsApp::select_(uint32_t now) {
  if (this->select_timer_.tick(now) == HabitSelect::SINGLE && this->focus_.valid())
    this->score_((size_t) this->focus_.index(), true);
}

void HabitsApp::move_focus_(bool forward) {
  this->focus_.set_count((int) this->list_.habits().size());
  if (forward) {
    this->focus_.next();
  } else {
    this->focus_.prev();
  }
  this->first_ = this->focus_.keep_visible(this->first_, this->rows_);
  this->changed_();
}

bool HabitsApp::tap_(int x, int y) {
  for (const Target &t : this->targets_) {
    if (t.rect.contains(x, y)) {
      this->score_(t.index, t.up);
      return true;
    }
  }
  return false;
}

bool HabitsApp::input(Input input, int x, int y) {
  const int total = (int) this->list_.habits().size();
  switch (input) {
    case Input::TAP:
      return this->tap_(x, y);
    case Input::SWIPE_UP:  // Finger moves up: show what is below.
    case Input::SWIPE_DOWN: {
      const int step = std::max(1, this->rows_ - 1) * (input == Input::SWIPE_UP ? 1 : -1);
      this->first_ = std::max(0, std::min(this->first_ + step, total - this->rows_));
      this->changed_();
      return true;
    }
    case Input::NEXT:
    case Input::PREV:
      this->move_focus_(input == Input::NEXT);
      return true;
    case Input::SELECT: {
      if (!this->focus_.valid() || this->focus_.index() >= total)
        return true;
      const Habit &h = this->list_.habits()[this->focus_.index()];
      // One side: it scores at once. Both: one press up, two down.
      if (!(h.up && h.down)) {
        this->score_((size_t) this->focus_.index(), h.up);
      } else if (this->select_timer_.press(esphome::millis()) == HabitSelect::DOUBLE) {
        this->score_((size_t) this->focus_.index(), false);
      }
      return true;
    }
    default:
      return false;
  }
}

void HabitsApp::draw(AppView &v) {
  this->targets_.clear();
  const int pad = v.px(8);
  int top = v.y + pad;
  if (this->header_) {
    this->header_(v, Rect{v.x + v.px(12), top, v.w - v.px(24), v.px(18)});
    top += v.px(24);
  }
  const auto &habits = this->list_.habits();
  const HabitList::State state = this->list_.state();
  if (state != HabitList::State::READY || habits.empty()) {
    const char *key =
        state == HabitList::State::FAILED ? "error" : (state == HabitList::State::READY ? "empty" : "loading");
    if (this->list_.source().empty())
      key = "no_source";
    this->draw_message_(v, this->word_(key));
    this->draw_notice_(v);
    return;
  }
  // The notice line keeps its strip at the bottom while it shows.
  const int strip = this->notice_text_(esphome::millis()).empty() ? 0 : v.px(22);
  const Rect area{v.x + pad, top, v.w - 2 * pad, v.y + v.h - pad - top - strip};
  const int row_h = v.px(46);
  this->rows_ = std::max(1, area.h / row_h);
  const int total = (int) habits.size();
  this->first_ = std::max(0, std::min(this->first_, total - this->rows_));
  this->focus_.set_count(total);
  for (int k = 0; k < this->rows_ && this->first_ + k < total; k++) {
    const int index = this->first_ + k;
    const Rect r{area.x, area.y + k * row_h, area.w - (total > this->rows_ ? v.px(8) : 0), row_h - v.px(4)};
    this->draw_row_(v, r, (size_t) index, v.focus && index == this->focus_.index());
  }
  if (total > this->rows_)
    this->draw_scroll_(v, area, total);
  this->draw_notice_(v);
}

void HabitsApp::draw_message_(AppView &v, const std::string &text) {
  v.display.print(v.x + v.w / 2, v.y + v.h / 2, v.small, v.theme.on(v.theme.panel, v.theme.muted), TextAlign::CENTER,
                  fit_text(v.display, v.small, text, v.w - v.px(24)).c_str(), v.theme.panel);
  UiTree::add("text", text, Rect{v.x, v.y + v.h / 2 - v.px(10), v.w, v.px(20)});
}

// A row: the value bar, the title and the counts, then minus and plus.
void HabitsApp::draw_row_(AppView &v, const Rect &r, size_t index, bool focused) {
  auto &it = v.display;
  const Theme &t = v.theme;
  const Habit &h = this->list_.habits()[index];
  if (focused)
    Utilities::Draw::roundedRectangle(&it, r.x - v.px(2), r.y - v.px(2), r.w + v.px(4), r.h + v.px(4), v.px(8),
                                      t.on(t.panel, t.focus_color()));
  const Color band = t.on(t.panel, t.color(PREFIX + BANDS[habit_value_band(h.value)]));
  Utilities::Draw::roundedRectangle(&it, r.x, r.y, v.px(6), r.h, v.px(3), band);
  // The buttons, right to left: plus, then minus.
  const int bw = v.px(40);
  const int gap = v.px(6);
  int right = r.right();
  if (h.up) {
    const Rect b{right - bw, r.y, bw, r.h};
    this->draw_button_(v, b, true, h.title + " +");
    this->targets_.push_back(Target{Rect{b.x - v.x, b.y - v.y, b.w, b.h}, index, true});
    right = b.x - gap;
  }
  if (h.down) {
    const Rect b{right - bw, r.y, bw, r.h};
    this->draw_button_(v, b, false, h.title + " -");
    this->targets_.push_back(Target{Rect{b.x - v.x, b.y - v.y, b.w, b.h}, index, false});
    right = b.x - gap;
  }
  const int tx = r.x + v.px(14);
  const int room = right - tx;
  it.print(tx, r.y + r.h * 32 / 100, v.text, t.on(t.panel, t.ink), TextAlign::CENTER_LEFT,
           fit_text(it, v.text, h.title, room).c_str(), t.panel);
  std::string counts = habit_counts(h);
  if (!counts.empty())
    counts += " " + this->word_(habit_period_word(h.period));
  it.print(tx, r.y + r.h * 76 / 100, v.small, t.on(t.panel, t.muted), TextAlign::CENTER_LEFT,
           fit_text(it, v.small, counts, room).c_str(), t.panel);
  UiTree::add("row", h.title, r, focused, counts);
}

void HabitsApp::draw_button_(AppView &v, const Rect &r, bool up, const std::string &name) {
  auto &it = v.display;
  const Theme &t = v.theme;
  const int radius = std::min(v.px(10), r.h / 2);
  const int rim = v.px(2);
  Utilities::Draw::roundedRectangle(&it, r.x, r.y, r.w, r.h, radius, t.on(t.panel, t.muted));
  Utilities::Draw::roundedRectangle(&it, r.x + rim, r.y + rim, r.w - 2 * rim, r.h - 2 * rim, radius - rim, t.panel);
  // The sign as bars, so plus and minus weigh the same in any font.
  const Color ink = t.on(t.panel, t.ink);
  const int arm = v.px(7);
  const int thick = std::max(2, v.px(3));
  it.filled_rectangle(r.cx() - arm, r.cy() - thick / 2, 2 * arm + 1, thick, ink);
  if (up)
    it.filled_rectangle(r.cx() - thick / 2, r.cy() - arm, thick, 2 * arm + 1, ink);
  UiTree::add("button", name, r);
}

// A busy notice, "Couldn't score", a drop or quest progress, at the bottom.
void HabitsApp::draw_notice_(AppView &v) {
  const std::string text = this->notice_text_(esphome::millis());
  if (text.empty())
    return;
  auto &it = v.display;
  const Theme &t = v.theme;
  const int w = std::min(v.w - v.px(16), text_width(it, v.small, text) + v.px(20));
  const Rect r{v.x + (v.w - w) / 2, v.y + v.h - v.px(26), w, v.px(20)};
  const Color fill_color = t.on(t.panel, t.ink);
  Utilities::Draw::roundedRectangle(&it, r.x, r.y, r.w, r.h, r.h / 2, fill_color);
  it.print(r.cx(), r.cy(), v.small, t.on(fill_color, t.panel), TextAlign::CENTER,
           fit_text(it, v.small, text, r.w - v.px(12)).c_str(), fill_color);
  UiTree::add("notice", text, r);
}

void HabitsApp::draw_scroll_(AppView &v, const Rect &area, int total) {
  const Theme &t = v.theme;
  const int x = area.right() - v.px(3);
  v.display.vertical_line(x, area.y, area.h, t.fit(t.dot));
  const int thumb = std::max(v.px(12), area.h * this->rows_ / total);
  const int y = area.y + (area.h - thumb) * this->first_ / std::max(1, total - this->rows_);
  v.display.filled_rectangle(x - 1, y, 3, thumb, t.on(t.panel, t.accent));
}

}  // namespace Daruma
