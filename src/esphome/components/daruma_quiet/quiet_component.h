#pragma once

#include <vector>

#include "esphome/components/daruma/hub.h"
#include "esphome/components/datetime/time_entity.h"
#include "esphome/components/light/light_state.h"
#include "esphome/components/number/number.h"
#include "esphome/components/switch/switch.h"
#include "esphome/components/time/real_time_clock.h"
#include "esphome/core/component.h"
#include "esphome/core/preferences.h"
#include "quiet_rules.h"

namespace Daruma {

// Quiet hours, Do not disturb and the idle screen.
//
// - Do not disturb (the switch, or quiet hours): info prompts and HA
//   messages wait (Hub::add_card_hold), Sounds goes off and comes back as
//   it was, and a mark shows on the info line. Urgent prompts still show
//   and still sound.
// - Quiet hours (two time entities; needs a valid clock): Do not disturb,
//   the persona asleep, the screen at quiet_brightness. An input wakes the
//   screen for wake_for; that first input does nothing else.
// - Idle: after "Dim after" minutes with no input, prompt or message, the
//   screen dims to idle_brightness.
//
// The screen never goes above the person's own brightness, which comes
// back when the screen wakes. It and the Sounds state survive a reboot.
//
// As a module it offers quiet.dnd (toggles Do not disturb).
class QuietComponent : public esphome::Component, public Module {
 public:
  QuietComponent() : Module("quiet") {}

  void set_screen(esphome::light::LightState *screen) { this->screen_ = screen; }
  void set_sounds(esphome::switch_::Switch *sounds) { this->sounds_ = sounds; }
  void set_clock(esphome::time::RealTimeClock *clock) { this->clock_ = clock; }
  void set_dnd_switch(esphome::switch_::Switch *dnd) { this->dnd_switch_ = dnd; }
  void set_quiet_times(esphome::datetime::TimeEntity *start, esphome::datetime::TimeEntity *end) {
    this->start_ = start;
    this->end_ = end;
  }
  void set_dim_after(esphome::number::Number *minutes) { this->dim_after_ = minutes; }
  void set_quiet_brightness(float b) { this->quiet_brightness_ = b; }
  void set_idle_brightness(float b) { this->idle_brightness_ = b; }
  void set_wake_for(uint32_t ms) { this->wake_ms_ = ms; }
  void add_dnd_during(StateId activity) { this->dnd_during_.push_back(activity); }
  void set_limits(int cap, uint32_t keep_ms) { this->limits_ = CardLimits{cap, keep_ms}; }

  void setup(Hub &hub) override;
  void loop() override;
  void dump_config() override;
  float get_setup_priority() const override { return esphome::setup_priority::LATE; }

  // Inside quiet hours now (with a valid clock).
  bool quiet() const { return this->quiet_; }
  // Do not disturb now: the switch or quiet hours.
  bool dnd() const { return this->dnd_on_; }

 protected:
  // What survives a reboot: Sounds as it was before Do not disturb, and
  // the screen's own brightness while it is dimmed.
  struct Saved {
    bool holding_sounds{false};
    bool sounds_were_on{false};
    bool dimmed{false};
    bool screen_on{true};
    float brightness{1.0f};
  };

  bool quiet_now_() const;
  bool holds_cards_() const;
  void update_dnd_(uint32_t now);
  Quiet::ScreenNow screen_now_(uint32_t now) const;
  void apply_dnd_(bool on);
  void apply_level_(Quiet::Level level);
  void save_() { this->pref_.save(&this->saved_); }
  void draw_mark_(esphome::display::Display &display);

  Hub *hub_{nullptr};
  esphome::light::LightState *screen_{nullptr};
  esphome::switch_::Switch *sounds_{nullptr};
  esphome::time::RealTimeClock *clock_{nullptr};
  esphome::switch_::Switch *dnd_switch_{nullptr};
  esphome::datetime::TimeEntity *start_{nullptr};
  esphome::datetime::TimeEntity *end_{nullptr};
  esphome::number::Number *dim_after_{nullptr};
  float quiet_brightness_{0.0f};
  float idle_brightness_{0.3f};
  uint32_t wake_ms_{30000};
  std::vector<StateId> dnd_during_;
  CardLimits limits_;

  esphome::ESPPreferenceObject pref_;
  Saved saved_;
  bool quiet_{false};
  bool dnd_on_{false};
  bool ready_{false};
  Quiet::Level applied_{Quiet::Level::NORMAL};
};

}  // namespace Daruma
