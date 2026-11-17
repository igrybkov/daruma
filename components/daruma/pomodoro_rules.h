#pragma once

// Which pomodoro buttons make sense now. The menu, the actions' own menu
// buttons and the Pomodoro page all ask here, so they never offer a button
// that contradicts what is going on (Break during a focus).
//
//   focus, running or paused   Pause or Resume, Stop, Skip
//   break                      Resume (when paused), Focus, End
//   idle, in the break window  Focus, Custom, Break, Long break
//   idle otherwise             Focus, Custom
//
// The break window: the last focus ended less than the break it earned ago
// (a long break after every Nth pomodoro of the day, else a short one).
// After that you have had your break, or none is due: no Break buttons.
// A focus starts its break by itself when it ends, so the window shows
// after End or Stop on that break.
//
// Plain C++ with no ESPHome includes, so a host test can check it
// (tests/test_pomodoro_rules.cpp).

#include <cstdint>
#include <vector>

namespace Daruma {
namespace Pomodoro {

enum class Phase : uint8_t { IDLE = 0, FOCUS = 1, SHORT_BREAK = 2, LONG_BREAK = 3 };

enum class Button : uint8_t {
  FOCUS,   // Start a focus of the default length (ends a break first).
  CUSTOM,  // Pick the focus length.
  PAUSE,
  RESUME,
  STOP,   // End a focus early.
  SKIP,   // Jump to the break; the focus does not count.
  BREAK,  // A short break.
  LONG_BREAK,
  END,  // End a break.
};

struct Now {
  Phase phase{Phase::IDLE};
  bool paused{false};
  // Seconds since the last finished focus; negative when none today.
  int32_t since_focus_end{-1};
  // That focus earned a long break (it was the Nth of the day).
  bool earned_long{false};
  int32_t short_break_s{5 * 60};
  int32_t long_break_s{15 * 60};
};

// True after every `every`-th pomodoro of the day.
inline bool earns_long(int done, int every) { return done > 0 && every > 0 && done % every == 0; }

inline bool break_window(const Now &n) {
  if (n.phase != Phase::IDLE || n.since_focus_end < 0)
    return false;
  return n.since_focus_end < (n.earned_long ? n.long_break_s : n.short_break_s);
}

// The buttons for now, in the order a menu shows them.
inline std::vector<Button> buttons(const Now &n) {
  switch (n.phase) {
    case Phase::FOCUS:
      return {n.paused ? Button::RESUME : Button::PAUSE, Button::STOP, Button::SKIP};
    case Phase::SHORT_BREAK:
    case Phase::LONG_BREAK:
      if (n.paused)
        return {Button::RESUME, Button::FOCUS, Button::END};
      return {Button::FOCUS, Button::END};
    default:
      if (break_window(n))
        return {Button::FOCUS, Button::CUSTOM, Button::BREAK, Button::LONG_BREAK};
      return {Button::FOCUS, Button::CUSTOM};
  }
}

inline bool shows(const Now &n, Button b) {
  for (Button x : buttons(n)) {
    if (x == b)
      return true;
  }
  return false;
}

}  // namespace Pomodoro
}  // namespace Daruma
