#pragma once

// The Habits app's data: habits with plus and minus, from an HA script,
// and the scores the device sends back. Plain C++ with no ESPHome
// includes, so a host test can check it (tests/test_habits.cpp). Times
// come in as arguments.
//
// The script's replies reach the device as text that HA renders from them
// (packages/app_habits.yaml), one record per line, fields split by tabs:
//
//   L  <count>                                   a list follows
//   H  <id> <up> <down> <value> <count_up> <count_down> <period> <title>
//   R  <ok> <delta> <quest> <drop>               a score's answer
//   S  <hp> <hp_max> <mp> <mp_max> <xp> <xp_next> <gold> <level>
//
// up, down and ok are 1 or 0. period is d, w or m. -1 is unknown.
//
// A tap is one score. It bumps the count at once and waits in a queue;
// one score is in flight at a time. An error or no answer takes the bump
// back. Two caps keep the account's request budget: a tap is dropped when
// too many wait, or when too many went out in the last minute.

#include <algorithm>
#include <cctype>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <deque>
#include <functional>
#include <string>
#include <vector>

namespace Daruma {

struct Habit {
  std::string id;
  std::string title;
  bool up{false};
  bool down{false};
  float value{0};
  int count_up{0};
  int count_down{0};
  char period{'d'};  // d daily, w weekly, m monthly.
};

// The hero's numbers a reply may carry. -1 is unknown.
struct HabitStats {
  float hp{-1}, hp_max{-1};
  float mp{-1}, mp_max{-1};
  float xp{-1}, xp_next{-1};
  float gold{-1};
  int level{-1};
};

struct HabitReply {
  bool ok{false};
  float delta{0};  // The habit's value change.
  float quest{0};  // Quest progress.
  std::string drop;
  bool has_stats{false};
  HabitStats stats;
};

inline std::vector<std::string> habit_fields(const std::string &line) {
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

inline float habit_float(const std::string &text, float fallback) {
  char *end = nullptr;
  const float v = std::strtof(text.c_str(), &end);
  return text.empty() || end != text.c_str() + text.size() ? fallback : v;
}

inline int habit_int(const std::string &text) { return (int) habit_float(text, 0); }

// An S record's fields.
inline bool habit_parse_stats(const std::vector<std::string> &f, HabitStats &s) {
  if (f[0] != "S" || f.size() < 9)
    return false;
  s.hp = habit_float(f[1], -1);
  s.hp_max = habit_float(f[2], -1);
  s.mp = habit_float(f[3], -1);
  s.mp_max = habit_float(f[4], -1);
  s.xp = habit_float(f[5], -1);
  s.xp_next = habit_float(f[6], -1);
  s.gold = habit_float(f[7], -1);
  s.level = (int) habit_float(f[8], -1);
  return true;
}

inline bool habit_parse_habit(const std::vector<std::string> &f, Habit &h) {
  if (f.size() < 9 || f[1].empty())
    return false;
  h.id = f[1];
  h.up = f[2] == "1";
  h.down = f[3] == "1";
  h.value = habit_float(f[4], 0);
  h.count_up = habit_int(f[5]);
  h.count_down = habit_int(f[6]);
  h.period = f[7] == "w" || f[7] == "m" ? f[7][0] : 'd';
  h.title = f[8];
  return true;
}

// A list reply: false when it is not one. Keeps at most `max_items`.
inline bool habit_parse_list(const std::string &text, size_t max_items, std::vector<Habit> &habits, HabitReply &stats) {
  habits.clear();
  stats.has_stats = false;
  bool list = false;
  size_t from = 0;
  while (from < text.size()) {  // pragma: no mutate
    size_t end = text.find('\n', from);
    if (end == std::string::npos)
      end = text.size();
    const std::vector<std::string> f = habit_fields(text.substr(from, end - from));
    from = end + 1;
    Habit h;
    if (f[0] == "L") {
      list = true;
    } else if (f[0] == "H" && habits.size() < max_items && habit_parse_habit(f, h)) {
      habits.push_back(h);
    } else if (f[0] == "S") {
      stats.has_stats = habit_parse_stats(f, stats.stats);
    }
  }
  return list;
}

// A score's reply: false when it is not one.
inline bool habit_parse_reply(const std::string &text, HabitReply &r) {
  r = HabitReply{};
  const size_t nl = text.find('\n');
  const std::vector<std::string> f = habit_fields(text.substr(0, nl));
  if (f[0] != "R" || f.size() < 5)
    return false;
  r.ok = f[1] == "1";
  r.delta = habit_float(f[2], 0);
  r.quest = habit_float(f[3], 0);
  r.drop = f[4];
  if (nl != std::string::npos)
    r.has_stats = habit_parse_stats(habit_fields(text.substr(nl + 1)), r.stats);
  return true;
}

// Habitica's value colors, worst (0) to best (6).
inline int habit_value_band(float value) {
  static const float LIMITS[] = {-20, -10, -1, 1, 5, 10};
  int band = 0;
  for (float limit : LIMITS) {
    if (value >= limit)
      band++;
  }
  return band;
}

// "+3", "-1", "0".
inline std::string habit_signed(int n) { return (n > 0 ? "+" : "") + std::to_string(n); }

// The counts of the sides a habit has: "+3 -1", "+3", "-2".
inline std::string habit_counts(const Habit &h) {
  std::string out = h.up ? "+" + std::to_string(h.count_up) : "";
  if (h.down)
    out += (out.empty() ? "-" : " -") + std::to_string(h.count_down);
  return out;
}

// The theme word for a period: "today", "week" or "month".
inline const char *habit_period_word(char period) {
  return period == 'w' ? "week" : (period == 'm' ? "month" : "today");
}

// Today's net score: ups less downs of the daily habits.
inline int habit_today_net(const std::vector<Habit> &habits) {
  int net = 0;
  for (const Habit &h : habits) {
    if (h.period == 'd')
      net += h.count_up - h.count_down;
  }
  return net;
}

// A number with at most one decimal: 3.46 -> "3.5", 3.0 -> "3".
inline std::string habit_decimal(float v) {
  const long tenths = std::lround(v * 10);
  const std::string whole = std::to_string(tenths / 10);
  return tenths % 10 == 0 ? whole : whole + "." + std::to_string(std::labs(tenths % 10));
}

// What a score's reply leaves in the notice line: its drop, else its quest
// progress in `quest_word` ("Quest +{n}"); "" for neither.
inline std::string habit_news(const HabitReply &r, std::string quest_word) {
  if (!r.drop.empty())
    return r.drop;
  if (!(r.quest > 0))
    return "";
  const size_t at = quest_word.find("{n}");
  if (at != std::string::npos)
    quest_word.replace(at, 3, habit_decimal(r.quest));
  return quest_word;
}

// The busy notice: HA's error for a rate limit.
inline bool habit_rate_limited(std::string error) {
  for (char &c : error)
    c = (char) std::tolower((unsigned char) c);
  return error.find("rate limit") != std::string::npos || error.find("429") != std::string::npos ||
         error.find("too many") != std::string::npos;
}

// SELECT on a habit with both sides: one press scores up, two quick
// presses score down. The first waits `double_ms` for a second.
class HabitSelect {
 public:
  enum Result { NONE, SINGLE, DOUBLE };
  explicit HabitSelect(uint32_t double_ms = 400) : double_ms_(double_ms) {}
  Result press(uint32_t now) {
    if (this->waiting_ && now - this->at_ <= this->double_ms_) {
      this->waiting_ = false;
      return DOUBLE;
    }
    this->waiting_ = true;
    this->at_ = now;
    return NONE;
  }
  Result tick(uint32_t now) {
    if (!this->waiting_ || now - this->at_ <= this->double_ms_)
      return NONE;
    this->waiting_ = false;
    return SINGLE;
  }
  void cancel() { this->waiting_ = false; }

 protected:
  uint32_t double_ms_;
  uint32_t at_{0};  // pragma: no mutate
  bool waiting_{false};
};

class HabitList {
 public:
  enum class State { EMPTY, LOADING, READY, FAILED };
  enum class Tap { QUEUED, NO_SIDE, FULL, CAPPED };
  enum class Notice { NONE, BUSY, ERROR };
  using Fetch = std::function<void(int generation)>;
  using Score = std::function<void(int seq, const std::string &id, bool up)>;
  using Reply = std::function<void(const HabitReply &)>;

  void set_limits(size_t max_waiting, size_t per_minute, uint32_t timeout_ms) {
    this->max_waiting_ = max_waiting;
    this->per_minute_ = per_minute;
    this->timeout_ms_ = timeout_ms;
  }
  void set_max_items(size_t n) { this->max_items_ = n; }
  void set_fetcher(Fetch f) { this->fetch_ = std::move(f); }
  void set_scorer(Score s) { this->score_ = std::move(s); }
  // A score HA did, or a list with stats: what the reply carried.
  void set_on_reply(Reply r) { this->on_reply_ = std::move(r); }

  // A new source: the list goes, and replies for the old one are dropped.
  void set_source(const std::string &source) {
    if (source == this->source_)
      return;
    this->source_ = source;
    this->generation_++;  // pragma: no mutate
    this->habits_.clear();
    this->state_ = State::EMPTY;
    this->fetching_ = false;
  }
  const std::string &source() const { return this->source_; }

  // Fetch the list unless a fetch is on the way.
  void refresh(uint32_t now) {
    if (this->fetching_ || !this->fetch_ || this->source_.empty())
      return;
    this->fetching_ = true;
    this->fetch_at_ = now;
    if (this->state_ != State::READY)
      this->state_ = State::LOADING;
    this->fetch_(this->generation_);
  }

  void on_list(int generation, const std::string &text) {
    if (generation != this->generation_ || !this->fetching_)
      return;
    this->fetching_ = false;
    HabitReply stats;
    if (!habit_parse_list(text, this->max_items_, this->habits_, stats)) {
      this->state_ = State::FAILED;
      return;
    }
    this->state_ = State::READY;
    // Scores HA has not answered yet stay counted.
    for (const Job &j : this->waiting_)
      this->bump_(j.id, j.up, 1);
    if (this->sending_)
      this->bump_(this->current_.id, this->current_.up, 1);
    if (stats.has_stats && this->on_reply_) {
      stats.ok = true;
      this->on_reply_(stats);
    }
  }

  void on_list_error(int generation) {
    if (generation != this->generation_ || !this->fetching_)
      return;
    this->fetching_ = false;
    if (this->state_ != State::READY)
      this->state_ = State::FAILED;
  }

  // A tap on a habit's plus (up) or minus. The count moves now.
  Tap score(size_t index, bool up, uint32_t now) {
    if (index >= this->habits_.size())  // pragma: no mutate
      return Tap::NO_SIDE;
    if (!(up ? this->habits_[index].up : this->habits_[index].down))
      return Tap::NO_SIDE;
    while (!this->sent_.empty() && now - this->sent_.front() >= MINUTE_MS)
      this->sent_.pop_front();
    if (this->waiting_.size() >= this->max_waiting_) {
      this->notify_(Notice::BUSY, now);
      return Tap::FULL;
    }
    // Scores out in the last minute, and the ones waiting to go.
    if (this->sent_.size() + this->waiting_.size() >= this->per_minute_) {
      this->notify_(Notice::BUSY, now);
      return Tap::CAPPED;
    }
    Habit &h = this->habits_[index];
    this->bump_(h.id, up, 1);
    this->waiting_.push_back(Job{++this->seq_, h.id, up});  // pragma: no mutate
    this->send_next_(now);
    return Tap::QUEUED;
  }

  void on_score(int seq, const std::string &text, uint32_t now) {
    if (!this->sending_ || seq != this->current_.seq)
      return;
    this->sending_ = false;
    HabitReply r;
    if (!habit_parse_reply(text, r) || !r.ok) {
      this->bump_(this->current_.id, this->current_.up, -1);
      this->notify_(Notice::ERROR, now);
    } else {
      Habit *h = this->find_(this->current_.id);
      if (h != nullptr)
        h->value += r.delta;
      if (this->on_reply_)
        this->on_reply_(r);
    }
    this->send_next_(now);
  }

  void on_score_error(int seq, const std::string &error, uint32_t now) {
    if (!this->sending_ || seq != this->current_.seq)
      return;
    this->sending_ = false;
    this->bump_(this->current_.id, this->current_.up, -1);
    this->notify_(habit_rate_limited(error) ? Notice::BUSY : Notice::ERROR, now);
    this->send_next_(now);
  }

  // Call often: a score or a fetch with no answer gives up.
  void tick(uint32_t now) {
    if (this->sending_ && now - this->sent_at_ >= this->timeout_ms_)
      this->on_score_error(this->current_.seq, "", now);
    if (this->fetching_ && now - this->fetch_at_ >= this->timeout_ms_)
      this->on_list_error(this->generation_);
  }

  State state() const { return this->state_; }
  const std::vector<Habit> &habits() const { return this->habits_; }
  size_t waiting() const { return this->waiting_.size(); }
  bool sending() const { return this->sending_; }
  bool fetching() const { return this->fetching_; }
  Notice notice(uint32_t now) const { return now - this->notice_at_ < NOTICE_MS ? this->notice_ : Notice::NONE; }

  static constexpr uint32_t MINUTE_MS = 60000;
  static constexpr uint32_t NOTICE_MS = 3000;

 protected:
  struct Job {
    int seq;
    std::string id;
    bool up;
  };

  Habit *find_(const std::string &id) {
    for (Habit &h : this->habits_) {
      if (h.id == id)
        return &h;
    }
    return nullptr;
  }

  void bump_(const std::string &id, bool up, int by) {
    Habit *h = this->find_(id);
    if (h == nullptr)
      return;
    int &count = up ? h->count_up : h->count_down;
    count = std::max(0, count + by);
  }

  void notify_(Notice n, uint32_t now) {
    this->notice_ = n;
    this->notice_at_ = now;
  }

  void send_next_(uint32_t now) {
    if (this->sending_ || this->waiting_.empty() || !this->score_)
      return;
    this->current_ = this->waiting_.front();
    this->waiting_.pop_front();
    this->sending_ = true;
    this->sent_at_ = now;
    this->sent_.push_back(now);
    this->score_(this->current_.seq, this->current_.id, this->current_.up);
  }

  Fetch fetch_;
  Score score_;
  Reply on_reply_;
  std::string source_;
  int generation_{0};  // pragma: no mutate
  State state_{State::EMPTY};
  std::vector<Habit> habits_;
  size_t max_items_{20};
  bool fetching_{false};  // pragma: no mutate
  uint32_t fetch_at_{0};  // pragma: no mutate

  size_t max_waiting_{5};
  size_t per_minute_{12};
  uint32_t timeout_ms_{10000};
  std::deque<Job> waiting_;
  Job current_{0, "", true};  // pragma: no mutate
  bool sending_{false};
  uint32_t sent_at_{0};        // pragma: no mutate
  std::deque<uint32_t> sent_;  // When each score of the last minute went out.
  int seq_{0};                 // pragma: no mutate

  Notice notice_{Notice::NONE};
  uint32_t notice_at_{0};  // pragma: no mutate
};

}  // namespace Daruma
