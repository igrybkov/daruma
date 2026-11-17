#pragma once

#include <cstdint>
#include <map>
#include <string>
#include <utility>
#include <vector>

#include "esphome/components/display/display.h"
#include "layout.h"
#include "profile.h"
#include "signals.h"
#include "state_machine.h"
#include "states.h"
#include "synth.h"
#include "theme.h"

namespace Daruma {

// What a persona does for one state: an animation (an index into the
// persona's own list), a sound and optional words. The build resolves one for
// every state, fallbacks included (registry.py), so the persona never guesses.
struct Behavior {
  int16_t animation{0};
  const char *sound{""};  // Synth sound name; "" for none.
  const char *say{""};    // Words for the speech bubble; "" for none.
  bool own{false};        // A look of its own for the state, not a fallback's.
};

// A persona draws the device: a persona that answers to states. The hub keeps
// one active persona and asks it to show the current state (reaction, top
// activity or mood). Swap personas at runtime with the "Persona" select.
class Persona {
 public:
  explicit Persona(const std::string &name) : name_(name) {}
  virtual ~Persona() = default;

  const std::string &get_name() const { return this->name_; }

  // Idle frame for a state. Must fill the whole stage (stage_()), which is
  // the whole screen today. look_y shifts the persona up (negative, in design
  // pixels) to make room for a speech bubble, if the persona can.
  virtual void draw(esphome::display::Display &display, StateId state, float look_y) = 0;
  // One still frame (the voice phases: listening, offline, ...).
  virtual void draw_still(esphome::display::Display &display, StateId state) = 0;
  // True when the next idle frame would differ from the last one drawn.
  virtual bool needs_redraw(StateId state) = 0;
  // Optional fast path: repaint only what changed since the last draw() or
  // draw_delta() of the same state. Return false to ask for a full draw().
  // The display keeps its buffer between frames (no auto-clear), so the
  // untouched pixels, layers included, stay as they were.
  virtual bool draw_delta(esphome::display::Display &display, StateId state) { return false; }
  // The screen area the last draw_delta() repainted, background included,
  // when that may cover the hub's layers (a timer, a badge). The hub draws
  // the layers again, clipped to it. Empty: the persona never paints under a
  // layer, or repaints only pixels of its own.
  virtual Rect delta_area() const { return Rect{}; }

  virtual void blink() {}
  virtual void wink() {}
  virtual void look_around() {}

  void set_signals(const Signals *signals) { this->signals_ = signals; }
  // The hub's layout and display profile (they live as long as the hub).
  void set_screen(const Layout *layout, const DisplayProfile *profile) {
    this->layout_ = layout;
    this->profile_ = profile;
  }

  // --- Behaviors (set by codegen, one per state in StateId order) -------------
  void set_behaviors(std::vector<Behavior> behaviors) { this->behaviors_ = std::move(behaviors); }
  const Behavior &behavior(StateId state) const {
    static const Behavior NONE;
    const size_t i = static_cast<size_t>(state);
    return i < this->behaviors_.size() ? this->behaviors_[i] : NONE;
  }
  // The animation to play for `state`. A reaction over an activity plays
  // the variant `during:` names for that activity, if any, so the
  // activity's props stay in the picture.
  int animation_for(StateId state) const {
    const int16_t shown = this->behavior(state).animation;
    StateId activity;
    if (this->during_.empty() || this->machine_ == nullptr || state_info(state).kind != StateKind::REACTION ||
        !this->machine_->top_activity(&activity))
      return shown;
    for (const auto &d : this->during_) {
      if (d.activity == activity && d.shown == shown)
        return d.instead;
    }
    return shown;
  }
  // While `activity` is on, a reaction that would play animation `shown`
  // plays `instead`.
  void add_during(StateId activity, int shown, int instead) {
    this->during_.push_back(During{activity, (int16_t) shown, (int16_t) instead});
  }
  // What is on under a reaction, for animation_for(). Set by the hub.
  void set_machine(const StateMachine *machine) { this->machine_ = machine; }

  // --- Params: things only this persona has (`pixel_corgi.rug`) -------------
  // Values are ints: a choice's index, or 0/1. The build declares each one.
  void add_param(const std::string &name, int value) { this->params_.emplace_back(name, value); }
  void set_param(const std::string &name, int value) {
    for (auto &param : this->params_) {
      if (param.first == name)
        param.second = value;
    }
  }
  int param(const std::string &name, int fallback = 0) const {
    for (const auto &param : this->params_) {
      if (param.first == name)
        return param.second;
    }
    return fallback;
  }

  // How the menu and apps look while this persona is shown.
  void set_theme(const Theme *theme) { this->theme_ = theme; }
  const Theme &theme() const { return this->theme_ != nullptr ? *this->theme_ : default_theme(); }

  // Synth sounds this persona makes its own way, by name ("pet", "timer", ...).
  // Sounds it leaves out are the built-in ones (Synth::sound).
  void set_sound(const std::string &name, std::vector<Synth::Step> steps) { this->sounds_[name] = std::move(steps); }
  std::vector<Synth::Step> sound(const std::string &name) const {
    auto it = this->sounds_.find(name);
    return it != this->sounds_.end() ? it->second : Synth::sound(name);
  }

 protected:
  const Signals &signals_ref_() const {
    static const Signals NONE;
    return this->signals_ != nullptr ? *this->signals_ : NONE;
  }
  // Where the persona draws, in screen pixels: the layout's stage, or the whole
  // display before a layout exists.
  Rect stage_(esphome::display::Display &display) const {
    if (this->layout_ != nullptr && this->layout_->width > 0)
      return this->layout_->stage;
    return Rect{0, 0, display.get_width(), display.get_height()};
  }
  float unit_(esphome::display::Display &display) const {
    if (this->layout_ != nullptr && this->layout_->width > 0)
      return this->layout_->unit;
    return Layout::compute(display.get_width(), display.get_height()).unit;
  }
  ColorMode color_mode_() const { return this->profile_ != nullptr ? this->profile_->colors : ColorMode::FULL; }

  std::string name_;
  const Signals *signals_{nullptr};
  const Layout *layout_{nullptr};
  const DisplayProfile *profile_{nullptr};
  const Theme *theme_{nullptr};
  std::vector<Behavior> behaviors_;
  struct During {
    StateId activity;
    int16_t shown;
    int16_t instead;
  };
  std::vector<During> during_;
  const StateMachine *machine_{nullptr};
  std::vector<std::pair<std::string, int>> params_;
  std::map<std::string, std::vector<Synth::Step>> sounds_;
};

}  // namespace Daruma
