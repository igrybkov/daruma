#pragma once

// The random events engine on the device: it feeds the engine
// (random_events.h) what the hub shows, plays what the engine picks on the
// active persona, and tells Home Assistant. The build makes it only when a
// persona or the device yaml has events (daruma/__init__.py).

#include "esphome/core/defines.h"

#ifdef USE_DARUMA_RANDOM_EVENTS

#include <string>
#include <vector>

#include "esphome/components/api/custom_api_device.h"
#include "esphome/components/event/event.h"
#include "esphome/components/time/real_time_clock.h"
#include "esphome/core/component.h"
#include "esphome/core/preferences.h"
#include "hub.h"
#include "random_events.h"

namespace Daruma {

class RandomEventsComponent : public esphome::Component, public esphome::api::CustomAPIDevice {
 public:
  explicit RandomEventsComponent(Hub *hub) : hub_(hub) {}

  // --- Set by the build -------------------------------------------------------
  void set_tick(uint32_t min_ms, uint32_t max_ms) {
    this->tick_min_ms_ = min_ms;
    this->tick_max_ms_ = max_ms;
  }
  void set_clock(esphome::time::RealTimeClock *clock) { this->clock_ = clock; }
  void set_event(esphome::event::Event *event) { this->event_ = event; }
  // An activity that holds events back while it is on (pomodoro's focus).
  void add_quiet(StateId activity) { this->quiet_.push_back(activity); }
  // A persona's events. `id` is the persona's id, for Home Assistant.
  void add_pool(Persona *persona, const char *id, const RandomEvents::EventDef *events, uint8_t count);

  // --- Set by the HA entities ---------------------------------------------------
  void set_enabled(bool enabled) { this->enabled_ = enabled; }
  void set_liveliness(float percent) { this->liveliness_ = percent / 100.0f; }
  void set_min_gap(float minutes) { this->min_gap_ms_ = (uint32_t) (minutes * 60000.0f); }

  // play_random_event: a named event of the active persona, or "" for one
  // the engine picks.
  void play(std::string name);

  void setup() override;
  void loop() override;
  void dump_config() override;
  // After the hub, whose personas and filters it uses.
  float get_setup_priority() const override { return esphome::setup_priority::LATE; }

 protected:
  struct Pool {
    Persona *persona;
    const char *id;
    const RandomEvents::EventDef *events;
    uint8_t count;
    std::vector<RandomEvents::EventState> states;
    // A cooldown stamp per event; only events with a cooldown keep one.
    std::vector<esphome::ESPPreferenceObject> stamps;
  };

  // Rolls: `rolls` adds the switch to the gates.
  RandomEvents::Context context_(bool rolls) const;
  // A menu, app, prompt, screen, quiet activity, reaction or voice phase is
  // up, or HA is gone.
  bool screen_blocked_() const;
  void follow_persona_();
  void step_(uint32_t now);
  void start_(int index, bool manual, uint32_t now);
  void announce_(const RandomEvents::EventDef &event, bool manual);
  // Puts the phase's animation on the persona.
  void show_();
  // Ends a playing event at once: input, a blocked screen or a reaction.
  void stop_();
  uint32_t wait_ms_();

  Hub *hub_;
  esphome::time::RealTimeClock *clock_{nullptr};
  esphome::event::Event *event_{nullptr};
  std::vector<StateId> quiet_;
  std::vector<Pool> pools_;
  Pool *pool_{nullptr};        // The active persona's, or none.
  Persona *persona_{nullptr};  // The persona the engine follows, and plays on.

  RandomEvents::Engine engine_;
  RandomEvents::Playback playback_;
  RandomEvents::Rng rng_{};

  bool enabled_{true};
  float liveliness_{1.0f};
  uint32_t min_gap_ms_{15 * 60 * 1000};
  uint32_t tick_min_ms_{2 * 60 * 1000};
  uint32_t tick_max_ms_{20 * 60 * 1000};
  uint32_t sampled_ms_{0};    // The last sample.
  uint32_t next_roll_ms_{0};  // The next random roll.
};

}  // namespace Daruma

#endif  // USE_DARUMA_RANDOM_EVENTS
