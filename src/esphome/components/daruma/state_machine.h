#pragma once

// What the device shows: a reaction if one is playing, else the top activity,
// else the mood. Plain C++ with no ESPHome parts, so a host test can run it
// (tests/test_input.cpp).

#include <cstdint>
#include <string>
#include <vector>

#include "states.h"

namespace Daruma {

class StateMachine {
 public:
  void set_mood(StateId mood) { this->mood_ = mood; }
  StateId mood() const { return this->mood_; }

  // Activities are a stack with owners: each owner holds at most one. Setting
  // one puts it on top, replacing what that owner had. Returns true when the
  // top changed.
  bool set_activity(const std::string &owner, StateId activity) {
    const bool was = this->has_activity();
    const StateId top = was ? this->activities_.back().state : this->mood_;
    this->remove_(owner);
    this->activities_.push_back(Entry{owner, activity});
    return !was || top != activity;
  }
  // Drops the owner's activity, if any. Returns true when the top changed.
  bool clear_activity(const std::string &owner) {
    if (!this->has_activity())
      return false;
    const Entry before = this->activities_.back();
    this->remove_(owner);
    return !this->has_activity() || this->activities_.back().state != before.state ||
           this->activities_.back().owner != before.owner;
  }
  bool has_activity() const { return !this->activities_.empty(); }
  // The top activity; false when there is none.
  bool top_activity(StateId *out) const {
    if (this->activities_.empty())
      return false;
    *out = this->activities_.back().state;
    return true;
  }
  // True when any owner holds this activity.
  bool holds(StateId activity) const {
    for (const auto &entry : this->activities_) {
      if (entry.state == activity)
        return true;
    }
    return false;
  }
  // The owner's activity; false when it has none.
  bool activity_of(const std::string &owner, StateId *out) const {
    for (const auto &entry : this->activities_) {
      if (entry.owner == owner) {
        *out = entry.state;
        return true;
      }
    }
    return false;
  }

  // A reaction for `ms` from `now`. A new one replaces one still playing.
  void react(StateId reaction, uint32_t now, uint32_t ms) {
    this->reaction_ = reaction;
    this->reaction_until_ = now + ms;
    this->reacting_ = ms > 0;
  }
  // True while a reaction plays. Ends it once its time is up.
  bool reacting(uint32_t now) {
    if (this->reacting_ && (int32_t) (now - this->reaction_until_) >= 0)
      this->reacting_ = false;
    return this->reacting_;
  }
  StateId reaction() const { return this->reaction_; }
  void end_reaction() { this->reacting_ = false; }

  StateId current(uint32_t now) {
    if (this->reacting(now))
      return this->reaction_;
    if (this->has_activity())
      return this->activities_.back().state;
    return this->mood_;
  }

 protected:
  struct Entry {
    std::string owner;
    StateId state;
  };
  void remove_(const std::string &owner) {
    for (auto it = this->activities_.begin(); it != this->activities_.end(); ++it) {
      if (it->owner == owner) {
        this->activities_.erase(it);
        return;
      }
    }
  }

  StateId mood_{static_cast<StateId>(0)};
  std::vector<Entry> activities_;
  StateId reaction_{static_cast<StateId>(0)};
  uint32_t reaction_until_{0};
  bool reacting_{false};
};

}  // namespace Daruma
