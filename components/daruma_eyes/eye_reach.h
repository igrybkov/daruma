#pragma once

// Where the eyes persona's looks reach on screen, and how high each look
// sits so it keeps clear of the bottom corners: the pomodoro plaque on the
// left, the temperature badge on the right. Plain C++ with no ESPHome
// includes, so the host test checks the same numbers the persona draws with
// (tests/test_layout.cpp).
//
// The eyes center in layout.upper. Every look first rises as far as the
// resting Neutral eyes need, so all looks keep their offsets to each
// other. A look that still reaches a corner (Sad, Sleepy, the thinking
// glance, the focus look) rises further, just enough. Only a corner the
// eyes meet across counts, so on wide screens nothing moves.
//
// The corners checked are the tallest plaques of a goal up to 9 (three
// rows of tomatoes, two rows of timer dots) and the badge. A bigger goal
// stacks a fourth and fifth row of tomatoes, which may meet the eyes.

#include <algorithm>
#include <cmath>
#include <cstdint>

#include "../daruma/plaque.h"

namespace Daruma {
namespace Eyes {

enum Mood : uint8_t { NEUTRAL, HAPPY, SAD, LOVED, SCARED, SLEEPY, SLEEPING, MOOD_COUNT };

// A mood's eyes, shifted (design pixels) and maybe half closed.
struct Look {
  uint8_t mood;
  int8_t dx, dy;
  float lid;  // 1 = open; less is half closed.
};

// One per entry of LOOKS in __init__.py, in the same order.
static const Look LOOKS[] = {
    {NEUTRAL, 0, 0, 1.0f},   {HAPPY, 0, 0, 1.0f},  {SAD, 0, 0, 1.0f},     {LOVED, 0, 0, 1.0f},
    {SCARED, 0, 0, 1.0f},    {SLEEPY, 0, 0, 1.0f}, {SLEEPING, 0, 0, 1.0f},
    {NEUTRAL, 0, -15, 1.0f},  // listening: eyes up.
    {NEUTRAL, 30, 10, 1.0f},  // thinking: a glance aside while HA works.
    {NEUTRAL, 0, 30, 0.5f},   // focus: eyes down and narrowed, as if reading.
};
static const int LOOK_COUNT = sizeof(LOOKS) / sizeof(LOOKS[0]);

// look_around() glances up to this far to either side (design pixels).
static const int GLANCE = 40;
// The tallest tomato plaque the eyes keep clear of: three rows of three.
static const int CLEAR_SLOTS = 9;

// What a mood paints, in design pixels around the eyes' center, before a
// look's offsets: both eyes span x l..r and y cy - half .. cy + half; a
// look's lid narrows them around cy (only Neutral looks use one). The
// wink clears a box over the right eye (wink_t == wink_b: no wink).
// Matches each state's render() and EyesPersona::draw_wink_().
struct MoodReach {
  int16_t l, r, cy, half;
  int16_t wink_l, wink_r, wink_t, wink_b;
  bool moves_x, moves_y;  // The mood follows the glance / the look's offset.
};
static const MoodReach MOODS[MOOD_COUNT] = {
    {-80, 80, 0, 40, 16, 84, -44, 44, true, true},     // NEUTRAL: 60x80 eyes.
    {-80, 80, -50, 10, 16, 84, -68, -20, true, true},  // HAPPY: arcs 20 high, 40 up.
    {-80, 80, 40, 30, 16, 84, 6, 74, true, true},      // SAD: 60x60 eyes, 40 down.
    {-80, 80, 0, 30, 0, 0, 0, 0, true, true},          // LOVED: 60 px hearts.
    {-61, 61, 0, 14, 0, 0, 0, 0, true, false},         // SCARED: jittering dots.
    {-80, 80, 10, 40, 0, 0, 0, 0, false, false},       // SLEEPY: lids droop 20.
    {-80, 80, 23, 5, 0, 0, 0, 0, false, false},        // SLEEPING: breathing lines.
};

// A box in design pixels around the eyes' center.
struct Span {
  int l{0}, t{0}, r{0}, b{0};
  bool empty() const { return r <= l || b <= t; }
};

// Where a look can paint over its whole glance: the eyes, and the wink
// (empty when the look has none). A narrowed look does not wink.
inline void look_reach(const Look &look, Span *eyes, Span *wink) {
  const MoodReach &m = MOODS[look.mood < MOOD_COUNT ? (int) look.mood : (int) NEUTRAL];
  const int dx = m.moves_x ? look.dx : 0, dy = m.moves_y ? look.dy : 0;
  const int g = m.moves_x ? GLANCE : 0;
  const int half = (int) std::lround(m.half * std::min(look.lid, 1.0f));
  *eyes = Span{m.l + dx - g, m.cy - half + dy, m.r + dx + g, m.cy + half + dy};
  *wink = look.lid >= 1.0f && m.wink_b > m.wink_t
              ? Span{m.wink_l + dx - g, m.wink_t + dy, m.wink_r + dx + g, m.wink_b + dy}
              : Span{};
}

// A span on screen for eyes centered at (cx, cy).
inline Rect on_screen(const Layout &l, const Span &s, int cx, int cy) {
  if (s.empty())
    return Rect{};
  return Rect{cx + l.px(s.l), cy + l.px(s.t), l.px(s.r) - l.px(s.l), l.px(s.b) - l.px(s.t)};
}

// What the eyes keep clear of: the left corner as the tallest plaque
// covers it (timer font metrics as on the BOX-3), the badge, the info line.
struct Corners {
  Rect rects[3];
};
inline Corners corners(const Layout &l) {
  const TimerPlaque timer = TimerPlaque::compute(l, l.px(14), l.px(16), PLAQUE_MAX_SLOTS);
  const Rect left = TomatoPlaque::compute(l, CLEAR_SLOTS).rect.united(timer.rect).united(timer.pause_tab());
  return Corners{{left, l.badge(), l.info}};
}

// Space kept between the eyes and a corner.
inline int clearance(const Layout &l) { return std::max(l.px(3), 2); }

// How far eyes centered at (cx, cy) must rise for a look to clear every
// corner it meets across (0: it already does).
inline int lift_for(const Layout &l, const Look &look, int cx, int cy) {
  Span eyes, wink;
  look_reach(look, &eyes, &wink);
  const Corners c = corners(l);
  int lift = 0;
  for (const Span &s : {eyes, wink}) {
    const Rect r = on_screen(l, s, cx, cy);
    if (r.empty())
      continue;
    for (const Rect &k : c.rects) {
      if (r.right() <= k.x || r.x >= k.right())
        continue;  // Not across this corner.
      lift = std::max(lift, r.bottom() + clearance(l) - k.y);
    }
  }
  return lift;
}

// The eyes' center for a look: layout.upper's center, risen as the resting
// eyes need, then as this look needs on top.
inline void center(const Layout &l, const Look &look, int *cx, int *cy) {
  *cx = l.upper.cx();
  const int rest = l.upper.cy() - lift_for(l, LOOKS[0], *cx, l.upper.cy());
  *cy = rest - lift_for(l, look, *cx, rest);
}

}  // namespace Eyes
}  // namespace Daruma
