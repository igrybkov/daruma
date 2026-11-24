#pragma once

// Device settings the hub adds to HA (entity_category: config). They keep
// their values across reboots; the device yaml sets the first value.

#include <string>

#include "hub.h"
#include "esphome/components/select/select.h"
#include "esphome/components/switch/switch.h"
#include "esphome/core/component.h"
#include "esphome/core/preferences.h"

#ifdef USE_TOUCHSCREEN
#include "esphome/components/touchscreen/touchscreen.h"
#endif

#ifdef USE_DARUMA_RANDOM_EVENTS
#include <functional>

#include "esphome/components/number/number.h"
#include "random_events_component.h"
#endif

namespace Daruma {

// "App: Calendar": off takes the app off the board and stops its fetching.
class AppSwitch : public esphome::switch_::Switch, public esphome::Component {
 public:
  AppSwitch(Hub *hub, std::string app) : hub_(hub), app_(std::move(app)) {}
  void setup() override;
  // After the hub has set its modules up.
  float get_setup_priority() const override { return esphome::setup_priority::LATE; }

 protected:
  void write_state(bool state) override;
  Hub *hub_;
  std::string app_;
};

// One binding as a select: "none" or any action. Stores the chosen action by
// name, so a build with more or fewer modules keeps the choice.
class BindingSelect : public esphome::select::Select, public esphome::Component {
 public:
  BindingSelect(Hub *hub, int binding) : hub_(hub), binding_(binding) {}
  void setup() override;
  float get_setup_priority() const override { return esphome::setup_priority::LATE; }

 protected:
  void control(size_t index) override;
  Hub *hub_;
  int binding_;
  esphome::ESPPreferenceObject pref_;
};

// A persona param of type choice, as a select.
class ParamSelect : public esphome::select::Select, public esphome::Component {
 public:
  ParamSelect(Hub *hub, Persona *persona, std::string param) : hub_(hub), persona_(persona), param_(std::move(param)) {}
  void setup() override;
  float get_setup_priority() const override { return esphome::setup_priority::LATE; }

 protected:
  void control(size_t index) override;
  Hub *hub_;
  Persona *persona_;
  std::string param_;
  esphome::ESPPreferenceObject pref_;
};

// A persona param of type bool, as a switch.
class ParamSwitch : public esphome::switch_::Switch, public esphome::Component {
 public:
  ParamSwitch(Hub *hub, Persona *persona, std::string param) : hub_(hub), persona_(persona), param_(std::move(param)) {}
  void setup() override;
  float get_setup_priority() const override { return esphome::setup_priority::LATE; }

 protected:
  void write_state(bool state) override;
  Hub *hub_;
  Persona *persona_;
  std::string param_;
};

#ifdef USE_DARUMA_RANDOM_EVENTS
// "Random events": off stops the rolls. play_random_event still plays.
class RandomEventsSwitch : public esphome::switch_::Switch, public esphome::Component {
 public:
  explicit RandomEventsSwitch(RandomEventsComponent *engine) : engine_(engine) {}
  void setup() override;
  float get_setup_priority() const override { return esphome::setup_priority::LATE; }

 protected:
  void write_state(bool state) override;
  RandomEventsComponent *engine_;
};

// A number setting that keeps its value ("Liveliness", "Min gap"). `apply`
// gets every value, the first one at setup.
class TunableNumber : public esphome::number::Number, public esphome::Component {
 public:
  TunableNumber(float initial, std::function<void(float)> apply) : initial_(initial), apply_(std::move(apply)) {}
  void setup() override;
  float get_setup_priority() const override { return esphome::setup_priority::LATE; }

 protected:
  void control(float value) override;
  float initial_;
  std::function<void(float)> apply_;
  esphome::ESPPreferenceObject pref_;
};
#endif

#ifdef USE_TOUCHSCREEN
// Feeds a touch screen into the hub's screen input.
class TouchInput : public esphome::touchscreen::TouchListener {
 public:
  explicit TouchInput(Hub *hub) : hub_(hub) {}
  void touch(esphome::touchscreen::TouchPoint tp) override {
    this->id_ = tp.id;
    this->hub_->touch_start(tp.x, tp.y);
  }
  void update(const esphome::touchscreen::TouchPoints_t &points) override {
    const auto *p = follow_finger(points, &this->id_, [](const esphome::touchscreen::TouchPoint &tp) {
      return tp.state == esphome::touchscreen::STATE_PRESSED || tp.state == esphome::touchscreen::STATE_UPDATED;
    });
    if (p != nullptr)
      this->hub_->touch_move(p->x, p->y);
  }
  void release() override { this->hub_->touch_end(); }

 protected:
  Hub *hub_;
  int id_{-1};
};
#endif

}  // namespace Daruma
