// Host test of the random events engine (daruma/random_events.h): the
// tables, the generator, the conditions, the guards, the rates of random
// and scheduled rolls, the draw counts and the phases of one event.
//
//   uv run pytest tests/test_random_events.cpp   (pytest builds and runs it: tests/conftest.py)

#define DARUMA_STATE_LIST \
  X(NEUTRAL, "neutral", MOOD, -1, 0, false) \
  X(HAPPY, "happy", MOOD, 0, 0, false) \
  X(SLEEPING, "sleeping", MOOD, 0, 0, false)

#include <cmath>
#include <cstdio>
#include <initializer_list>

#include "esphome/components/daruma/random_events.h"

using namespace Daruma;
using namespace Daruma::RandomEvents;

static int failures = 0;

#define CHECK(cond) \
  do { \
    if (!(cond)) { \
      std::printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond); \
      failures++; \
    } \
  } while (0)

static const uint32_t MIN = 60 * 1000;
static const uint32_t DAY_S = 86400;

// A one-shot with an animation, no conditions.
static EventDef event(const char *name, uint8_t frequency = 8) {
  EventDef e{};
  e.name = name;
  e.kind = Kind::ONE_SHOT;
  e.enter = -1;
  e.animation = 0;
  e.exit = -1;
  e.frequency = frequency;
  e.sound = "";
  return e;
}

// Awake, unblocked, synced: Monday 06-15 at 10:00.
static Context awake() {
  Context c{};
  c.clock = true;
  c.epoch = 1750000000;
  c.month_day = 615;
  c.weekday = 2;
  c.minute = 600;
  c.mood = StateId::NEUTRAL;
  c.liveliness = 1.0f;
  c.animate = true;
  return c;
}

// A pool of up to four events. Every array the tests point at holds one
// entry past its count, and the pool holds an always-eligible "ghost" past
// its count, so a loop that reads one too far changes a result.
struct Pool {
  EventDef events[5];
  EventState states[5]{};
  uint8_t count;
  Engine engine;
  Pool(std::initializer_list<EventDef> list) : count(0) {
    for (const EventDef &e : list)
      events[count++] = e;
    events[count] = event("ghost", 10);
    engine.set_pool(events, count, states);
  }
};

// How many draws took `before` to `after`.
static int draws(Rng before, const Rng &after) {
  for (int n = 0; n < 10000; n++) {
    if (before.state == after.state)
      return n;
    before.next();
  }
  return -1;
}

// A generator whose first unit() is exactly 0.
static Rng zero_first() { return Rng{0u - Rng::INCREMENT}; }

static void test_tables() {
  const uint32_t mean[] = {0, 7776000, 2592000, 1209600, 604800, 259200, 86400, 21600, 7200, 1800, 600};
  const uint8_t chance[] = {0, 1, 5, 15, 25, 40, 55, 70, 85, 95, 100};
  CHECK(sizeof(MEAN_S) / sizeof(MEAN_S[0]) == 11);
  CHECK(sizeof(AT_CHANCE) / sizeof(AT_CHANCE[0]) == 11);
  for (int f = 0; f <= 10; f++) {
    CHECK(MEAN_S[f] == mean[f]);
    CHECK(AT_CHANCE[f] == chance[f]);
  }
}

static void test_rng() {
  Rng r{1};
  CHECK(r.next() == 0x1A4B4B98u);
  CHECK(r.next() == 0xB2E5A32Au);
  Rng u{1};
  CHECK(u.unit() == static_cast<float>(0x1A4B4Bu) / 16777216.0f);
  Rng b{1};
  CHECK(b.below(1000) == 168u);
  Rng z = zero_first();
  CHECK(z.unit() == 0.0f);
  // unit() covers [0, 1).
  Rng s{7};
  float lo = 1, hi = 0, sum = 0;
  for (int i = 0; i < 10000; i++) {
    float x = s.unit();
    lo = std::fmin(lo, x);
    hi = std::fmax(hi, x);
    sum += x;
  }
  CHECK(lo >= 0.0f && lo < 0.01f && hi < 1.0f && hi > 0.99f);
  CHECK(std::fabs(sum / 10000 - 0.5f) < 0.02f);
}

static void test_dates() {
  const DateRange winter[] = {{1220, 105}, {101, 1231}};
  const DateRange either[] = {{1220, 105}, {601, 630}, {101, 1231}};
  const DateRange spring[] = {{401, 531}, {101, 1231}};
  const DateRange pi[] = {{314, 314}, {101, 1231}};
  EventDef e = event("e");
  e.dates = winter;
  e.date_count = 1;
  CHECK(on_date(e, 1220) && on_date(e, 1231) && on_date(e, 101) && on_date(e, 105));
  CHECK(!on_date(e, 1219) && !on_date(e, 106) && !on_date(e, 615));
  e.dates = spring;
  CHECK(on_date(e, 401) && on_date(e, 531));
  CHECK(!on_date(e, 331) && !on_date(e, 601));
  e.dates = pi;
  CHECK(on_date(e, 314) && !on_date(e, 313) && !on_date(e, 315));
  // Any of the ranges.
  e.dates = either;
  e.date_count = 2;
  CHECK(on_date(e, 615) && on_date(e, 101) && !on_date(e, 700));
  e.date_count = 0;
  CHECK(on_date(e, 615));
}

static void test_times() {
  const TimeRange night[] = {{1320, 360}, {0, 1440}};
  const TimeRange morning[] = {{600, 660}, {0, 1440}};
  const TimeRange none[] = {{600, 600}, {0, 1440}};
  const TimeRange late[] = {{1380, 1440}, {0, 1440}};
  const TimeRange either[] = {{600, 660}, {1380, 1440}, {0, 1440}};
  EventDef e = event("e");
  e.times = night;
  e.time_count = 1;
  CHECK(in_times(e, 1320) && in_times(e, 1439) && in_times(e, 0) && in_times(e, 359));
  CHECK(!in_times(e, 1319) && !in_times(e, 360) && !in_times(e, 720));
  e.times = morning;
  CHECK(in_times(e, 600) && in_times(e, 659));
  CHECK(!in_times(e, 599) && !in_times(e, 660));
  e.times = none;
  CHECK(!in_times(e, 600) && !in_times(e, 0));
  e.times = late;
  CHECK(in_times(e, 1439) && !in_times(e, 0));
  e.times = either;
  e.time_count = 2;
  CHECK(in_times(e, 1400) && in_times(e, 600) && !in_times(e, 720));
  e.time_count = 0;
  CHECK(in_times(e, 720));
}

static void test_weekdays() {
  EventDef e = event("e");
  CHECK(on_weekday(e, 1) && on_weekday(e, 7));
  e.weekdays = 0x3E;  // Monday to Friday
  CHECK(!on_weekday(e, 1) && !on_weekday(e, 7));
  for (uint8_t d = 2; d <= 6; d++)
    CHECK(on_weekday(e, d));
  e.weekdays = 0x01;  // Sunday
  CHECK(on_weekday(e, 1) && !on_weekday(e, 2));
}

static void test_moods() {
  const StateId happy[] = {StateId::HAPPY, StateId::NEUTRAL};
  const StateId sleeping_happy[] = {StateId::SLEEPING, StateId::HAPPY, StateId::NEUTRAL};
  EventDef any = event("any");
  CHECK(mood_fits(any, StateId::NEUTRAL) && mood_fits(any, StateId::HAPPY));
  CHECK(!mood_fits(any, StateId::SLEEPING));
  EventDef glad = event("glad");
  glad.moods = happy;
  glad.mood_count = 1;
  CHECK(mood_fits(glad, StateId::HAPPY) && !mood_fits(glad, StateId::NEUTRAL));
  CHECK(!mood_fits(glad, StateId::SLEEPING));
  // moods: [sleeping], with or without SLEEPING in the list.
  EventDef snore = event("snore");
  snore.sleeping = true;
  CHECK(mood_fits(snore, StateId::SLEEPING) && !mood_fits(snore, StateId::NEUTRAL));
  snore.moods = sleeping_happy;
  snore.mood_count = 1;
  CHECK(mood_fits(snore, StateId::SLEEPING) && !mood_fits(snore, StateId::NEUTRAL));
  snore.mood_count = 2;
  CHECK(mood_fits(snore, StateId::HAPPY) && !mood_fits(snore, StateId::NEUTRAL));
}

// Date, weekday and time conditions need the clock; moods don't.
static void test_clock() {
  const DateRange year[] = {{101, 1231}};
  const TimeRange day[] = {{0, 1440}};
  const StateId neutral[] = {StateId::NEUTRAL};
  Context synced = awake();
  Context unsynced = awake();
  unsynced.clock = false;
  EventDef plain = event("plain");
  CHECK(when_holds(plain, unsynced));
  EventDef dated = event("dated");
  dated.dates = year;
  dated.date_count = 1;
  EventDef weekly = event("weekly");
  weekly.weekdays = 0x7F;
  EventDef timed = event("timed");
  timed.times = day;
  timed.time_count = 1;
  EventDef moody = event("moody");
  moody.moods = neutral;
  moody.mood_count = 1;
  for (const EventDef *e : {&dated, &weekly, &timed}) {
    CHECK(when_holds(*e, synced));
    CHECK(!when_holds(*e, unsynced));
  }
  CHECK(when_holds(moody, unsynced));
  Context asleep = awake();
  asleep.mood = StateId::SLEEPING;
  CHECK(!when_holds(plain, asleep));
}

static void test_cooldown() {
  EventDef e = event("bath");
  e.cooldown_s = DAY_S;
  Pool p{e};
  Context c = awake();
  CHECK(p.engine.eligible(0, c));
  p.engine.played(0, c);
  CHECK(p.states[0].last_epoch == c.epoch);
  p.engine.set_pool(p.events, p.count, p.states);  // forget it was last
  c.epoch += DAY_S - 1;
  CHECK(!p.engine.eligible(0, c));
  c.epoch += 1;
  CHECK(p.engine.eligible(0, c));
  // No clock: a cooldown event sits out, and a play keeps no stamp.
  Context unsynced = c;
  unsynced.clock = false;
  CHECK(!p.engine.eligible(0, unsynced));
  unsynced.epoch = c.epoch + 10;
  p.engine.played(0, unsynced);
  CHECK(p.states[0].last_epoch == c.epoch - DAY_S);
  // An event without a cooldown ignores the clock and the stamp.
  EventDef plain = event("plain");
  Pool q{plain};
  q.engine.played(0, c);
  q.engine.set_pool(q.events, q.count, q.states);
  CHECK(q.engine.eligible(0, unsynced) && q.engine.eligible(0, c));
}

static void test_gates() {
  Pool p{event("a")};
  Context c = awake();
  CHECK(p.engine.eligible(0, c));
  Context blocked = c;
  blocked.blocked = true;
  CHECK(!p.engine.eligible(0, blocked));
  Context dull = c;
  dull.liveliness = 0.0f;
  CHECK(!p.engine.eligible(0, dull));
  // A still-only display plays only say-only events.
  Context still = c;
  still.animate = false;
  CHECK(!p.engine.eligible(0, still));
  p.events[0].animation = -1;
  CHECK(p.engine.eligible(0, still));
  // `at:` events never join random rolls.
  const uint16_t at[] = {600};
  p.events[0].at = at;
  p.events[0].at_count = 1;
  CHECK(!p.engine.eligible(0, c));
}

static void test_gap_and_repeat() {
  Pool p{event("a", 10), event("b", 10)};
  Context c = awake();
  c.min_gap_ms = 15 * MIN;
  // The gap counts from boot.
  CHECK(!p.engine.eligible(0, c));
  p.engine.sample(c, 15 * MIN - 1);
  CHECK(!p.engine.eligible(0, c) && !p.engine.eligible(1, c));
  p.engine.sample(c, 1);
  CHECK(p.engine.eligible(0, c) && p.engine.eligible(1, c));
  p.engine.played(0, c);
  CHECK(p.engine.last() == 0);
  CHECK(!p.engine.eligible(1, c));
  p.engine.sample(c, 15 * MIN);
  CHECK(p.engine.eligible(1, c));
  // Never twice in a row, however long ago: the other one could play.
  p.engine.sample(c, 100 * MIN);
  CHECK(!p.engine.eligible(0, c));
  // A new pool forgets the last event and keeps the gap clock.
  p.engine.played(0, c);
  p.engine.set_pool(p.events, p.count, p.states);
  CHECK(p.engine.last() == -1);
  CHECK(!p.engine.eligible(0, c));
}

// The only event that could play repeats after twice its mean interval.
static void test_alone_repeats() {
  Pool p{event("other", 10), event("snore", 10)};
  Context c = awake();
  p.engine.played(1, c);
  c.animate = false;
  p.events[1].animation = -1;  // say-only: "other" can't show now
  p.engine.sample(c, 20 * MIN - 1);
  CHECK(!p.engine.eligible(1, c));
  p.engine.sample(c, 1);
  CHECK(p.engine.eligible(1, c));
  // Once the other one could play, no repeat.
  c.animate = true;
  CHECK(!p.engine.eligible(1, c) && p.engine.eligible(0, c));
  // Frequency 1: twice 90 days, past what millis can count.
  Pool q{event("rare", 1)};
  q.engine.played(0, c);
  for (int i = 0; i < 4; i++)
    q.engine.sample(c, 3888000000u - (i == 3 ? 3600000u : 0u));
  CHECK(!q.engine.eligible(0, c));
  q.engine.sample(c, 3600000u);
  CHECK(q.engine.eligible(0, c));
}

static void test_eligible_time() {
  const StateId happy[] = {StateId::HAPPY};
  Pool p{event("glad"), event("a")};
  p.events[0].moods = happy;
  p.events[0].mood_count = 1;
  Context c = awake();
  p.engine.sample(c, 5000);
  CHECK(p.states[1].eligible_ms == 5000);
  CHECK(p.states[0].eligible_ms == 0);
  CHECK(p.states[2].eligible_ms == 0);  // the ghost is outside the pool
  Context blocked = c;
  blocked.blocked = true;
  p.engine.sample(blocked, 5000);
  CHECK(p.states[1].eligible_ms == 5000);
  // A roll starts the eligible events from zero; the others keep theirs.
  p.states[0].eligible_ms = 7000;
  Rng r{3};
  p.engine.roll(c, r);
  CHECK(p.states[1].eligible_ms == 0);
  CHECK(p.states[0].eligible_ms == 7000);
  // A blocked roll keeps them all.
  p.states[1].eligible_ms = 9000;
  p.engine.roll(blocked, r);
  CHECK(p.states[1].eligible_ms == 9000);
}

static void test_roll_draws() {
  Pool p{event("a"), event("b"), event("c")};
  Context c = awake();
  Rng r{11};
  Rng before = r;
  p.engine.roll(c, r);
  CHECK(draws(before, r) == 4);
  // Hits or not, eligible or not: the same count.
  p.events[1].animation = 1;
  Context still = c;
  still.animate = false;
  for (EventState &s : p.states)
    s.eligible_ms = 1000000000;
  before = r;
  p.engine.roll(still, r);
  CHECK(draws(before, r) == 4);
  Context dull = c;
  dull.liveliness = 0.0f;
  before = r;
  CHECK(p.engine.roll(dull, r) == -1);
  CHECK(draws(before, r) == 4);
  // A blocked roll draws nothing.
  Context blocked = c;
  blocked.blocked = true;
  before = r;
  CHECK(p.engine.roll(blocked, r) == -1);
  CHECK(draws(before, r) == 0);
  // No events: just the pick.
  Engine empty;
  before = r;
  CHECK(empty.roll(c, r) == -1);
  CHECK(draws(before, r) == 1);
}

static void test_roll_hits() {
  Pool p{event("a"), event("b")};
  Context c = awake();
  // No eligible time: no chance, even when u is 0.
  Rng z = zero_first();
  CHECK(p.engine.roll(c, z) == -1);
  // A sure hit: one of the hits plays.
  int seen[2] = {0, 0};
  Rng r{5};
  for (int i = 0; i < 400; i++) {
    for (int k = 0; k < 2; k++)
      p.states[k].eligible_ms = 1000ull * MEAN_S[8] * 40;
    int got = p.engine.roll(c, r);
    CHECK(got == 0 || got == 1);
    if (got >= 0)
      seen[got]++;
  }
  CHECK(seen[0] > 150 && seen[1] > 150);
}

// Hits per mean interval of eligible time, stepping one random wait at a
// time, with waits from mean / 100 to mean / 20. A roll plays at most one
// event, so waits near the mean would count fewer plays than the rate.
static double rate(uint8_t frequency, float liveliness, bool block_every_other) {
  Pool p{event("e", frequency)};
  Context c = awake();
  c.liveliness = liveliness;
  Context blocked = c;
  blocked.blocked = true;
  const double mean = 1000.0 * MEAN_S[frequency];
  const auto wait_min = static_cast<uint32_t>(mean / 100);
  const auto wait_max = static_cast<uint32_t>(mean / 20);
  Rng waits{99};
  Rng r{42};
  const double total = 2000 * mean;
  double elapsed = 0;
  int hits = 0;
  for (int step = 0; elapsed < total; step++) {
    uint32_t dt = wait_min + waits.below(wait_max - wait_min + 1);
    p.engine.sample(c, dt);
    elapsed += dt;
    bool skip = block_every_other && step % 2 == 1;
    if (p.engine.roll(skip ? blocked : c, r) >= 0)
      hits++;
  }
  return hits / (elapsed / mean);
}

static bool near(double value, double expected) { return std::fabs(value - expected) <= 0.1 * expected; }

static void test_rates() {
  for (uint8_t f = 1; f <= 10; f++)
    CHECK(near(rate(f, 1.0f, false), 1.0));
  CHECK(near(rate(8, 2.0f, false), 2.0));
  CHECK(near(rate(8, 0.5f, false), 0.5));
  CHECK(rate(8, 0.0f, false) == 0.0);
  CHECK(near(rate(8, 1.0f, true), 1.0));
}

static EventDef scheduled(const char *name, uint8_t frequency, const uint16_t *at, uint8_t count) {
  EventDef e = event(name, frequency);
  e.at = at;
  e.at_count = count;
  return e;
}

// One step every 5 s through a minute. Returns the plays.
static int minute_of_steps(Pool &p, Context c, Rng &r, int blocked_steps = 0) {
  int plays = 0;
  for (int s = 0; s < 12; s++) {
    c.blocked = s < blocked_steps;
    int got = p.engine.roll_at(c, r);
    if (got >= 0) {
      plays++;
      p.engine.played(static_cast<uint8_t>(got), c);
    }
  }
  return plays;
}

static void test_at_once_per_minute() {
  const uint16_t at[] = {914, 600, 600};
  Pool p{scheduled("pi", 10, at, 1)};
  Context c = awake();
  c.minute = 914;
  Rng r{1};
  CHECK(minute_of_steps(p, c, r) == 1);
  // Not at another minute, nor at a minute one past the list.
  c.minute = 600;
  CHECK(minute_of_steps(p, c, r) == 0);
  // The next day, the same minute rolls again.
  c.minute = 914;
  c.epoch += DAY_S;
  CHECK(minute_of_steps(p, c, r) == 1);
  // A list of minutes.
  p.events[0].at_count = 2;
  c.minute = 600;
  CHECK(minute_of_steps(p, c, r) == 1);
  // No clock: no scheduled roll.
  Context unsynced = c;
  unsynced.clock = false;
  unsynced.minute = 914;
  CHECK(minute_of_steps(p, unsynced, r) == 0);
}

static void test_at_rules() {
  const uint16_t at[] = {914, 600};
  Pool p{scheduled("pi", 10, at, 1), event("plain", 10)};
  Context c = awake();
  c.minute = 914;
  c.min_gap_ms = 15 * MIN;
  Rng r{2};
  // Skips the gap and the no-repeat rule.
  CHECK(minute_of_steps(p, c, r) == 1);
  CHECK(p.engine.last() == 0);
  c.minute = 915;
  minute_of_steps(p, c, r);
  c.minute = 914;
  CHECK(minute_of_steps(p, c, r) == 1);
  // Never in a random roll, however long it waited.
  Context random = c;
  random.min_gap_ms = 0;
  p.engine.sample(random, 1000000);
  CHECK(p.states[0].eligible_ms == 0);
  p.states[0].eligible_ms = 1000000000;
  for (int i = 0; i < 50; i++)
    CHECK(p.engine.roll(random, r) != 0);
  // Obeys cooldowns, conditions and the animate gate.
  c.minute = 915;
  minute_of_steps(p, c, r);
  c.minute = 914;
  p.events[0].cooldown_s = DAY_S;
  CHECK(minute_of_steps(p, c, r) == 0);
  p.events[0].cooldown_s = 0;
  p.events[0].weekdays = 0x01;
  CHECK(minute_of_steps(p, c, r) == 0);
  p.events[0].weekdays = 0;
  Context still = c;
  still.animate = false;
  CHECK(minute_of_steps(p, still, r) == 0);
  CHECK(minute_of_steps(p, c, r) == 1);
}

static void test_at_blocked() {
  const uint16_t at[] = {914, 915};
  Pool p{scheduled("pi", 10, at, 1)};
  Context c = awake();
  c.minute = 914;
  Rng r{3};
  // Blocked for one step: a later step in the minute plays.
  CHECK(minute_of_steps(p, c, r, 1) == 1);
  // Blocked for the whole minute: lost for the day.
  c.minute = 915;
  minute_of_steps(p, c, r);
  c.minute = 914;
  CHECK(minute_of_steps(p, c, r, 12) == 0);
  c.minute = 915;
  CHECK(minute_of_steps(p, c, r) == 0);
}

static void test_at_chance() {
  const uint16_t at[] = {914, 915};
  // Liveliness scales the chance: 85% at 150% always plays.
  Pool p{scheduled("pi", 8, at, 1)};
  Context c = awake();
  c.liveliness = 1.5f;
  Context other = c;
  other.minute = 915;
  c.minute = 914;
  Rng r{4};
  int plays = 0;
  for (int day = 0; day < 300; day++) {
    plays += minute_of_steps(p, c, r);
    minute_of_steps(p, other, r);
  }
  CHECK(plays == 300);
  // 40% at 100%, and at 50%.
  for (float lively : {1.0f, 0.5f}) {
    Pool q{scheduled("pi", 5, at, 1)};
    c.liveliness = lively;
    other.liveliness = lively;
    plays = 0;
    for (int day = 0; day < 3000; day++) {
      plays += minute_of_steps(q, c, r);
      minute_of_steps(q, other, r);
    }
    CHECK(near(plays, 3000 * 0.4 * lively));
  }
  // At 0%, even u = 0 misses.
  Pool z{scheduled("pi", 10, at, 1)};
  c.liveliness = 0.0f;
  Rng zero = zero_first();
  CHECK(z.engine.roll_at(c, zero) == -1);
}

static void test_at_draws() {
  const uint16_t at[] = {914, 915, 916};
  Pool p{scheduled("a", 10, at, 1), scheduled("b", 10, at, 1), scheduled("c", 10, at + 1, 1), event("d")};
  p.events[4] = scheduled("ghost", 10, at, 3);  // due at every minute here, but outside the pool
  Context c = awake();
  c.minute = 914;
  Rng r{5};
  Rng before = r;
  int got = p.engine.roll_at(c, r);
  CHECK(got == 0 || got == 1);
  CHECK(draws(before, r) == 3);
  // Latched: the rest of the minute draws nothing.
  before = r;
  CHECK(p.engine.roll_at(c, r) == -1);
  CHECK(draws(before, r) == 0);
  // Nothing due, or blocked: no draws, no latch.
  c.minute = 916;
  before = r;
  CHECK(p.engine.roll_at(c, r) == -1);
  CHECK(draws(before, r) == 0);
  c.minute = 915;
  c.blocked = true;
  CHECK(p.engine.roll_at(c, r) == -1);
  CHECK(draws(before, r) == 0);
  c.blocked = false;
  CHECK(p.engine.roll_at(c, r) == 2);
  CHECK(draws(before, r) == 2);
}

static void test_pick() {
  Pool p{event("often", 10), event("less", 9)};
  Context c = awake();
  Rng r{6};
  int seen[2] = {0, 0};
  for (int i = 0; i < 4000; i++) {
    int got = p.engine.pick(c, r);
    CHECK(got == 0 || got == 1);
    if (got == 0 || got == 1)
      seen[got]++;
  }
  CHECK(near(seen[0], 3000) && near(seen[1], 1000));
  // Even weights, and the rarest frequency.
  Pool q{event("x", 1), event("y", 1)};
  seen[0] = seen[1] = 0;
  for (int i = 0; i < 400; i++) {
    int got = q.engine.pick(c, r);
    CHECK(got == 0 || got == 1);
    if (got == 0 || got == 1)
      seen[got]++;
  }
  CHECK(seen[0] > 150 && seen[1] > 150);
  // Only eligible events, and one draw.
  q.engine.played(0, c);
  Rng before = r;
  CHECK(q.engine.pick(c, r) == 1);
  CHECK(draws(before, r) == 1);
  // Nothing eligible: no draw.
  Context dull = c;
  dull.liveliness = 0.0f;
  before = r;
  CHECK(q.engine.pick(dull, r) == -1);
  CHECK(draws(before, r) == 0);
  // `at:` events are left out.
  const uint16_t at[] = {600};
  Pool s{scheduled("pi", 10, at, 1), event("plain", 1)};
  for (int i = 0; i < 50; i++)
    CHECK(s.engine.pick(c, r) == 1);
}

static void test_find() {
  Pool p{event("lick_paw"), event("sneeze")};
  CHECK(p.engine.find("lick_paw") == 0);
  CHECK(p.engine.find("sneeze") == 1);
  CHECK(p.engine.find("ghost") == -1);
  CHECK(p.engine.find("snore") == -1);
  Engine fresh;
  CHECK(fresh.last() == -1);
}

static void test_next_roll() {
  Pool p{event("a")};
  Context c = awake();
  c.min_gap_ms = 15 * MIN;
  p.engine.played(0, c);
  CHECK(p.engine.next_roll_ms(1000, 2 * MIN, c) == 1000 + 15 * MIN);
  CHECK(p.engine.next_roll_ms(1000, 20 * MIN, c) == 1000 + 20 * MIN);
  // Near the millis wrap.
  CHECK(p.engine.next_roll_ms(0xFFFFFFF0u, 2 * MIN, c) == 15 * MIN - 16);
  // Part of the gap is gone.
  p.engine.sample(c, 10 * MIN);
  CHECK(p.engine.next_roll_ms(1000, 2 * MIN, c) == 1000 + 5 * MIN);
  p.engine.sample(c, 10 * MIN);
  CHECK(p.engine.next_roll_ms(1000, 2 * MIN, c) == 1000 + 2 * MIN);
}

static EventDef spell() {
  EventDef e = event("bath");
  e.kind = Kind::SPELL;
  e.enter = 0;
  e.animation = 1;
  e.exit = 2;
  e.hold_ms = 1000;
  return e;
}

static void test_one_shot() {
  EventDef e = event("lick");
  Playback b;
  CHECK(b.phase() == Phase::IDLE && b.animation() == -1);
  CHECK(!b.tick(100));
  b.start(e, 100, 50, 300, 70);
  CHECK(b.phase() == Phase::ONE_SHOT && b.animation() == 0 && b.once());
  CHECK(!b.tick(399));
  CHECK(b.tick(400));
  CHECK(b.phase() == Phase::IDLE && b.animation() == -1);
  // A say-only one-shot takes no screen time.
  e.animation = -1;
  b.start(e, 100, 50, 300, 70);
  CHECK(b.phase() == Phase::IDLE);
  // Stopped at once.
  e.animation = 0;
  b.start(e, 100, 50, 300, 70);
  b.stop();
  CHECK(b.phase() == Phase::IDLE && !b.tick(1000));
}

static void test_spell() {
  EventDef e = spell();
  Playback b;
  b.start(e, 0xFFFFFFF0u, 100, 300, 200);  // across the millis wrap
  uint32_t t0 = 0xFFFFFFF0u;
  CHECK(b.phase() == Phase::ENTER && b.animation() == 0 && b.once());
  CHECK(!b.tick(t0 + 99));
  CHECK(b.tick(t0 + 150));
  CHECK(b.phase() == Phase::LOOP && b.animation() == 1 && !b.once());
  // The loop's time counts from the end of enter, not from the late tick.
  CHECK(!b.tick(t0 + 1099));
  CHECK(b.tick(t0 + 1100));
  CHECK(b.phase() == Phase::EXIT && b.animation() == 2 && b.once());
  CHECK(!b.tick(t0 + 1299));
  CHECK(b.tick(t0 + 1300));
  CHECK(b.phase() == Phase::IDLE);
  // A late tick passes every phase that ended.
  b.start(e, 0, 100, 300, 200);
  CHECK(b.tick(5000));
  CHECK(b.phase() == Phase::IDLE);
}

static void test_spell_parts() {
  EventDef e = spell();
  Playback b;
  // No enter: straight to the loop. No exit: done after the loop.
  e.enter = -1;
  e.exit = -1;
  b.start(e, 0, 100, 300, 200);
  CHECK(b.phase() == Phase::LOOP);
  CHECK(b.tick(1000));
  CHECK(b.phase() == Phase::IDLE);
  // Animation index 0 is an animation too.
  e = spell();
  e.exit = 0;
  b.start(e, 0, 100, 300, 200);
  CHECK(b.tick(1100) && b.phase() == Phase::EXIT);
  CHECK(!b.tick(1299));
  // Stopped in each phase: no exit plays.
  e = spell();
  for (uint32_t at : {50u, 500u, 1200u}) {
    b.start(e, 0, 100, 300, 200);
    b.tick(at);
    CHECK(b.phase() != Phase::IDLE);
    b.stop();
    CHECK(b.phase() == Phase::IDLE && b.animation() == -1);
  }
  // A one-shot after a spell ends after its one pass.
  b.start(event("lick"), 0, 100, 300, 200);
  CHECK(b.tick(300) && b.phase() == Phase::IDLE);
}

int main() {
  test_tables();
  test_rng();
  test_dates();
  test_times();
  test_weekdays();
  test_moods();
  test_clock();
  test_cooldown();
  test_gates();
  test_gap_and_repeat();
  test_alone_repeats();
  test_eligible_time();
  test_roll_draws();
  test_roll_hits();
  test_rates();
  test_at_once_per_minute();
  test_at_rules();
  test_at_blocked();
  test_at_chance();
  test_at_draws();
  test_pick();
  test_find();
  test_next_roll();
  test_one_shot();
  test_spell();
  test_spell_parts();
  if (failures == 0)
    std::printf("ok\n");
  return failures == 0 ? 0 : 1;
}
