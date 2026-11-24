// Host test of quiet hours and the screen level (daruma_quiet/quiet_rules.h),
// and of the messages that wait while cards are held (daruma/card_queue.h).
//
//   uv run pytest tests/test_quiet.cpp   (pytest builds and runs it: tests/conftest.py)

#include <cstdio>
#include <string>

#include "card_queue.h"
#include "sound_gate.h"
#include "esphome/components/daruma_quiet/quiet_rules.h"

using namespace Daruma;
using Quiet::Level;

static int failures = 0;

#define CHECK(cond) \
  do { \
    if (!(cond)) { \
      std::printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond); \
      failures++; \
    } \
  } while (0)

static int at(int hour, int minute) { return Quiet::minute_of_day(hour, minute); }

static void ranges() {
  // Overnight: 22:00 to 07:00.
  const int start = at(22, 0), end = at(7, 0);
  CHECK(Quiet::in_range(at(22, 0), start, end));
  CHECK(Quiet::in_range(at(23, 59), start, end));
  CHECK(Quiet::in_range(at(0, 0), start, end));
  CHECK(Quiet::in_range(at(6, 59), start, end));
  CHECK(!Quiet::in_range(at(7, 0), start, end));
  CHECK(!Quiet::in_range(at(12, 0), start, end));
  CHECK(!Quiet::in_range(at(21, 59), start, end));
  // Inside one day: 13:00 to 14:30.
  CHECK(Quiet::in_range(at(13, 0), at(13, 0), at(14, 30)));
  CHECK(Quiet::in_range(at(14, 29), at(13, 0), at(14, 30)));
  CHECK(!Quiet::in_range(at(14, 30), at(13, 0), at(14, 30)));
  CHECK(!Quiet::in_range(at(12, 59), at(13, 0), at(14, 30)));
  // The same time twice: no quiet hours.
  CHECK(!Quiet::in_range(at(9, 0), at(9, 0), at(9, 0)));
  CHECK(!Quiet::in_range(at(3, 0), at(9, 0), at(9, 0)));
}

static Quiet::ScreenNow screen(bool quiet, uint32_t idle_ms, uint32_t dim_after_ms = 0, bool card = false) {
  Quiet::ScreenNow n;
  n.quiet = quiet;
  n.card_open = card;
  n.idle_ms = idle_ms;
  n.wake_ms = 30000;
  n.dim_after_ms = dim_after_ms;
  return n;
}

static void levels() {
  // Day, no dimming.
  CHECK(Quiet::level(screen(false, 0)) == Level::NORMAL);
  CHECK(Quiet::level(screen(false, 3600000)) == Level::NORMAL);
  // Day, dims after 5 minutes.
  CHECK(Quiet::level(screen(false, 299999, 300000)) == Level::NORMAL);
  CHECK(Quiet::level(screen(false, 300000, 300000)) == Level::IDLE);
  // Night: quiet, except for 30 s after a tap.
  CHECK(Quiet::level(screen(true, 60000)) == Level::QUIET);
  CHECK(Quiet::level(screen(true, 0)) == Level::NORMAL);
  CHECK(Quiet::level(screen(true, 29999)) == Level::NORMAL);
  CHECK(Quiet::level(screen(true, 30000)) == Level::QUIET);
  // A wake still dims when Dim after is shorter than it.
  CHECK(Quiet::level(screen(true, 20000, 10000)) == Level::IDLE);
  // A card on screen keeps it bright, day or night.
  CHECK(Quiet::level(screen(true, 600000, 0, true)) == Level::NORMAL);
  CHECK(Quiet::level(screen(false, 600000, 60000, true)) == Level::NORMAL);
}

static void brightness() {
  CHECK(Quiet::brightness(Level::NORMAL, 0.8f, 0.0f, 0.3f) == 0.8f);
  CHECK(Quiet::brightness(Level::QUIET, 0.8f, 0.0f, 0.3f) == 0.0f);
  CHECK(Quiet::brightness(Level::QUIET, 0.8f, 0.1f, 0.3f) == 0.1f);
  CHECK(Quiet::brightness(Level::IDLE, 0.8f, 0.0f, 0.3f) == 0.3f);
  // Never above the person's own.
  CHECK(Quiet::brightness(Level::IDLE, 0.2f, 0.0f, 0.3f) == 0.2f);
  CHECK(Quiet::brightness(Level::IDLE, 0.0f, 0.0f, 0.3f) == 0.0f);
}

static void queue() {
  const CardLimits limits{3, 60000};
  // Oldest first.
  {
    CardQueue q;
    q.push("a", 5, 0, limits);
    q.push("b", 6, 10, limits);
    QueuedMessage m;
    CHECK(q.pop(100, limits, &m) && m.text == "a" && m.seconds == 5);
    CHECK(q.pop(100, limits, &m) && m.text == "b" && m.seconds == 6);
    CHECK(!q.pop(100, limits, &m));
  }
  // Over the cap, the oldest goes.
  {
    CardQueue q;
    for (const char *t : {"a", "b", "c", "d", "e"})
      q.push(t, 5, 0, limits);
    CHECK(q.size() == 3);
    QueuedMessage m;
    CHECK(q.pop(0, limits, &m) && m.text == "c");
  }
  // One that waited past keep_ms drops; the next one in time shows.
  {
    CardQueue q;
    q.push("old", 5, 0, limits);
    q.push("new", 5, 50000, limits);
    QueuedMessage m;
    CHECK(q.pop(60001, limits, &m) && m.text == "new");
    CHECK(q.empty());
  }
  // Exactly keep_ms still shows; the clock may wrap.
  {
    CardQueue q;
    q.push("edge", 5, 0xFFFFFF00u, limits);
    QueuedMessage m;
    CHECK(q.pop(0xFFFFFF00u + 60000, limits, &m) && m.text == "edge");
  }
  // A cap of 0 keeps nothing.
  {
    CardQueue q;
    q.push("a", 5, 0, CardLimits{0, 60000});
    CHECK(q.empty());
  }
}

static void sounds() {
  // Sounds on: all play.
  CHECK(sound_passes(true, false, false));
  CHECK(sound_passes(true, true, false));
  // Held by Do not disturb: only urgent ones.
  CHECK(sound_passes(false, true, true));
  CHECK(!sound_passes(false, true, false));
  // Turned off by the person: urgent stays silent too.
  CHECK(!sound_passes(false, false, true));
}

int main() {
  sounds();
  ranges();
  levels();
  brightness();
  queue();
  if (failures == 0)
    std::printf("All quiet tests passed\n");
  return failures == 0 ? 0 : 1;
}
