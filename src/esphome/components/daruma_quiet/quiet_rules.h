#pragma once

// The rules of quiet hours and the screen level. Plain C++, host-tested
// (tests/test_quiet.cpp).

#include <algorithm>
#include <cstdint>

namespace Daruma {
namespace Quiet {

// Minutes since midnight, 0 .. 1439.
inline int minute_of_day(int hour, int minute) { return hour * 60 + minute; }

// True when `now` lies in [start, end). The range may wrap past midnight
// (22:00 to 07:00). start == end means no quiet hours.
inline bool in_range(int now, int start, int end) {
  if (start == end)
    return false;
  if (start < end)
    return now >= start && now < end;
  return now >= start || now < end;
}

enum class Level { NORMAL, IDLE, QUIET };

struct ScreenNow {
  bool quiet{false};         // Inside quiet hours, with a valid clock.
  bool card_open{false};     // A prompt is on screen.
  uint32_t idle_ms{0};       // Since the last input, prompt or message.
  uint32_t wake_ms{0};       // How long a wake lasts in quiet hours.
  uint32_t dim_after_ms{0};  // 0: never dims when idle.
};

// What the screen should be now. A card on screen keeps it bright. In
// quiet hours an input wakes it for wake_ms; idle dimming then still
// applies.
inline Level level(const ScreenNow &n) {
  if (n.card_open)
    return Level::NORMAL;
  if (n.quiet && n.idle_ms >= n.wake_ms)
    return Level::QUIET;
  if (n.dim_after_ms > 0 && n.idle_ms >= n.dim_after_ms)
    return Level::IDLE;
  return Level::NORMAL;
}

// The brightness for a level, never above the person's own (`base`; 0 when
// they turned the screen off).
inline float brightness(Level l, float base, float quiet, float idle) {
  switch (l) {
    case Level::QUIET:
      return std::min(base, quiet);
    case Level::IDLE:
      return std::min(base, idle);
    default:
      return base;
  }
}

}  // namespace Quiet
}  // namespace Daruma
