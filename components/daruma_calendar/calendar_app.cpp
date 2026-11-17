#include "calendar_app.h"

#include "next_line.h"

#include <algorithm>

#include "esphome/components/api/api_server.h"
#include "esphome/core/hal.h"
#include "esphome/core/log.h"

namespace Daruma {

static const char *const TAG = "daruma_calendar";

static const int MIN_OFFSET = -30;
static const int MAX_OFFSET = 60;
// Most events one day view request brings.
static const int DAY_LIMIT = 12;
// Home Assistant subscribes to device actions a moment after it connects;
// a request sent before that is lost.
static const uint32_t CONNECT_GRACE_MS = 5000;
// Opening the app fetches the agenda again when the copy is older than this.
static const uint32_t OPEN_STALE_MS = 60000;
// First automatic retry after a failure; it doubles up to the refresh interval.
static const uint32_t RETRY_MIN_MS = 30000;
static const uint32_t TICK_MS = 250;

static bool before(uint32_t now_ms, uint32_t at_ms) { return (int32_t) (now_ms - at_ms) < 0; }

esphome::ESPTime CalendarApp::now_() const {
  return this->clock_ != nullptr ? this->clock_->now() : esphome::ESPTime{};
}

std::string CalendarApp::word_(const char *key) const { return this->hub_->theme().word(this->prefix_ + "." + key); }

void CalendarApp::show_line(esphome::display::BaseFont *font) {
  this->line_ = true;
  NextEventLine::get().add(*this->hub_, this, font);
}

void CalendarApp::set_line_hours(float hours) {
  const time_t window = hours > 0 ? (time_t) (hours * 3600.0f) : 0;
  if (window == this->line_window_s_)
    return;
  this->line_window_s_ = window;
  if (this->line_)
    NextEventLine::get().changed();
}

const CalendarEvent *CalendarApp::line_pick(time_t now, time_t day_end, NextEventKind *kind) const {
  if (!this->line_on() || !this->agenda_.loaded)
    return nullptr;
  const NextEventPick pick = pick_next_event(this->agenda_.events, now, this->line_window_s_, day_end);
  if (pick.kind == NextEventKind::NONE)
    return nullptr;
  *kind = pick.kind;
  return &this->agenda_.events[pick.index];
}

void CalendarApp::set_enabled(bool enabled) {
  if (this->line_ && enabled != this->enabled_)
    NextEventLine::get().changed();
  this->enabled_ = enabled;
  if (!enabled) {
    this->pending_ = false;  // A late reply is dropped.
    this->open_ = false;
  } else {
    this->kick_ = true;
  }
}

void CalendarApp::set_days_ahead(int days) {
  days = std::max(1, std::min(31, days));
  if (days == this->days_ahead_)
    return;
  this->days_ahead_ = days;
  this->force_agenda_ = true;
  this->kick_ = true;
}

void CalendarApp::dump_config() {
  ESP_LOGCONFIG(TAG,
                "Calendar app '%s':\n"
                "  Days ahead: %d (at most %d events)\n"
                "  Refresh: %" PRIu32 " s\n"
                "  Timeout: %" PRIu32 " s",
                this->prefix_.c_str(), this->days_ahead_, this->agenda_limit_, this->refresh_ms_ / 1000,
                this->timeout_ms_ / 1000);
}

// --- Fetching ---------------------------------------------------------------

void CalendarApp::loop() {
  const uint32_t now_ms = esphome::millis();
  if (now_ms - this->tick_ms_ < TICK_MS)
    return;
  this->tick_ms_ = now_ms;

  if (this->pending_ && now_ms - this->sent_ms_ >= this->timeout_ms_) {
    ESP_LOGW(TAG, "No reply from Home Assistant in %" PRIu32 " s", this->timeout_ms_ / 1000);
    this->fail_(Failure::OFFLINE);
  }

  const esphome::ESPTime now = this->now_();
  if (!now.is_valid())
    return;
  if (this->line_)
    NextEventLine::get().tick();

  const time_t today = local_day_start(now, 0);
  if (today != 0 && today != this->today_start_) {
    // A new day, or the first time the clock is set. The agenda is fetched
    // again for the new window; until then the old one stays on screen.
    this->today_start_ = today;
    this->other_.clear();
    this->auto_scroll_ = true;
    this->hub_->request_redraw();
  }

  // Move the time along while the app is on screen.
  if (this->open_ && now.minute != this->drawn_minute_) {
    this->drawn_minute_ = now.minute;
    this->hub_->request_redraw();
  }

  this->maybe_fetch_();
}

bool CalendarApp::agenda_covers_(time_t start, time_t end) const {
  return this->agenda_.has(this->today_start_) && start >= this->agenda_.start && end <= this->agenda_.complete_until();
}

void CalendarApp::maybe_fetch_() {
  if (!this->enabled_ || this->pending_ || !this->fetcher_ || this->today_start_ == 0)
    return;
  const uint32_t now_ms = esphome::millis();
  auto *api = esphome::api::global_api_server;
  if (api == nullptr || !api->is_connected()) {
    this->connected_ms_ = 0;
    return;
  }
  if (this->connected_ms_ == 0)
    this->connected_ms_ = now_ms | 1;  // Never 0 while connected.
  if (now_ms - this->connected_ms_ < CONNECT_GRACE_MS)
    return;
  if (this->failures_ > 0 && !this->kick_ && before(now_ms, this->retry_at_ms_))
    return;

  const esphome::ESPTime now = this->now_();
  // A day view outside the agenda first, then the agenda.
  if (this->open_ && this->day_mode_) {
    const time_t start = local_day_start(now, this->offset_);
    const time_t end = local_day_start(now, this->offset_ + 1);
    if (start != 0 && !this->agenda_covers_(start, end) && !this->other_.has(start)) {
      this->send_day_(this->offset_, start);
      return;
    }
  }
  const time_t end = local_day_start(now, this->days_ahead_);
  const bool stale = !this->agenda_.has(this->today_start_) || this->agenda_.end != end ||
                     now_ms - this->agenda_.fetched_ms >= this->refresh_ms_;
  if (stale || this->force_agenda_) {
    this->send_agenda_();
    return;
  }
  this->kick_ = false;
}

void CalendarApp::send_agenda_() {
  this->pending_ = true;
  this->pending_agenda_ = true;
  this->request_++;
  this->pending_start_ = this->today_start_;
  this->pending_end_ = local_day_start(this->now_(), this->days_ahead_);
  this->sent_ms_ = esphome::millis();
  this->kick_ = false;
  this->force_agenda_ = false;
  const std::string from = iso_utc(this->pending_start_), to = iso_utc(this->pending_end_);
  ESP_LOGD(TAG, "Request %d: agenda from %s to %s", this->request_, from.c_str(), to.c_str());
  this->fetcher_(this->request_, from, to, this->agenda_limit_);
}

void CalendarApp::send_day_(int offset, time_t start) {
  this->pending_ = true;
  this->pending_agenda_ = false;
  this->request_++;
  this->pending_start_ = start;
  this->pending_end_ = local_day_start(this->now_(), offset + 1);
  this->sent_ms_ = esphome::millis();
  this->kick_ = false;
  const std::string from = iso_utc(start), to = iso_utc(this->pending_end_);
  ESP_LOGD(TAG, "Request %d: day from %s to %s", this->request_, from.c_str(), to.c_str());
  this->fetcher_(this->request_, from, to, DAY_LIMIT);
}

void CalendarApp::on_reply(int request, ArduinoJson::JsonObjectConst reply) {
  if (!this->pending_ || request != this->request_) {
    ESP_LOGD(TAG, "Dropped a late reply to request %d", request);
    return;
  }
  CalendarDay span;
  span.start = this->pending_start_;
  span.end = this->pending_end_;
  if (!parse_calendar_reply(reply, span)) {
    ESP_LOGW(TAG, "Reply to request %d has an unexpected shape", request);
    this->fail_(Failure::ERROR);
    return;
  }
  this->pending_ = false;
  this->failures_ = 0;
  this->failure_ = Failure::NONE;
  span.loaded = true;
  span.fetched_ms = esphome::millis();
  ESP_LOGD(TAG, "Request %d: %u of %d events", request, (unsigned) span.events.size(), span.total);
  if (this->pending_agenda_) {
    this->agenda_ = std::move(span);
    if (this->line_)
      NextEventLine::get().changed();
  } else {
    this->other_ = std::move(span);
  }
  this->hub_->request_redraw();
}

void CalendarApp::on_error(int request, const std::string &error) {
  if (!this->pending_ || request != this->request_)
    return;
  ESP_LOGW(TAG, "Request %d failed: %s", request, error.c_str());
  this->fail_(Failure::ERROR);
}

void CalendarApp::fail_(Failure failure) {
  this->pending_ = false;
  this->failure_ = failure;
  this->failed_agenda_ = this->pending_agenda_;
  this->failed_start_ = this->pending_start_;
  this->failures_++;
  const uint32_t backoff = RETRY_MIN_MS << std::min(this->failures_ - 1, 5);
  this->retry_at_ms_ = esphome::millis() + std::min(backoff, this->refresh_ms_);
  this->hub_->request_redraw();
}

void CalendarApp::retry_() {
  if (this->failure_ == Failure::NONE || this->pending_)
    return;
  this->kick_ = true;
  if (this->failed_agenda_)
    this->force_agenda_ = true;
}

void CalendarApp::reload() {
  this->agenda_.clear();
  if (this->line_)
    NextEventLine::get().changed();
  this->other_.clear();
  this->pending_ = false;  // A reply for the old list is dropped.
  this->failure_ = Failure::NONE;
  this->failures_ = 0;
  this->kick_ = true;
  this->auto_scroll_ = true;
  this->hub_->request_redraw();
}

// --- Board and app ----------------------------------------------------------

std::string CalendarApp::status() {
  const esphome::ESPTime now = this->now_();
  if (!now.is_valid() || !this->agenda_.has(this->today_start_)) {
    if (this->failure_ != Failure::NONE && this->failed_agenda_)
      return this->word_("status_error");
    return "…";
  }
  const CalendarDay today = this->agenda_.slice(this->today_start_, local_day_start(now, 1));
  const time_t t = now.timestamp;
  for (const CalendarEvent &event : today.events) {
    if (!event.all_day && event.start > t)
      return this->word_("next") + " " + local_hhmm(event.start);
  }
  for (const CalendarEvent &event : today.events) {
    if (event.is_now(t)) {
      if (event.end > today.end)
        return this->word_("busy");
      return this->word_("until") + " " + local_hhmm(event.end);
    }
  }
  return this->word_("free");
}

void CalendarApp::on_open() {
  this->open_ = true;
  this->day_mode_ = false;
  this->offset_ = 0;
  this->agenda_view_.reset();
  if (!this->agenda_.has(this->today_start_) || esphome::millis() - this->agenda_.fetched_ms >= OPEN_STALE_MS) {
    this->force_agenda_ = true;
    this->kick_ = true;
  }
}

bool CalendarApp::back() {
  if (!this->open_ || !this->day_mode_)
    return false;
  this->day_mode_ = false;
  this->hub_->request_redraw();
  return true;
}

void CalendarApp::show_day_(int offset) {
  offset = std::max(MIN_OFFSET, std::min(MAX_OFFSET, offset));
  if (this->day_mode_ && offset == this->offset_)
    return;
  this->day_mode_ = true;
  this->offset_ = offset;
  this->auto_scroll_ = true;
  const time_t start = local_day_start(this->now_(), offset);
  // Stop waiting for a day no longer on screen; its late reply is dropped.
  if (this->pending_ && !this->pending_agenda_ && this->pending_start_ != start)
    this->pending_ = false;
  this->kick_ = true;
  this->hub_->request_redraw();
}

bool CalendarApp::day_(int offset, CalendarDay &out) const {
  const esphome::ESPTime now = this->now_();
  const time_t start = local_day_start(now, offset), end = local_day_start(now, offset + 1);
  if (start == 0)
    return false;
  if (this->agenda_covers_(start, end)) {
    out = this->agenda_.slice(start, end);
    return true;
  }
  if (this->other_.has(start)) {
    out = this->other_;
    return true;
  }
  return false;
}

// "Wed 19 Nov", with the theme's short weekday and month names.
std::string CalendarApp::date_(time_t start) const {
  const esphome::ESPTime noon = esphome::ESPTime::from_epoch_local(start + HALF_DAY);
  return agenda_date(noon.day_of_week, noon.day_of_month, noon.month, split_names(this->word_("weekdays")),
                     split_names(this->word_("months")));
}

std::string CalendarApp::day_label_(int offset, time_t start) const {
  switch (offset) {
    case 0:
      return this->word_("today");
    case 1:
      return this->word_("tomorrow");
    case -1:
      return this->word_("yesterday");
    default:
      break;
  }
  return start == 0 ? "" : this->date_(start);
}

void CalendarApp::draw(AppView &v) {
  const esphome::ESPTime now = this->now_();
  if (now.is_valid())
    this->drawn_minute_ = now.minute;
  if (this->day_mode_) {
    this->draw_day_(v, now);
  } else {
    this->draw_agenda_(v, now);
  }
}

void CalendarApp::draw_agenda_(AppView &v, const esphome::ESPTime &now) {
  AgendaViewState state;
  std::vector<time_t> day_starts;
  if (now.is_valid() && this->agenda_.loaded) {
    for (int d = 0; d <= this->days_ahead_; d++)
      day_starts.push_back(local_day_start(now, d));
    state.span = &this->agenda_;
    this->rows_ = build_agenda(this->agenda_.events, day_starts, this->agenda_.hidden());
    for (int d = 0; d < this->days_ahead_; d++) {
      const bool used = std::any_of(this->rows_.begin(), this->rows_.end(),
                                    [d](const AgendaRow &r) { return r.kind == AgendaRowKind::HEADING && r.day == d; });
      state.headings.push_back(used ? this->day_label_(d, day_starts[d]) : "");
    }
    state.rows = this->rows_;
    state.today_end = day_starts[1];
  } else {
    this->rows_.clear();
  }
  const bool failed = this->failure_ != Failure::NONE && this->failed_agenda_;
  state.loading = (this->pending_ && this->pending_agenda_) || !failed;
  if (failed) {
    state.error = this->failure_ == Failure::OFFLINE ? this->word_("offline") : this->word_("error");
  }
  state.now = now.is_valid() ? now.timestamp : 0;
  state.loading_text = this->word_("loading");
  state.nothing_text = this->word_("nothing");
  state.all_day_text = this->word_("all_day");
  state.more_text = this->word_("more");
  state.untitled_text = this->word_("untitled");
  this->agenda_view_.draw(v, state);
}

void CalendarApp::draw_day_(AppView &v, const esphome::ESPTime &now) {
  const time_t start = now.is_valid() ? local_day_start(now, this->offset_) : 0;
  CalendarDay day;
  const bool have = now.is_valid() && this->day_(this->offset_, day);

  CalendarViewState state;
  state.label = this->day_label_(this->offset_, start);
  if (start != 0 && this->offset_ >= -1 && this->offset_ <= 1)
    state.date = this->date_(start);
  state.day = have ? &day : nullptr;
  state.is_today = this->offset_ == 0;
  state.now = now.is_valid() ? now.timestamp : 0;
  state.can_go_back = this->offset_ > MIN_OFFSET;
  state.can_go_forward = this->offset_ < MAX_OFFSET;
  const bool failed = this->failure_ != Failure::NONE && (this->failed_agenda_ || this->failed_start_ == start);
  state.loading = this->pending_ || !failed;
  if (failed) {
    state.error = this->failure_ == Failure::OFFLINE ? this->word_("offline") : this->word_("error");
  }
  state.loading_text = this->word_("loading");
  state.empty_text = this->word_("empty");
  state.all_day_text = this->word_("all_day");
  state.more_text = this->word_("more");
  state.untitled_text = this->word_("untitled");

  if (have && this->auto_scroll_) {
    this->auto_scroll_ = false;
    int row = 0;
    if (state.is_today) {
      row = day.focus(state.now);
      if (row < 0)
        row = (int) day.events.size();
    }
    this->day_view_.scroll_to(row);
  }
  this->day_view_.draw(v, state);
}

bool CalendarApp::input(Input input, int x, int y) {
  if (!this->day_mode_) {
    const int page = std::max(1, this->agenda_view_.rows() - 1);
    int row = -1;
    switch (input) {
      // Boards without touch: next and previous move the focus over the
      // rows; select opens the focused row's day, or retries.
      case Input::NEXT:
        return this->agenda_view_.move_focus(true);
      case Input::PREV:
        return this->agenda_view_.move_focus(false);
      case Input::SELECT:
        if (this->rows_.empty()) {
          this->retry_();
          return true;
        }
        row = this->agenda_view_.focused();
        break;
      case Input::SWIPE_UP:
        this->agenda_view_.scroll_by(page);
        return true;
      case Input::SWIPE_DOWN:
        this->agenda_view_.scroll_by(-page);
        return true;
      case Input::TAP:
        if (this->rows_.empty()) {
          this->retry_();
          return true;
        }
        row = this->agenda_view_.row_at(x, y);
        break;
      default:
        return false;
    }
    // A heading or one of its events opens that day.
    if (row >= 0 && row < (int) this->rows_.size() && this->rows_[row].day >= 0)
      this->show_day_(this->rows_[row].day);
    return true;
  }

  const int page = std::max(1, this->day_view_.rows() - 1);
  switch (input) {
    // Boards without touch: next and previous change the day; select pages
    // through the day's events and wraps to the top, or retries after a
    // failure.
    case Input::NEXT:
      this->show_day_(this->offset_ + 1);
      return true;
    case Input::PREV:
      this->show_day_(this->offset_ - 1);
      return true;
    case Input::SELECT:
      if (this->failure_ != Failure::NONE && !this->pending_) {
        this->retry_();
      } else if (this->day_view_.at_end()) {
        this->day_view_.set_scroll(0);
      } else {
        this->day_view_.scroll_by(page);
      }
      return true;
    case Input::SWIPE_UP:
      this->day_view_.scroll_by(page);
      return true;
    case Input::SWIPE_DOWN:
      this->day_view_.scroll_by(-page);
      return true;
    case Input::SWIPE_LEFT:
      this->show_day_(this->offset_ + 1);
      return true;
    case Input::SWIPE_RIGHT:
      this->show_day_(this->offset_ - 1);
      return true;
    case Input::TAP:
      break;
    default:
      return false;
  }
  switch (this->day_view_.hit(x, y)) {
    case CalendarHit::PREVIOUS:
      this->show_day_(this->offset_ - 1);
      return true;
    case CalendarHit::NEXT:
      this->show_day_(this->offset_ + 1);
      return true;
    case CalendarHit::LABEL:
      this->show_day_(0);
      return true;
    case CalendarHit::LIST:
      // A tap on an error message tries again.
      this->retry_();
      return true;
    case CalendarHit::NONE:
      break;
  }
  return false;
}

}  // namespace Daruma
