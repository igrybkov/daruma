#pragma once

// The next event line on the device's own screen: which event it shows, and
// its text from a template. "14:00 Dentist" for one that starts soon,
// "Now: Standup · until 10:30" for one that runs.
//
// Plain C++ with no ESPHome includes, so a host test can check it
// (tests/test_agenda.cpp).

#include <algorithm>
#include <ctime>
#include <string>
#include <utility>
#include <vector>

#include "agenda.h"

namespace Daruma {

enum class NextEventKind : uint8_t {
  NONE,  // Nothing to show.
  NEXT,  // Starts within the window.
  NOW,   // Running now.
};

struct NextEventPick {
  NextEventKind kind{NextEventKind::NONE};
  int index{-1};  // Into the events.
};

// The event for the line, at `now`:
// - All-day events never count.
// - A running event wins; of several, the one that started last (a meeting
//   inside a longer block).
// - Else the earliest that starts after now and before now + window_s,
//   and before day_end (the local midnight that ends today): the line is
//   about today only.
// A window of 0 or less turns the line off.
inline NextEventPick pick_next_event(const std::vector<CalendarEvent> &events, time_t now, time_t window_s,
                                     time_t day_end) {
  NextEventPick pick;
  if (window_s <= 0)
    return pick;
  const time_t until = std::min(now + window_s, day_end);
  int running = -1, next = -1;
  for (size_t i = 0; i < events.size(); i++) {
    const CalendarEvent &e = events[i];
    if (e.all_day)
      continue;
    if (e.is_now(now)) {
      if (running < 0 || e.start > events[running].start)
        running = (int) i;
    } else if (e.start > now && e.start < until) {
      if (next < 0 || e.start < events[next].start)
        next = (int) i;
    }
  }
  if (running >= 0)
    return NextEventPick{NextEventKind::NOW, running};
  if (next >= 0)
    return NextEventPick{NextEventKind::NEXT, next};
  return pick;
}

// True when (kind a, event a) should show rather than (kind b, event b),
// for several calendars that share one line: running before upcoming, the
// later-started running one, the earlier upcoming one.
inline bool next_event_better(NextEventKind a, const CalendarEvent &ea, NextEventKind b, const CalendarEvent &eb) {
  if (a == NextEventKind::NONE)
    return false;
  if (b == NextEventKind::NONE)
    return true;
  if (a != b)
    return a == NextEventKind::NOW;
  return a == NextEventKind::NOW ? ea.start > eb.start : ea.start < eb.start;
}

// The line's text in three parts, so the title alone is cut to fit.
struct LineText {
  std::string before;
  std::string title;
  std::string after;

  bool empty() const { return this->before.empty() && this->title.empty() && this->after.empty(); }
  bool operator==(const LineText &o) const {
    return this->before == o.before && this->title == o.title && this->after == o.after;
  }
  bool operator!=(const LineText &o) const { return !(*this == o); }
};

// Fills a template such as "Now: {title} · until {end}": {start} and {end}
// become the times, and the text splits around {title}. A template without
// {title} is all `before`.
inline LineText line_text(const std::string &tmpl, const std::string &title, const std::string &start,
                          const std::string &end) {
  auto fill = [&](std::string s) {
    for (const auto &kv : {std::make_pair(std::string("{start}"), start), std::make_pair(std::string("{end}"), end)}) {
      size_t at;
      while ((at = s.find(kv.first)) != std::string::npos)
        s.replace(at, kv.first.size(), kv.second);
    }
    return s;
  };
  LineText out;
  const std::string key = "{title}";
  const size_t at = tmpl.find(key);
  if (at == std::string::npos) {
    out.before = fill(tmpl);
    return out;
  }
  out.before = fill(tmpl.substr(0, at));
  out.title = title;
  out.after = fill(tmpl.substr(at + key.size()));
  return out;
}

}  // namespace Daruma
