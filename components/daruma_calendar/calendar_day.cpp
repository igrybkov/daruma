#include "calendar_day.h"

#include <algorithm>
#include <cinttypes>

#include "esphome/core/helpers.h"

namespace Daruma {

int CalendarDay::focus(time_t now) const {
  for (size_t i = 0; i < this->events.size(); i++) {
    const CalendarEvent &event = this->events[i];
    if (!event.all_day && now < event.end)
      return (int) i;
  }
  return -1;
}

CalendarDay CalendarDay::slice(time_t from, time_t to) const {
  CalendarDay day;
  day.start = from;
  day.end = to;
  day.loaded = this->loaded;
  day.fetched_ms = this->fetched_ms;
  for (const CalendarEvent &event : this->events) {
    if (event.overlaps(from, to))
      day.events.push_back(event);
  }
  std::stable_sort(day.events.begin(), day.events.end(), [](const CalendarEvent &a, const CalendarEvent &b) {
    if (a.all_day != b.all_day)
      return a.all_day;
    return a.start < b.start;
  });
  day.total = (int) day.events.size();
  return day;
}

bool parse_calendar_reply(ArduinoJson::JsonObjectConst reply, CalendarDay &day) {
  ArduinoJson::JsonVariantConst body = reply["response"];
  // HA turns the rendered template back into an object when it can; if it
  // could not, the object arrives as JSON text.
  ArduinoJson::JsonDocument text_doc;
  if (body.is<const char *>()) {
    text_doc = esphome::json::parse_json(std::string(body.as<const char *>()));
    body = text_doc.as<ArduinoJson::JsonVariantConst>();
  }
  ArduinoJson::JsonArrayConst rows = body["e"];
  if (rows.isNull())
    return false;

  std::vector<CalendarEvent> events;
  for (ArduinoJson::JsonArrayConst row : rows) {
    if (row.size() < 4 || (int) events.size() >= CALENDAR_MAX_EVENTS)
      continue;
    CalendarEvent event;
    event.start = (time_t) row[0].as<int64_t>();
    event.end = (time_t) row[1].as<int64_t>();
    event.all_day = row[2].as<int>() != 0;
    const char *title = row[3].as<const char *>();
    event.title = title != nullptr ? title : "";
    if (event.end < event.start)
      event.end = event.start;
    events.push_back(std::move(event));
  }
  std::stable_sort(events.begin(), events.end(),
                   [](const CalendarEvent &a, const CalendarEvent &b) { return a.start < b.start; });

  day.total = std::max(body["n"] | 0, (int) events.size());
  day.events = std::move(events);
  return true;
}

time_t local_day_start(const esphome::ESPTime &now, int offset) {
  if (!now.is_valid())
    return 0;
  // Step from about noon, so a 23 or 25 hour day cannot land on the wrong date.
  const time_t noon = now.timestamp - (now.hour * 3600 + now.minute * 60 + now.second) + 12 * 3600;
  esphome::ESPTime day = esphome::ESPTime::from_epoch_local(noon + (time_t) offset * 86400);
  day.hour = 0;
  day.minute = 0;
  day.second = 0;
  day.recalc_timestamp_local();
  return day.timestamp > 0 ? day.timestamp : 0;
}

std::string iso_utc(time_t epoch) {
  esphome::ESPTime t = esphome::ESPTime::from_epoch_utc(epoch);
  return esphome::str_sprintf("%04d-%02d-%02dT%02d:%02d:%02d+00:00", t.year, t.month, t.day_of_month, t.hour,
                              t.minute, t.second);
}

std::string local_hhmm(time_t epoch) {
  esphome::ESPTime t = esphome::ESPTime::from_epoch_local(epoch);
  return esphome::str_sprintf("%02d:%02d", t.hour, t.minute);
}

}  // namespace Daruma
