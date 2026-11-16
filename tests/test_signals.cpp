// Host test of the clock signals (signals.h): the day part for an hour, and
// which weekday colors a weekday picks.
//
//   c++ -std=c++17 -Wall -Wextra -I components/daruma \
//       tests/test_signals.cpp -o /tmp/test_signals && /tmp/test_signals

#include <cstdio>
#include <initializer_list>

#include "signals.h"

using namespace Daruma;

static int failures = 0;

#define CHECK(cond)                                                \
  do {                                                             \
    if (!(cond)) {                                                 \
      std::printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond);  \
      failures++;                                                  \
    }                                                              \
  } while (0)

static void test_weekday_slot() {
  // Sunday (1) .. Saturday (7) pick their own entry, Sunday first.
  for (int day = 1; day <= 7; day++)
    CHECK(weekday_slot(day, 7) == day - 1);
  // Anything else is the plain look: never Sunday's (white on the corgi's
  // rug), whatever the value.
  for (int day : {0, 8, 9, 255, 256, -1, -7})
    CHECK(weekday_slot(day, 7) == -1);
  // Fewer entries than days: the missing days are plain too.
  CHECK(weekday_slot(3, 3) == 2);
  CHECK(weekday_slot(4, 3) == -1);
  CHECK(weekday_slot(1, 0) == -1);
  // An unset clock (the Signals default) is plain.
  CHECK(weekday_slot(Signals{}.weekday, 7) == -1);
}

static void test_day_part() {
  CHECK(day_part_for_hour(0) == DayPart::NIGHT);
  CHECK(day_part_for_hour(4) == DayPart::NIGHT);
  CHECK(day_part_for_hour(5) == DayPart::MORNING);
  CHECK(day_part_for_hour(11) == DayPart::MORNING);
  CHECK(day_part_for_hour(12) == DayPart::DAY);
  CHECK(day_part_for_hour(16) == DayPart::DAY);
  CHECK(day_part_for_hour(17) == DayPart::EVENING);
  CHECK(day_part_for_hour(20) == DayPart::EVENING);
  CHECK(day_part_for_hour(21) == DayPart::EVENING);
  CHECK(day_part_for_hour(22) == DayPart::NIGHT);
  CHECK(day_part_for_hour(23) == DayPart::NIGHT);
}

int main() {
  test_weekday_slot();
  test_day_part();
  if (failures) {
    std::printf("%d failure(s)\n", failures);
    return 1;
  }
  std::printf("ok\n");
  return 0;
}
