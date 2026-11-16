// Host test of the hub's plain C++ parts: press, double and hold timing,
// taps, swipes and strokes on a touch screen (gesture.h) and what state
// shows (state_machine.h).
//
//   c++ -std=c++17 -Wall -Wextra -I components/daruma \
//       tests/test_input.cpp -o /tmp/test_input && /tmp/test_input

#define DARUMA_STATE_LIST                                \
  X(NEUTRAL, "neutral", MOOD, -1, 0, false)             \
  X(HAPPY, "happy", MOOD, 0, 0, false)                  \
  X(SLEEPING, "sleeping", MOOD, 0, 0, false)            \
  X(LISTENING, "listening", ACTIVITY, 0, 0, false)      \
  X(FOCUS, "focus", ACTIVITY, 0, 0, false)              \
  X(PETTED, "petted", REACTION, 1, 2000, false)

#include <cstdio>
#include <cstdlib>
#include <vector>

#include "gesture.h"
#include "state_machine.h"

using namespace Daruma;

static int failures = 0;

#define CHECK(cond)                                                \
  do {                                                             \
    if (!(cond)) {                                                 \
      std::printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond);  \
      failures++;                                                  \
    }                                                              \
  } while (0)

static const uint16_t NOTHING = 0;
static const uint16_t DOUBLE = gesture_bit(Gesture::DOUBLE);
static const uint16_t HOLD = gesture_bit(Gesture::HOLD);
static const uint16_t LONG = gesture_bit(Gesture::LONG_HOLD);

// Runs ticks every 10 ms from `from` to `to`; returns the first gesture.
static Gesture ticks(PressRecognizer &r, uint32_t from, uint32_t to, uint16_t bound, uint32_t *at = nullptr) {
  for (uint32_t t = from; t <= to; t += 10) {
    const Gesture g = r.tick(t, bound);
    if (g != Gesture::NONE) {
      if (at != nullptr)
        *at = t;
      return g;
    }
  }
  return Gesture::NONE;
}

static void press_without_double_or_hold_fires_on_down() {
  PressRecognizer r;
  CHECK(r.down(1000, NOTHING) == Gesture::PRESS);
  CHECK(r.up(1080, NOTHING) == Gesture::NONE);
  CHECK(ticks(r, 1080, 2000, NOTHING) == Gesture::NONE);
  // A long press with nothing bound for it is still just the one press.
  CHECK(r.down(3000, NOTHING) == Gesture::PRESS);
  CHECK(ticks(r, 3000, 6000, NOTHING) == Gesture::NONE);
  CHECK(r.up(6000, NOTHING) == Gesture::NONE);
}

static void hold_bound_makes_press_fire_on_release() {
  PressRecognizer r;
  r.set_timing(PressTiming{300, 1500, 3000});
  CHECK(r.down(0, HOLD) == Gesture::NONE);
  CHECK(r.up(200, HOLD) == Gesture::PRESS);
  // Held: HOLD fires at hold time, while still held; release adds nothing.
  CHECK(r.down(1000, HOLD) == Gesture::NONE);
  uint32_t at = 0;
  CHECK(ticks(r, 1000, 4000, HOLD, &at) == Gesture::HOLD);
  CHECK(at == 2500);
  CHECK(r.up(3000, HOLD) == Gesture::NONE);
}

static void double_bound_waits_for_a_second_press() {
  PressRecognizer r;
  // Two quick presses: DOUBLE on the second press-down, nothing else.
  CHECK(r.down(0, DOUBLE) == Gesture::NONE);
  CHECK(r.up(80, DOUBLE) == Gesture::NONE);
  CHECK(ticks(r, 80, 200, DOUBLE) == Gesture::NONE);
  CHECK(r.down(200, DOUBLE) == Gesture::DOUBLE);
  CHECK(r.up(260, DOUBLE) == Gesture::NONE);
  CHECK(ticks(r, 260, 1000, DOUBLE) == Gesture::NONE);
  // One press: PRESS once the double window is over.
  CHECK(r.down(2000, DOUBLE) == Gesture::NONE);
  CHECK(r.up(2080, DOUBLE) == Gesture::NONE);
  uint32_t at = 0;
  CHECK(ticks(r, 2080, 3000, DOUBLE, &at) == Gesture::PRESS);
  CHECK(at == 2380);
  // A second press after the window is a new press, not a double.
  CHECK(r.down(4000, DOUBLE) == Gesture::NONE);
  CHECK(r.up(4050, DOUBLE) == Gesture::NONE);
  CHECK(ticks(r, 4050, 4350, DOUBLE) == Gesture::PRESS);
  CHECK(r.down(4400, DOUBLE) == Gesture::NONE);
}

static void custom_double_window() {
  PressRecognizer r;
  r.set_timing(PressTiming{500, 1000, 3000});
  CHECK(r.down(0, DOUBLE) == Gesture::NONE);
  CHECK(r.up(50, DOUBLE) == Gesture::NONE);
  CHECK(ticks(r, 50, 500, DOUBLE) == Gesture::NONE);
  CHECK(r.down(500, DOUBLE) == Gesture::DOUBLE);
}

static void hold_and_long_hold() {
  PressRecognizer r;  // hold 1 s, long hold 3 s
  // Both bound: HOLD on release between the two, LONG_HOLD at 3 s.
  CHECK(r.down(0, HOLD | LONG) == Gesture::NONE);
  CHECK(ticks(r, 0, 1800, HOLD | LONG) == Gesture::NONE);
  CHECK(r.up(1800, HOLD | LONG) == Gesture::HOLD);
  CHECK(r.down(5000, HOLD | LONG) == Gesture::NONE);
  uint32_t at = 0;
  CHECK(ticks(r, 5000, 9000, HOLD | LONG, &at) == Gesture::LONG_HOLD);
  CHECK(at == 8000);
  CHECK(r.up(8500, HOLD | LONG) == Gesture::NONE);
  // Only the long hold bound: a 2 s press fires nothing.
  CHECK(r.down(10000, LONG) == Gesture::NONE);
  CHECK(r.up(12000, LONG) == Gesture::NONE);
}

static void double_and_hold_bound() {
  PressRecognizer r;
  CHECK(r.down(0, DOUBLE | HOLD) == Gesture::NONE);
  CHECK(ticks(r, 0, 1200, DOUBLE | HOLD) == Gesture::HOLD);
  CHECK(r.up(1300, DOUBLE | HOLD) == Gesture::NONE);
  CHECK(ticks(r, 1300, 2000, DOUBLE | HOLD) == Gesture::NONE);  // No stray press after a hold.
  CHECK(r.down(3000, DOUBLE | HOLD) == Gesture::NONE);
  CHECK(r.up(3100, DOUBLE | HOLD) == Gesture::NONE);
  CHECK(ticks(r, 3100, 3500, DOUBLE | HOLD) == Gesture::PRESS);
}

static void touch_taps_wait_for_lift_off() {
  PressRecognizer r(Gesture::TAP, true);
  CHECK(r.down(0, NOTHING) == Gesture::NONE);
  CHECK(r.up(120, NOTHING) == Gesture::TAP);  // At once at lift-off.
  // A swipe cancels the tap.
  CHECK(r.down(1000, NOTHING) == Gesture::NONE);
  r.cancel();
  CHECK(r.up(1200, NOTHING) == Gesture::NONE);
  CHECK(ticks(r, 1200, 2000, NOTHING) == Gesture::NONE);
  // A long touch with no hold bound (an open app) is no tap.
  CHECK(r.down(2000, NOTHING) == Gesture::NONE);
  CHECK(r.up(3500, NOTHING) == Gesture::NONE);
  // Double tap bound: the single tap waits for the window.
  CHECK(r.down(3000, DOUBLE) == Gesture::NONE);
  CHECK(r.up(3100, DOUBLE) == Gesture::NONE);
  CHECK(ticks(r, 3100, 3500, DOUBLE) == Gesture::TAP);
}

// Moves the finger from (x0, y0) to (x1, y1) in `steps` samples.
static void slide(TouchTracker &t, int x0, int y0, int x1, int y1, int steps) {
  for (int i = 1; i <= steps; i++)
    t.move(x0 + (x1 - x0) * i / steps, y0 + (y1 - y0) * i / steps);
}

static void touch_taps_swipes_and_strokes() {
  TouchTracker t;
  // Still, or jitter inside the slop: a tap (NONE, not moved).
  t.start(0, 100, 100);
  t.move(103, 98);
  CHECK(t.end(80) == Gesture::NONE && !t.moved());
  CHECK(t.track().travel_x == 3 && t.track().travel_y == 2);
  CHECK(t.track().x == 103 && t.track().up_ms == 80);
  CHECK(t.track().after_drag_ms == TouchTrack::NO_DRAG);
  // Past the slop: move() says so once, and the touch is no tap.
  t.start(1000, 160, 190);
  CHECK(!t.move(160, 175));
  CHECK(t.move(160, 160));
  CHECK(!t.move(160, 130));
  slide(t, 160, 130, 160, 90, 4);
  CHECK(t.moved() && t.end(1200) == Gesture::SWIPE_UP);
  // Out and back past the slop: no tap, though it ends where it began.
  t.start(1300, 100, 100);
  slide(t, 100, 100, 100, 125, 3);
  slide(t, 100, 125, 100, 100, 3);
  CHECK(t.end(1400) == Gesture::NONE && t.moved());
  CHECK(t.track().travel_y == 25);
  // The next touch knows how long ago the last drag ended.
  t.start(1550, 50, 50);
  CHECK(t.track().after_drag_ms == 150);
  t.end(1600);
  t.start(2000, 50, 50);
  CHECK(t.track().after_drag_ms == 600);  // Taps in between do not count.
  // Sideways and down.
  slide(t, 50, 50, 200, 60, 8);
  CHECK(t.end(2200) == Gesture::SWIPE_RIGHT);
  t.start(3000, 160, 60);
  slide(t, 160, 60, 165, 160, 8);
  CHECK(t.end(3200) == Gesture::SWIPE_DOWN);
  // Too slow: a drag, no swipe.
  t.start(4000, 160, 60);
  slide(t, 160, 60, 160, 160, 20);
  CHECK(t.end(4800) == Gesture::NONE && t.moved());
  // Diagonal: neither.
  t.start(5000, 100, 100);
  slide(t, 100, 100, 180, 180, 6);
  CHECK(t.end(5150) == Gesture::NONE);
  // Back and forth: a stroke (petting), however long it takes.
  t.start(6000, 130, 100);
  for (int leg = 0; leg < 5; leg++)
    slide(t, leg % 2 ? 190 : 130, 100, leg % 2 ? 130 : 190, 100, 10);
  CHECK(t.end(7000) == Gesture::STROKE);
  // Samples with no touch down are ignored.
  CHECK(!t.move(10, 10) && t.end(7100) == Gesture::NONE);
}

struct FakePoint {
  int id;
  int x;
  bool down;
};

static void follows_one_finger() {
  auto on_glass = [](const FakePoint &p) { return p.down; };
  int id = 0;
  std::vector<FakePoint> points = {{0, 10, true}};
  CHECK(follow_finger(points, &id, on_glass)->x == 10);
  // The screen lost the finger and found it again under a new id; the old
  // one stays in the list, lifted. Follow the new one.
  points = {{0, 10, false}, {1, 60, true}};
  const FakePoint *p = follow_finger(points, &id, on_glass);
  CHECK(p != nullptr && p->x == 60 && id == 1);
  // A second finger does not take over.
  points = {{0, 5, true}, {1, 70, true}};
  CHECK(follow_finger(points, &id, on_glass)->x == 70);
  // All lifted: nothing.
  points = {{0, 5, false}, {1, 70, false}};
  CHECK(follow_finger(points, &id, on_glass) == nullptr);
}

static void state_order() {
  StateMachine m;
  m.set_mood(StateId::HAPPY);
  CHECK(m.current(0) == StateId::HAPPY);
  // Activities: top of the stack wins over the mood.
  CHECK(m.set_activity("pomodoro", StateId::FOCUS));
  CHECK(m.current(0) == StateId::FOCUS);
  CHECK(m.set_activity("voice", StateId::LISTENING));
  CHECK(m.current(0) == StateId::LISTENING);
  // A reaction wins over both, for its time.
  m.react(StateId::PETTED, 100, 2000);
  CHECK(m.current(500) == StateId::PETTED);
  CHECK(m.current(2100) == StateId::LISTENING);
  // Clearing the top shows the one under it; owners hold one each.
  CHECK(m.clear_activity("voice"));
  CHECK(m.current(3000) == StateId::FOCUS);
  CHECK(!m.set_activity("pomodoro", StateId::FOCUS));
  StateId mine;
  CHECK(m.activity_of("pomodoro", &mine) && mine == StateId::FOCUS);
  CHECK(!m.activity_of("voice", &mine));
  CHECK(m.clear_activity("pomodoro"));
  CHECK(m.current(3000) == StateId::HAPPY);
  CHECK(!m.clear_activity("pomodoro"));
  // A zero-length reaction is sound only.
  m.react(StateId::PETTED, 4000, 0);
  CHECK(m.current(4000) == StateId::HAPPY);
}

static void state_table() {
  CHECK(state_count() == 6);
  CHECK(state_info(StateId::PETTED).kind == StateKind::REACTION);
  CHECK(state_info(StateId::PETTED).duration_ms == 2000);
  StateId found;
  CHECK(state_by_name("Sleeping", &found) && found == StateId::SLEEPING);
  CHECK(!state_by_name("sleep", &found));
}

// An activity under another still counts as held (prompts wait during focus,
// even while a prompt's own activity is on top).
static void held_activities() {
  StateMachine m;
  CHECK(!m.holds(StateId::FOCUS));
  m.set_activity("pomodoro", StateId::FOCUS);
  m.set_activity("prompts", StateId::LISTENING);
  CHECK(m.holds(StateId::FOCUS));
  CHECK(m.holds(StateId::LISTENING));
  m.clear_activity("pomodoro");
  CHECK(!m.holds(StateId::FOCUS));
}

// What is on under a reaction: the top activity, which a persona uses to keep
// that activity's props in the reaction's look.
static void activity_under_a_reaction() {
  StateMachine m;
  StateId top = StateId::NEUTRAL;
  CHECK(!m.top_activity(&top));
  m.set_activity("pomodoro", StateId::FOCUS);
  m.react(StateId::PETTED, 0, 2000);
  CHECK(m.current(100) == StateId::PETTED);
  CHECK(m.top_activity(&top) && top == StateId::FOCUS);
  m.set_activity("voice", StateId::LISTENING);
  CHECK(m.top_activity(&top) && top == StateId::LISTENING);
  m.clear_activity("voice");
  m.clear_activity("pomodoro");
  CHECK(!m.top_activity(&top));
}

int main() {
  press_without_double_or_hold_fires_on_down();
  hold_bound_makes_press_fire_on_release();
  double_bound_waits_for_a_second_press();
  custom_double_window();
  hold_and_long_hold();
  double_and_hold_bound();
  touch_taps_wait_for_lift_off();
  touch_taps_swipes_and_strokes();
  follows_one_finger();
  state_order();
  state_table();
  held_activities();
  activity_under_a_reaction();
  if (failures == 0)
    std::printf("All input and state tests passed\n");
  return failures == 0 ? EXIT_SUCCESS : EXIT_FAILURE;
}
