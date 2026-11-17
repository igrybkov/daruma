#pragma once

// What the Weather app knows, and how a Home Assistant condition looks.
// Plain C++ with no ESPHome includes, so a host test can check it
// (tests/test_weather.cpp).
//
// Conditions are HA's weather states ("partlycloudy", "clear-night", ...).
// Each has a Material Design Icons glyph (menu.yaml's icon font lists them
// all) and a theme word key under the app's id ("weather.partlycloudy").

#include <cmath>
#include <cstdint>
#include <string>
#include <vector>

namespace Daruma {

struct WeatherLook {
  const char *condition;  // HA's state.
  const char *word;       // Theme word key, without the app's prefix.
  const char *icon;       // UTF-8 MDI glyph.
};

// Every condition HA documents for weather entities.
static const WeatherLook WEATHER_LOOKS[] = {
    {"sunny", "sunny", "\U000F0599"},                      // weather-sunny
    {"clear-night", "clear_night", "\U000F0594"},          // weather-night
    {"partlycloudy", "partlycloudy", "\U000F0595"},        // weather-partly-cloudy
    {"cloudy", "cloudy", "\U000F0590"},                    // weather-cloudy
    {"fog", "fog", "\U000F0591"},                          // weather-fog
    {"hail", "hail", "\U000F0592"},                        // weather-hail
    {"lightning", "lightning", "\U000F0593"},              // weather-lightning
    {"lightning-rainy", "lightning_rainy", "\U000F067E"},  // weather-lightning-rainy
    {"pouring", "pouring", "\U000F0596"},                  // weather-pouring
    {"rainy", "rainy", "\U000F0597"},                      // weather-rainy
    {"snowy", "snowy", "\U000F0598"},                      // weather-snowy
    {"snowy-rainy", "snowy_rainy", "\U000F067F"},          // weather-snowy-rainy
    {"windy", "windy", "\U000F059D"},                      // weather-windy
    {"windy-variant", "windy_variant", "\U000F059E"},      // weather-windy-variant
    {"exceptional", "exceptional", "\U000F05D6"},          // alert-circle-outline
};

// The look for a condition; nullptr for an unknown one ("unavailable").
inline const WeatherLook *weather_look(const std::string &condition) {
  for (const auto &look : WEATHER_LOOKS) {
    if (condition == look.condition)
      return &look;
  }
  return nullptr;
}

// One hour of the forecast. NAN for what HA left out.
struct WeatherHour {
  int64_t time{0};  // Epoch seconds.
  std::string condition;
  float temperature{NAN};
  float precipitation{NAN};  // Chance, in percent.
};

// One day of the forecast.
struct WeatherDay {
  int64_t time{0};
  std::string condition;
  float high{NAN};
  float low{NAN};
  float precipitation{NAN};
  float wind{NAN};
};

struct WeatherReport {
  // Now, from the entity itself.
  std::string condition;
  float temperature{NAN};
  float wind{NAN};
  std::string temperature_unit;  // "°F", "°C"
  std::string wind_unit;         // "mph", "km/h"
  std::vector<WeatherHour> hours;
  std::vector<WeatherDay> days;

  bool empty() const {
    return this->condition.empty() && std::isnan(this->temperature) && this->hours.empty() && this->days.empty();
  }

  // Today's row of the daily forecast: the first that is not over yet
  // (`today_start` is local midnight). nullptr when there is none.
  const WeatherDay *today(int64_t today_start) const {
    for (const auto &d : this->days) {
      if (d.time >= today_start - 12 * 3600)
        return &d;
    }
    return nullptr;
  }

  // The hours still ahead of `now` (the one running now first), at most `n`.
  std::vector<const WeatherHour *> next_hours(int64_t now, size_t n) const {
    std::vector<const WeatherHour *> out;
    for (const auto &h : this->hours) {
      if (h.time + 3600 <= now)
        continue;
      if (out.size() >= n)
        break;
      out.push_back(&h);
    }
    return out;
  }

  // The chance of rain to show: today's from the daily forecast, else the
  // highest of the next hours.
  float rain_chance(int64_t now, int64_t today_start, size_t hours) const {
    const WeatherDay *d = this->today(today_start);
    if (d != nullptr && !std::isnan(d->precipitation))
      return d->precipitation;
    float best = NAN;
    for (const WeatherHour *h : this->next_hours(now, hours)) {
      if (!std::isnan(h->precipitation) && (std::isnan(best) || h->precipitation > best))
        best = h->precipitation;
    }
    return best;
  }
};

// A whole number for the screen: "72", "-3"; "" for NAN.
inline std::string weather_number(float v) {
  if (std::isnan(v))
    return "";
  return std::to_string((int) std::lround(v));
}

}  // namespace Daruma
