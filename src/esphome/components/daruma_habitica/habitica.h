#pragma once

// The Habitica stats the device knows, and the reactions a change plays.
// Plain C++ with no ESPHome includes, so a host test can check it
// (tests/test_habitica_stats.cpp).
//
// Numbers come from Home Assistant one entity at a time (the stat sensors)
// or as a set (a score reply). Each goes through apply(): the model
// compares it with the last number it knows and returns what to play.
// A field it does not know yet never plays anything, so the first values
// after a boot or a reconnect only fill the sheet. The same numbers
// arriving twice (a reply, then the sensor push) play once.

#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <string>
#include <vector>

namespace Daruma {

// -1 (or any negative number) means unknown, for every number.
struct HabiticaStats {
  float hp{-1}, hp_max{-1};
  float mp{-1}, mp_max{-1};
  float xp{-1}, xp_next{-1};
  float gold{-1};
  int level{-1};
  std::string cls;  // warrior, rogue, wizard or healer; "" unknown.
  int resting{-1};  // In the inn: 1 yes, 0 no, -1 unknown.
};

inline bool habitica_known(float v) { return v >= 0; }

// What the persona holds while it lasts. Fainted wins over resting.
enum class HabiticaActivity { NONE, FAINTED, RESTING };

// What one apply() asks the device to play.
struct HabiticaReactions {
  bool level_up{false};
  bool hurt{false};
  bool activity_changed{false};
  HabiticaActivity activity{HabiticaActivity::NONE};
};

// A number from an HA state: "47.3" -> 47.3. "unknown", "unavailable",
// text and negative numbers give -1.
inline float habitica_number(const std::string &text) {
  if (text.empty())
    return -1;
  char *end = nullptr;
  const float v = std::strtof(text.c_str(), &end);
  if (end != text.c_str() + text.size() || !std::isfinite(v) || v < 0)
    return -1;
  return v;
}

// A class from the class sensor; "" for anything else.
inline std::string habitica_class(const std::string &text) {
  for (const char *c : {"warrior", "rogue", "wizard", "healer"}) {
    if (text == c)
      return text;
  }
  return "";
}

// Sets one field from an HA state, by the field's name. An unknown state
// sets the field to unknown. Returns false for a name it does not know.
inline bool habitica_set_field(HabiticaStats &s, const std::string &field, const std::string &state) {
  const float v = habitica_number(state);
  if (field == "health") {
    s.hp = v;
  } else if (field == "max_health") {
    s.hp_max = v;
  } else if (field == "mana") {
    s.mp = v;
  } else if (field == "max_mana") {
    s.mp_max = v;
  } else if (field == "experience") {
    s.xp = v;
  } else if (field == "next_level") {
    s.xp_next = v;
  } else if (field == "gold") {
    s.gold = v;
  } else if (field == "level") {
    s.level = (int) v;  // -1 stays -1.
  } else if (field == "class") {
    s.cls = habitica_class(state);
  } else if (field == "inn") {
    s.resting = state == "on" ? 1 : (state == "off" ? 0 : -1);
  } else {
    return false;
  }
  return true;
}

// The known fields of `news` over `base`.
inline HabiticaStats habitica_merge(HabiticaStats base, const HabiticaStats &news) {
  for (auto field : {&HabiticaStats::hp, &HabiticaStats::hp_max, &HabiticaStats::mp, &HabiticaStats::mp_max,
                     &HabiticaStats::xp, &HabiticaStats::xp_next, &HabiticaStats::gold}) {
    if (habitica_known(news.*field))
      base.*field = news.*field;
  }
  if (news.level >= 0)
    base.level = news.level;
  if (!news.cls.empty())
    base.cls = news.cls;
  if (news.resting >= 0)
    base.resting = news.resting;
  return base;
}

// A number as the sheet shows it: whole, rounded down. HP rounds up, so a
// hero with 0.4 HP left does not read as fainted. "" when unknown.
inline std::string habitica_shown(float v, bool round_up = false) {
  if (!habitica_known(v))
    return "";
  return std::to_string((long) (round_up ? std::ceil(v) : std::floor(v)));
}

// How much of a bar `width` wide is filled: value / max, kept in the bar.
// 0 when either is unknown.
inline int habitica_fill(float value, float max, int width) {
  if (!habitica_known(value) || !(max > 0))
    return 0;
  return (int) std::lround(std::min(1.0f, value / max) * width);
}

// Where to break a line in two: the space nearest the middle, or
// std::string::npos without one.
inline size_t habitica_split(const std::string &text) {
  size_t best = std::string::npos;
  for (size_t i = 0; i < text.size(); i++) {  // pragma: no mutate
    if (text[i] != ' ')
      continue;
    const long off = std::labs((long) (2 * i) - (long) text.size());
    if (best == std::string::npos || off < std::labs((long) (2 * best) - (long) text.size()))
      best = i;
  }
  return best;
}

// One skill of the hero's class, from the skills script. The reply reaches
// the device as lines, fields split by tabs (packages/habitica.yaml):
//
//   C  <class>
//   K  <id> <mp> <level> <target> <ready> <name> <why>
//   R  <ok>                  a cast's answer
//   S  <hp> <hp_max> <mp> <mp_max> <xp> <xp_next> <gold> <level>
//
// target is s (self), p (party) or t (a task). ready is 1 or 0.
struct HabiticaSkill {
  std::string id;
  std::string name;
  std::string why;  // Why it is not ready: "Needs 30 MP".
  int mp{0};
  int level{0};
  char target{'s'};
  bool ready{false};
};

inline std::vector<std::string> habitica_fields(const std::string &line) {
  std::vector<std::string> out;
  size_t from = 0;
  while (true) {
    const size_t at = line.find('\t', from);
    out.push_back(line.substr(from, at == std::string::npos ? std::string::npos : at - from));
    if (at == std::string::npos)
      return out;
    from = at + 1;
  }
}

inline std::vector<std::string> habitica_lines(const std::string &text) {
  std::vector<std::string> out;
  size_t from = 0;
  while (from < text.size()) {  // pragma: no mutate
    size_t end = text.find('\n', from);
    if (end == std::string::npos)
      end = text.size();
    out.push_back(text.substr(from, end - from));
    from = end + 1;
  }
  return out;
}

// An S line into the known fields of `s`.
inline bool habitica_parse_stats_line(const std::vector<std::string> &f, HabiticaStats &s) {
  if (f[0] != "S" || f.size() < 9)
    return false;
  float *fields[] = {&s.hp, &s.hp_max, &s.mp, &s.mp_max, &s.xp, &s.xp_next, &s.gold};
  for (int i = 0; i < 7; i++)
    *fields[i] = habitica_number(f[i + 1]);
  s.level = (int) habitica_number(f[8]);
  return true;
}

// The skills reply: false when it is not one (no C line).
inline bool habitica_parse_skills(const std::string &text, std::string &cls, std::vector<HabiticaSkill> &skills) {
  skills.clear();
  bool found = false;
  for (const std::string &line : habitica_lines(text)) {
    const std::vector<std::string> f = habitica_fields(line);
    if (f[0] == "C" && f.size() >= 2) {
      cls = habitica_class(f[1]);
      found = true;
    } else if (f[0] == "K" && f.size() >= 8 && !f[1].empty()) {
      HabiticaSkill k;
      k.id = f[1];
      k.mp = (int) std::max(0.0f, habitica_number(f[2]));
      k.level = (int) std::max(0.0f, habitica_number(f[3]));
      k.target = f[4] == "p" || f[4] == "t" ? f[4][0] : 's';
      k.ready = f[5] == "1";
      k.name = f[6];
      k.why = f[7];
      skills.push_back(k);
    }
  }
  return found;
}

// A cast's reply: ok, and its stats when it has them. False when it is not one.
inline bool habitica_parse_cast(const std::string &text, bool &ok, HabiticaStats &stats) {
  const std::vector<std::string> lines = habitica_lines(text);
  if (lines.empty())
    return false;
  const std::vector<std::string> f = habitica_fields(lines[0]);
  if (f[0] != "R" || f.size() < 2)
    return false;
  ok = f[1] == "1";
  stats = HabiticaStats{};
  // The last line, when it is an S line, holds the stats.
  habitica_parse_stats_line(habitica_fields(lines.back()), stats);
  return true;
}

// MP after a cast of `cost`, as a guess until HA sends the real number.
inline float habitica_mp_after(float mp, int cost) {
  if (!habitica_known(mp))
    return -1;
  return std::max(0.0f, mp - (float) cost);
}

class HabiticaModel {
 public:
  // HP lost in one change that plays `hurt`.
  void set_hurt_threshold(float hp) { this->hurt_tenths_ = std::lround(hp * 10); }

  // What the sheet shows: the last known value of each field.
  const HabiticaStats &stats() const { return this->shown_; }

  // Numbers from before a reboot: shown until HA sends its own, never
  // compared with them.
  void restore(const HabiticaStats &saved) {
    this->shown_ = habitica_merge(this->shown_, saved);
    this->activity_ = this->activity_now_();
  }

  // HA went away: what it sends next is a first value again.
  void forget() { this->known_ = HabiticaStats{}; }

  // New numbers: the known fields of `news`. Reactions come from fields
  // known before and now. The activity follows the numbers shown.
  HabiticaReactions apply(const HabiticaStats &news) {
    HabiticaReactions r;
    const HabiticaStats &was = this->known_;
    r.level_up = was.level >= 0 && news.level > was.level;
    if (habitica_known(was.hp) && habitica_known(news.hp))
      r.hurt = std::lround(was.hp * 10) - std::lround(news.hp * 10) >= this->hurt_tenths_;
    this->known_ = habitica_merge(this->known_, news);
    this->shown_ = habitica_merge(this->shown_, news);
    const HabiticaActivity now = this->activity_now_();
    r.activity_changed = now != this->activity_;
    r.activity = now;
    this->activity_ = now;
    return r;
  }

  HabiticaActivity activity() const { return this->activity_; }

 protected:
  HabiticaActivity activity_now_() const {
    if (habitica_known(this->shown_.hp) && this->shown_.hp <= 0)
      return HabiticaActivity::FAINTED;
    if (this->shown_.resting == 1)
      return HabiticaActivity::RESTING;
    return HabiticaActivity::NONE;
  }

  HabiticaStats shown_;
  HabiticaStats known_;
  HabiticaActivity activity_{HabiticaActivity::NONE};
  long hurt_tenths_{10};
};

}  // namespace Daruma
