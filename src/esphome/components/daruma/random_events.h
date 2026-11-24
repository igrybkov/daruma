#pragma once

// The random events engine: when a persona's quirk may play, the rolls
// that pick one, and the phases of one playing event.
//
// Plain C++ with no ESPHome includes, so a host test can check it
// (tests/test_random_events.cpp). The engine has its own generator and
// never draws from esphome::random_uint32(), so the rest of the device
// sees the same random stream with or without it.
//
// How an event's fields are encoded (the build writes them):
//
//   dates      (from, to), month * 100 + day, inclusive; from > to wraps the year
//   weekdays   bit (weekday - 1), Sunday = bit 0 (ESPTime::day_of_week is
//              1 = Sunday); 0 = any day
//   times      `between:`. (from, to), minute of day, end exclusive; from > to wraps
//              midnight; the end may be 1440
//   at         minutes of day, 0..1439; none = no scheduled roll
//   moods      StateId values; `sleeping` is true when the list names sleeping
//   frequency  1..10; MEAN_S for random rolls, AT_CHANCE for scheduled rolls
//   key        FNV-1a of "random_events/<persona id>/<event name>"
//   enter, animation, exit   the persona's animation index; -1 = none
//
// A random roll gives each event the chance
// 1 - e^(-liveliness * eligible time / mean interval). Eligible time is the
// time the event could have played since it last rolled, so the rates hold
// whatever the waits between rolls are. Events with `at:` never join random
// rolls. They roll once in each of their minutes, with AT_CHANCE.

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstring>

#include "states.h"

namespace Daruma {
namespace RandomEvents {

// The mean interval of each frequency, in seconds. Index 0 is unused.
inline constexpr uint32_t MEAN_S[] = {0,         90 * 86400, 30 * 86400, 14 * 86400, 7 * 86400, 3 * 86400,
                                      1 * 86400, 6 * 3600,   2 * 3600,   30 * 60,    10 * 60};
// The chance of each frequency at a scheduled roll, in percent.
inline constexpr uint8_t AT_CHANCE[] = {0, 1, 5, 15, 25, 40, 55, 70, 85, 95, 100};

enum class Kind : uint8_t { ONE_SHOT, SPELL };

struct DateRange {
  uint16_t from, to;
};
struct TimeRange {
  uint16_t from, to;
};

struct EventDef {
  const char *name;
  uint32_t key;  // the preference that keeps the cooldown stamp
  Kind kind;
  int16_t enter, animation, exit;
  uint32_t hold_ms;  // how long a spell's animation loops
  uint8_t frequency;
  uint32_t cooldown_s;  // 0 = none
  const char *sound;    // "" = none
  const char *const *say;
  uint8_t say_count;
  const DateRange *dates;
  uint8_t date_count;
  uint8_t weekdays;
  const TimeRange *times;
  uint8_t time_count;
  const uint16_t *at;
  uint8_t at_count;
  const StateId *moods;
  uint8_t mood_count;
  bool sleeping;
};

// What the engine sees at one moment. The component fills it in.
struct Context {
  // A menu, app, prompt, screen, quiet activity or voice phase is up, HA is
  // gone, or the switch is off.
  bool blocked;
  bool clock;          // the time is synced; the fields below are valid
  uint32_t epoch;      // UTC seconds
  uint16_t month_day;  // local, month * 100 + day
  uint8_t weekday;     // local, 1 = Sunday
  uint16_t minute;     // local minute of day
  StateId mood;
  float liveliness;  // 1 = the frequency table as is
  uint32_t min_gap_ms;
  bool animate;  // the display shows animations; else only say-only events play
};

// splitmix32. Its increment differs from ESPHome's, so a stream seeded
// from the same bytes still differs.
struct Rng {
  static constexpr uint32_t INCREMENT = 0x6D2B79F5u;
  uint32_t state;
  uint32_t next() {
    uint32_t z = (state += INCREMENT);
    z = (z ^ (z >> 16)) * 0x85EBCA6Bu;
    z = (z ^ (z >> 13)) * 0xC2B2AE35u;
    return z ^ (z >> 16);
  }
  // [0, 1)
  float unit() { return static_cast<float>(next() >> 8) * 0x1p-24f; }
  // [0, n); n > 0
  uint32_t below(uint32_t n) { return next() % n; }
};

struct EventState {
  uint64_t eligible_ms{};  // eligible time since the event last rolled
  uint32_t last_epoch{};   // the last play, UTC seconds; 0 = never
};

inline float mean_ms(const EventDef &e) { return static_cast<float>(MEAN_S[e.frequency]) * 1000.0f; }

inline bool in_range(uint16_t from, uint16_t to, uint16_t value, bool end_inside) {
  if (from > to)
    return value >= from || (end_inside ? value <= to : value < to);
  return value >= from && (end_inside ? value <= to : value < to);
}

inline bool on_date(const EventDef &e, uint16_t month_day) {
  for (uint8_t i = 0; i < e.date_count; i++) {
    if (in_range(e.dates[i].from, e.dates[i].to, month_day, true))
      return true;
  }
  return e.date_count == 0;
}

inline bool on_weekday(const EventDef &e, uint8_t weekday) {
  return e.weekdays == 0 || (e.weekdays & (1u << (weekday - 1))) != 0;
}

inline bool in_times(const EventDef &e, uint16_t minute) {
  for (uint8_t i = 0; i < e.time_count; i++) {
    if (in_range(e.times[i].from, e.times[i].to, minute, false))
      return true;
  }
  return e.time_count == 0;
}

inline bool at_minute(const EventDef &e, uint16_t minute) {
  for (uint8_t i = 0; i < e.at_count; i++) {
    if (e.at[i] == minute)
      return true;
  }
  return false;
}

// While asleep, only events that list sleeping. Awake, events with no
// moods, and events that list the current one.
inline bool mood_fits(const EventDef &e, StateId mood) {
  if (mood == StateId::SLEEPING)
    return e.sleeping;
  for (uint8_t i = 0; i < e.mood_count; i++) {
    if (e.moods[i] == mood)
      return true;
  }
  return e.mood_count == 0 && !e.sleeping;
}

// The `when:` conditions. Dates, weekdays and times need the clock.
inline bool when_holds(const EventDef &e, const Context &ctx) {
  bool timed = e.date_count != 0 || e.weekdays != 0 || e.time_count != 0;
  if (timed && !ctx.clock)
    return false;
  return mood_fits(e, ctx.mood) && on_date(e, ctx.month_day) && on_weekday(e, ctx.weekday) && in_times(e, ctx.minute);
}

inline bool cooled_down(const EventDef &e, const EventState &s, const Context &ctx) {
  return e.cooldown_s == 0 || (ctx.clock && ctx.epoch - s.last_epoch >= e.cooldown_s);
}

class Engine {
 public:
  // The active persona's events. A new pool forgets the last event; the
  // gap clock keeps running.
  void set_pool(const EventDef *events, uint8_t count, EventState *states) {
    events_ = events;
    count_ = count;
    states_ = states;
    last_ = -1;
  }

  // Call it at every step, blocked or not: it also runs the gap clock.
  // Each event that is eligible now gains dt of eligible time.
  void sample(const Context &ctx, uint32_t dt_ms) {
    since_play_ms_ += dt_ms;
    for (uint8_t i = 0; i < count_; i++) {
      if (eligible(i, ctx))
        states_[i].eligible_ms += dt_ms;
    }
  }

  // The event may play at a random roll now. The last event played may not
  // play again, unless it is the only one that could and twice its mean
  // interval has passed since.
  bool eligible(uint8_t i, const Context &ctx) const {
    if (!open_(i, ctx))
      return false;
    if (i != last_)
      return true;
    return alone_(ctx) && static_cast<float>(since_play_ms_) >= 2.0f * mean_ms(events_[i]);
  }

  // A random roll. A blocked roll is skipped: it draws nothing and keeps
  // the eligible time. Else it draws one unit() per event and one below(),
  // whatever the hits, and the eligible events start again from zero.
  // Returns the event to play, or -1.
  int roll(const Context &ctx, Rng &rng) {
    if (ctx.blocked)
      return -1;
    Hits hits;
    for (uint8_t i = 0; i < count_; i++) {
      float u = rng.unit();
      if (!eligible(i, ctx))
        continue;
      float p = 1.0f - expf(-ctx.liveliness * static_cast<float>(states_[i].eligible_ms) / mean_ms(events_[i]));
      hits.add(i, u < p);
      states_[i].eligible_ms = 0;
    }
    return hits.pick(rng);
  }

  // The scheduled roll of this minute, for the `at:` events due now. Call
  // it at every step. It rolls once per minute: one unit() per due event,
  // then one below(). It skips the gap and the no-repeat rule. A blocked
  // step, or one with nothing due, draws nothing and lets a later step in
  // the same minute try. A step in another minute clears the latch.
  int roll_at(const Context &ctx, Rng &rng) {
    uint16_t minute = ctx.clock ? ctx.minute : NO_MINUTE;
    if (minute == rolled_at_)
      return -1;
    rolled_at_ = NO_MINUTE;
    if (ctx.blocked || minute == NO_MINUTE)
      return -1;
    Hits hits;
    bool any = false;
    for (uint8_t i = 0; i < count_; i++) {
      if (!due_(i, ctx))
        continue;
      any = true;
      hits.add(i, rng.unit() < AT_CHANCE[events_[i].frequency] * 0.01f * ctx.liveliness);
    }
    if (!any)
      return -1;
    rolled_at_ = minute;
    return hits.pick(rng);
  }

  // play_random_event(""): one eligible event, weighted by 1 / mean. One
  // below(), or none when nothing is eligible.
  int pick(const Context &ctx, Rng &rng) const {
    uint32_t total = 0;
    for (uint8_t i = 0; i < count_; i++)
      total += weight_(i, ctx);
    if (total == 0)
      return -1;
    uint32_t r = rng.below(total);
    for (uint8_t i = 0; i < count_; i++) {  // pragma: no mutate (r < total returns inside the loop)
      uint32_t w = weight_(i, ctx);
      if (r < w)
        return i;
      r -= w;
    }
    return -1;  // pragma: no mutate (not reached: r < total)
  }

  int find(const char *name) const {
    for (uint8_t i = 0; i < count_; i++) {
      if (strcmp(events_[i].name, name) == 0)
        return i;
    }
    return -1;
  }

  // The event started: it is the last one, the gap starts again, and it
  // keeps the time for its cooldown (when there is a clock).
  void played(uint8_t i, const Context &ctx) {
    last_ = i;
    since_play_ms_ = 0;
    if (ctx.clock)
      states_[i].last_epoch = ctx.epoch;
  }

  // When the next random roll is due, `wait` after now but never inside
  // the gap.
  uint32_t next_roll_ms(uint32_t now_ms, uint32_t wait_ms, const Context &ctx) const {
    uint64_t gap_left = ctx.min_gap_ms - std::min<uint64_t>(ctx.min_gap_ms, since_play_ms_);
    return now_ms + static_cast<uint32_t>(std::max<uint64_t>(wait_ms, gap_left));
  }

  int last() const { return last_; }

 protected:
  static constexpr uint16_t NO_MINUTE = 0xFFFF;

  // The events that hit at one roll; one of them plays.
  struct Hits {
    uint8_t list[256];  // pragma: no mutate (one per possible event; more is spare room)
    uint16_t count{};
    void add(uint8_t i, bool hit) {
      if (hit)
        list[count++] = i;
    }
    int pick(Rng &rng) const {
      uint32_t k = rng.below(std::max<uint32_t>(count, 1));
      if (count == 0)
        return -1;
      return list[k];
    }
  };

  // Every rule but the no-repeat one.
  bool open_(uint8_t i, const Context &ctx) const {
    if (ctx.blocked || ctx.liveliness <= 0.0f || events_[i].at_count != 0)
      return false;
    return since_play_ms_ >= ctx.min_gap_ms && playable_(i, ctx);
  }

  // Its own conditions, its cooldown, and the screen can show it.
  bool playable_(uint8_t i, const Context &ctx) const {
    const EventDef &e = events_[i];
    if (e.animation >= 0 && !ctx.animate)
      return false;
    return when_holds(e, ctx) && cooled_down(e, states_[i], ctx);
  }

  bool due_(uint8_t i, const Context &ctx) const { return at_minute(events_[i], ctx.minute) && playable_(i, ctx); }

  // No other event passes every rule but the no-repeat one.
  bool alone_(const Context &ctx) const {
    for (uint8_t i = 0; i < count_; i++) {
      if (i != last_ && open_(i, ctx))
        return false;
    }
    return true;
  }

  uint32_t weight_(uint8_t i, const Context &ctx) const {
    return eligible(i, ctx) ? MEAN_S[1] / MEAN_S[events_[i].frequency] : 0;
  }

  const EventDef *events_{nullptr};
  uint8_t count_{};
  EventState *states_{nullptr};
  int last_{-1};
  uint64_t since_play_ms_{};
  uint16_t rolled_at_{NO_MINUTE};  // the minute the last scheduled roll ran
};

enum class Phase : uint8_t { IDLE, ONE_SHOT, ENTER, LOOP, EXIT };

// The phases of one playing event: times in, phase and animation out. A
// one-shot plays its animation once. A spell plays `enter`, loops
// `animation` for hold_ms, then plays `exit`. A missing animation takes no
// time, so a say-only one-shot is over at once.
class Playback {
 public:
  // The lengths of one pass of each animation, from the persona.
  void start(const EventDef &e, uint32_t now_ms, uint32_t enter_ms, uint32_t once_ms, uint32_t exit_ms) {
    if (e.kind == Kind::SPELL) {
      steps_[0] = step_(Phase::ENTER, e.enter, enter_ms);
      steps_[1] = {Phase::LOOP, e.animation, e.hold_ms};
      steps_[2] = step_(Phase::EXIT, e.exit, exit_ms);
      count_ = 3;
    } else {
      steps_[0] = step_(Phase::ONE_SHOT, e.animation, once_ms);
      count_ = 1;
    }
    at_ = 0;
    since_ms_ = now_ms;
    tick(now_ms);
  }

  // Moves on past every phase that has ended. True when the phase changed.
  bool tick(uint32_t now_ms) {
    bool changed = false;
    while (at_ < count_ && now_ms - since_ms_ >= steps_[at_].ms) {
      since_ms_ += steps_[at_].ms;
      at_++;
      changed = true;
    }
    return changed;
  }

  // Ends the event at once, in any phase: input, a prompt, a quiet
  // activity, a reaction or a persona switch. No exit plays.
  void stop() { at_ = count_; }

  Phase phase() const { return at_ < count_ ? steps_[at_].phase : Phase::IDLE; }

  // The animation to show now; -1 when idle.
  int16_t animation() const { return at_ < count_ ? steps_[at_].animation : -1; }

  // The animation plays once and holds its last frame; only a spell's loop
  // repeats.
  bool once() const { return phase() != Phase::LOOP; }

 protected:
  struct Step {
    Phase phase;
    int16_t animation;
    uint32_t ms;
  };

  static Step step_(Phase phase, int16_t animation, uint32_t ms) { return {phase, animation, animation >= 0 ? ms : 0}; }

  Step steps_[3]{};  // pragma: no mutate (a spell's three; more is spare room)
  uint8_t count_{};
  uint8_t at_{};
  uint32_t since_ms_{};
};

}  // namespace RandomEvents
}  // namespace Daruma
