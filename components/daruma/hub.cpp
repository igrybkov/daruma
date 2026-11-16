#include "hub.h"

#include <algorithm>
#include <cmath>
#include <cstdlib>

#include "esphome/core/hal.h"
#include "esphome/core/helpers.h"
#include "esphome/core/log.h"
#include "ui_tree.h"

namespace Daruma {

static const char *const TAG = "daruma";
static const uint32_t SECOND_WINK_MS = 700;

void Hub::setup() {
  // The layout first: modules size their screens from it.
  if (this->display_ != nullptr)
    this->apply_layout_(this->display_->get_width(), this->display_->get_height());
  // Gray and mono screens: each persona's theme in the screen's colors. They
  // live as long as the hub.
  const ColorMode mode = this->profile().colors;
  if (mode != ColorMode::FULL) {
    for (auto *persona : this->personas_)
      persona->set_theme(new Theme(persona->theme().for_mode(mode)));  // NOLINT
  }
  for (auto *module : this->modules_) {
    ESP_LOGD(TAG, "Setting up module %s", module->module_name().c_str());
    this->setting_up_ = module->module_name();
    module->setup(*this);
  }
  this->setting_up_.clear();
  for (const auto &binding : this->bindings_) {
    if (!binding.action.empty() && binding.action != "none" && !this->has_action(binding.action)) {
      ESP_LOGE(TAG, "Binding %s.%s: no module registered the action '%s'", this->inputs_[binding.input].name.c_str(),
               gesture_name(binding.gesture), binding.action.c_str());
    }
  }
  // Board order: the apps: list first, then the rest as they came.
  std::stable_sort(this->apps_.begin(), this->apps_.end(), [this](const App &a, const App &b) {
    auto rank = [this](const App &app) {
      auto it = std::find(this->app_order_.begin(), this->app_order_.end(), app.id);
      return (size_t) (it - this->app_order_.begin());
    };
    return rank(a) < rank(b);
  });
  if (this->persona_ == nullptr) {
    ESP_LOGW(TAG, "No persona registered; the screen stays blank");
  }
}

void Hub::loop() {
  const uint32_t now = esphome::millis();
  if (this->init_in_progress_ && this->happiness_meter_ != nullptr && this->happiness_meter_->has_state()) {
    this->set_happiness((int) this->happiness_meter_->state, true, false);
    this->init_in_progress_ = false;
  }

  if (!this->message_.empty() && (int32_t) (now - this->message_until_) >= 0)
    this->clear_message();

  for (size_t i = 0; i < this->inputs_.size(); i++) {
    const Gesture g = this->inputs_[i].press.tick(now, this->bound_mask_(i));
    if (g != Gesture::NONE)
      this->emit_(i, g, this->touch_.track().x0, this->touch_.track().y0);
  }

  // Drift into Sleepy / Sleeping when nothing has happened for a while.
  if (!this->has_forced_mood_ && !this->has_happiness_changed_(300000)) {
    if (this->mood_ == StateId::SLEEPY && !this->has_mood_changed_(30000)) {
      if (esphome::random_uint32() % 100 < 50) {
        this->sleeping = true;
      } else {
        this->sleepy = false;
      }
    } else if (!this->has_mood_changed_(300000)) {
      uint32_t roll = esphome::random_uint32() % 100;
      if (this->sleeping) {
        if (roll < 50) {
          this->sleeping = false;
        } else {
          // Stays asleep: roll again in 5 minutes, not on the next loop.
          this->last_mood_change_ = now;
        }
      } else if (roll < 10) {
        this->sleepy = true;
      } else {
        this->last_mood_change_ = now;
      }
    }
  }

  const StateId mood = this->compute_mood_();
  if (mood != this->mood_) {
    this->mood_ = mood;
    this->machine_.set_mood(mood);
    this->last_mood_change_ = now;
    ESP_LOGI(TAG, "Mood: %s", state_name(mood));
  }

  // Home Assistant calls that wait for a reply: one at a time, once HA listens.
  const std::string *sent = this->ha_calls_.tick(now, this->ha_link_ && this->ha_link_());
  if (sent != nullptr) {
    ESP_LOGV(TAG, "HA call: %s (%u waiting)", sent->c_str(), (unsigned) this->ha_calls_.queued());
  }

  // Frames: whatever asked for one since the last, no sooner than min_frame.
  // Idle motion (the persona, a ticking clock) only while the gate allows it.
  if (this->display_ != nullptr && this->display_->is_ready() && this->scheduler_.ready(now)) {
    const bool motion = (!this->frame_gate_ || this->frame_gate_()) && this->needs_redraw();
    if (this->scheduler_.pending() || motion) {
      this->full_frame_ = this->scheduler_.full_frame();
      this->display_->update();
      this->scheduler_.drawn(now, this->full_frame_);
      // A draw outside the scheduler repaints everything.
      this->full_frame_ = true;
    }
  }
}

void Hub::dump_config() {
  ESP_LOGCONFIG(TAG, "Daruma hub: %d states", state_count());
  const DisplayProfile &p = this->profile();
  static const char *const COLORS[] = {"full", "gray4", "mono"};
  ESP_LOGCONFIG(TAG, "  Screen: %dx%d %s, unit %.2f; colors %s, %s, frames >= %u ms%s",
                this->layout_.width, this->layout_.height, size_class_name(this->layout_.size_class),
                this->layout_.unit, COLORS[(int) p.colors], p.animate ? "animated" : "stills",
                (unsigned) p.min_frame_ms, p.partial_refresh ? "" : ", full refresh");
  for (auto *persona : this->personas_) {
    ESP_LOGCONFIG(TAG, "  Persona: %s%s", persona->get_name().c_str(), persona == this->persona_ ? " (active)" : "");
  }
  for (auto *module : this->modules_) {
    ESP_LOGCONFIG(TAG, "  Module: %s", module->module_name().c_str());
  }
  for (const auto &binding : this->bindings_) {
    ESP_LOGCONFIG(TAG, "  Binding: %s.%s -> %s%s", this->inputs_[binding.input].name.c_str(),
                  gesture_name(binding.gesture), binding.action.c_str(), binding.idle_only ? " (idle)" : "");
  }
}

// --- State ------------------------------------------------------------------

StateId Hub::state() { return this->machine_.current(esphome::millis()); }

void Hub::started_(StateId state) {
  if (this->persona_ == nullptr)
    return;
  const Behavior &behavior = this->persona_->behavior(state);
  if (behavior.sound[0] != '\0' && this->sound_player_)
    this->sound_player_(behavior.sound);
  if (behavior.say[0] != '\0')
    this->show_message(behavior.say, 4);
}

void Hub::set_activity(const std::string &owner, StateId activity, bool sound) {
  StateId old;
  if (this->machine_.activity_of(owner, &old) && old == activity)
    return;
  this->machine_.set_activity(owner, activity);
  ESP_LOGI(TAG, "Activity: %s (%s)", state_name(activity), owner.c_str());
  if (sound)
    this->started_(activity);
  this->dirty_ = true;
}

void Hub::clear_activity(const std::string &owner) {
  StateId old;
  if (!this->machine_.activity_of(owner, &old))
    return;
  this->machine_.clear_activity(owner);
  ESP_LOGI(TAG, "Activity ended: %s (%s)", state_name(old), owner.c_str());
  this->dirty_ = true;
}

void Hub::react(StateId reaction, uint32_t ms) {
  const StateInfo &info = state_info(reaction);
  if (ms == 0)
    ms = info.duration_ms;
  ESP_LOGI(TAG, "Reaction: %s", state_name(reaction));
  if (ms > 0)
    this->machine_.react(reaction, esphome::millis(), ms);
  this->started_(reaction);
  this->dirty_ = true;
  if (info.celebrates && ms > 0) {
    // Hearts, then a double wink.
    this->set_timeout("celebrate", ms, [this]() {
      this->wink();
      this->set_timeout("celebrate", SECOND_WINK_MS, [this]() { this->wink(); });
    });
  }
}

std::string Hub::sound_for(StateId state) const {
  return this->persona_ != nullptr ? this->persona_->behavior(state).sound : "";
}

// --- Mood -------------------------------------------------------------------

StateId Hub::compute_mood_() {
  if (this->has_forced_mood_)
    return this->forced_mood_;
  if (this->muted() || this->sleeping)
    return StateId::SLEEPING;
  if (this->sleepy)
    return StateId::SLEEPY;
  if (this->happiness_ < -50)
    return StateId::SAD;
  if (this->happiness_ > 50)
    return StateId::HAPPY;
  return StateId::NEUTRAL;
}

void Hub::set_happiness(int value, bool update_last_change, bool publish) {
  this->happiness_ = std::max(-100, std::min(100, value));
  if (publish && this->happiness_meter_ != nullptr) {
    this->happiness_meter_->publish_state(this->happiness_);
  }
  if (update_last_change) {
    this->last_happiness_change_ = esphome::millis();
  }
  ESP_LOGI(TAG, "Happiness: %d", this->happiness_);
}

void Hub::add_happiness(int delta, bool update_last_change) {
  this->set_happiness(this->happiness_ + delta, update_last_change);
}

void Hub::decay_happiness() {
  // Drift 5% toward zero, but not within 15 minutes of a real change.
  if (this->has_happiness_changed_(900000) || this->happiness_ == 0)
    return;
  int delta = this->happiness_ > 0 ? (int) std::max(this->happiness_ * 0.05f, 1.0f)
                                   : (int) std::min(this->happiness_ * 0.05f, -1.0f);
  this->add_happiness(-delta, false);
}

void Hub::force_mood(const std::string &mood) {
  StateId id;
  if (mood.empty() || mood == "Auto" || !state_by_name(mood.c_str(), &id) ||
      state_info(id).kind != StateKind::MOOD) {
    this->has_forced_mood_ = false;
    ESP_LOGI(TAG, "Forced mood: (auto)");
    return;
  }
  this->has_forced_mood_ = true;
  this->forced_mood_ = id;
  ESP_LOGI(TAG, "Forced mood: %s", state_name(id));
}

void Hub::reset_reactions() {
  this->sleepy = false;
  this->sleeping = false;
}

void Hub::set_mute(bool muted) {
  this->mute_ = muted;
  this->dirty_ = true;
}

void Hub::set_hardware_mute(bool muted) {
  this->hardware_mute_ = muted;
  this->dirty_ = true;
}

bool Hub::has_happiness_changed_(uint32_t ms) const {
  return esphome::millis() - this->last_happiness_change_ < ms;
}

bool Hub::has_mood_changed_(uint32_t ms) const { return esphome::millis() - this->last_mood_change_ < ms; }

// --- Message bubble -----------------------------------------------------------

void Hub::show_message(const std::string &text, int seconds) {
  this->message_ = text;
  this->message_until_ = esphome::millis() + std::max(seconds, 1) * 1000;
  this->dirty_ = true;
}

void Hub::clear_message() {
  if (this->message_.empty())
    return;
  this->message_.clear();
  this->dirty_ = true;
}

// --- Screen -----------------------------------------------------------------

void Hub::apply_layout_(int width, int height) {
  if (width == this->layout_.width && height == this->layout_.height)
    return;
  this->layout_ = Layout::compute(width, height);
  this->dirty_ = true;
  ESP_LOGD(TAG, "Layout %dx%d (%s)", width, height, size_class_name(this->layout_.size_class));
}

void Hub::set_profile(int colors, bool animate, uint32_t min_frame_ms, bool partial_refresh,
                        uint16_t full_refresh_every) {
  DisplayProfile profile;
  profile.colors = static_cast<ColorMode>(colors);
  profile.animate = animate;
  profile.min_frame_ms = min_frame_ms;
  profile.partial_refresh = partial_refresh;
  profile.full_refresh_every = full_refresh_every;
  this->scheduler_.set_profile(profile);
}

bool Hub::uses_focus() const {
  bool next = false, prev = false;
  for (const auto &nav : this->navigation_) {
    next = next || nav.nav == Input::NEXT;
    prev = prev || nav.nav == Input::PREV;
  }
  return next && prev;
}

// --- Personas ------------------------------------------------------------------

void Hub::add_persona(Persona *persona) {
  persona->set_signals(&this->signals_);
  persona->set_machine(&this->machine_);
  persona->set_screen(&this->layout_, &this->scheduler_.profile());
  this->personas_.push_back(persona);
  if (this->persona_ == nullptr)
    this->persona_ = persona;
}

bool Hub::set_persona(const std::string &name) {
  for (auto *persona : this->personas_) {
    if (persona->get_name() == name) {
      if (persona != this->persona_) {
        this->persona_ = persona;
        this->dirty_ = true;
        ESP_LOGI(TAG, "Persona: %s", name.c_str());
      }
      return true;
    }
  }
  ESP_LOGW(TAG, "No persona named '%s'", name.c_str());
  return false;
}

// Still screens do not blink, wink or look around.
void Hub::blink() {
  if (this->persona_ != nullptr && this->profile().animate)
    this->persona_->blink();
}

void Hub::wink() {
  if (this->persona_ != nullptr && this->profile().animate)
    this->persona_->wink();
}

void Hub::look_around() {
  if (this->persona_ != nullptr && this->profile().animate)
    this->persona_->look_around();
}

// --- Signals ----------------------------------------------------------------

void Hub::add_progress_source(const std::string &name, float weight) {
  this->progress_.push_back(ProgressSource{name, weight});
}

void Hub::set_progress(const std::string &source, float value, bool behind) {
  for (auto &entry : this->progress_) {
    if (entry.name == source) {
      entry.value = std::max(0.0f, std::min(10.0f, value));
      entry.behind = behind;
      this->update_progress_();
      return;
    }
  }
  // Not in the device yaml's weights: this source does not count.
  ESP_LOGV(TAG, "Progress from %s ignored", source.c_str());
}

void Hub::set_progress_override(bool on) {
  this->progress_override_ = on;
  this->update_progress_();
}

void Hub::set_custom_progress(int value, bool behind) {
  this->custom_progress_ = std::max(0, std::min(10, value));
  this->custom_behind_ = behind;
  this->update_progress_();
}

void Hub::update_progress_() {
  int progress = 0;
  bool behind = false;
  if (this->progress_override_) {
    progress = this->custom_progress_;
    behind = this->custom_behind_;
  } else {
    float sum = 0, weights = 0;
    for (const auto &entry : this->progress_) {
      if (entry.value < 0 || entry.weight <= 0)
        continue;
      sum += entry.value * entry.weight;
      weights += entry.weight;
      behind = behind || entry.behind;
    }
    progress = weights > 0 ? (int) lroundf(sum / weights) : 0;
  }
  if (progress != this->signals_.progress || behind != this->signals_.behind) {
    this->signals_.progress = (uint8_t) progress;
    this->signals_.behind = behind;
    this->dirty_ = true;
    ESP_LOGI(TAG, "Progress: %d%s", progress, behind ? ", behind" : "");
  }
}

void Hub::set_wellbeing(int value) {
  const int8_t v = value < 0 ? -1 : (int8_t) std::min(10, value);
  if (v != this->signals_.wellbeing) {
    this->signals_.wellbeing = v;
    this->dirty_ = true;
    ESP_LOGI(TAG, "Wellbeing: %d", v);
  }
}

void Hub::set_sky(const std::string &sky) {
  static const struct {
    const char *name;
    Sky sky;
  } SKIES[] = {{"Clear", Sky::CLEAR}, {"Cloudy", Sky::CLOUDY}, {"Rain", Sky::RAIN},
               {"Snow", Sky::SNOW},   {"Night", Sky::NIGHT}};
  for (const auto &entry : SKIES) {
    if (sky == entry.name) {
      if (this->signals_.sky != entry.sky) {
        this->signals_.sky = entry.sky;
        this->dirty_ = true;
        ESP_LOGI(TAG, "Sky: %s", entry.name);
      }
      return;
    }
  }
  ESP_LOGW(TAG, "No sky named '%s'", sky.c_str());
}

void Hub::set_hour(int hour) {
  const DayPart part = day_part_for_hour(hour);
  if (part != this->signals_.day_part) {
    this->signals_.day_part = part;
    this->dirty_ = true;
  }
}

void Hub::set_goal(Goal goal, bool announce) {
  const Goal old = this->signals_.goal;
  if (goal == old)
    return;
  this->signals_.goal = goal;
  this->dirty_ = true;
  ESP_LOGI(TAG, "Goal: %d", (int) goal);
  if (announce && goal > old && this->persona_ != nullptr && this->persona_->behavior(StateId::PAINT).own)
    this->react(StateId::PAINT);
}

void Hub::set_weekday(int weekday) {
  if (weekday < 1 || weekday > 7 || weekday == this->signals_.weekday)
    return;
  this->signals_.weekday = (uint8_t) weekday;
  this->dirty_ = true;
  ESP_LOGI(TAG, "Weekday: %d", weekday);
}

// --- Drawing ----------------------------------------------------------------

void Hub::render(esphome::display::Display &display) {
  this->apply_layout_(display.get_width(), display.get_height());
  if (this->renderer_) {
    this->renderer_(display);
  } else {
    this->draw_idle(display, 0.0f);
  }
  // Tap areas, for test runners on the host. Every frame: partial frames
  // draw no layers, but the parts are still there.
  if (UiTree::enabled() && !this->screen_shown_ && !this->ui_open()) {
    for (const auto &entry : this->areas_) {
      if (entry.second.action.empty() || entry.second.action == "none" || !entry.second.area)
        continue;
      const Rect r = entry.second.area();
      if (!r.empty())
        UiTree::add("target", entry.first, r, false, entry.second.action);
    }
  }
}

void Hub::draw_idle(esphome::display::Display &display, float look_y) {
  this->dirty_ = false;
  this->area_ = Rect{};  // A full frame covers it.
  for (auto &screen : this->screens_) {
    if (screen.value(display)) {
      this->screen_shown_ = true;
      return;
    }
  }
  this->screen_shown_ = false;

  this->draw_persona(display, look_y);
  this->drawn_state_ = this->state();
  this->drawn_valid_ = true;

  for (auto &layer : this->layers_) {
    layer.value(display);
  }
}

void Hub::draw_persona(esphome::display::Display &display, float look_y) {
  const StateId state = this->state();
  if (this->persona_ == nullptr) {
    display.fill(esphome::Color::BLACK);
  } else if (this->profile().animate) {
    this->persona_->draw(display, state, look_y);
  } else {
    this->persona_->draw_still(display, state);
  }
}

bool Hub::draw_idle_delta(esphome::display::Display &display) {
  const StateId state = this->state();
  if (this->dirty_ || this->screen_shown_ || this->persona_ == nullptr || !this->drawn_valid_ ||
      state != this->drawn_state_ || this->full_frame_)
    return false;
  auto layers_in = [this, &display](const Rect &area) {
    if (area.empty() || this->layers_.empty())
      return;
    display.start_clipping(esphome::display::Rect(area.x, area.y, area.w, area.h));
    for (auto &layer : this->layers_)
      layer.value(display);
    display.end_clipping();
  };
  // Only a layer's own area changed (a timer tick) and the persona holds
  // still: leave the persona alone, so the frame stays that small.
  const bool layer_only = !this->area_.empty() && !this->persona_->needs_redraw(state);
  if (this->profile().animate && !layer_only) {
    if (!this->persona_->draw_delta(display, state))
      return false;
    // The persona repainted a box that may cross a layer: put the layers back
    // on top, inside that box only.
    layers_in(this->persona_->delta_area());
  } else if (this->area_.empty()) {
    return false;  // Still personas: a full frame.
  }
  // A layer changed inside an area of its own (request_area).
  layers_in(this->area_);
  this->area_ = Rect{};
  return true;
}

Rect Hub::info_line() const {
  if (!this->info_used_)
    return Rect{};
  switch (this->theme().info_line) {
    case InfoPlace::TOP:
      return this->layout_.info_top;
    case InfoPlace::OFF:
      return Rect{};
    default:
      return this->layout_.info;
  }
}

void Hub::draw_still(esphome::display::Display &display, StateId state) {
  if (this->persona_ != nullptr) {
    this->persona_->draw_still(display, state);
  } else {
    display.fill(esphome::Color::BLACK);
  }
  // Whatever comes next must replace this still frame.
  this->dirty_ = true;
}

bool Hub::needs_redraw() {
  if (this->dirty_ || !this->area_.empty())
    return true;
  if (this->screen_shown_)
    return false;  // A static screen (menu) is up; persona motion is hidden.
  const StateId state = this->state();
  if (!this->drawn_valid_ || state != this->drawn_state_)
    return true;
  // Stills change only with the state.
  return this->profile().animate && this->persona_ != nullptr && this->persona_->needs_redraw(state);
}

template<typename T>
void Hub::insert_sorted_(std::vector<Ordered<T>> &list, int order, T value, bool descending) {
  auto it = std::find_if(list.begin(), list.end(), [&](const Ordered<T> &entry) {
    return descending ? entry.order < order : entry.order > order;
  });
  list.insert(it, Ordered<T>{order, std::move(value)});
}

void Hub::add_layer(int order, Layer layer) { insert_sorted_(this->layers_, order, std::move(layer), false); }

void Hub::add_screen(int priority, Screen screen) {
  insert_sorted_(this->screens_, priority, std::move(screen), true);
}

// --- Actions ----------------------------------------------------------------

bool Hub::has_action(const std::string &name) const {
  const size_t colon = name.find(':');
  if (colon != std::string::npos)
    return this->arg_actions_.count(name.substr(0, colon)) != 0;
  return this->actions_.count(name) != 0;
}

bool Hub::run_action(const std::string &name) {
  const size_t colon = name.find(':');
  if (colon != std::string::npos) {
    auto arg = this->arg_actions_.find(name.substr(0, colon));
    if (arg == this->arg_actions_.end()) {
      ESP_LOGW(TAG, "No action named '%s'", name.c_str());
      return false;
    }
    ESP_LOGD(TAG, "Action: %s", name.c_str());
    arg->second(name.substr(colon + 1));
    return true;
  }
  auto it = this->actions_.find(name);
  if (it == this->actions_.end()) {
    if (name != "none" && !name.empty())
      ESP_LOGW(TAG, "No action named '%s'", name.c_str());
    return false;
  }
  ESP_LOGD(TAG, "Action: %s", name.c_str());
  it->second();
  return true;
}

std::string Hub::tap_target_at(int x, int y) const {
  for (const auto &entry : this->areas_) {
    const TapArea &a = entry.second;
    if (a.action.empty() || a.action == "none" || !a.area)
      continue;
    if (a.area().contains(x, y))
      return a.action;
  }
  return "";
}

std::vector<std::string> Hub::action_names() const {
  std::vector<std::string> names;
  for (const auto &entry : this->actions_)
    names.push_back(entry.first);
  return names;
}

// --- Inputs -------------------------------------------------------------------

int Hub::add_input(const std::string &name, bool touch, uint32_t double_ms, uint32_t hold_ms,
                     uint32_t long_hold_ms) {
  InputSlot slot{name, touch, PressRecognizer(touch ? Gesture::TAP : Gesture::PRESS, touch)};
  slot.press.set_timing(PressTiming{double_ms, hold_ms, long_hold_ms});
  this->inputs_.push_back(std::move(slot));
  if (touch)
    this->touch_input_ = (int) this->inputs_.size() - 1;
  return (int) this->inputs_.size() - 1;
}

void Hub::add_navigation(int input, Gesture gesture, Input nav) {
  this->navigation_.push_back(NavSlot{input, gesture, nav});
}

int Hub::add_binding(int input, Gesture gesture, const std::string &action, bool idle_only) {
  this->bindings_.push_back(BindingSlot{input, gesture, action, idle_only});
  return (int) this->bindings_.size() - 1;
}

void Hub::set_binding_action(int binding, const std::string &action) {
  if (binding < 0 || binding >= (int) this->bindings_.size())
    return;
  this->bindings_[binding].action = action;
  ESP_LOGI(TAG, "Binding %s.%s -> %s", this->inputs_[this->bindings_[binding].input].name.c_str(),
           gesture_name(this->bindings_[binding].gesture), action.c_str());
}

void Hub::add_gesture_filter(int priority, GestureFilter filter) {
  insert_sorted_(this->filters_, priority, std::move(filter), true);
}

void Hub::add_input_handler(int priority, InputHandler handler) {
  insert_sorted_(this->input_handlers_, priority, std::move(handler), true);
}

bool Hub::dispatch(Input input, int x, int y) {
  bool consumed = false;
  for (auto &handler : this->input_handlers_) {
    if (handler.value(input, x, y)) {
      consumed = true;
      if (input != Input::DISMISS)
        break;
    }
  }
  this->dirty_ = true;
  return consumed;
}

uint16_t Hub::bound_mask_(int input) const {
  uint16_t mask = 0;
  const bool touch = this->inputs_[input].touch;
  if (this->ui_open()) {
    for (const auto &nav : this->navigation_) {
      if (nav.input == input)
        mask |= gesture_bit(nav.gesture);
    }
  }
  // On an open screen, touch gestures belong to it; idle bindings rest.
  if (!(touch && this->ui_open())) {
    for (const auto &binding : this->bindings_) {
      if (binding.input == input && (!this->ui_open() || !binding.idle_only) && binding.action != "none" &&
          !binding.action.empty())
        mask |= gesture_bit(binding.gesture);
    }
  }
  return mask;
}

static bool to_input(Gesture gesture, Input *out) {
  switch (gesture) {
    case Gesture::TAP:
    case Gesture::PRESS:
      *out = Input::TAP;
      return true;
    case Gesture::HOLD:
      *out = Input::HOLD;
      return true;
    case Gesture::LONG_HOLD:
      *out = Input::LONG_HOLD;
      return true;
    case Gesture::SWIPE_LEFT:
      *out = Input::SWIPE_LEFT;
      return true;
    case Gesture::SWIPE_RIGHT:
      *out = Input::SWIPE_RIGHT;
      return true;
    case Gesture::SWIPE_UP:
      *out = Input::SWIPE_UP;
      return true;
    case Gesture::SWIPE_DOWN:
      *out = Input::SWIPE_DOWN;
      return true;
    case Gesture::STROKE:
      *out = Input::STROKE;
      return true;
    default:
      return false;
  }
}

void Hub::emit_(int input, Gesture gesture, int x, int y) {
  const InputSlot &slot = this->inputs_[input];
  ESP_LOGD(TAG, "Gesture: %s.%s", slot.name.c_str(), gesture_name(gesture));
  const GestureEvent event{slot.name, gesture, slot.touch, x, y};
  for (auto &filter : this->filters_) {
    if (filter.value(event)) {
      this->dirty_ = true;
      return;
    }
  }
  if (this->ui_open()) {
    for (const auto &nav : this->navigation_) {
      if (nav.input == input && nav.gesture == gesture) {
        this->dispatch(nav.nav, x, y);
        return;
      }
    }
    Input ui;
    if (slot.touch && to_input(gesture, &ui)) {
      this->dispatch(ui, x, y);
      return;
    }
  }
  // A tap on a part of the persona that leads somewhere (tap areas).
  if (slot.touch && gesture == Gesture::TAP && !this->ui_open()) {
    const std::string action = this->tap_target_at(x, y);
    if (!action.empty()) {
      ESP_LOGD(TAG, "Tap area -> %s", action.c_str());
      this->run_action(action);
      this->dirty_ = true;
      return;
    }
  }
  for (const auto &binding : this->bindings_) {
    if (binding.input != input || binding.gesture != gesture || (this->ui_open() && binding.idle_only))
      continue;
    if (slot.touch && this->ui_open())
      break;
    this->run_action(binding.action);
    this->dirty_ = true;
    return;
  }
  // Unbound gestures on the device's own screen go to the input handlers.
  Input ui;
  if (slot.touch && !this->ui_open() && to_input(gesture, &ui))
    this->dispatch(ui, x, y);
}

void Hub::button_edge(int input, bool pressed) {
  if (input < 0 || input >= (int) this->inputs_.size())
    return;
  auto &slot = this->inputs_[input];
  const uint32_t now = esphome::millis();
  const uint16_t mask = this->bound_mask_(input);
  const Gesture g = pressed ? slot.press.down(now, mask) : slot.press.up(now, mask);
  if (g != Gesture::NONE)
    this->emit_(input, g, -1, -1);
}

// --- Touch gestures ---------------------------------------------------------

void Hub::touch_start(int x, int y) {
  this->touch_.start(esphome::millis(), x, y);
  if (this->touch_input_ >= 0) {
    const TouchTrack &t = this->touch_.track();
    const Gesture g = this->inputs_[this->touch_input_].press.down(t.down_ms, this->bound_mask_(this->touch_input_));
    if (g != Gesture::NONE)
      this->emit_(this->touch_input_, g, x, y);
  }
}

void Hub::touch_move(int x, int y) {
  if (this->touch_.move(x, y) && this->touch_input_ >= 0)
    this->inputs_[this->touch_input_].press.cancel();
}

void Hub::touch_end() {
  if (!this->touch_.down())
    return;
  const uint32_t now = esphome::millis();
  const Gesture gesture = this->touch_.end(now);
  if (this->touch_input_ < 0)
    return;
  const TouchTrack &t = this->touch_.track();
  // A touch that moved was cancelled; up() then fires nothing.
  const Gesture press = this->inputs_[this->touch_input_].press.up(now, this->bound_mask_(this->touch_input_));
  const Gesture g = this->touch_.moved() ? gesture : press;
  if (g != Gesture::NONE)
    this->emit_(this->touch_input_, g, t.x0, t.y0);
}

// --- Menu content -----------------------------------------------------------

void Hub::add_menu_provider(int order, MenuProvider provider) {
  insert_sorted_(this->menu_providers_, order, OwnedProvider{this->setting_up_, std::move(provider)}, false);
}

std::vector<MenuItem> Hub::menu_items() {
  std::vector<MenuItem> items;
  for (auto &provider : this->menu_providers_) {
    provider.value.provider(items);
  }
  return items;
}

void Hub::add_menu_entry(const std::string &menu, uint8_t kind, const std::string &id, const std::string &label,
                           const std::string &icon, const std::string &color) {
  this->menus_[menu].push_back(MenuEntry{static_cast<MenuEntry::Kind>(kind), id, label, icon, color});
}

// A button's color: a module theme key, or "RRGGBB".
static esphome::Color entry_color(const Theme &theme, const std::string &color) {
  if (color.empty())
    return theme.edge;
  if (color.find('.') != std::string::npos)
    return theme.color(color);
  const uint32_t rgb = strtoul(color.c_str(), nullptr, 16);
  return theme.fit(esphome::Color((rgb >> 16) & 0xFF, (rgb >> 8) & 0xFF, rgb & 0xFF));
}

// Dark icons on light buttons, white on dark ones.
static esphome::Color ink_for(esphome::Color bg) {
  const int luma = (bg.r * 299 + bg.g * 587 + bg.b * 114) / 1000;
  return luma >= 150 ? esphome::Color::BLACK : esphome::Color::WHITE;
}

std::vector<MenuItem> Hub::menu_items(const std::string &menu) {
  std::vector<MenuItem> items;
  auto found = this->menus_.find(menu);
  if (found == this->menus_.end())
    return items;
  const Theme &theme = this->theme();
  for (const MenuEntry &entry : found->second) {
    switch (entry.kind) {
      case MenuEntry::MODULE:
        for (auto &provider : this->menu_providers_) {
          if (provider.value.module == entry.id)
            provider.value.provider(items);
        }
        break;
      case MenuEntry::APP: {
        const App *app = this->find_app(entry.id);
        if (app == nullptr || !app->enabled)
          break;  // Switched off in HA.
        const esphome::Color bg = theme.fit(app->color);
        MenuItem item = MenuItem::make(app->name, app->icon, bg, ink_for(bg), nullptr);
        item.app = app->id;
        items.push_back(item);
        break;
      }
      case MenuEntry::ACTION: {
        const esphome::Color bg = entry_color(theme, entry.color);
        const std::string action = entry.id;
        MenuItem item = MenuItem::make(entry.label, entry.icon, bg, ink_for(bg),
                                       [this, action]() { this->run_action(action); });
        auto look = this->action_buttons_.find(action);
        if (look != this->action_buttons_.end() && !look->second(item))
          break;  // Makes no sense now.
        items.push_back(std::move(item));
        break;
      }
      case MenuEntry::MORE: {
        MenuItem item = MenuItem::make("", "", theme.edge, esphome::Color::WHITE, nullptr);
        item.board = true;  // The menu fills in its label and icon.
        items.push_back(item);
        break;
      }
      case MenuEntry::MENU: {
        MenuItem item = MenuItem::make(entry.label, "", theme.edge, esphome::Color::WHITE, nullptr);
        item.menu = entry.id;
        items.push_back(item);
        break;
      }
      case MenuEntry::EVENT: {
        const esphome::Color bg = entry_color(theme, entry.color);
        const std::string event = entry.id;
        items.push_back(MenuItem::make(entry.label, entry.icon, bg, ink_for(bg), [this, event]() {
          if (this->event_sender_)
            this->event_sender_(event);
        }));
        break;
      }
    }
  }
  return items;
}

std::string Hub::menu_title() { return this->menu_title_ ? this->menu_title_() : ""; }

// --- Apps -------------------------------------------------------------------

std::vector<App *> Hub::apps() {
  std::vector<App *> out;
  for (auto &app : this->apps_) {
    if (app.enabled)
      out.push_back(&app);
  }
  return out;
}

App *Hub::find_app(const std::string &id) {
  for (auto &app : this->apps_) {
    if (app.id == id)
      return &app;
  }
  return nullptr;
}

void Hub::set_app_enabled(const std::string &id, bool enabled) {
  App *app = this->find_app(id);
  if (app == nullptr) {
    ESP_LOGW(TAG, "No app '%s' to switch", id.c_str());
    return;
  }
  if (app->enabled == enabled)
    return;
  app->enabled = enabled;
  ESP_LOGI(TAG, "App %s: %s", id.c_str(), enabled ? "on" : "off");
  if (app->on_enable)
    app->on_enable(enabled);
  if (!enabled)
    this->dispatch(Input::DISMISS);  // It may be on screen.
  this->dirty_ = true;
}

}  // namespace Daruma
