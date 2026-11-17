#pragma once

// The Calendar app's state: the agenda or one day on screen, what is
// loaded, and when to ask Home Assistant again. Fetching itself is a YAML
// script (see daruma/app_calendar.yaml) that this class runs through
// the fetcher.
//
// Two spans live in memory: the agenda (today and the days ahead, in one
// request), which also feeds the board's status line, and one day outside
// it when the day view shows such a day.

#include <functional>
#include <string>

#include "agenda_view.h"
#include "calendar_day.h"
#include "calendar_view.h"
#include "esphome/components/daruma/hub.h"
#include "next_event.h"
#include "esphome/components/time/real_time_clock.h"
#include "esphome/core/component.h"

namespace Daruma {

class CalendarApp : public esphome::Component {
 public:
  // Asks HA for at most `limit` events between start and end (ISO times,
  // UTC). The reply goes to on_reply() or on_error() with the same request
  // number.
  using Fetcher = std::function<void(int request, const std::string &start, const std::string &end, int limit)>;

  void set_hub(Hub *hub) { this->hub_ = hub; }
  void set_clock(esphome::time::RealTimeClock *clock) { this->clock_ = clock; }
  void set_refresh_interval(uint32_t ms) { this->refresh_ms_ = ms; }
  void set_timeout(uint32_t ms) { this->timeout_ms_ = ms; }
  void set_fetcher(Fetcher fetcher) { this->fetcher_ = std::move(fetcher); }
  // The theme keys' prefix: the app's id ("calendar.today").
  void set_theme_prefix(const std::string &prefix) { this->prefix_ = prefix; }
  // Most events one agenda request brings.
  void set_agenda_limit(int limit) { this->agenda_limit_ = std::max(1, std::min(limit, CALENDAR_MAX_EVENTS)); }
  // Days the agenda covers, today included (1 to 31). A change fetches again.
  void set_days_ahead(int days);

  void loop() override;
  void dump_config() override;
  float get_setup_priority() const override { return esphome::setup_priority::LATE; }

  // App hooks, for Daruma::App.
  std::string status();
  void draw(AppView &v);
  bool input(Input input, int x, int y);
  void on_open();
  void on_close() { this->open_ = false; }
  // Back while open: the day view goes back to the agenda.
  bool back();
  // The app's switch: off stops every fetch.
  void set_enabled(bool enabled);

  // The calendar list changed: drop what is loaded and fetch again.
  void reload();

  // --- The next event line on the device's own screen (next_line.h) ---------
  // Show this copy's events there, in `font`.
  void show_line(esphome::display::BaseFont *font);
  // "Next event within": hours ahead an event may start to show; 0 = off.
  void set_line_hours(float hours);
  // The line may show something for this copy: on, with a window.
  bool line_on() const { return this->line_ && this->enabled_ && this->line_window_s_ > 0; }
  // The agenda's event for the line at `now`, or nullptr. `day_end` is the
  // local midnight that ends today. Works from the agenda as loaded, even
  // a day old (it spans many days), so midnight needs no fetch first.
  const CalendarEvent *line_pick(time_t now, time_t day_end, NextEventKind *kind) const;
  // A theme word under this copy's id ("calendar.line_next").
  std::string word(const char *key) const { return this->word_(key); }
  esphome::ESPTime clock_now() const { return this->now_(); }

  // Fetch results.
  void on_reply(int request, ArduinoJson::JsonObjectConst reply);
  void on_error(int request, const std::string &error);

 protected:
  enum class Failure { NONE, OFFLINE, ERROR };

  void show_day_(int offset);
  void maybe_fetch_();
  void send_agenda_();
  void send_day_(int offset, time_t start);
  void fail_(Failure failure);
  esphome::ESPTime now_() const;
  // The day `offset` days from today, from the agenda when it holds all of
  // that day, else from the separately fetched day. False when neither has it.
  bool day_(int offset, CalendarDay &out) const;
  bool agenda_covers_(time_t start, time_t end) const;
  std::string day_label_(int offset, time_t start) const;
  std::string date_(time_t start) const;
  std::string word_(const char *key) const;
  void draw_agenda_(AppView &v, const esphome::ESPTime &now);
  void draw_day_(AppView &v, const esphome::ESPTime &now);
  void retry_();

  Hub *hub_{nullptr};
  esphome::time::RealTimeClock *clock_{nullptr};
  Fetcher fetcher_;
  std::string prefix_{"calendar"};
  uint32_t refresh_ms_{15 * 60 * 1000};
  uint32_t timeout_ms_{10000};
  int days_ahead_{14};
  int agenda_limit_{25};

  CalendarDay agenda_;
  CalendarDay other_;
  AgendaView agenda_view_;
  std::vector<AgendaRow> rows_;  // The agenda's rows at the last draw, for taps.
  CalendarView day_view_;
  time_t today_start_{0};
  bool day_mode_{false};  // The day view is on screen, else the agenda.
  int offset_{0};         // The day view's day, in days from today.

  // The one request in flight, if any.
  bool pending_{false};
  bool pending_agenda_{false};
  int request_{0};
  time_t pending_start_{0};
  time_t pending_end_{0};
  uint32_t sent_ms_{0};

  // The last failure, and whether it was the agenda's. Automatic retries
  // back off; anything the user does retries at once.
  Failure failure_{Failure::NONE};
  bool failed_agenda_{false};
  time_t failed_start_{0};
  int failures_{0};
  uint32_t retry_at_ms_{0};
  bool kick_{false};
  // Fetch the agenda again even though the copy is not old yet.
  bool force_agenda_{false};

  bool open_{false};
  bool enabled_{true};
  bool line_{false};
  time_t line_window_s_{3 * 3600};
  bool auto_scroll_{false};

  uint32_t connected_ms_{0};
  uint32_t tick_ms_{0};
  int drawn_minute_{-1};
};

}  // namespace Daruma
