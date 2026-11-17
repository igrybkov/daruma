#pragma once

// Shared signals: a small typed set every persona may show its own way.
// Modules and HA set them through the Hub; personas only read them.

#include <cstddef>
#include <cstdint>

namespace Daruma {

enum class Sky : uint8_t { CLEAR, CLOUDY, RAIN, SNOW, NIGHT };
enum class DayPart : uint8_t { MORNING, DAY, EVENING, NIGHT };
// Today's goal: not started, started (some work done), or reached.
enum class Goal : uint8_t { NONE, STARTED, DONE };

struct Signals {
  // 0..10: how far along today's or this week's work is (pomodoros, tasks).
  uint8_t progress{0};
  // A progress source is behind its pace. The corgi's plant wilts.
  bool behind{false};
  // 0..10 from HA (a plant sensor, a sleep score), or -1 when unset.
  int8_t wellbeing{-1};
  Sky sky{Sky::CLEAR};
  DayPart day_part{DayPart::DAY};
  // 1 = Sunday .. 7 = Saturday; 0 until the clock is set.
  uint8_t weekday{0};
  // Where today's goal stands. Resets at midnight. The daruma paints its eyes.
  Goal goal{Goal::NONE};
};

// The day part for an hour of the day: morning 5-11, day 12-16, evening
// 17-21, night 22-4.
inline DayPart day_part_for_hour(int hour) {
  if (hour >= 5 && hour < 12)
    return DayPart::MORNING;
  if (hour >= 12 && hour < 17)
    return DayPart::DAY;
  if (hour >= 17 && hour < 22)
    return DayPart::EVENING;
  return DayPart::NIGHT;
}

// Which of `days` weekday entries (Sunday first) a weekday picks: 0 for
// Sunday (1) .. 6 for Saturday (7), or -1 for anything else, such as 0
// before the clock is set. -1 means the plain look, never a day's.
inline int weekday_slot(int weekday, size_t days) {
  if (weekday < 1 || weekday > 7 || (size_t) weekday > days)
    return -1;
  return weekday - 1;
}

}  // namespace Daruma
