#pragma once

// Calendar events and the agenda's grouping by day: which rows the agenda
// shows, in what order, and the day headings' text.
//
// Plain C++ with no ESPHome includes, so a host test can check it
// (tests/test_agenda.cpp). Local time comes in as a list of day
// starts (local midnights as UTC epochs), which the caller works out.

#include <algorithm>
#include <cstdint>
#include <ctime>
#include <string>
#include <vector>

namespace Daruma {

// An all-day event starts and ends at a local midnight (HA's). Grouping
// looks at its middle, so a device clock a few hours off HA's still puts it
// on the right day.
static const time_t HALF_DAY = 12 * 3600;

struct CalendarEvent {
  // UTC epoch seconds. An all-day event runs from one local midnight to
  // another (the end is the day after its last day).
  time_t start{0};
  time_t end{0};
  bool all_day{false};
  std::string title;

  bool is_now(time_t now) const { return !this->all_day && this->start <= now && now < this->end; }
  bool is_past(time_t now) const { return !this->all_day && this->end <= now; }
  // True when the event takes up part of [from, to).
  bool overlaps(time_t from, time_t to) const {
    if (this->all_day)
      return this->start + HALF_DAY<to &&this->end - HALF_DAY> from;
    if (this->start == this->end)
      return this->start >= from && this->start < to;
    return this->start<to &&this->end> from;
  }
};

enum class AgendaRowKind : uint8_t {
  HEADING,  // "Today", "Tomorrow", "Wed 19 Nov".
  EVENT,    // Time (or "All day") and title.
  NOTHING,  // Under Today when it has no events.
  MORE,     // "+3 more" at the end, when HA left events out.
};

struct AgendaRow {
  AgendaRowKind kind;
  int day;    // Days from today. -1 for MORE.
  int event;  // Index into the events, for EVENT rows; else -1.
};

// The day (0 = today) an event is listed under, or -1 when it is outside
// the window. day_starts holds the local midnights of today, tomorrow, ...
// and the one that ends the window, so days = day_starts.size() - 1.
//
// An event is listed under the day it starts. One that started before
// today and has not ended goes under today.
inline int agenda_day_of(const CalendarEvent &event, const std::vector<time_t> &day_starts) {
  if (day_starts.size() < 2)
    return -1;
  const time_t first = day_starts.front();
  const time_t key = event.all_day ? event.start + HALF_DAY : event.start;
  if (key >= day_starts.back())
    return -1;
  if (key < first) {
    const bool running = event.all_day ? event.end - HALF_DAY > first : event.end > first;
    return running ? 0 : -1;
  }
  const auto it = std::upper_bound(day_starts.begin(), day_starts.end(), key);
  return (int) (it - day_starts.begin()) - 1;
}

// The agenda's rows. Today always gets a heading, with NOTHING under it
// when it is free; later days get one only when they have events. Under
// each heading: all-day events, then the rest by start time. `hidden`
// events that HA left out add a MORE row at the end.
inline std::vector<AgendaRow> build_agenda(const std::vector<CalendarEvent> &events,
                                           const std::vector<time_t> &day_starts, int hidden) {
  struct Placed {
    int day;
    int index;
  };
  std::vector<Placed> placed;
  for (size_t i = 0; i < events.size(); i++) {
    const int day = agenda_day_of(events[i], day_starts);
    if (day >= 0)
      placed.push_back(Placed{day, (int) i});
  }
  std::stable_sort(placed.begin(), placed.end(), [&events](const Placed &a, const Placed &b) {
    if (a.day != b.day)
      return a.day < b.day;
    const CalendarEvent &x = events[a.index], &y = events[b.index];
    if (x.all_day != y.all_day)
      return x.all_day;
    return x.start < y.start;
  });

  std::vector<AgendaRow> rows;
  rows.push_back(AgendaRow{AgendaRowKind::HEADING, 0, -1});
  if (placed.empty() || placed.front().day != 0)
    rows.push_back(AgendaRow{AgendaRowKind::NOTHING, 0, -1});
  int day = 0;
  for (const Placed &p : placed) {
    if (p.day != day) {
      day = p.day;
      rows.push_back(AgendaRow{AgendaRowKind::HEADING, day, -1});
    }
    rows.push_back(AgendaRow{AgendaRowKind::EVENT, day, p.index});
  }
  if (hidden > 0)
    rows.push_back(AgendaRow{AgendaRowKind::MORE, -1, -1});
  return rows;
}

// "Wed 19 Nov" from short names: weekdays from Sunday (7 of them) and
// months from January (12). weekday is 1 (Sunday) to 7, month 1 to 12.
inline std::string agenda_date(int weekday, int day_of_month, int month, const std::vector<std::string> &weekdays,
                               const std::vector<std::string> &months) {
  if (weekday < 1 || weekday > (int) weekdays.size() || month < 1 || month > (int) months.size())
    return std::to_string(day_of_month);
  return weekdays[weekday - 1] + " " + std::to_string(day_of_month) + " " + months[month - 1];
}

// Splits "Sun,Mon,Tue" into its names.
inline std::vector<std::string> split_names(const std::string &list) {
  std::vector<std::string> out;
  size_t from = 0;
  while (from <= list.size()) {
    const size_t comma = std::min(list.find(',', from), list.size());
    std::string name = list.substr(from, comma - from);
    const size_t a = name.find_first_not_of(' '), b = name.find_last_not_of(' ');
    out.push_back(a == std::string::npos ? "" : name.substr(a, b - a + 1));
    from = comma + 1;
  }
  return out;
}

}  // namespace Daruma
