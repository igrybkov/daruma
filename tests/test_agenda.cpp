// Host test of the Calendar agenda's grouping by day and its date
// headings (daruma_calendar/agenda.h), and of the next event line on the
// device's screen (daruma_calendar/next_event.h).
//
//   tests/run_cpp.sh   (builds and runs it with the other C++ tests)

#include <cstdio>
#include <string>
#include <vector>

#include "esphome/components/daruma_calendar/agenda.h"
#include "esphome/components/daruma_calendar/next_event.h"

using namespace Daruma;

static int failures = 0;

#define CHECK(cond) \
  do { \
    if (!(cond)) { \
      std::printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond); \
      failures++; \
    } \
  } while (0)

static const time_t H = 3600;
// Local midnights from "today": a 23-hour day (clocks forward) on day 2.
static const time_t T0 = 1795068000;  // Some local midnight.
static const std::vector<time_t> DAYS = {T0, T0 + 24 * H, T0 + 48 * H, T0 + 71 * H, T0 + 95 * H};

static CalendarEvent timed(time_t start, time_t end, const char *title = "x") {
  return CalendarEvent{start, end, false, title};
}
static CalendarEvent all_day(time_t start, time_t end, const char *title = "x") {
  return CalendarEvent{start, end, true, title};
}

static std::string shape(const std::vector<AgendaRow> &rows) {
  std::string out;
  for (const AgendaRow &r : rows) {
    switch (r.kind) {
      case AgendaRowKind::HEADING:
        out += "H" + std::to_string(r.day);
        break;
      case AgendaRowKind::EVENT:
        out += "e" + std::to_string(r.event);
        break;
      case AgendaRowKind::NOTHING:
        out += '-';
        break;
      case AgendaRowKind::MORE:
        out += '+';
        break;
    }
    out += ' ';
  }
  return out;
}

static void test_day_of() {
  CHECK(agenda_day_of(timed(T0 + 9 * H, T0 + 10 * H), DAYS) == 0);
  CHECK(agenda_day_of(timed(T0 + 24 * H, T0 + 25 * H), DAYS) == 1);  // At midnight: the new day.
  CHECK(agenda_day_of(timed(T0 + 70 * H, T0 + 71 * H), DAYS) == 2);  // Late on the short day.
  CHECK(agenda_day_of(timed(T0 + 71 * H, T0 + 72 * H), DAYS) == 3);
  CHECK(agenda_day_of(timed(T0 + 95 * H, T0 + 96 * H), DAYS) == -1);  // Past the window.
  // Started last night, still on: today. Already over: left out.
  CHECK(agenda_day_of(timed(T0 - 2 * H, T0 + H), DAYS) == 0);
  CHECK(agenda_day_of(timed(T0 - 2 * H, T0), DAYS) == -1);
  // All day, at HA's midnight or a few hours off it.
  CHECK(agenda_day_of(all_day(T0 + 24 * H, T0 + 48 * H), DAYS) == 1);
  CHECK(agenda_day_of(all_day(T0 + 21 * H, T0 + 45 * H), DAYS) == 1);
  CHECK(agenda_day_of(all_day(T0 + 27 * H, T0 + 51 * H), DAYS) == 1);
  // A trip that began last week and ends tomorrow: today.
  CHECK(agenda_day_of(all_day(T0 - 96 * H, T0 + 48 * H), DAYS) == 0);
  // One that ended yesterday (end = today's midnight): left out.
  CHECK(agenda_day_of(all_day(T0 - 48 * H, T0), DAYS) == -1);
}

static void test_rows() {
  // Nothing at all: Today and "nothing".
  CHECK(shape(build_agenda({}, DAYS, 0)) == "H0 - ");
  // Free today, busy later; days without events have no heading.
  std::vector<CalendarEvent> events = {
      timed(T0 + 48 * H + 9 * H, T0 + 48 * H + 10 * H),   // 0: day 2
      timed(T0 + 24 * H + 15 * H, T0 + 24 * H + 16 * H),  // 1: day 1, 15:00
      all_day(T0 + 24 * H, T0 + 48 * H),                  // 2: day 1, all day
      timed(T0 + 24 * H + 8 * H, T0 + 24 * H + 9 * H),    // 3: day 1, 08:00
  };
  CHECK(shape(build_agenda(events, DAYS, 0)) == "H0 - H1 e2 e3 e1 H2 e0 ");
  // Busy today: no "nothing"; trimmed: "+N more" at the end.
  events.push_back(timed(T0 + 13 * H, T0 + 14 * H));  // 4: today
  CHECK(shape(build_agenda(events, DAYS, 3)) == "H0 e4 H1 e2 e3 e1 H2 e0 + ");
  // Out of the window: dropped, and day 3 gets no heading.
  events.push_back(timed(T0 + 200 * H, T0 + 201 * H));  // 5
  CHECK(shape(build_agenda(events, DAYS, 0)) == "H0 e4 H1 e2 e3 e1 H2 e0 ");
}

static void test_overlaps() {
  const time_t d1 = T0 + 24 * H, d2 = T0 + 48 * H;
  CHECK(all_day(d1, d2).overlaps(d1, d2));
  CHECK(!all_day(d1, d2).overlaps(T0, d1));
  CHECK(!all_day(d1, d2).overlaps(d2, d2 + 24 * H));
  CHECK(all_day(d1 - 3 * H, d2 - 3 * H).overlaps(d1, d2));  // A clock a few hours off.
  CHECK(!all_day(d1 - 3 * H, d2 - 3 * H).overlaps(T0, d1));
  CHECK(timed(d1 - H, d1 + H).overlaps(T0, d1));
  CHECK(timed(d1 - H, d1 + H).overlaps(d1, d2));
  CHECK(!timed(d1 - H, d1).overlaps(d1, d2));
  CHECK(timed(d1, d1).overlaps(d1, d2));  // No length: on the day it is.
}

static void test_headings() {
  const std::vector<std::string> days = split_names("Sun,Mon,Tue,Wed,Thu,Fri,Sat");
  const std::vector<std::string> months = split_names("Jan, Feb, Mar, Apr, May, Jun, Jul, Aug, Sep, Oct, Nov, Dec");
  CHECK(days.size() == 7 && months.size() == 12);
  CHECK(months[1] == "Feb");  // Spaces after commas go.
  CHECK(agenda_date(4, 19, 11, days, months) == "Wed 19 Nov");
  CHECK(agenda_date(1, 1, 1, days, months) == "Sun 1 Jan");
  CHECK(agenda_date(7, 31, 12, days, months) == "Sat 31 Dec");
  // A short list falls back to the day number.
  CHECK(agenda_date(4, 19, 11, split_names("Su,Mo"), months) == "19");
  CHECK(split_names("").size() == 1);
}

// Made-up events. "Today" is T0 to T0 + 24 h; the clock reads 10:00.
static void test_next_event() {
  const time_t now = T0 + 10 * H, end = T0 + 24 * H, three = 3 * H;
  auto pick = [&](const std::vector<CalendarEvent> &events, time_t at = 0, time_t window = 3 *H) {
    return pick_next_event(events, at ? at : now, window, end);
  };
  auto is = [](NextEventPick p, NextEventKind kind, int index) { return p.kind == kind && p.index == index; };

  // Window edges: starts inside, exactly at the end (out), just before it (in).
  CHECK(is(pick({timed(now + 2 * H, now + 3 * H)}), NextEventKind::NEXT, 0));
  CHECK(is(pick({timed(now + three, now + 4 * H)}), NextEventKind::NONE, -1));
  CHECK(is(pick({timed(now + three - 60, now + 4 * H)}), NextEventKind::NEXT, 0));
  // The earliest of several; order in the list does not matter.
  CHECK(is(pick({timed(now + 2 * H, now + 3 * H), timed(now + H, now + 2 * H)}), NextEventKind::NEXT, 1));
  // Starting this very second counts as running.
  CHECK(is(pick({timed(now, now + H)}), NextEventKind::NOW, 0));
  // A past event is gone; one that ends now is over.
  CHECK(is(pick({timed(now - 2 * H, now - H)}), NextEventKind::NONE, -1));
  CHECK(is(pick({timed(now - H, now)}), NextEventKind::NONE, -1));

  // Running beats upcoming; of two running, the later-started one.
  CHECK(is(pick({timed(now + 30 * 60, now + H), timed(now - H, now + H)}), NextEventKind::NOW, 1));
  CHECK(is(pick({timed(T0 + 9 * H, T0 + 17 * H), timed(now - 600, now + 900)}), NextEventKind::NOW, 1));
  // A timed event from yesterday still on counts as running.
  CHECK(is(pick({timed(T0 - 2 * H, now + H)}), NextEventKind::NOW, 0));

  // All-day events never show, running or not.
  CHECK(is(pick({all_day(T0, end)}), NextEventKind::NONE, -1));
  CHECK(is(pick({all_day(T0, end), timed(now + H, now + 2 * H)}), NextEventKind::NEXT, 1));

  // Midnight: today only. At 23:00 an event at 00:30 tomorrow is out, one
  // at 23:30 is in.
  const time_t late = T0 + 23 * H;
  CHECK(is(pick({timed(end + 30 * 60, end + H)}, late), NextEventKind::NONE, -1));
  CHECK(is(pick({timed(late + 30 * 60, late + 45 * 60)}, late), NextEventKind::NEXT, 0));
  // Right after midnight the new day's events count (day_end moves on).
  CHECK(is(pick_next_event({timed(end + H, end + 2 * H)}, end + 60, three, end + 24 * H), NextEventKind::NEXT, 0));

  // N = 0 turns it off, running events included.
  CHECK(is(pick({timed(now - H, now + H)}, 0, 0), NextEventKind::NONE, -1));
  CHECK(is(pick({timed(now + H, now + 2 * H)}, 0, 0), NextEventKind::NONE, -1));
  CHECK(is(pick({}), NextEventKind::NONE, -1));

  // Several calendars on one line.
  const CalendarEvent a = timed(now + H, now + 2 * H), b = timed(now + 2 * H, now + 3 * H);
  const CalendarEvent r1 = timed(now - H, now + H), r2 = timed(now - 600, now + H);
  CHECK(next_event_better(NextEventKind::NEXT, a, NextEventKind::NEXT, b));
  CHECK(!next_event_better(NextEventKind::NEXT, b, NextEventKind::NEXT, a));
  CHECK(next_event_better(NextEventKind::NOW, r1, NextEventKind::NEXT, a));
  CHECK(next_event_better(NextEventKind::NOW, r2, NextEventKind::NOW, r1));
  CHECK(next_event_better(NextEventKind::NEXT, a, NextEventKind::NONE, b));
  CHECK(!next_event_better(NextEventKind::NONE, a, NextEventKind::NEXT, b));
}

static void test_line_text() {
  LineText t = line_text("{start} {title}", "Dentist", "14:00", "15:00");
  CHECK(t.before == "14:00 " && t.title == "Dentist" && t.after.empty());
  t = line_text("Now: {title} \u00b7 until {end}", "Standup", "10:00", "10:30");
  CHECK(t.before == "Now: " && t.title == "Standup" && t.after == " \u00b7 until 10:30");
  // Another word order.
  t = line_text("{title} um {start}", "Zahnarzt", "14:00", "");
  CHECK(t.before.empty() && t.title == "Zahnarzt" && t.after == " um 14:00");
  // No {title}: all of it before.
  t = line_text("Busy until {end}", "x", "", "11:00");
  CHECK(t.before == "Busy until 11:00" && t.title.empty() && t.after.empty());
  CHECK(LineText{}.empty() && !t.empty());
  CHECK(line_text("{start} {title}", "a", "1", "2") != line_text("{start} {title}", "b", "1", "2"));
}

int main() {
  test_next_event();
  test_line_text();
  test_day_of();
  test_rows();
  test_overlaps();
  test_headings();
  if (failures == 0)
    std::printf("agenda: all passed\n");
  return failures == 0 ? 0 : 1;
}
