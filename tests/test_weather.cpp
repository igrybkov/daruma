// Host test of the Weather app's report (daruma_weather/weather.h).
//
//   c++ -std=c++17 -Wall -Wextra -I components/daruma_weather \
//       tests/test_weather.cpp -o /tmp/test_weather && /tmp/test_weather

#include <cmath>
#include <cstdio>
#include <cstring>
#include <set>
#include <string>

#include "weather.h"

using namespace Daruma;

static int failures = 0;

#define CHECK(cond) \
  do { \
    if (!(cond)) { \
      std::printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond); \
      failures++; \
    } \
  } while (0)

int main() {
  // Every HA condition has a look; an unknown one has none.
  {
    const char *conditions[] = {"sunny", "clear-night", "partlycloudy",    "cloudy",        "fog",
                                "hail",  "lightning",   "lightning-rainy", "pouring",       "rainy",
                                "snowy", "snowy-rainy", "windy",           "windy-variant", "exceptional"};
    std::set<std::string> words;
    for (const char *c : conditions) {
      const WeatherLook *look = weather_look(c);
      CHECK(look != nullptr);
      if (look == nullptr)
        continue;
      // A glyph in the MDI private use area (U+F0000..), 4 bytes of UTF-8.
      CHECK(std::strlen(look->icon) == 4 && (unsigned char) look->icon[0] == 0xF3);
      // Word keys are theme key names: lowercase and _.
      for (const char *p = look->word; *p; p++)
        CHECK((*p >= 'a' && *p <= 'z') || *p == '_');
      words.insert(look->word);
    }
    CHECK(words.size() == sizeof(conditions) / sizeof(conditions[0]));
    CHECK(weather_look("unavailable") == nullptr);
    CHECK(weather_look("") == nullptr);
  }
  // Numbers for the screen.
  {
    CHECK(weather_number(71.6f) == "72");
    CHECK(weather_number(-2.6f) == "-3");
    CHECK(weather_number(NAN).empty());
  }
  // The next hours: the one running now first, at most n.
  {
    WeatherReport r;
    const int64_t hour = 1773223200;  // 10:00
    for (int i = -2; i < 10; i++)
      r.hours.push_back(WeatherHour{hour + i * 3600, "sunny", 60.0f + i, i * 10.0f});
    const int64_t now = hour + 25 * 60;  // 10:25
    auto next = r.next_hours(now, 4);
    CHECK(next.size() == 4);
    CHECK(next[0]->time == hour);
    CHECK(next[3]->time == hour + 3 * 3600);
    CHECK(r.next_hours(hour + 20 * 3600, 4).empty());
    // Without a daily row, the rain chance is the highest of those hours.
    CHECK(std::fabs(r.rain_chance(now, hour - 10 * 3600, 4) - 30.0f) < 0.01f);
  }
  // Today's row of the daily forecast, and its rain chance first.
  {
    WeatherReport r;
    const int64_t midnight = 1773187200;  // 00:00 that day
    r.days.push_back(WeatherDay{midnight - 86400, "sunny", 70, 50, 5, 3});
    r.days.push_back(WeatherDay{midnight, "rainy", 68, 49, 80, 12});
    r.days.push_back(WeatherDay{midnight + 86400, "sunny", 71, 50, 0, 6});
    const WeatherDay *today = r.today(midnight);
    CHECK(today != nullptr && today->time == midnight);
    CHECK(std::fabs(r.rain_chance(midnight + 36000, midnight, 4) - 80.0f) < 0.01f);
    // Some services start the daily list at noon, or at the hour now.
    WeatherReport noon;
    noon.days.push_back(WeatherDay{midnight + 12 * 3600, "cloudy", 60, 40, NAN, NAN});
    CHECK(noon.today(midnight) != nullptr);
    CHECK(std::isnan(noon.rain_chance(midnight + 36000, midnight, 4)));
    CHECK(WeatherReport{}.today(midnight) == nullptr);
    CHECK(WeatherReport{}.empty());
    CHECK(!r.empty());
  }
  if (failures == 0)
    std::printf("weather: all passed\n");
  return failures == 0 ? 0 : 1;
}
