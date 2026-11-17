// Host test of which pomodoro buttons show when (daruma/pomodoro_rules.h).
//
//   c++ -std=c++17 -Wall -Wextra -I components/daruma \
//       tests/test_pomodoro_rules.cpp -o /tmp/test_pomodoro_rules && /tmp/test_pomodoro_rules

#include <cstdio>
#include <vector>

#include "pomodoro_rules.h"

using namespace Daruma::Pomodoro;

static int failures = 0;

#define CHECK(cond) \
  do { \
    if (!(cond)) { \
      std::printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond); \
      failures++; \
    } \
  } while (0)

static bool same(const std::vector<Button> &a, const std::vector<Button> &b) { return a == b; }

static Now idle_after(int32_t seconds, bool long_break = false) {
  Now n;
  n.since_focus_end = seconds;
  n.earned_long = long_break;
  return n;
}

int main() {
  // No focus today: Focus and Custom only.
  {
    Now n;
    CHECK(same(buttons(n), {Button::FOCUS, Button::CUSTOM}));
    CHECK(!shows(n, Button::BREAK));
    CHECK(!shows(n, Button::STOP));
  }
  // A focus, running and paused: no Break, no Focus.
  {
    Now n;
    n.phase = Phase::FOCUS;
    CHECK(same(buttons(n), {Button::PAUSE, Button::STOP, Button::SKIP}));
    n.paused = true;
    CHECK(same(buttons(n), {Button::RESUME, Button::STOP, Button::SKIP}));
    CHECK(!shows(n, Button::BREAK) && !shows(n, Button::LONG_BREAK) && !shows(n, Button::FOCUS));
  }
  // A break: Focus (ends it) and End; Resume first while paused.
  {
    Now n;
    n.phase = Phase::SHORT_BREAK;
    n.since_focus_end = 10;
    CHECK(same(buttons(n), {Button::FOCUS, Button::END}));
    n.phase = Phase::LONG_BREAK;
    n.paused = true;
    CHECK(same(buttons(n), {Button::RESUME, Button::FOCUS, Button::END}));
    CHECK(!shows(n, Button::BREAK) && !shows(n, Button::STOP));
  }
  // Idle inside the break window: both breaks, after Focus and Custom.
  {
    const Now n = idle_after(60);
    CHECK(break_window(n));
    CHECK(same(buttons(n), {Button::FOCUS, Button::CUSTOM, Button::BREAK, Button::LONG_BREAK}));
  }
  // The window is the break the focus earned: 5 min short, 15 min long.
  {
    CHECK(break_window(idle_after(5 * 60 - 1)));
    CHECK(!break_window(idle_after(5 * 60)));
    CHECK(break_window(idle_after(10 * 60, true)));
    CHECK(!break_window(idle_after(15 * 60, true)));
    Now n = idle_after(5 * 60);
    CHECK(same(buttons(n), {Button::FOCUS, Button::CUSTOM}));
    // Other settings move it.
    n.short_break_s = 10 * 60;
    CHECK(break_window(n));
  }
  // Never outside idle, and never without a finished focus.
  {
    Now n = idle_after(10);
    n.phase = Phase::FOCUS;
    CHECK(!break_window(n));
    CHECK(!break_window(idle_after(-1)));
  }
  // The long break comes after every Nth pomodoro.
  {
    CHECK(!earns_long(0, 4));
    CHECK(!earns_long(3, 4));
    CHECK(earns_long(4, 4));
    CHECK(!earns_long(5, 4));
    CHECK(earns_long(8, 4));
    CHECK(!earns_long(4, 0));
  }
  if (failures == 0)
    std::printf("pomodoro rules: all passed\n");
  return failures == 0 ? 0 : 1;
}
