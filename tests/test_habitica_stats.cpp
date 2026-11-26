// Host test of the Habitica stats model (daruma_habitica/habitica.h).
//
//   c++ -std=c++17 -Wall -Wextra -I src tests/test_habitica_stats.cpp \
//       -o /tmp/test_habitica_stats && /tmp/test_habitica_stats

#include <cstdio>
#include <string>

#include "esphome/components/daruma_habitica/habitica.h"

using namespace Daruma;

static int failures = 0;

#define CHECK(cond) \
  do { \
    if (!(cond)) { \
      std::printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond); \
      failures++; \
    } \
  } while (0)

static HabiticaStats hero(float hp, int level) {
  HabiticaStats s;
  s.hp = hp;
  s.level = level;
  return s;
}

static HabiticaStats only_hp(float hp) { return hero(hp, -1); }

static void unknown_by_default() {
  // Every field starts unknown: -1 exactly.
  HabiticaStats s;
  CHECK(s.hp == -1 && s.hp_max == -1 && s.mp == -1 && s.mp_max == -1);
  CHECK(s.xp == -1 && s.xp_next == -1 && s.gold == -1);
  CHECK(s.level == -1 && s.resting == -1 && s.cls.empty());
  HabiticaReactions r;
  CHECK(!r.level_up && !r.hurt && !r.activity_changed && r.activity == HabiticaActivity::NONE);
}

static void numbers_from_states() {
  CHECK(habitica_number("47.3") == 47.3f);
  CHECK(habitica_number("0") == 0.0f);
  CHECK(habitica_number("12") == 12.0f);
  for (const char *bad : {"", "unknown", "unavailable", "12a", "-3", "inf", "nan"})
    CHECK(habitica_number(bad) == -1.0f);
  CHECK(habitica_known(0.0f));
  CHECK(!habitica_known(-1.0f));

  CHECK(habitica_class("warrior") == "warrior");
  CHECK(habitica_class("rogue") == "rogue");
  CHECK(habitica_class("wizard") == "wizard");
  CHECK(habitica_class("healer") == "healer");
  CHECK(habitica_class("unknown").empty());
  CHECK(habitica_class("Warrior").empty());
}

static void fields_by_name() {
  HabiticaStats s;
  CHECK(habitica_set_field(s, "health", "45.5") && s.hp == 45.5f);
  CHECK(habitica_set_field(s, "max_health", "55") && s.hp_max == 55.0f);
  CHECK(habitica_set_field(s, "mana", "20.25") && s.mp == 20.25f);
  CHECK(habitica_set_field(s, "max_mana", "64") && s.mp_max == 64.0f);
  CHECK(habitica_set_field(s, "experience", "120") && s.xp == 120.0f);
  CHECK(habitica_set_field(s, "next_level", "380") && s.xp_next == 380.0f);
  CHECK(habitica_set_field(s, "gold", "93.71") && s.gold == 93.71f);
  CHECK(habitica_set_field(s, "level", "12") && s.level == 12);
  CHECK(habitica_set_field(s, "class", "healer") && s.cls == "healer");
  CHECK(habitica_set_field(s, "inn", "on") && s.resting == 1);
  CHECK(habitica_set_field(s, "inn", "off") && s.resting == 0);
  CHECK(!habitica_set_field(s, "strength", "3"));
}

static void unknown_states_unset_fields() {
  HabiticaStats s;
  s.resting = 1;
  s.level = 12;
  s.cls = "healer";
  s.hp = 40;
  // An unknown state makes the field unknown.
  CHECK(habitica_set_field(s, "inn", "unavailable") && s.resting == -1);
  CHECK(habitica_set_field(s, "level", "unknown") && s.level == -1);
  CHECK(habitica_set_field(s, "class", "unavailable") && s.cls.empty());
  CHECK(habitica_set_field(s, "health", "unavailable") && s.hp == -1.0f);
}

static void merge_keeps_what_news_lacks() {
  HabiticaStats base;
  base.hp = 30;
  base.hp_max = 50;
  base.mp = 10;
  base.mp_max = 40;
  base.xp = 100;
  base.xp_next = 200;
  base.gold = 7;
  base.level = 3;
  base.cls = "rogue";
  base.resting = 1;
  // Nothing known: nothing changes.
  HabiticaStats same = habitica_merge(base, HabiticaStats{});
  CHECK(same.hp == 30 && same.hp_max == 50 && same.mp == 10 && same.mp_max == 40);
  CHECK(same.xp == 100 && same.xp_next == 200 && same.gold == 7 && same.level == 3);
  CHECK(same.cls == "rogue" && same.resting == 1);
  // Every field known, zeros included: every field changes.
  HabiticaStats news;
  news.hp = 0;
  news.hp_max = 0;
  news.mp = 0;
  news.mp_max = 0;
  news.xp = 0;
  news.xp_next = 0;
  news.gold = 0;
  news.level = 0;
  news.cls = "wizard";
  news.resting = 0;
  HabiticaStats all = habitica_merge(base, news);
  CHECK(all.hp == 0 && all.hp_max == 0 && all.mp == 0 && all.mp_max == 0);
  CHECK(all.xp == 0 && all.xp_next == 0 && all.gold == 0 && all.level == 0);
  CHECK(all.cls == "wizard" && all.resting == 0);
}

static void shown_and_bars() {
  CHECK(habitica_shown(47.3f) == "47");
  CHECK(habitica_shown(47.3f, true) == "48");
  CHECK(habitica_shown(0.4f, true) == "1");
  CHECK(habitica_shown(0.0f, true) == "0");
  CHECK(habitica_shown(-1.0f).empty());

  CHECK(habitica_fill(25, 50, 100) == 50);
  CHECK(habitica_fill(50, 50, 100) == 100);
  CHECK(habitica_fill(80, 50, 100) == 100);  // More than the max: full.
  CHECK(habitica_fill(0, 50, 100) == 0);
  CHECK(habitica_fill(1, 3, 100) == 33);
  CHECK(habitica_fill(2, 3, 100) == 67);  // Rounded, not cut.
  CHECK(habitica_fill(-1, 50, 100) == 0);
  CHECK(habitica_fill(25, -1, 100) == 0);
  CHECK(habitica_fill(25, 0, 100) == 0);
  CHECK(habitica_fill(0.25f, 0.5f, 100) == 50);  // A max under 1.
}

static void split_in_two() {
  CHECK(habitica_split("Buy a health potion for 25 gold?") == 19);  // "...potion" | "for..."
  CHECK(habitica_split("one two") == 3);
  // Two spaces as near the middle: the first.
  CHECK(habitica_split("abc d ef") == 3);
  CHECK(habitica_split("abcdef") == std::string::npos);
  CHECK(habitica_split("") == std::string::npos);
  CHECK(habitica_split("a bcdefgh") == 1);
  CHECK(habitica_split("abcdefg h") == 7);
  CHECK(habitica_split(" abc") == 0);
}

static void first_values_play_nothing() {
  HabiticaModel m;
  HabiticaReactions r = m.apply(hero(50, 12));
  CHECK(!r.level_up && !r.hurt && !r.activity_changed);
  CHECK(m.stats().hp == 50 && m.stats().level == 12);
  // One field at a time, as HA sends them: still nothing.
  HabiticaModel one;
  r = one.apply(hero(-1, 12));
  CHECK(!r.level_up && !r.hurt && !r.activity_changed);
  r = one.apply(only_hp(20));
  CHECK(!r.level_up && !r.hurt);
}

static void level_up() {
  HabiticaModel m;
  m.apply(hero(50, 12));
  HabiticaReactions r = m.apply(hero(50, 13));
  CHECK(r.level_up && !r.hurt);
  // The same level again: nothing.
  r = m.apply(hero(50, 13));
  CHECK(!r.level_up);
  // A level lost (fainting costs one): nothing.
  r = m.apply(hero(50, 12));
  CHECK(!r.level_up);
  // A set without the level leaves it alone.
  r = m.apply(only_hp(50));
  CHECK(!r.level_up && m.stats().level == 12);
  // Any known level counts, the lowest too.
  HabiticaModel low;
  low.apply(hero(50, 0));
  CHECK(low.apply(hero(50, 1)).level_up);
}

static void hurt_by_threshold() {
  // The default threshold: 1 HP.
  HabiticaModel m;
  m.apply(only_hp(50));
  CHECK(m.apply(only_hp(49)).hurt);
  CHECK(!m.apply(only_hp(48.1f)).hurt);  // 0.9 lost.
  CHECK(!m.apply(only_hp(50)).hurt);     // HP back up.
  // Fractions: 47.3 to 46.3 is 1 HP, though floats may say 0.99999.
  m.apply(only_hp(47.3f));
  CHECK(m.apply(only_hp(46.3f)).hurt);

  HabiticaModel big;
  big.set_hurt_threshold(5);
  big.apply(only_hp(50));
  CHECK(!big.apply(only_hp(45.1f)).hurt);
  CHECK(big.apply(only_hp(40.1f)).hurt);  // Exactly 5.
}

static void a_reply_then_the_same_push_plays_once() {
  HabiticaModel m;
  m.apply(hero(50, 12));
  // The score reply: level up and HP down.
  HabiticaStats reply = hero(42, 13);
  reply.gold = 120;
  HabiticaReactions r = m.apply(reply);
  CHECK(r.level_up && r.hurt);
  // The sensors follow, one at a time, with the same numbers.
  r = m.apply(hero(-1, 13));
  CHECK(!r.level_up && !r.hurt);
  r = m.apply(only_hp(42));
  CHECK(!r.level_up && !r.hurt);
}

static void unknown_values() {
  HabiticaModel m;
  m.apply(hero(50, 12));
  // HA says "unavailable": no news, nothing shown changes.
  HabiticaReactions r = m.apply(hero(-1, -1));
  CHECK(!r.level_up && !r.hurt);
  CHECK(m.stats().hp == 50 && m.stats().level == 12);
}

static void reconnect_plays_nothing() {
  HabiticaModel m;
  m.apply(hero(50, 12));
  m.forget();
  // HA sends every state again on connect; HP fell and a level came while
  // the device was away. Shown, not played.
  HabiticaReactions r = m.apply(hero(30, 13));
  CHECK(!r.level_up && !r.hurt);
  CHECK(m.stats().hp == 30 && m.stats().level == 13);
  // From now on it plays again.
  CHECK(m.apply(hero(20, 14)).level_up);
}

static void restored_numbers_are_shown_not_compared() {
  HabiticaModel m;
  HabiticaStats saved = hero(50, 12);
  saved.hp_max = 50;
  m.restore(saved);
  CHECK(m.stats().hp == 50 && m.stats().level == 12 && m.stats().hp_max == 50);
  // HA's first numbers after the boot differ: nothing plays.
  HabiticaReactions r = m.apply(hero(30, 13));
  CHECK(!r.level_up && !r.hurt);
  CHECK(m.stats().hp_max == 50);
  // Restored at 0 HP: fainted at once.
  HabiticaModel down;
  down.restore(only_hp(0));
  CHECK(down.activity() == HabiticaActivity::FAINTED);
}

static void fainted_and_resting() {
  HabiticaModel m;
  CHECK(m.activity() == HabiticaActivity::NONE);
  // The first values set the activity: it shows what is, not a change.
  HabiticaReactions r = m.apply(only_hp(0));
  CHECK(r.activity_changed && r.activity == HabiticaActivity::FAINTED);
  CHECK(m.activity() == HabiticaActivity::FAINTED);
  // Again: no change.
  r = m.apply(only_hp(0));
  CHECK(!r.activity_changed && r.activity == HabiticaActivity::FAINTED);
  // Revived: cleared.
  r = m.apply(only_hp(50));
  CHECK(r.activity_changed && r.activity == HabiticaActivity::NONE);
  // Just above 0 is alive.
  r = m.apply(only_hp(0.2f));
  CHECK(!r.activity_changed && r.activity == HabiticaActivity::NONE);
  r = m.apply(only_hp(0.04f));
  CHECK(!r.activity_changed && r.activity == HabiticaActivity::NONE);

  // The inn.
  HabiticaStats inn;
  inn.resting = 1;
  r = m.apply(inn);
  CHECK(r.activity_changed && r.activity == HabiticaActivity::RESTING);
  // Fainted in the inn: fainted wins.
  r = m.apply(only_hp(0));
  CHECK(r.activity_changed && r.activity == HabiticaActivity::FAINTED);
  r = m.apply(only_hp(50));
  CHECK(r.activity_changed && r.activity == HabiticaActivity::RESTING);
  inn.resting = 0;
  r = m.apply(inn);
  CHECK(r.activity_changed && r.activity == HabiticaActivity::NONE);
  // A drop to 0 plays hurt and holds fainted.
  r = m.apply(only_hp(0));
  CHECK(r.hurt && r.activity == HabiticaActivity::FAINTED);
}

int main() {
  unknown_by_default();
  numbers_from_states();
  fields_by_name();
  unknown_states_unset_fields();
  merge_keeps_what_news_lacks();
  shown_and_bars();
  split_in_two();
  first_values_play_nothing();
  level_up();
  hurt_by_threshold();
  a_reply_then_the_same_push_plays_once();
  unknown_values();
  reconnect_plays_nothing();
  restored_numbers_are_shown_not_compared();
  fainted_and_resting();
  if (failures == 0)
    std::printf("test_habitica_stats: all passed\n");
  return failures == 0 ? 0 : 1;
}
