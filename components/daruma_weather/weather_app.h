#pragma once

// The Weather app: today's report from one Home Assistant weather entity.
// Now (condition, temperature, wind), today's high and low and chance of
// rain, and a strip of the next hours.
//
// Fetching is a YAML script (daruma/app_weather.yaml) that this class
// runs through the fetcher: `weather.get_forecasts` once for the hours and
// once for the days, one after the other, through the hub's gate for HA
// calls (ha_calls.h). It fetches only while open: when it opens, and every
// refresh interval while it stays open.

#include <functional>
#include <string>

#include "esphome/components/daruma/hub.h"
#include "esphome/components/json/json_util.h"
#include "esphome/components/time/real_time_clock.h"
#include "esphome/core/component.h"
#include "weather.h"

namespace Daruma {

class WeatherApp : public esphome::Component {
 public:
  enum Kind : int { HOURLY = 0, DAILY = 1 };
  // Asks HA for the forecast of one kind. The reply goes to on_reply() or
  // on_error() with the same request number.
  using Fetcher = std::function<void(int request, int kind)>;

  void set_hub(Hub *hub) { this->hub_ = hub; }
  void set_clock(esphome::time::RealTimeClock *clock) { this->clock_ = clock; }
  void set_refresh_interval(uint32_t ms) { this->refresh_ms_ = ms; }
  void set_timeout(uint32_t ms) { this->timeout_ms_ = ms; }
  void set_fetcher(Fetcher fetcher) { this->fetcher_ = std::move(fetcher); }
  // The theme keys' prefix: the app's id ("weather.loading").
  void set_theme_prefix(const std::string &prefix) { this->prefix_ = prefix; }
  // The big temperature's font.
  void set_big_font(esphome::display::BaseFont *font) { this->big_font_ = font; }

  void loop() override;
  float get_setup_priority() const override { return esphome::setup_priority::LATE; }

  // App hooks, for Daruma::App.
  std::string status();
  void draw(AppView &v);
  bool input(Input input, int x, int y);
  void on_open();
  void on_close() { this->open_ = false; }
  void set_enabled(bool enabled) { this->enabled_ = enabled; }

  // The weather entity changed: drop the report and fetch again.
  void reload();

  // Fetch results.
  void on_reply(int request, ArduinoJson::JsonObjectConst reply);
  void on_error(int request, const std::string &error);

  const WeatherReport &report() const { return this->report_; }

 protected:
  enum class Failure { NONE, OFFLINE, ERROR };

  void send_(int kind);
  void done_(bool ok);
  std::string word_(const char *key) const;
  std::string condition_word_(const std::string &condition) const;
  std::string degrees_(float v) const;

  Hub *hub_{nullptr};
  esphome::time::RealTimeClock *clock_{nullptr};
  Fetcher fetcher_;
  std::string prefix_{"weather"};
  esphome::display::BaseFont *big_font_{nullptr};
  uint32_t refresh_ms_{30 * 60 * 1000};
  uint32_t timeout_ms_{10000};

  WeatherReport report_;
  WeatherReport incoming_;  // Filled by the two replies, then shown.
  bool have_report_{false};
  uint32_t fetched_ms_{0};

  bool pending_{false};
  int kind_{HOURLY};
  int request_{0};
  uint32_t sent_ms_{0};
  int ok_replies_{0};       // Of this round's two.
  bool want_fetch_{false};  // A round should start when HA is there.
  Failure failure_{Failure::NONE};

  bool open_{false};
  bool enabled_{true};
  uint32_t connected_ms_{0};
  uint32_t tick_ms_{0};
};

}  // namespace Daruma
