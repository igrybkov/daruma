#include "habitica_app.h"

#include <algorithm>

#include "esphome/components/api/api_server.h"
#include "esphome/components/daruma/draw.h"
#include "esphome/components/daruma/text.h"
#include "esphome/components/daruma/ui_tree.h"
#include "esphome/core/hal.h"
#include "esphome/core/helpers.h"
#include "esphome/core/log.h"

namespace Daruma {

using esphome::Color;
using esphome::display::TextAlign;

static const char *const TAG = "daruma_habitica";
// The theme keys' prefix: the module's name.
static const std::string PREFIX = "habitica.";
static const char *const CLASSES[] = {"warrior", "rogue", "wizard", "healer"};
// The potion asks first; the question goes away on its own after this long.
static const uint32_t CONFIRM_MS = 10000;
static const char *const POTION = "potion";

void HabiticaApp::follow(const std::string &field, const std::string &entity) {
  this->follows_.emplace_back(field, entity);
}

void HabiticaApp::add_button(const std::string &key, const std::string &entity) {
  this->buttons_.push_back(Button{key, entity, false});
}

void HabiticaApp::setup() {
  this->restore_();
  auto *api = esphome::api::global_api_server;
  if (api == nullptr)
    return;
  // HA learns the subscriptions when it connects, so they are made once,
  // here, for the life of the device.
  for (const auto &f : this->follows_) {
    const std::string field = f.first;
    api->subscribe_home_assistant_state(f.second, {}, [this, field](esphome::StringRef s) {
      HabiticaStats news;
      habitica_set_field(news, field, std::string(s.c_str(), s.size()));
      this->apply_stats(news);
    });
  }
  for (size_t i = 0; i < this->buttons_.size(); i++) {
    api->subscribe_home_assistant_state(this->buttons_[i].entity, {}, [this, i](esphome::StringRef s) {
      // A button never pressed is "unknown", and still available.
      this->buttons_[i].available = std::string(s.c_str(), s.size()) != "unavailable";
      this->changed_();
    });
  }
  ESP_LOGD(TAG, "Following %u stats and %u buttons", (unsigned) this->follows_.size(),
           (unsigned) this->buttons_.size());
}

void HabiticaApp::loop() {
  auto *api = esphome::api::global_api_server;
  const bool connected = api != nullptr && api->is_connected();
  if (connected != this->connected_) {
    this->connected_ = connected;
    if (!connected) {
      // HA sends every state again when it comes back: first values then.
      this->model_.forget();
      for (Button &b : this->buttons_)
        b.available = false;
      this->changed_();
    }
  }
  if (this->confirm_ && (int32_t) (esphome::millis() - this->confirm_until_ms_) >= 0) {
    this->confirm_ = false;
    this->changed_();
  }
}

void HabiticaApp::apply_stats(const HabiticaStats &news) {
  const HabiticaReactions r = this->model_.apply(news);
  if (r.level_up) {
    ESP_LOGI(TAG, "Level up: %d", this->model_.stats().level);
    this->hub_->react(StateId::LEVEL_UP);
  } else if (r.hurt) {
    this->hub_->react(StateId::HURT);
  }
  if (r.activity_changed)
    this->hold_(r.activity);
  this->save_();
  this->changed_();
}

void HabiticaApp::hold_(HabiticaActivity activity) {
  if (activity == HabiticaActivity::FAINTED) {
    this->hub_->set_activity("habitica", StateId::FAINTED);
  } else if (activity == HabiticaActivity::RESTING) {
    this->hub_->set_activity("habitica", StateId::RESTING);
  } else {
    this->hub_->clear_activity("habitica");
  }
}

void HabiticaApp::event(const std::string &kind, const std::string &message) {
  if (kind == "drop") {
    this->hub_->react(StateId::DROP);
  } else if (kind != "quest") {
    ESP_LOGW(TAG, "Unknown event kind '%s'; known: drop, quest", kind.c_str());
    return;
  }
  if (!message.empty())
    this->hub_->post_message(message, this->message_seconds_);
}

void HabiticaApp::save_() {
  const HabiticaStats &s = this->model_.stats();
  Saved saved{s.hp, s.hp_max, s.mp, s.mp_max, s.xp, s.xp_next, s.gold, s.level, -1, s.resting};
  for (int i = 0; i < 4; i++) {
    if (s.cls == CLASSES[i])
      saved.cls = i;
  }
  this->pref_.save(&saved);
}

// The sheet from before a reboot, shown until HA sends its own numbers.
void HabiticaApp::restore_() {
  this->pref_ = esphome::global_preferences->make_preference<Saved>(esphome::fnv1_hash("daruma_habitica"));
  HabiticaStats base;
  base.hp_max = this->hp_max_;
  Saved saved{};
  if (this->pref_.load(&saved)) {
    HabiticaStats s;
    s.hp = saved.hp;
    s.hp_max = saved.hp_max;
    s.mp = saved.mp;
    s.mp_max = saved.mp_max;
    s.xp = saved.xp;
    s.xp_next = saved.xp_next;
    s.gold = saved.gold;
    s.level = saved.level;
    s.cls = saved.cls >= 0 && saved.cls < 4 ? CLASSES[saved.cls] : "";
    s.resting = saved.resting;
    base = habitica_merge(base, s);
  }
  this->model_.restore(base);
  if (this->model_.activity() != HabiticaActivity::NONE)
    this->hold_(this->model_.activity());
}

void HabiticaApp::changed_() {
  if (this->hub_ != nullptr)
    this->hub_->request_redraw();
}

std::string HabiticaApp::word_(const char *key) const { return this->hub_->theme().word(PREFIX + key); }

// "Lv 12 · HP 45", for the board.
std::string HabiticaApp::status() {
  const HabiticaStats &s = this->model_.stats();
  if (s.level < 0)
    return "";
  std::string line = fill(this->word_("status"), "level", std::to_string(s.level));
  return fill(line, "hp", habitica_shown(s.hp, true));
}

void HabiticaApp::on_open() {
  this->open_ = true;
  this->confirm_ = false;
  this->focus_.reset();
}

void HabiticaApp::on_close() {
  this->open_ = false;
  this->confirm_ = false;
}

bool HabiticaApp::back() {
  if (!this->confirm_)
    return false;
  this->confirm_ = false;
  this->changed_();
  return true;
}

// The buttons on show now: the available ones, in the build's order.
std::vector<int> HabiticaApp::shown_buttons_() const {
  std::vector<int> shown;
  for (size_t i = 0; i < this->buttons_.size(); i++) {
    if (this->buttons_[i].available && this->connected_)
      shown.push_back((int) i);
  }
  return shown;
}

void HabiticaApp::press_(int button) {
  const Button &b = this->buttons_[button];
  // A potion spends gold: ask once first.
  if (b.key == POTION && !this->confirm_) {
    this->confirm_ = true;
    this->confirm_until_ms_ = esphome::millis() + CONFIRM_MS;
    // The focus starts on Cancel, so a second SELECT spends nothing.
    this->focus_.set_count(2);
    this->focus_.set(1);
    this->changed_();
    return;
  }
  this->confirm_ = false;
  ESP_LOGI(TAG, "Press %s", b.entity.c_str());
  if (this->presser_)
    this->presser_(b.entity);
  this->changed_();
}

void HabiticaApp::tap_target_(const Target &target) {
  if (target.button < 0) {
    this->back();
    return;
  }
  this->press_(target.button);
}

bool HabiticaApp::input(Input input, int x, int y) {
  this->focus_.set_count((int) this->targets_.size());
  switch (input) {
    case Input::TAP:
      for (const Target &t : this->targets_) {
        if (t.rect.contains(x, y)) {
          this->tap_target_(t);
          return true;
        }
      }
      return false;
    case Input::SELECT:
      if (this->focus_.valid())
        this->tap_target_(this->targets_[this->focus_.index()]);
      return true;
    case Input::NEXT:
    case Input::PREV:
      if (input == Input::NEXT) {
        this->focus_.next();
      } else {
        this->focus_.prev();
      }
      this->changed_();
      return true;
    default:
      return false;
  }
}

void HabiticaApp::draw(AppView &v) {
  this->targets_.clear();
  const HabiticaStats &s = this->model_.stats();
  if (s.level < 0 && !habitica_known(s.hp)) {
    const std::string message = this->word_(this->connected_ ? "loading" : "offline");
    v.display.print(v.x + v.w / 2, v.y + v.h / 2, v.small, v.theme.muted, TextAlign::CENTER,
                    fit_text(v.display, v.small, message, v.w - v.px(24)).c_str(), v.theme.panel);
    UiTree::add("text", message, Rect{v.x, v.y + v.h / 2 - v.px(10), v.w, v.px(20)});
    return;
  }
  this->draw_head_(v);
  // A fixed order with labels, so gray and mono screens tell them apart.
  this->draw_bar_(v, 0, "hp", s.hp, s.hp_max, "hp");
  this->draw_bar_(v, 1, "xp", s.xp, s.xp_next, "xp");
  this->draw_bar_(v, 2, "mp", s.mp, s.mp_max, "mp");
  if (this->confirm_) {
    this->draw_confirm_(v);
  } else {
    this->draw_buttons_(v);
  }
  this->focus_.set_count((int) this->targets_.size());
}

// "a · b", or the one that is there.
static std::string joined(const std::string &a, const std::string &b) {
  return a.empty() || b.empty() ? a + b : a + " · " + b;
}

// The top line: "Lv 12 · Healer", "In the inn" while resting, and the gold.
// When it all does not fit, the inn goes before the class.
void HabiticaApp::draw_head_(AppView &v) {
  auto &it = v.display;
  const Theme &t = v.theme;
  const HabiticaStats &s = this->model_.stats();
  const int pad = v.px(12);
  const int cy = v.y + v.px(16);
  // The gold: a coin in the gold color, the amount in ink, so it reads on
  // light themes too.
  const std::string gold = habitica_known(s.gold) ? fill(this->word_("gold"), "gold", habitica_shown(s.gold)) : "";
  const int coin = v.px(5);
  int gold_w = 0;
  if (!gold.empty()) {
    const int text_w = text_width(it, v.small, gold);
    it.print(v.x + v.w - pad, cy, v.small, t.on(t.panel, t.ink), TextAlign::CENTER_RIGHT, gold.c_str(), t.panel);
    it.filled_circle(v.x + v.w - pad - text_w - v.px(4) - coin, cy, coin, t.on(t.panel, t.color(PREFIX + "gold")));
    gold_w = text_w + v.px(12) + 2 * coin;
  }
  const int room = v.w - 2 * pad - gold_w;
  const std::string level = s.level >= 0 ? fill(this->word_("level"), "level", std::to_string(s.level)) : "";
  const std::string inn = s.resting == 1 ? this->word_("in_inn") : "";
  std::string head = joined(joined(level, s.cls.empty() ? "" : this->word_(s.cls.c_str())), inn);
  if (!inn.empty() && text_width(it, v.text, head) > room)
    head = joined(level, inn);
  it.print(v.x + pad, cy, v.text, t.on(t.panel, t.ink), TextAlign::CENTER_LEFT,
           fit_text(it, v.text, head, room).c_str(), t.panel);
  UiTree::add("text", head, Rect{v.x + pad, cy - v.px(10), room, v.px(20)}, false, gold);
}

// One bar: its label, the bar filled to value / max, and the numbers.
void HabiticaApp::draw_bar_(AppView &v, int row, const char *label, float value, float max, const char *color) {
  auto &it = v.display;
  const Theme &t = v.theme;
  const int pad = v.px(12);
  const int cy = v.y + v.px(42) + row * v.px(22);
  const std::string name = this->word_(label);
  it.print(v.x + pad, cy, v.small, t.on(t.panel, t.ink), TextAlign::CENTER_LEFT, name.c_str(), t.panel);
  // HP rounds up, so a sliver left does not read as 0.
  const bool up = row == 0;
  std::string numbers = habitica_shown(value, up);
  if (habitica_known(max))
    numbers += " / " + habitica_shown(max, up);
  const int numbers_w = v.px(76);
  it.print(v.x + v.w - pad, cy, v.small, t.on(t.panel, t.muted), TextAlign::CENTER_RIGHT,
           fit_text(it, v.small, numbers, numbers_w).c_str(), t.panel);
  const int bh = v.px(10);
  const Rect bar{v.x + pad + v.px(30), cy - bh / 2, v.w - 2 * pad - v.px(30) - numbers_w - v.px(6), bh};
  // An outlined track: it shows on gray and mono screens, where the fill's
  // color may come out like the panel's.
  const int radius = bh / 2;
  Utilities::Draw::roundedRectangle(&it, bar.x, bar.y, bar.w, bar.h, radius, t.on(t.panel, t.muted));
  Utilities::Draw::roundedRectangle(&it, bar.x + 1, bar.y + 1, bar.w - 2, bar.h - 2, radius - 1, t.panel);
  const int filled = habitica_fill(value, max, bar.w - 2);
  if (filled > 0)
    Utilities::Draw::roundedRectangle(&it, bar.x + 1, bar.y + 1, std::max(filled, bh - 2), bar.h - 2, radius - 1,
                                      t.on(t.panel, t.color(PREFIX + color)));
  UiTree::add("meter", name, Rect{v.x + pad, cy - v.px(10), v.w - 2 * pad, v.px(20)}, false, numbers);
}

// Where the buttons go: under the bars, to the bottom of the app area.
Rect HabiticaApp::buttons_area_(const AppView &v) const {
  const int pad = v.px(12);
  const int top = v.y + v.px(104);
  return Rect{v.x + pad, top, v.w - 2 * pad, v.y + v.h - v.px(4) - top};
}

// The HA buttons that are available, two to a row.
void HabiticaApp::draw_buttons_(AppView &v) {
  const std::vector<int> shown = this->shown_buttons_();
  if (shown.empty())
    return;
  const Rect area = this->buttons_area_(v);
  const int gap = v.px(8);
  const int cols = std::min(2, (int) shown.size());
  const int rows = ((int) shown.size() + 1) / 2;
  const int bh = std::min(v.px(34), (area.h - gap) / 2);
  const Rect grid{area.x, area.y, area.w, rows * bh + (rows - 1) * gap};
  for (size_t i = 0; i < shown.size(); i++) {
    const Rect r = grid.cell((int) i, cols, rows, gap);
    const bool focused = v.focus && (int) i == this->focus_.index();
    this->draw_button_(v, r, this->word_(this->buttons_[shown[i]].key.c_str()), focused, false);
    this->targets_.push_back(Target{Rect{r.x - v.x, r.y - v.y, r.w, r.h}, shown[i]});
  }
}

// "Buy a health potion for 25 gold?" with Buy and Cancel.
void HabiticaApp::draw_confirm_(AppView &v) {
  auto &it = v.display;
  const Theme &t = v.theme;
  const Rect area = this->buttons_area_(v);
  const std::string question = this->word_("potion_confirm");
  // On one line when it fits, else on two.
  const size_t split = text_width(it, v.small, question) > area.w ? habitica_split(question) : std::string::npos;
  const int line = v.px(15);
  const int qy = area.y + v.px(10) - (split == std::string::npos ? 0 : v.px(4));
  const Color ink = t.on(t.panel, t.ink);
  if (split == std::string::npos) {
    it.print(area.cx(), qy, v.small, ink, TextAlign::CENTER, fit_text(it, v.small, question, area.w).c_str(), t.panel);
  } else {
    it.print(area.cx(), qy, v.small, ink, TextAlign::CENTER,
             fit_text(it, v.small, question.substr(0, split), area.w).c_str(), t.panel);
    it.print(area.cx(), qy + line, v.small, ink, TextAlign::CENTER,
             fit_text(it, v.small, question.substr(split + 1), area.w).c_str(), t.panel);
  }
  const int last = qy + (split == std::string::npos ? 0 : line);
  UiTree::add("text", question, Rect{area.x, qy - v.px(10), area.w, last - qy + v.px(20)});
  const int gap = v.px(8);
  const int bh = std::min(v.px(34), area.bottom() - (last + v.px(14)));
  const Rect row{area.x, area.bottom() - bh, area.w, bh};
  int potion = -1;
  for (size_t i = 0; i < this->buttons_.size(); i++) {
    if (this->buttons_[i].key == POTION)
      potion = (int) i;
  }
  const Rect buy = row.cell(0, 2, 1, gap);
  const Rect cancel = row.cell(1, 2, 1, gap);
  this->draw_button_(v, buy, this->word_("buy"), v.focus && this->focus_.index() == 0, true);
  this->draw_button_(v, cancel, this->word_("cancel"), v.focus && this->focus_.index() == 1, false);
  this->targets_.push_back(Target{Rect{buy.x - v.x, buy.y - v.y, buy.w, buy.h}, potion});
  this->targets_.push_back(Target{Rect{cancel.x - v.x, cancel.y - v.y, cancel.w, cancel.h}, -1});
}

void HabiticaApp::draw_button_(AppView &v, const Rect &r, const std::string &label, bool focused, bool primary) {
  auto &it = v.display;
  const Theme &t = v.theme;
  const int radius = std::min(v.px(10), r.h / 2);
  if (focused)
    Utilities::Draw::roundedRectangle(&it, r.x - v.px(3), r.y - v.px(3), r.w + v.px(6), r.h + v.px(6), radius + v.px(3),
                                      t.on(t.panel, t.focus_color()));
  // A card with a rim, as a Controls tile; the confirming one filled.
  const Color fill_color = primary ? t.on(t.panel, t.color(PREFIX + "hp")) : t.panel;
  const int rim = v.px(2);
  Utilities::Draw::roundedRectangle(&it, r.x, r.y, r.w, r.h, radius, t.on(t.panel, t.muted));
  Utilities::Draw::roundedRectangle(&it, r.x + rim, r.y + rim, r.w - 2 * rim, r.h - 2 * rim, radius - rim, fill_color);
  it.print(r.cx(), r.cy(), v.small, t.on(fill_color, primary ? t.panel : t.ink), TextAlign::CENTER,
           fit_text(it, v.small, label, r.w - v.px(8)).c_str(), fill_color);
  UiTree::add("button", label, r, focused);
}

}  // namespace Daruma
