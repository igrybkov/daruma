// Host test of the Habits app's data (daruma_habits/habits.h).
//
//   c++ -std=c++17 -Wall -Wextra -I src tests/test_habits.cpp \
//       -o /tmp/test_habits && /tmp/test_habits

#include <cstdio>
#include <string>
#include <vector>

#include "esphome/components/daruma_habits/habits.h"

using namespace Daruma;

static int failures = 0;

#define CHECK(cond) \
  do { \
    if (!(cond)) { \
      std::printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond); \
      failures++; \
    } \
  } while (0)

// Two habits: "Water" with plus only, "Snack" with both sides, weekly.
static const char *const LIST = "L\t2\n"
                                "H\th1\t1\t0\t4.5\t3\t0\td\tWater\n"
                                "H\th2\t1\t1\t-12\t1\t2\tw\tSnack\n"
                                "S\t42\t50\t20\t45\t380\t520\t93.7\t12";

struct Sent {
  int seq;
  std::string id;
  bool up;
};

// A list with its fetcher and scorer recorded.
struct Rig {
  HabitList list;
  std::vector<int> fetches;
  std::vector<Sent> sent;
  std::vector<HabitReply> replies;

  Rig() {
    list.set_limits(5, 12, 10000);
    list.set_fetcher([this](int g) { fetches.push_back(g); });
    list.set_scorer([this](int seq, const std::string &id, bool up) { sent.push_back(Sent{seq, id, up}); });
    list.set_on_reply([this](const HabitReply &r) { replies.push_back(r); });
    list.set_source("script.habits");
    list.refresh(0);
    list.on_list(fetches.back(), LIST);
  }
};

static void parse_a_list() {
  std::vector<Habit> habits;
  HabitReply stats;
  CHECK(habit_parse_list(LIST, 20, habits, stats));
  CHECK(habits.size() == 2);
  const Habit &w = habits[0];
  CHECK(w.id == "h1" && w.title == "Water" && w.up && !w.down);
  CHECK(w.value == 4.5f && w.count_up == 3 && w.count_down == 0 && w.period == 'd');
  const Habit &s = habits[1];
  CHECK(s.id == "h2" && s.up && s.down && s.value == -12 && s.count_up == 1 && s.count_down == 2);
  CHECK(s.period == 'w');
}

static void parse_list_stats() {
  std::vector<Habit> habits;
  HabitReply r;
  CHECK(habit_parse_list(LIST, 20, habits, r));
  const HabitStats &st = r.stats;
  CHECK(r.has_stats);
  CHECK(st.hp == 42 && st.hp_max == 50 && st.mp == 20 && st.mp_max == 45);
  CHECK(st.xp == 380 && st.xp_next == 520 && st.gold == 93.7f && st.level == 12);
}

static void parse_odd_lists() {
  std::vector<Habit> habits;
  HabitReply stats;
  // A cap on the rows; monthly; no stats; a row without an id is skipped.
  CHECK(habit_parse_list("L\t3\nH\t\t1\t1\t0\t0\t0\td\tNo id\nH\ta\t0\t1\t0\t0\t0\tm\tA\nH\tb\t1\t0\t0\t0\t0\td\tB", 1,
                         habits, stats));
  CHECK(habits.size() == 1 && habits[0].id == "a" && habits[0].period == 'm' && !habits[0].up);
  CHECK(!stats.has_stats);
  // An empty list is a list.
  CHECK(habit_parse_list("L\t0", 20, habits, stats) && habits.empty());
  // Not a list, and a short row.
  CHECK(!habit_parse_list("", 20, habits, stats));
  CHECK(!habit_parse_list("R\t1\t0\t0\t", 20, habits, stats));
  CHECK(habit_parse_list("L\t1\nH\tx\t1\t0\t0\t0\t0\td", 20, habits, stats) && habits.empty());
  // A short stats row is no stats.
  CHECK(habit_parse_list("L\t0\nS\t1\t2", 20, habits, stats) && !stats.has_stats);
  // Unknown numbers: value 0, counts 0, stats -1.
  CHECK(habit_parse_list("L\t1\nH\tx\t1\t0\tnan?\t\tz\tq\tT\nS\t-1\t\t\t\t\t\t\t", 20, habits, stats));
  CHECK(habits[0].value == 0 && habits[0].count_up == 0 && habits[0].count_down == 0 && habits[0].period == 'd');
  CHECK(stats.has_stats && stats.stats.hp == -1 && stats.stats.hp_max == -1 && stats.stats.level == -1);
}

static void defaults() {
  Habit h;
  CHECK(!h.up && !h.down && h.value == 0 && h.count_up == 0 && h.count_down == 0 && h.period == 'd');
  HabitStats s;
  CHECK(s.hp == -1 && s.hp_max == -1 && s.mp == -1 && s.mp_max == -1);
  CHECK(s.xp == -1 && s.xp_next == -1 && s.gold == -1 && s.level == -1);
}

static void empty_stats() {
  HabitReply r;
  CHECK(!r.ok && r.delta == 0 && r.quest == 0 && r.drop.empty() && !r.has_stats);
  HabitStats s;
  // Every stat field left empty is unknown.
  std::vector<Habit> habits;
  CHECK(habit_parse_list("L\t0\nS\t\t\t\t\t\t\t\t", 20, habits, r) && r.has_stats);
  CHECK(r.stats.hp == -1 && r.stats.hp_max == -1 && r.stats.mp == -1 && r.stats.mp_max == -1);
  CHECK(r.stats.xp == -1 && r.stats.xp_next == -1 && r.stats.gold == -1 && r.stats.level == -1);
  // A stats row needs its tag.
  CHECK(!habit_parse_stats(habit_fields("X\t1\t2\t3\t4\t5\t6\t7\t8"), s));
}

static void list_defaults() {
  // No set_limits: 5 may wait, 12 a minute, 10 s to answer, 20 rows.
  HabitList list;
  std::vector<int> fetches;
  int sends = 0;
  list.set_fetcher([&](int g) { fetches.push_back(g); });
  list.set_scorer([&](int, const std::string &, bool) { sends++; });
  list.set_source("script.a");
  list.refresh(0);
  std::string text = "L\t21";
  for (int i = 0; i < 21; i++)
    text += "\nH\th" + std::to_string(i) + "\t1\t0\t0\t0\t0\td\tT";
  list.on_list(fetches.back(), text);
  CHECK(list.habits().size() == 20);
  for (int i = 0; i < 6; i++)
    CHECK(list.score(0, true, 0) == HabitList::Tap::QUEUED);
  CHECK(list.score(0, true, 0) == HabitList::Tap::FULL);
  list.tick(9999);
  CHECK(list.sending() && sends == 1);
  list.tick(10000);  // Timed out; the next goes.
  CHECK(sends == 2);

  // Twelve a minute, each answered at once.
  HabitList quick;
  int seq = 0;
  quick.set_fetcher([&](int g) { fetches.push_back(g); });
  quick.set_scorer([&](int s, const std::string &, bool) { seq = s; });
  quick.set_source("script.a");
  quick.refresh(0);
  quick.on_list(fetches.back(), text);
  for (int i = 0; i < 12; i++) {
    CHECK(quick.score(0, true, 0) == HabitList::Tap::QUEUED);
    quick.on_score(seq, "R\t1\t0\t0\t", 0);
  }
  CHECK(quick.score(0, true, 0) == HabitList::Tap::CAPPED);
}

static void parse_a_reply() {
  HabitReply r;
  CHECK(habit_parse_reply("R\t1\t0.98\t3.5\tYou found a Wolf Egg!\nS\t40\t50\t21\t45\t400\t520\t95\t13", r));
  CHECK(r.ok && r.delta == 0.98f && r.quest == 3.5f && r.drop == "You found a Wolf Egg!");
  CHECK(r.has_stats && r.stats.level == 13 && r.stats.hp == 40 && r.stats.gold == 95);
  CHECK(habit_parse_reply("R\t0\t0\t0\t", r));
  CHECK(!r.ok && r.drop.empty() && !r.has_stats && r.delta == 0);
  CHECK(!habit_parse_reply("L\t0", r));
  // Empty numbers are 0.
  CHECK(habit_parse_reply("R\t1\t\t\t", r) && r.delta == 0 && r.quest == 0);
  CHECK(!habit_parse_reply("R\t1\t0", r));
  CHECK(!habit_parse_reply("", r));
}

static void small_parts() {
  CHECK(habit_fields("a\tb\t\tc").size() == 4);
  CHECK(habit_fields("").size() == 1);
  CHECK(habit_float("2.5", -1) == 2.5f);
  CHECK(habit_float("", -1) == -1);
  CHECK(habit_float("x", 7) == 7);
  CHECK(habit_int("3") == 3);

  // Value colors: worst below -20, then -10, -1, 1, 5, 10, best.
  CHECK(habit_value_band(-25) == 0);
  CHECK(habit_value_band(-20.5f) == 0);
  CHECK(habit_value_band(-20) == 1);
  CHECK(habit_value_band(-10.5f) == 1);
  CHECK(habit_value_band(-10) == 2);
  CHECK(habit_value_band(-1.5f) == 2);
  CHECK(habit_value_band(-1) == 3);
  CHECK(habit_value_band(0.5f) == 3);
  CHECK(habit_value_band(1) == 4);
  CHECK(habit_value_band(4.9f) == 4);
  CHECK(habit_value_band(5) == 5);
  CHECK(habit_value_band(9.9f) == 5);
  CHECK(habit_value_band(10) == 6);
  CHECK(habit_value_band(30) == 6);

  CHECK(habit_signed(4) == "+4");
  CHECK(habit_signed(1) == "+1");
  CHECK(habit_signed(-2) == "-2");
  CHECK(habit_signed(0) == "0");

  Habit h;
  h.up = true;
  h.count_up = 3;
  CHECK(habit_counts(h) == "+3");
  h.down = true;
  h.count_down = 1;
  CHECK(habit_counts(h) == "+3 -1");
  h.up = false;
  CHECK(habit_counts(h) == "-1");
  h.down = false;
  CHECK(habit_counts(h).empty());

  CHECK(std::string(habit_period_word('d')) == "today");
  CHECK(std::string(habit_period_word('w')) == "week");
  CHECK(std::string(habit_period_word('m')) == "month");

  std::vector<Habit> hs(3);
  hs[0].count_up = 4;
  hs[0].count_down = 1;
  hs[1].count_up = 2;
  hs[2].period = 'w';
  hs[2].count_up = 9;
  CHECK(habit_today_net(hs) == 5);

  CHECK(habit_rate_limited("Rate limit exceeded, try again in 30 seconds"));
  CHECK(habit_rate_limited("HTTP 429"));
  CHECK(habit_rate_limited("Too Many Requests"));
  CHECK(!habit_rate_limited("Task not found"));
  CHECK(!habit_rate_limited(""));
}

static void select_once_or_twice() {
  // The default waits 400 ms; nothing waits before a press.
  HabitSelect d;
  CHECK(d.tick(10000) == HabitSelect::NONE);
  d.press(1000);
  CHECK(d.tick(1400) == HabitSelect::NONE && d.tick(1401) == HabitSelect::SINGLE);
  HabitSelect s(400);
  CHECK(s.press(1000) == HabitSelect::NONE);
  CHECK(s.tick(1400) == HabitSelect::NONE);
  CHECK(s.tick(1401) == HabitSelect::SINGLE);
  CHECK(s.tick(2000) == HabitSelect::NONE);  // Once only.
  CHECK(s.press(3000) == HabitSelect::NONE);
  CHECK(s.press(3400) == HabitSelect::DOUBLE);
  CHECK(s.tick(4000) == HabitSelect::NONE);
  // Too slow for a double: two singles.
  CHECK(s.press(5000) == HabitSelect::NONE);
  CHECK(s.press(5401) == HabitSelect::NONE);
  CHECK(s.tick(5801) == HabitSelect::NONE);
  CHECK(s.tick(5802) == HabitSelect::SINGLE);
  s.press(6000);
  s.cancel();
  CHECK(s.tick(7000) == HabitSelect::NONE);
}

static void fetch_and_generations() {
  HabitList list;
  std::vector<int> fetches;
  list.set_fetcher([&](int g) { fetches.push_back(g); });
  CHECK(list.state() == HabitList::State::EMPTY);
  list.refresh(0);  // No source: nothing.
  CHECK(fetches.empty());
  list.set_source("script.a");
  list.refresh(0);
  CHECK(fetches.size() == 1 && list.state() == HabitList::State::LOADING && list.fetching());
  list.refresh(10);  // One at a time.
  CHECK(fetches.size() == 1);
  // The source changes while it fetches: the old reply is dropped.
  list.set_source("script.b");
  CHECK(!list.fetching() && list.state() == HabitList::State::EMPTY);
  list.set_source("script.b");  // The same again: nothing changes.
  list.refresh(20);
  CHECK(fetches.size() == 2 && fetches[1] != fetches[0]);
  list.on_list(fetches[0], LIST);
  CHECK(list.habits().empty() && list.fetching());
  list.on_list(fetches[1], LIST);
  CHECK(list.habits().size() == 2 && list.state() == HabitList::State::READY && !list.fetching());
  // A late answer is dropped.
  list.on_list(fetches[1], "L\t0");
  CHECK(list.habits().size() == 2);
  // A refresh keeps the list on screen while it loads.
  list.refresh(30);
  CHECK(list.state() == HabitList::State::READY);
  list.on_list_error(fetches.back());
  CHECK(list.state() == HabitList::State::READY && !list.fetching());
  list.on_list_error(fetches.back());  // Not fetching: nothing.
  // A reply that is not a list fails.
  list.refresh(40);
  list.on_list(fetches.back(), "nonsense");
  CHECK(list.state() == HabitList::State::FAILED);
}

static void fetch_fails_and_times_out() {
  HabitList list;
  std::vector<int> fetches;
  list.set_limits(5, 12, 1000);
  list.set_fetcher([&](int g) { fetches.push_back(g); });
  list.set_source("script.a");
  list.refresh(0);
  list.on_list_error(fetches.back() + 1);  // Another generation.
  CHECK(list.fetching());
  list.on_list_error(fetches.back());
  CHECK(list.state() == HabitList::State::FAILED);
  list.refresh(100);
  list.tick(1099);
  CHECK(list.fetching());
  list.tick(1100);
  CHECK(!list.fetching() && list.state() == HabitList::State::FAILED);
}

static void a_tap_bumps_and_sends() {
  Rig r;
  CHECK(r.list.score(0, true, 100) == HabitList::Tap::QUEUED);
  CHECK(r.list.habits()[0].count_up == 4);
  CHECK(r.sent.size() == 1 && r.sent[0].id == "h1" && r.sent[0].up && r.list.sending());
  // A side the habit lacks, and a row that is not there.
  CHECK(r.list.score(0, false, 100) == HabitList::Tap::NO_SIDE);
  CHECK(r.list.score(9, true, 100) == HabitList::Tap::NO_SIDE);
  CHECK(r.list.score(2, true, 100) == HabitList::Tap::NO_SIDE);  // Just past the end.
  // HA scored it: the value moves by the delta; the reply goes out.
  r.list.on_score(r.sent[0].seq, "R\t1\t0.75\t0\tA drop!\nS\t42\t50\t20\t45\t390\t520\t94\t12", 200);
  CHECK(!r.list.sending() && r.list.habits()[0].count_up == 4 && r.list.habits()[0].value == 5.25f);
  CHECK(r.replies.size() == 2 && r.replies[1].drop == "A drop!" && r.replies[1].stats.xp == 390);
  // The list's own stats came first, as a reply.
  CHECK(r.replies[0].ok && r.replies[0].has_stats && r.replies[0].stats.level == 12);
  CHECK(r.list.notice(200) == HabitList::Notice::NONE);
  // Down on the two-sided one.
  CHECK(r.list.score(1, false, 300) == HabitList::Tap::QUEUED);
  CHECK(r.list.habits()[1].count_down == 3 && !r.sent.back().up);
}

static void errors_take_the_bump_back() {
  Rig r;
  r.list.score(1, true, 0);
  // ok 0: back, with the error notice.
  r.list.on_score(r.sent[0].seq, "R\t0\t0\t0\t", 100);
  CHECK(r.list.habits()[1].count_up == 1);
  CHECK(r.list.notice(100) == HabitList::Notice::ERROR);
  CHECK(r.list.notice(3099) == HabitList::Notice::ERROR);
  CHECK(r.list.notice(3100) == HabitList::Notice::NONE);
  // A reply that is not one: back too.
  r.list.score(1, true, 4000);
  r.list.on_score(r.sent[1].seq, "", 4100);
  CHECK(r.list.habits()[1].count_up == 1);
  // An HA error; a rate limit says busy.
  r.list.score(1, false, 5000);
  r.list.on_score_error(r.sent[2].seq, "Rate limit exceeded", 5100);
  CHECK(r.list.habits()[1].count_down == 2 && r.list.notice(5100) == HabitList::Notice::BUSY);
  r.list.score(1, false, 9000);
  r.list.on_score_error(r.sent[3].seq, "Task not found", 9100);
  CHECK(r.list.notice(9100) == HabitList::Notice::ERROR);
  // Answers to another score are dropped.
  r.list.score(0, true, 10000);
  r.list.on_score(r.sent[4].seq + 1, "R\t0\t0\t0\t", 10100);
  r.list.on_score_error(r.sent[4].seq + 1, "x", 10100);
  CHECK(r.list.sending() && r.list.habits()[0].count_up == 4);
  // A count never goes below 0.
  Rig z;
  z.list.on_list(z.fetches.back(), "");
  z.list.refresh(0);
  z.list.on_list(z.fetches.back(), "L\t1\nH\tz\t0\t1\t0\t0\t0\td\tZ");
  z.list.score(0, false, 0);
  z.list.on_list(z.fetches.back(), "");  // Not fetching: dropped.
  CHECK(z.list.habits()[0].count_down == 1);
  z.list.refresh(10);
  z.list.on_list(z.fetches.back(), "L\t1\nH\tz\t0\t1\t0\t0\t0\td\tZ");  // HA's 0, plus the one in flight.
  CHECK(z.list.habits()[0].count_down == 1);
  z.list.refresh(20);
  z.list.on_list(z.fetches.back(), "L\t1\nH\tz\t0\t1\t0\t0\t0\td\tZ");
  z.list.on_score_error(z.sent[0].seq, "", 30);
  CHECK(z.list.habits()[0].count_down == 0);
}

static void a_score_times_out() {
  Rig r;
  r.list.score(0, true, 1000);
  r.list.tick(10999);
  CHECK(r.list.sending() && r.list.habits()[0].count_up == 4);
  r.list.tick(11000);
  CHECK(!r.list.sending() && r.list.habits()[0].count_up == 3);
  CHECK(r.list.notice(11000) == HabitList::Notice::ERROR);
  // The late answer changes nothing.
  r.list.on_score(r.sent[0].seq, "R\t1\t1\t0\t", 12000);
  CHECK(r.list.habits()[0].count_up == 3 && r.replies.size() == 1);
}

static void one_in_flight_and_the_queue_cap() {
  Rig r;
  for (int i = 0; i < 6; i++)
    CHECK(r.list.score(0, true, 0) == HabitList::Tap::QUEUED);
  // One went, five wait: the next is dropped with the notice.
  CHECK(r.sent.size() == 1 && r.list.waiting() == 5);
  CHECK(r.list.score(0, true, 0) == HabitList::Tap::FULL);
  CHECK(r.list.habits()[0].count_up == 9);
  CHECK(r.list.notice(0) == HabitList::Notice::BUSY);
  // An answer sends the next.
  r.list.on_score(r.sent[0].seq, "R\t1\t0\t0\t", 10);
  CHECK(r.sent.size() == 2 && r.list.waiting() == 4 && r.list.sending());
  // A fresh list keeps the scores not answered yet: 1 in flight, 4 waiting.
  r.list.refresh(20);
  r.list.on_list(r.fetches.back(), LIST);
  CHECK(r.list.habits()[0].count_up == 8);
  // An error sends the next too.
  r.list.on_score_error(r.sent[1].seq, "x", 30);
  CHECK(r.sent.size() == 3 && r.list.habits()[0].count_up == 7);
}

static void the_minute_cap() {
  Rig r;
  r.list.set_limits(5, 3, 10000);
  for (int i = 0; i < 3; i++) {
    CHECK(r.list.score(0, true, 1000) == HabitList::Tap::QUEUED);
    r.list.on_score(r.sent.back().seq, "R\t1\t0\t0\t", 1000);
  }
  CHECK(r.list.score(0, true, 60999) == HabitList::Tap::CAPPED);
  CHECK(r.list.notice(60999) == HabitList::Notice::BUSY && r.list.habits()[0].count_up == 6);
  // A minute after the first went out, there is room again.
  CHECK(r.list.score(0, true, 61000) == HabitList::Tap::QUEUED);
  // Waiting scores count too.
  Rig w;
  w.list.set_limits(5, 2, 10000);
  CHECK(w.list.score(0, true, 0) == HabitList::Tap::QUEUED);  // Sent.
  CHECK(w.list.score(0, true, 0) == HabitList::Tap::QUEUED);  // Waits.
  CHECK(w.list.score(0, true, 0) == HabitList::Tap::CAPPED);
}

static void no_scorer_keeps_it_waiting() {
  HabitList list;
  std::vector<int> fetches;
  list.set_fetcher([&](int g) { fetches.push_back(g); });
  list.set_source("script.a");
  list.refresh(0);
  list.on_list(fetches.back(), LIST);
  CHECK(list.score(0, true, 0) == HabitList::Tap::QUEUED);
  CHECK(!list.sending() && list.waiting() == 1);
}

int main() {
  parse_a_list();
  parse_odd_lists();
  parse_list_stats();
  defaults();
  empty_stats();
  list_defaults();
  parse_a_reply();
  small_parts();
  select_once_or_twice();
  fetch_and_generations();
  fetch_fails_and_times_out();
  a_tap_bumps_and_sends();
  errors_take_the_bump_back();
  a_score_times_out();
  one_in_flight_and_the_queue_cap();
  the_minute_cap();
  no_scorer_keeps_it_waiting();
  if (failures == 0)
    std::printf("test_habits: all passed\n");
  return failures == 0 ? 0 : 1;
}
