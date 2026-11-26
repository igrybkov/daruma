#include "skills.h"

#include <algorithm>

#include "esphome/components/daruma/draw.h"
#include "esphome/components/daruma/text.h"
#include "esphome/components/daruma/ui_tree.h"
#include "esphome/core/hal.h"
#include "esphome/core/log.h"
#include "habitica_app.h"

namespace Daruma {

using esphome::Color;
using esphome::display::TextAlign;

static const char *const TAG = "daruma_habitica";
// How long a cast's words stay in the notice line.
static const uint32_t NOTICE_MS = 4000;

std::string HabiticaSkills::word_(const std::string &key) const {
  return this->app_->hub()->theme().word("habitica." + key);
}

void HabiticaSkills::changed_() { this->app_->hub()->request_redraw(); }

void HabiticaSkills::notify_(const std::string &text) {
  this->notice_ = text;
  this->notice_at_ = esphome::millis();
  this->changed_();
}

std::string HabiticaSkills::notice(uint32_t now) const {
  return now - this->notice_at_ < NOTICE_MS ? this->notice_ : "";
}

void HabiticaSkills::open() {
  this->view_ = View::LIST;
  this->first_ = 0;
  this->focus_.reset();
  this->refresh_();
}

void HabiticaSkills::refresh_() {
  if (!this->fetching_ && this->fetch_) {
    this->fetching_ = true;
    this->fetch_at_ = esphome::millis();
    this->fetch_(++this->generation_);
  }
  this->changed_();
}

bool HabiticaSkills::back() {
  if (this->view_ == View::NONE)
    return false;
  this->view_ = this->view_ == View::LIST ? View::NONE : View::LIST;
  this->changed_();
  return true;
}

void HabiticaSkills::loop(uint32_t now) {
  if (this->fetching_ && now - this->fetch_at_ >= this->timeout_ms_)
    this->on_list_error(this->generation_);
  if (this->casting_ && now - this->cast_at_ >= this->timeout_ms_)
    this->on_cast_error(this->seq_, "no answer");
  // The notice line goes away on its own.
  const std::string notice = this->notice(now);
  if (notice != this->shown_notice_) {
    this->shown_notice_ = notice;
    this->changed_();
  }
}

void HabiticaSkills::on_list(int generation, const std::string &text) {
  if (generation != this->generation_ || !this->fetching_)
    return;
  this->fetching_ = false;
  std::string cls;
  this->loaded_ = habitica_parse_skills(text, cls, this->skills_);
  this->failed_ = !this->loaded_;
  this->changed_();
}

void HabiticaSkills::on_list_error(int generation) {
  if (generation != this->generation_ || !this->fetching_)
    return;
  this->fetching_ = false;
  this->failed_ = !this->loaded_;
  this->changed_();
}

void HabiticaSkills::tap_skill_(int index) {
  const HabiticaSkill &k = this->skills_[index];
  if (!k.ready || this->casting_)
    return;
  this->chosen_ = index;
  this->focus_.reset();
  if (k.target == 't') {
    this->picks_ = this->tasks_ ? this->tasks_() : std::vector<std::pair<std::string, std::string>>{};
    this->view_ = View::PICK;
  } else if (this->ask_ && this->ask_()) {
    this->view_ = View::ASK;
    // The focus starts on Cancel.
    this->focus_.set_count(2);
    this->focus_.set(1);
  } else {
    this->cast_now_(index, "");
  }
  this->changed_();
}

// Sends the cast. Its MP comes off at once and plays `cast`.
void HabiticaSkills::cast_now_(int index, const std::string &task) {
  const HabiticaSkill &k = this->skills_[index];
  this->view_ = View::LIST;
  if (!this->cast_)
    return;
  this->casting_ = true;
  this->cast_at_ = esphome::millis();
  this->casting_name_ = k.name;
  this->mp_before_ = this->app_->stats().mp;
  HabiticaStats guess;
  guess.mp = habitica_mp_after(this->mp_before_, k.mp);
  this->app_->apply_stats(guess);
  this->app_->hub()->react(StateId::CAST);
  this->notify_(fill(this->word_("cast_done"), "name", k.name));
  ESP_LOGI(TAG, "Cast %s%s%s", k.id.c_str(), task.empty() ? "" : " on ", task.c_str());
  this->cast_(++this->seq_, k.id, task);
}

void HabiticaSkills::on_cast(int seq, const std::string &text) {
  if (!this->casting_ || seq != this->seq_)
    return;
  bool ok = false;
  HabiticaStats stats;
  if (!habitica_parse_cast(text, ok, stats) || !ok) {
    this->finish_(false);
    return;
  }
  // The reply's numbers replace the guess; without them the next push does.
  this->app_->apply_stats(stats);
  this->finish_(true);
}

void HabiticaSkills::on_cast_error(int seq, const std::string &error) {
  if (!this->casting_ || seq != this->seq_)
    return;
  ESP_LOGW(TAG, "Cast failed: %s", error.c_str());
  this->finish_(false);
}

void HabiticaSkills::finish_(bool ok) {
  this->casting_ = false;
  if (!ok) {
    HabiticaStats back;
    back.mp = this->mp_before_;
    this->app_->apply_stats(back);
    this->notify_(this->word_("cast_failed"));
  }
  // Ready flags change after a cast.
  this->refresh_();
}

int HabiticaSkills::count_() const {
  if (this->view_ == View::PICK)
    return (int) this->picks_.size();
  return this->view_ == View::ASK ? 2 : (int) this->skills_.size();
}

bool HabiticaSkills::scroll_(Input input, int total) {
  const int step = std::max(1, this->rows_ - 1) * (input == Input::SWIPE_UP ? 1 : -1);
  this->first_ = std::max(0, std::min(this->first_ + step, total - this->rows_));
  this->changed_();
  return true;
}

// The target the focus ring is on. The question's are in drawing order.
const HabiticaSkills::Target *HabiticaSkills::focused_target_() const {
  const int i = this->focus_.index();
  if (!this->focus_.valid())
    return nullptr;
  if (this->view_ == View::ASK)
    return i < (int) this->targets_.size() ? &this->targets_[i] : nullptr;
  for (const Target &t : this->targets_) {
    if (t.index == i)
      return &t;
  }
  return nullptr;
}

void HabiticaSkills::act_(const Target &t) {
  if (this->view_ == View::ASK) {
    if (t.index < 0) {
      this->back();
    } else {
      this->cast_now_(this->chosen_, "");
    }
  } else if (this->view_ == View::PICK) {
    this->cast_now_(this->chosen_, this->picks_[t.index].first);
  } else {
    this->tap_skill_(t.index);
  }
}

bool HabiticaSkills::input(Input input, int x, int y) {
  this->focus_.set_count(this->count_());
  switch (input) {
    case Input::TAP:
      for (const Target &t : this->targets_) {
        if (t.rect.contains(x, y)) {
          this->act_(t);
          break;
        }
      }
      return true;
    case Input::SWIPE_UP:
    case Input::SWIPE_DOWN:
      return this->scroll_(input, this->count_());
    case Input::NEXT:
    case Input::PREV:
      if (input == Input::NEXT) {
        this->focus_.next();
      } else {
        this->focus_.prev();
      }
      this->first_ = this->focus_.keep_visible(this->first_, this->rows_);
      this->changed_();
      return true;
    case Input::SELECT: {
      const Target *t = this->focused_target_();
      if (t != nullptr)
        this->act_(*t);
      return true;
    }
    default:
      return false;
  }
}

void HabiticaSkills::draw(AppView &v) {
  this->targets_.clear();
  this->focus_.set_count(this->count_());
  if (this->view_ == View::ASK) {
    this->draw_ask_(v);
  } else if (this->view_ == View::PICK) {
    this->draw_pick_(v);
  } else {
    this->draw_list_(v);
  }
}

void HabiticaSkills::draw_message_(AppView &v, const std::string &text) {
  v.display.print(v.x + v.w / 2, v.y + v.h / 2, v.small, v.theme.on(v.theme.panel, v.theme.muted), TextAlign::CENTER,
                  fit_text(v.display, v.small, text, v.w - v.px(24)).c_str(), v.theme.panel);
  UiTree::add("text", text, Rect{v.x, v.y + v.h / 2 - v.px(10), v.w, v.px(20)});
}

void HabiticaSkills::draw_list_(AppView &v) {
  if (this->skills_.empty()) {
    const char *key = this->failed_ ? "skills_error" : (this->loaded_ ? "no_skills" : "loading");
    this->draw_message_(v, this->word_(key));
    return;
  }
  const int pad = v.px(8);
  const Rect area{v.x + pad, v.y + pad, v.w - 2 * pad - v.px(8), v.h - 2 * pad};
  const int row_h = v.px(42);
  this->rows_ = std::max(1, area.h / row_h);
  const int total = (int) this->skills_.size();
  this->first_ = std::max(0, std::min(this->first_, total - this->rows_));
  for (int k = 0; k < this->rows_ && this->first_ + k < total; k++) {
    const int index = this->first_ + k;
    const Rect r{area.x, area.y + k * row_h, area.w, row_h - v.px(4)};
    this->draw_row_(v, r, this->skills_[index], v.focus && index == this->focus_.index());
    this->targets_.push_back(Target{Rect{r.x - v.x, r.y - v.y, r.w, r.h}, index});
  }
  this->draw_scroll_(v, area, total);
}

// A skill: its name and cost, and under them what it does, or why it is
// not ready. A skill that is not ready is grey.
void HabiticaSkills::draw_row_(AppView &v, const Rect &r, const HabiticaSkill &k, bool focused) {
  auto &it = v.display;
  const Theme &t = v.theme;
  if (focused)
    Utilities::Draw::roundedRectangle(&it, r.x - v.px(2), r.y - v.px(2), r.w + v.px(4), r.h + v.px(4), v.px(8),
                                      t.on(t.panel, t.focus_color()));
  const Color ink = t.on(t.panel, k.ready ? t.ink : t.muted);
  const Color mp = t.on(t.panel, k.ready ? t.color("habitica.mp") : t.muted);
  const std::string cost = fill(this->word_("mp_cost"), "mp", std::to_string(k.mp));
  const int cost_w = text_width(it, v.small, cost) + v.px(8);
  const int tx = r.x + v.px(6);
  it.print(r.right() - v.px(6), r.y + r.h * 30 / 100, v.small, mp, TextAlign::CENTER_RIGHT, cost.c_str(), t.panel);
  it.print(tx, r.y + r.h * 30 / 100, v.text, ink, TextAlign::CENTER_LEFT,
           fit_text(it, v.text, k.name, r.w - cost_w - v.px(12)).c_str(), t.panel);
  const std::string line = k.ready ? this->word_("effect_" + k.id) : k.why;
  it.print(tx, r.y + r.h * 76 / 100, v.small, t.on(t.panel, t.muted), TextAlign::CENTER_LEFT,
           fit_text(it, v.small, line, r.w - v.px(12)).c_str(), t.panel);
  UiTree::add("skill", k.name, r, focused, k.ready ? cost : k.why);
}

// "Cast Stealth for 45 MP?" with Cast and Cancel.
void HabiticaSkills::draw_ask_(AppView &v) {
  auto &it = v.display;
  const Theme &t = v.theme;
  const HabiticaSkill &k = this->skills_[this->chosen_];
  std::string question = fill(this->word_("cast_confirm"), "name", k.name);
  question = fill(question, "mp", std::to_string(k.mp));
  const int cy = v.y + v.h * 35 / 100;
  const int room = v.w - v.px(24);
  // On one line when it fits, else on two.
  const size_t split = text_width(it, v.text, question) > room ? habitica_split(question) : std::string::npos;
  const Color ink = t.on(t.panel, t.ink);
  if (split == std::string::npos) {
    it.print(v.x + v.w / 2, cy, v.text, ink, TextAlign::CENTER, fit_text(it, v.text, question, room).c_str(), t.panel);
  } else {
    const int line = v.px(13);
    it.print(v.x + v.w / 2, cy - line, v.text, ink, TextAlign::CENTER,
             fit_text(it, v.text, question.substr(0, split), room).c_str(), t.panel);
    it.print(v.x + v.w / 2, cy + line, v.text, ink, TextAlign::CENTER,
             fit_text(it, v.text, question.substr(split + 1), room).c_str(), t.panel);
  }
  UiTree::add("text", question, Rect{v.x, cy - v.px(24), v.w, v.px(48)});
  const int pad = v.px(12);
  const int bh = v.px(36);
  const Rect row{v.x + pad, v.y + v.h - pad - bh, v.w - 2 * pad, bh};
  const Rect cast = row.cell(0, 2, 1, v.px(8));
  const Rect cancel = row.cell(1, 2, 1, v.px(8));
  this->draw_pill_(v, cast, this->word_("cast"), v.focus && this->focus_.index() == 0, true);
  this->draw_pill_(v, cancel, this->word_("cancel"), v.focus && this->focus_.index() == 1, false);
  this->targets_.push_back(Target{Rect{cast.x - v.x, cast.y - v.y, cast.w, cast.h}, 0});
  this->targets_.push_back(Target{Rect{cancel.x - v.x, cancel.y - v.y, cancel.w, cancel.h}, -1});
}

// The tasks a task skill may target, as rows.
void HabiticaSkills::draw_pick_(AppView &v) {
  if (this->picks_.empty()) {
    this->draw_message_(v, this->word_("no_tasks"));
    return;
  }
  const int pad = v.px(8);
  const Rect area{v.x + pad, v.y + pad, v.w - 2 * pad - v.px(8), v.h - 2 * pad};
  const int row_h = v.px(36);
  this->rows_ = std::max(1, area.h / row_h);
  const int total = (int) this->picks_.size();
  this->first_ = std::max(0, std::min(this->first_, total - this->rows_));
  for (int k = 0; k < this->rows_ && this->first_ + k < total; k++) {
    const int index = this->first_ + k;
    const Rect r{area.x, area.y + k * row_h, area.w, row_h - v.px(6)};
    this->draw_pill_(v, r, this->picks_[index].second, v.focus && index == this->focus_.index(), false);
    this->targets_.push_back(Target{Rect{r.x - v.x, r.y - v.y, r.w, r.h}, index});
  }
  this->draw_scroll_(v, area, total);
}

// A thin bar right of the rows, while more rows than fit.
void HabiticaSkills::draw_scroll_(AppView &v, const Rect &area, int total) {
  if (total <= this->rows_)
    return;
  const Theme &t = v.theme;
  const int x = area.right() + v.px(5);
  v.display.vertical_line(x, area.y, area.h, t.fit(t.dot));
  const int thumb = std::max(v.px(12), area.h * this->rows_ / total);
  const int y = area.y + (area.h - thumb) * this->first_ / (total - this->rows_);
  v.display.filled_rectangle(x - 1, y, 3, thumb, t.on(t.panel, t.accent));
}

std::string HabiticaSkills::title() const {
  if (this->view_ == View::PICK && this->chosen_ >= 0)
    return this->skills_[this->chosen_].name;
  return this->word_("skills");
}

void HabiticaSkills::draw_pill_(AppView &v, const Rect &r, const std::string &label, bool focused, bool primary) {
  auto &it = v.display;
  const Theme &t = v.theme;
  const int radius = std::min(v.px(10), r.h / 2);
  if (focused)
    Utilities::Draw::roundedRectangle(&it, r.x - v.px(3), r.y - v.px(3), r.w + v.px(6), r.h + v.px(6), radius + v.px(3),
                                      t.on(t.panel, t.focus_color()));
  const Color fill_color = primary ? t.on(t.panel, t.color("habitica.mp")) : t.panel;
  const int rim = v.px(2);
  Utilities::Draw::roundedRectangle(&it, r.x, r.y, r.w, r.h, radius, t.on(t.panel, t.muted));
  Utilities::Draw::roundedRectangle(&it, r.x + rim, r.y + rim, r.w - 2 * rim, r.h - 2 * rim, radius - rim, fill_color);
  it.print(r.cx(), r.cy(), v.small, t.on(fill_color, primary ? t.panel : t.ink), TextAlign::CENTER,
           fit_text(it, v.small, label, r.w - v.px(12)).c_str(), fill_color);
  UiTree::add("button", label, r, focused);
}

}  // namespace Daruma
