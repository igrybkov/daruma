#pragma once

// A span of calendar events (one day, or the agenda's days ahead), and the
// date math around it. No drawing and no fetching here.

#include <cstdint>
#include <ctime>
#include <string>
#include <vector>

#include "agenda.h"
#include "esphome/components/json/json_util.h"
#include "esphome/core/time.h"

namespace Daruma {

struct CalendarDay {
  // Local midnight that starts the span, as a UTC epoch. 0 = nothing here.
  time_t start{0};
  // The local midnight that ends it. A day is 23 or 25 hours on a clock
  // change.
  time_t end{0};
  bool loaded{false};
  uint32_t fetched_ms{0};
  // Events HA found for the span. May be more than events holds.
  int total{0};
  // By start time; all-day events start at a local midnight.
  std::vector<CalendarEvent> events;

  void clear() { *this = CalendarDay{}; }
  bool has(time_t span_start) const { return this->loaded && this->start == span_start; }
  // Events HA left out.
  int hidden() const { return std::max(0, this->total - (int) this->events.size()); }
  // Up to here the span holds every event. HA sorts by start and cuts the
  // end off, so a trimmed span is whole up to its last event's start.
  time_t complete_until() const {
    return this->hidden() > 0 && !this->events.empty() ? this->events.back().start : this->end;
  }
  // The events of one day [from, to) in this span, as a day of its own.
  CalendarDay slice(time_t from, time_t to) const;

  // Index of the event in progress, else the next one to start, else -1.
  int focus(time_t now) const;
};

// The device never keeps more than this many events for a span.
static const int CALENDAR_MAX_EVENTS = 40;

// Fills day.events and day.total from a reply to the fetch script:
//   {"response": {"n": total, "e": [[start, end, all_day, "title"], ...]}}
// The inner object may also come as a JSON string. False when the shape is
// wrong; day is then left as it was.
bool parse_calendar_reply(ArduinoJson::JsonObjectConst reply, CalendarDay &day);

// Local midnight `offset` days from now, as a UTC epoch. 0 if now is not valid.
time_t local_day_start(const esphome::ESPTime &now, int offset);

// "2026-11-15T06:00:00+00:00", for calendar.get_events.
std::string iso_utc(time_t epoch);

// Local wall time as "14:05".
std::string local_hhmm(time_t epoch);

}  // namespace Daruma
