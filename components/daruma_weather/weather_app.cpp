#include "weather_app.h"

#include <algorithm>

#include "esphome/components/api/api_server.h"
#include "esphome/components/daruma/text.h"
#include "esphome/components/daruma/ui_tree.h"
#include "esphome/core/hal.h"
#include "esphome/core/log.h"

namespace Daruma {

using esphome::Color;
using esphome::display::TextAlign;

static const char *const TAG = "daruma_weather";

// Home Assistant subscribes to device actions a moment after it connects.
static const uint32_t CONNECT_GRACE_MS = 5000;
static const uint32_t TICK_MS = 250;
// Most hours the strip can show (wide screens).
static const size_t MAX_HOURS = 8;

std::string WeatherApp::word_(const char *key) const { return this->hub_->theme().word(this->prefix_ + "." + key); }

std::string WeatherApp::condition_word_(const std::string &condition) const {
  const WeatherLook *look = weather_look(condition);
  return look != nullptr ? this->word_(look->word) : std::string();
}

// "72°": the number and a degree sign; HA's unit says which degrees.
std::string WeatherApp::degrees_(float v) const {
  const std::string n = weather_number(v);
  return n.empty() ? std::string("–") : n + "°";
}

void WeatherApp::on_open() {
  this->open_ = true;
  this->want_fetch_ = true;
}

void WeatherApp::reload() {
  this->report_ = WeatherReport{};
  this->have_report_ = false;
  this->failure_ = Failure::NONE;
  this->want_fetch_ = this->open_;
  this->hub_->request_redraw();
}

void WeatherApp::loop() {
  const uint32_t now_ms = esphome::millis();
  if (now_ms - this->tick_ms_ < TICK_MS)
    return;
  this->tick_ms_ = now_ms;

  if (this->pending_ && now_ms - this->sent_ms_ >= this->timeout_ms_) {
    ESP_LOGW(TAG, "No reply from Home Assistant in %" PRIu32 " s", this->timeout_ms_ / 1000);
    this->pending_ = false;
    this->failure_ = Failure::OFFLINE;
    this->hub_->request_redraw();
  }
  if (!this->open_ || !this->enabled_ || this->pending_ || !this->fetcher_)
    return;
  // Every refresh interval while it stays open.
  if (this->have_report_ && now_ms - this->fetched_ms_ >= this->refresh_ms_)
    this->want_fetch_ = true;
  if (!this->want_fetch_)
    return;

  auto *api = esphome::api::global_api_server;
  if (api == nullptr || !api->is_connected()) {
    this->connected_ms_ = 0;
    if (this->failure_ != Failure::OFFLINE) {
      this->failure_ = Failure::OFFLINE;
      this->hub_->request_redraw();
    }
    return;
  }
  if (this->connected_ms_ == 0)
    this->connected_ms_ = now_ms | 1;  // Never 0 while connected.
  if (now_ms - this->connected_ms_ < CONNECT_GRACE_MS)
    return;
  this->want_fetch_ = false;
  this->incoming_ = WeatherReport{};
  this->ok_replies_ = 0;
  this->send_(HOURLY);
}

void WeatherApp::send_(int kind) {
  this->pending_ = true;
  this->kind_ = kind;
  this->request_++;
  this->sent_ms_ = esphome::millis();
  ESP_LOGD(TAG, "Request %d: %s forecast", this->request_, kind == HOURLY ? "hourly" : "daily");
  this->fetcher_(this->request_, kind);
}

static float number(ArduinoJson::JsonVariantConst v) { return v.isNull() ? NAN : v.as<float>(); }

static std::string text(ArduinoJson::JsonVariantConst v) {
  const char *s = v.as<const char *>();
  return s != nullptr ? s : "";
}

void WeatherApp::on_reply(int request, ArduinoJson::JsonObjectConst reply) {
  if (!this->pending_ || request != this->request_) {
    ESP_LOGD(TAG, "Dropped a late reply to request %d", request);
    return;
  }
  ArduinoJson::JsonVariantConst body = reply["response"];
  // HA turns the rendered template back into an object when it can; if it
  // could not, the object arrives as JSON text.
  ArduinoJson::JsonDocument text_doc;
  if (body.is<const char *>()) {
    text_doc = esphome::json::parse_json(std::string(body.as<const char *>()));
    body = text_doc.as<ArduinoJson::JsonVariantConst>();
  }
  bool ok = false;
  if (this->kind_ == HOURLY && !body["h"].isNull()) {
    auto &r = this->incoming_;
    r.condition = text(body["c"]);
    r.temperature = number(body["t"]);
    r.wind = number(body["ws"]);
    r.temperature_unit = text(body["u"]);
    r.wind_unit = text(body["w"]);
    for (ArduinoJson::JsonArrayConst row : body["h"].as<ArduinoJson::JsonArrayConst>()) {
      if (row.size() < 4 || r.hours.size() >= 24)
        continue;
      r.hours.push_back(WeatherHour{row[0].as<int64_t>(), text(row[1]), number(row[2]), number(row[3])});
    }
    ok = true;
  } else if (this->kind_ == DAILY && !body["d"].isNull()) {
    for (ArduinoJson::JsonArrayConst row : body["d"].as<ArduinoJson::JsonArrayConst>()) {
      if (row.size() < 6 || this->incoming_.days.size() >= 3)
        continue;
      this->incoming_.days.push_back(WeatherDay{row[0].as<int64_t>(), text(row[1]), number(row[2]), number(row[3]),
                                                number(row[4]), number(row[5])});
    }
    ok = true;
  } else {
    ESP_LOGW(TAG, "Reply to request %d has an unexpected shape", request);
  }
  this->done_(ok);
}

void WeatherApp::on_error(int request, const std::string &error) {
  if (!this->pending_ || request != this->request_)
    return;
  // Some weather services have no hourly forecast: the days still come.
  ESP_LOGW(TAG, "Request %d failed: %s", request, error.c_str());
  this->done_(false);
}

// One reply of the round is in. The hours go first, then the days; the
// report shows when both are back and at least one worked.
void WeatherApp::done_(bool ok) {
  this->pending_ = false;
  if (ok)
    this->ok_replies_++;
  if (this->kind_ == HOURLY) {
    this->send_(DAILY);
    return;
  }
  if (this->ok_replies_ > 0) {
    this->report_ = std::move(this->incoming_);
    this->have_report_ = true;
    this->failure_ = Failure::NONE;
  } else {
    this->failure_ = Failure::ERROR;
  }
  this->fetched_ms_ = esphome::millis();
  this->hub_->request_redraw();
}

std::string WeatherApp::status() {
  if (!this->have_report_)
    return "";
  const std::string word = this->condition_word_(this->report_.condition);
  const std::string t = std::isnan(this->report_.temperature) ? "" : this->degrees_(this->report_.temperature);
  return word.empty() ? t : (t.empty() ? word : t + " " + word);
}

bool WeatherApp::input(Input input, int x, int y) {
  // Anything on an error tries again at once.
  if ((input == Input::TAP || input == Input::SELECT) && this->failure_ != Failure::NONE && !this->pending_) {
    this->failure_ = Failure::NONE;
    this->want_fetch_ = true;
    this->hub_->request_redraw();
    return true;
  }
  return false;
}

void WeatherApp::draw(AppView &v) {
  auto &it = v.display;
  const Theme &t = v.theme;
  const int pad = v.px(12);
  const Color ink = t.ink;
  const Color muted = t.muted;

  if (!this->have_report_ || (this->failure_ != Failure::NONE && this->report_.empty())) {
    std::string message = this->word_("loading");
    if (this->failure_ == Failure::OFFLINE)
      message = this->word_("offline");
    else if (this->failure_ == Failure::ERROR)
      message = this->word_("error");
    it.print(v.x + v.w / 2, v.y + v.h / 2, v.small, muted, TextAlign::CENTER,
             fit_text(it, v.small, message, v.w - 2 * pad).c_str(), t.panel);
    UiTree::add("text", message, Rect{v.x, v.y + v.h / 2 - v.px(10), v.w, v.px(20)});
    return;
  }

  const WeatherReport &r = this->report_;
  const esphome::ESPTime now = this->clock_ != nullptr ? this->clock_->now() : esphome::ESPTime{};
  const int64_t now_s = now.is_valid() ? (int64_t) now.timestamp : 0;
  int64_t today_start = 0;
  if (now.is_valid())
    today_start = now_s - (now.hour * 3600 + now.minute * 60 + now.second);
  const Color icon_color = t.on(t.panel, t.color(this->prefix_ + ".icon"));

  // Now: the condition's icon, the temperature big, and its name.
  const WeatherLook *look = weather_look(r.condition);
  const int top_cy = v.y + v.px(30);
  if (look != nullptr)
    it.print(v.x + pad + v.px(16), top_cy, v.icons, icon_color, TextAlign::CENTER, look->icon, t.panel);
  const std::string temp = this->degrees_(r.temperature);
  const int temp_x = v.x + pad + v.px(38);
  esphome::display::BaseFont *big = this->big_font_ != nullptr ? this->big_font_ : v.text;
  it.print(temp_x, top_cy, big, ink, TextAlign::CENTER_LEFT, temp.c_str(), t.panel);
  const int room = v.x + v.w - pad - (temp_x + text_width(it, big, temp) + v.px(8));
  const int rx = v.x + v.w - pad;
  const std::string name = this->condition_word_(r.condition);
  it.print(rx, v.y + v.px(18), v.text, ink, TextAlign::CENTER_RIGHT, fit_text(it, v.text, name, room).c_str(),
           t.panel);
  UiTree::add("text", name, Rect{rx - room, v.y + v.px(8), room, v.px(20)}, false, temp);

  // Today's high and low.
  const WeatherDay *today = r.today(today_start);
  if (today != nullptr) {
    std::string hl = fill(this->word_("high_low"), "high", this->degrees_(today->high));
    hl = fill(hl, "low", this->degrees_(today->low));
    it.print(rx, v.y + v.px(42), v.small, muted, TextAlign::CENTER_RIGHT, fit_text(it, v.small, hl, room).c_str(),
             t.panel);
  }

  // Rain and wind, on one line.
  const int cols = std::max(3, std::min((int) MAX_HOURS, (v.w - 2 * pad) / v.px(46)));
  std::string details;
  const float rain = r.rain_chance(now_s, today_start, cols);
  if (!std::isnan(rain))
    details = fill(this->word_("rain"), "chance", weather_number(rain));
  const float wind = !std::isnan(r.wind) ? r.wind : (today != nullptr ? today->wind : NAN);
  if (!std::isnan(wind)) {
    std::string w = fill(this->word_("wind"), "speed", weather_number(wind));
    w = fill(w, "unit", r.wind_unit);
    details = details.empty() ? w : details + "  ·  " + w;
  }
  if (!details.empty())
    it.print(v.x + pad, v.y + v.px(68), v.small, muted, TextAlign::CENTER_LEFT,
             fit_text(it, v.small, details, v.w - 2 * pad).c_str(), t.panel);

  // The next hours: the hour, the icon, the temperature, the chance of rain.
  const auto hours = r.next_hours(now_s, cols);
  if (hours.empty())
    return;
  const int strip_top = v.y + v.px(84);
  it.horizontal_line(v.x + pad, strip_top, v.w - 2 * pad, t.fit(t.edge));
  const int col_w = (v.w - 2 * pad) / cols;
  const Color rain_color = t.on(t.panel, t.color(this->prefix_ + ".rain"));
  for (size_t i = 0; i < hours.size(); i++) {
    const WeatherHour &h = *hours[i];
    const int cx = v.x + pad + col_w * (int) i + col_w / 2;
    const esphome::ESPTime at = esphome::ESPTime::from_epoch_local((time_t) h.time);
    const std::string label = i == 0 && h.time <= now_s ? this->word_("now") : esphome::str_sprintf("%02d", at.hour);
    it.print(cx, strip_top + v.px(12), v.small, muted, TextAlign::CENTER, label.c_str(), t.panel);
    const WeatherLook *hl = weather_look(h.condition);
    if (hl != nullptr)
      it.print(cx, strip_top + v.px(40), v.icons, icon_color, TextAlign::CENTER, hl->icon, t.panel);
    it.print(cx, strip_top + v.px(68), v.small, ink, TextAlign::CENTER, this->degrees_(h.temperature).c_str(),
             t.panel);
    if (!std::isnan(h.precipitation) && h.precipitation >= 1.0f)
      it.print(cx, strip_top + v.px(84), v.small, rain_color, TextAlign::CENTER,
               (weather_number(h.precipitation) + "%").c_str(), t.panel);
    UiTree::add("cell", label, Rect{cx - col_w / 2, strip_top, col_w, v.px(92)}, false, this->degrees_(h.temperature));
  }
}

}  // namespace Daruma
