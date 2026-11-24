#include "quiet_component.h"

#include <algorithm>

#include "esphome/core/hal.h"
#include "esphome/core/log.h"

namespace Daruma {

static const char *const TAG = "daruma.quiet";
// Before the first gesture filter of core and voice: a wake eats the tap.
static const int WAKE_FILTER_PRIORITY = 200;
// The info line's mark draws over the other layers.
static const int MARK_LAYER = 95;
// Without a clock after this long, Do not disturb follows the switch alone.
static const uint32_t CLOCK_WAIT_MS = 60000;

void QuietComponent::setup(Hub &hub) {
  this->hub_ = &hub;
  this->pref_ = esphome::global_preferences->make_preference<Saved>(esphome::fnv1_hash("daruma_quiet"), true);
  if (!this->pref_.load(&this->saved_))
    this->saved_ = Saved{};
  // Sounds off from before a reboot stays held until Do not disturb is
  // known; a dimmed screen keeps its own brightness for later.
  this->dnd_on_ = this->saved_.holding_sounds;
  this->applied_ = this->saved_.dimmed ? Quiet::Level::IDLE : Quiet::Level::NORMAL;
  hub.set_sounds_held(this->saved_.holding_sounds && this->saved_.sounds_were_on);
  hub.set_card_limits(this->limits_);
  hub.add_card_hold([this]() { return this->holds_cards_(); });
  hub.add_gesture_filter(WAKE_FILTER_PRIORITY, [this](const GestureEvent &) {
    // The first input on a quiet screen only wakes it (loop() sees the poke).
    return this->applied_ == Quiet::Level::QUIET;
  });
  hub.add_layer(MARK_LAYER, [this](esphome::display::Display &d) { this->draw_mark_(d); });
  hub.add_action("quiet.dnd", [this]() {
    if (this->dnd_switch_ != nullptr)
      this->dnd_switch_->toggle();
  });
}

void QuietComponent::dump_config() {
  ESP_LOGCONFIG(TAG, "Quiet:");
  ESP_LOGCONFIG(TAG, "  Quiet brightness: %.0f%%, idle brightness: %.0f%%", this->quiet_brightness_ * 100,
                this->idle_brightness_ * 100);
  ESP_LOGCONFIG(TAG, "  Wake for: %u s", (unsigned) (this->wake_ms_ / 1000));
  ESP_LOGCONFIG(TAG, "  Cards: at most %d wait, for %u min", this->limits_.cap,
                (unsigned) (this->limits_.keep_ms / 60000));
  for (StateId s : this->dnd_during_)
    ESP_LOGCONFIG(TAG, "  Cards wait during: %s", state_name(s));
}

bool QuietComponent::quiet_now_() const {
  if (this->clock_ == nullptr || this->start_ == nullptr || this->end_ == nullptr)
    return false;
  if (!this->start_->has_state() || !this->end_->has_state())
    return false;
  const auto now = this->clock_->now();
  if (!now.is_valid())
    return false;
  return Quiet::in_range(Quiet::minute_of_day(now.hour, now.minute),
                         Quiet::minute_of_day(this->start_->hour, this->start_->minute),
                         Quiet::minute_of_day(this->end_->hour, this->end_->minute));
}

bool QuietComponent::holds_cards_() const {
  if (this->dnd_on_)
    return true;
  for (StateId s : this->dnd_during_) {
    if (this->hub_->holds_activity(s))
      return true;
  }
  return false;
}

void QuietComponent::loop() {
  if (this->hub_ == nullptr)
    return;
  const uint32_t now = esphome::millis();
  this->update_dnd_(now);
  const Quiet::Level level = Quiet::level(this->screen_now_(now));
  if (level != this->applied_)
    this->apply_level_(level);
}

void QuietComponent::update_dnd_(uint32_t now) {
  // Until the clock is set, quiet hours are unknown: wait a while before
  // Do not disturb ends on a held Sounds.
  const bool clock_ok = this->clock_ == nullptr || this->clock_->now().is_valid();
  if (!this->ready_ && (clock_ok || now > CLOCK_WAIT_MS))
    this->ready_ = true;
  const bool quiet = this->quiet_now_();
  if (quiet != this->quiet_) {
    this->quiet_ = quiet;
    this->hub_->set_asleep(quiet);
    ESP_LOGI(TAG, "Quiet hours: %s", quiet ? "on" : "off");
  }
  if (!this->ready_)
    return;
  const bool dnd = this->quiet_ || (this->dnd_switch_ != nullptr && this->dnd_switch_->state);
  if (dnd != this->dnd_on_ || dnd != this->hub_->info_mark_on())
    this->apply_dnd_(dnd);
}

Quiet::ScreenNow QuietComponent::screen_now_(uint32_t now) const {
  Quiet::ScreenNow s;
  s.quiet = this->quiet_;
  s.card_open = this->hub_->prompt_open();
  s.idle_ms = now - this->hub_->last_activity();
  s.wake_ms = this->wake_ms_;
  const float minutes = this->dim_after_ != nullptr && this->dim_after_->has_state() ? this->dim_after_->state : 0;
  s.dim_after_ms = minutes > 0 ? (uint32_t) (minutes * 60000) : 0;
  return s;
}

void QuietComponent::apply_dnd_(bool on) {
  this->dnd_on_ = on;
  this->hub_->set_info_mark(on);
  ESP_LOGI(TAG, "Do not disturb: %s", on ? "on" : "off");
  if (this->sounds_ == nullptr)
    return;
  if (on) {
    if (!this->saved_.holding_sounds) {
      this->saved_.holding_sounds = true;
      this->saved_.sounds_were_on = this->sounds_->state;
      this->save_();
    }
    if (this->sounds_->state)
      this->sounds_->turn_off();
    this->hub_->set_sounds_held(this->saved_.sounds_were_on);
    return;
  }
  if (this->saved_.holding_sounds) {
    if (this->saved_.sounds_were_on)
      this->sounds_->turn_on();
    this->saved_.holding_sounds = false;
    this->save_();
  }
  this->hub_->set_sounds_held(false);
}

void QuietComponent::apply_level_(Quiet::Level level) {
  const Quiet::Level was = this->applied_;
  this->applied_ = level;
  ESP_LOGD(TAG, "Screen: %s", level == Quiet::Level::QUIET ? "quiet" : level == Quiet::Level::IDLE ? "idle" : "normal");
  if (this->screen_ == nullptr)
    return;
  // Leaving normal: keep the person's own brightness to come back to.
  if (was == Quiet::Level::NORMAL) {
    const auto &v = this->screen_->remote_values;
    this->saved_.screen_on = v.is_on();
    this->saved_.brightness = v.get_brightness();
  }
  this->saved_.dimmed = level != Quiet::Level::NORMAL;
  this->save_();
  const float base = this->saved_.screen_on ? this->saved_.brightness : 0.0f;
  const float target = Quiet::brightness(level, base, this->quiet_brightness_, this->idle_brightness_);
  auto call = this->screen_->make_call();
  if (target <= 0.0f) {
    call.set_state(false);
  } else {
    call.set_state(true);
    call.set_brightness(target);
  }
  call.perform();
}

void QuietComponent::draw_mark_(esphome::display::Display &display) {
  const Rect box = this->hub_->info_mark();
  if (box.empty() || !this->hub_->message().empty())
    return;
  // Do not disturb: a filled circle with a bar across it.
  const Theme &theme = this->hub_->theme();
  const esphome::Color fill = theme.fit(theme.color("quiet.dnd"));
  const esphome::Color bar = theme.on(fill, esphome::Color::WHITE);
  const int r = box.h / 2;
  const int cx = box.x + box.w / 2;
  const int cy = box.y + box.h / 2;
  display.filled_circle(cx, cy, r, fill);
  const int half = std::max(2, r * 3 / 5);
  const int thick = std::max(2, r / 3);
  display.filled_rectangle(cx - half, cy - thick / 2, 2 * half, thick, bar);
}

}  // namespace Daruma
