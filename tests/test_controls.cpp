// Host test of the Controls app's tiles (daruma_controls/controls.h).
//
//   c++ -std=c++17 -Wall -Wextra -I src tests/test_controls.cpp -o /tmp/test_controls && /tmp/test_controls

#include <cstdio>
#include <cstring>
#include <string>

#include "esphome/components/daruma_controls/controls.h"

using namespace Daruma;

static int failures = 0;

#define CHECK(cond) \
  do { \
    if (!(cond)) { \
      std::printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond); \
      failures++; \
    } \
  } while (0)

static void check_eq(const std::string &got, const std::string &want, const char *what, int line) {
  if (got != want) {
    std::printf("FAIL %s:%d: %s is \"%s\", want \"%s\"\n", __FILE__, line, what, got.c_str(), want.c_str());
    failures++;
  }
}

#define CHECK_EQ(a, b) check_eq((a), (b), #a, __LINE__)

static TileState state(const std::string &s, const std::string &extra = "") {
  TileState t;
  t.known = true;
  t.state = s;
  t.extra = extra;
  return t;
}

static TileState light(const std::string &s, const std::string &brightness = "") {
  TileState t = state(s, brightness);
  t.scale = 255;
  return t;
}

static TileState fan(const std::string &s, const std::string &pct = "", const std::string &step = "") {
  TileState t = state(s, pct);
  t.scale = 100;
  t.step = step;
  return t;
}

static void kinds() {
  CHECK_EQ(control_domain("light.desk"), "light");
  CHECK_EQ(control_domain("nodot"), "");
  CHECK(control_kind("light.desk") == ControlKind::TOGGLE);
  CHECK(control_kind("switch.kettle") == ControlKind::TOGGLE);
  CHECK(control_kind("fan.office") == ControlKind::TOGGLE);
  CHECK(control_kind("input_boolean.guests") == ControlKind::TOGGLE);
  CHECK(control_kind("scene.movie") == ControlKind::SCENE);
  CHECK(control_kind("script.good_night") == ControlKind::SCENE);
  CHECK(control_kind("media_player.office") == ControlKind::MEDIA);
  CHECK(control_kind("cover.blinds") == ControlKind::COVER);
  CHECK(control_kind("sensor.co2") == ControlKind::SENSOR);
  CHECK(control_kind("climate.office") == ControlKind::UNKNOWN);
  CHECK(control_kind("light") == ControlKind::UNKNOWN);

  CHECK_EQ(control_attribute("light.desk"), "brightness");
  CHECK_EQ(control_attribute("media_player.office"), "media_title");
  CHECK_EQ(control_attribute("cover.blinds"), "current_position");
  CHECK_EQ(control_attribute("sensor.co2"), "unit_of_measurement");
  CHECK_EQ(control_attribute("fan.office"), "percentage");
  CHECK_EQ(control_attribute("switch.kettle"), "");
  CHECK_EQ(control_attribute("scene.movie"), "");
}

static void availability() {
  TileState none;
  CHECK(!control_available(none));
  CHECK(!control_available(state("unavailable")));
  CHECK(control_available(state("unknown")));
  CHECK(control_available(state("off")));

  CHECK(control_active(ControlKind::TOGGLE, state("on")));
  CHECK(!control_active(ControlKind::TOGGLE, state("off")));
  CHECK(!control_active(ControlKind::TOGGLE, none));
  CHECK(control_active(ControlKind::MEDIA, state("playing")));
  CHECK(!control_active(ControlKind::MEDIA, state("paused")));
  CHECK(control_active(ControlKind::COVER, state("open")));
  CHECK(control_active(ControlKind::COVER, state("opening")));
  CHECK(control_active(ControlKind::COVER, state("closing")));
  CHECK(!control_active(ControlKind::COVER, state("closed")));
  CHECK(!control_active(ControlKind::SCENE, state("on")));
  CHECK(!control_active(ControlKind::SENSOR, state("on")));
}

static void numbers() {
  CHECK_EQ(control_number(""), "");
  CHECK_EQ(control_number("21.53"), "21.5");
  CHECK_EQ(control_number("21.56"), "21.6");
  CHECK_EQ(control_number("40.0"), "40");
  CHECK_EQ(control_number("640"), "640");
  CHECK_EQ(control_number("-0.01"), "0");
  CHECK_EQ(control_number("-3.24"), "-3.2");
  CHECK_EQ(control_number("12abc"), "12abc");
  CHECK_EQ(control_number("unknown"), "unknown");
  CHECK_EQ(control_number("inf"), "inf");
  CHECK_EQ(control_number("0.05"), "0.1");
  CHECK_EQ(control_number("999999999999999"), "999999999999999");
  CHECK_EQ(control_number("1000000000000000"), "1000000000000000");
  CHECK_EQ(control_number("1e15"), "1e15");
}

static void texts() {
  const ControlWords w;
  TileState none;
  // Nothing from HA yet, or the entity is away.
  CHECK_EQ(control_text(ControlKind::TOGGLE, none, w), "Unavailable");
  CHECK_EQ(control_text(ControlKind::SCENE, none, w), "Unavailable");
  CHECK_EQ(control_text(ControlKind::SENSOR, state("unavailable"), w), "Unavailable");

  // Toggles: on, off, a brightness, anything else as HA says it.
  CHECK_EQ(control_text(ControlKind::TOGGLE, state("off"), w), "Off");
  CHECK_EQ(control_text(ControlKind::TOGGLE, state("on"), w), "On");
  CHECK_EQ(control_text(ControlKind::TOGGLE, light("on", "153"), w), "On · 60%");
  CHECK_EQ(control_text(ControlKind::TOGGLE, light("on", "255"), w), "On · 100%");
  CHECK_EQ(control_text(ControlKind::TOGGLE, light("on", "300"), w), "On · 100%");
  CHECK_EQ(control_text(ControlKind::TOGGLE, light("on", "-5"), w), "On · 0%");
  // Rounded to the nearest percent.
  CHECK_EQ(control_text(ControlKind::TOGGLE, light("on", "9"), w), "On · 4%");
  CHECK_EQ(control_text(ControlKind::TOGGLE, light("on", "14"), w), "On · 5%");
  CHECK_EQ(control_text(ControlKind::TOGGLE, light("on", "32"), w), "On · 13%");
  CHECK_EQ(control_text(ControlKind::TOGGLE, light("on", "None"), w), "On");
  CHECK_EQ(control_text(ControlKind::TOGGLE, state("unknown"), w), "unknown");

  // Media: the title while playing.
  CHECK_EQ(control_text(ControlKind::MEDIA, state("playing", "Blue in Green"), w), "Blue in Green");
  CHECK_EQ(control_text(ControlKind::MEDIA, state("playing"), w), "Playing");
  CHECK_EQ(control_text(ControlKind::MEDIA, state("paused", "Blue in Green"), w), "Paused");
  CHECK_EQ(control_text(ControlKind::MEDIA, state("idle"), w), "Idle");
  CHECK_EQ(control_text(ControlKind::MEDIA, state("off"), w), "Off");
  CHECK_EQ(control_text(ControlKind::MEDIA, state("standby"), w), "Off");
  CHECK_EQ(control_text(ControlKind::MEDIA, state("buffering"), w), "buffering");

  // Covers: the position part way.
  CHECK_EQ(control_text(ControlKind::COVER, state("opening"), w), "Opening");
  CHECK_EQ(control_text(ControlKind::COVER, state("closing"), w), "Closing");
  CHECK_EQ(control_text(ControlKind::COVER, state("closed", "0"), w), "Closed");
  CHECK_EQ(control_text(ControlKind::COVER, state("open"), w), "Open");
  CHECK_EQ(control_text(ControlKind::COVER, state("open", "100"), w), "Open");
  CHECK_EQ(control_text(ControlKind::COVER, state("open", "0"), w), "Closed");
  CHECK_EQ(control_text(ControlKind::COVER, state("open", "40"), w), "40%");
  CHECK_EQ(control_text(ControlKind::COVER, state("stopped"), w), "stopped");

  // Sensors: the value and its unit.
  CHECK_EQ(control_text(ControlKind::SENSOR, state("21.53", "°C"), w), "21.5°");
  CHECK_EQ(control_text(ControlKind::SENSOR, state("70", "°F"), w), "70°");
  CHECK_EQ(control_text(ControlKind::SENSOR, state("45", "%"), w), "45%");
  CHECK_EQ(control_text(ControlKind::SENSOR, state("640", "ppm"), w), "640 ppm");
  CHECK_EQ(control_text(ControlKind::SENSOR, state("42"), w), "42");

  // Scenes and scripts show no state.
  CHECK_EQ(control_text(ControlKind::SCENE, state("2026-01-01T10:00:00"), w), "");

  // The words come from the theme.
  ControlWords de;
  de.on = "An";
  CHECK_EQ(control_text(ControlKind::TOGGLE, light("on", "255"), de), "An · 100%");
}

static void actions() {
  CHECK_EQ(control_action("light.desk", state("on")), "light.toggle");
  CHECK_EQ(control_action("switch.kettle", state("off")), "switch.toggle");
  CHECK_EQ(control_action("fan.office", state("off")), "fan.toggle");
  CHECK_EQ(control_action("input_boolean.guests", state("off")), "input_boolean.toggle");
  CHECK_EQ(control_action("scene.movie", state("unknown")), "scene.turn_on");
  CHECK_EQ(control_action("script.good_night", state("off")), "script.turn_on");
  CHECK_EQ(control_action("media_player.office", state("paused")), "media_player.media_play_pause");
  CHECK_EQ(control_action("cover.blinds", state("closed")), "cover.open_cover");
  CHECK_EQ(control_action("cover.blinds", state("open")), "cover.close_cover");
  CHECK_EQ(control_action("cover.blinds", state("opening")), "cover.stop_cover");
  CHECK_EQ(control_action("cover.blinds", state("closing")), "cover.stop_cover");
  // Nothing to do: a sensor, an unknown kind, an entity that is away.
  CHECK_EQ(control_action("sensor.co2", state("640")), "");
  CHECK_EQ(control_action("climate.office", state("heat")), "");
  CHECK_EQ(control_action("light.desk", state("unavailable")), "");
  CHECK_EQ(control_action("light.desk", TileState{}), "");
}

static void levels() {
  CHECK(control_scale("light.desk") == 255);
  CHECK(control_scale("fan.office") == 100);
  CHECK(control_scale("switch.kettle") == 0);
  CHECK(control_fresh("light.desk").scale == 255);
  CHECK(!control_fresh("light.desk").known);
  CHECK(control_has_panel("light.desk"));
  CHECK(control_has_panel("fan.office"));
  CHECK(control_has_panel("media_player.office"));
  CHECK(!control_has_panel("switch.kettle"));
  CHECK(!control_has_panel("cover.blinds"));

  // Percent from HA's attribute.
  CHECK(control_percent(light("on", "153")) == 60);
  CHECK(control_percent(light("on", "152.6")) == 60);
  CHECK(control_percent(light("on", "300")) == 100);
  CHECK(control_percent(light("on", "-5")) == 0);
  CHECK(control_percent(light("on", "None")) == -1);
  CHECK(control_percent(light("on", "inf")) == -1);
  CHECK(control_percent(light("on")) == -1);
  CHECK(control_percent(state("on", "153")) == -1);  // No scale: not a light or fan.
  CHECK(control_percent(fan("on", "66")) == 66);
  CHECK(control_percent(fan("on", "67.0")) == 67);
  CHECK_EQ(control_text(ControlKind::TOGGLE, fan("on", "66"), ControlWords{}), "On · 66%");

  // The bar: 0 while off, 100 while on without a level.
  CHECK(control_level(light("off", "None")) == 0);
  CHECK(control_level(light("on")) == 100);
  CHECK(control_level(light("on", "153")) == 60);
  CHECK(control_level(light("on", "0")) == 0);
  CHECK(control_level(light("on", "1")) == 0);
  CHECK(control_level(fan("unavailable", "50")) == 0);

  // Steps.
  CHECK(control_step(fan("on", "", "33.333333333333336")) > 33.3);
  CHECK(control_step(fan("on", "", "")) == 1.0);
  CHECK(control_step(fan("on", "", "None")) == 1.0);
  CHECK(control_step(fan("on", "", "0.5")) == 1.0);
  CHECK(control_step(fan("on", "", "1")) == 1.0);
  CHECK(control_step(fan("on", "", "100")) == 100.0);
  CHECK(control_step(fan("on", "", "101")) == 100.0);
  CHECK(control_step(fan("on", "", "nan")) == 1.0);
  CHECK(control_step(fan("on", "", "1.5")) == 1.5);
  CHECK(control_step(fan("on", "", "25x")) == 1.0);

  // A tap on the bar.
  const TileState l = light("on", "153");
  CHECK(control_level_at(0, 200, l) == 1);
  CHECK(control_level_at(-10, 200, l) == 1);
  CHECK(control_level_at(1, 200, l) == 1);
  CHECK(control_level_at(3, 200, l) == 2);
  CHECK(control_level_at(100, 200, l) == 50);
  CHECK(control_level_at(199, 200, l) == 100);
  CHECK(control_level_at(250, 200, l) == 100);
  CHECK(control_level_at(10, 0, l) == 100);  // No bar: a 1-pixel one.
  CHECK(control_level_at(10, -5, l) == 100);
  CHECK(control_level_at(1, 1, l) == 100);
  CHECK(control_level_at(0, 2, l) == 1);
  CHECK(control_level_at(1, 100, fan("on", "", "1.5")) == 2);
  // A three-speed fan snaps to 33, 67 or 100.
  const TileState f = fan("on", "67", "33.333333333333336");
  CHECK(control_level_at(0, 300, f) == 33);
  CHECK(control_level_at(49, 300, f) == 33);
  CHECK(control_level_at(51, 300, f) == 33);
  CHECK(control_level_at(150, 300, f) == 67);
  CHECK(control_level_at(249, 300, f) == 67);
  CHECK(control_level_at(251, 300, f) == 100);
  CHECK(control_level_at(300, 300, f) == 100);
  // A four-speed fan.
  CHECK(control_level_at(110, 300, fan("on", "", "25")) == 25);
  CHECK(control_level_at(115, 300, fan("on", "", "25")) == 50);
}

static void media() {
  TileState s = state("playing", "Rain on a Tin Roof");
  // Unknown until HA says.
  CHECK(!control_supports(s, MEDIA_NEXT));
  CHECK(control_volume(s) == -1);
  s.features = "16437";  // Pause, volume, previous, next, play.
  CHECK(control_supports(s, MEDIA_PAUSE));
  CHECK(control_supports(s, MEDIA_VOLUME_SET));
  CHECK(control_supports(s, MEDIA_PREVIOUS));
  CHECK(control_supports(s, MEDIA_NEXT));
  s.features = "16385";  // Pause and play only: a speaker that can't skip.
  CHECK(control_supports(s, MEDIA_PAUSE));
  CHECK(!control_supports(s, MEDIA_NEXT));
  CHECK(!control_supports(s, MEDIA_VOLUME_SET));
  s.features = "1";  // Pause alone.
  CHECK(control_supports(s, MEDIA_PAUSE));
  CHECK(!control_supports(s, MEDIA_PREVIOUS));
  s.features = "None";
  CHECK(!control_supports(s, MEDIA_PAUSE));
  s.features = "5x";
  CHECK(!control_supports(s, MEDIA_PAUSE));

  s.volume = "0.35";
  CHECK(control_volume(s) == 35);
  s.volume = "0.355";
  CHECK(control_volume(s) == 36);
  s.volume = "0.9949";
  CHECK(control_volume(s) == 99);
  s.volume = "1";
  CHECK(control_volume(s) == 100);
  s.volume = "1.5";
  CHECK(control_volume(s) == 100);
  s.volume = "-0.2";
  CHECK(control_volume(s) == 0);
  s.volume = "None";
  CHECK(control_volume(s) == -1);
  s.volume = "nan";
  CHECK(control_volume(s) == -1);

  CHECK_EQ(control_media_action(0), "media_player.media_previous_track");
  CHECK_EQ(control_media_action(1), "media_player.media_play_pause");
  CHECK_EQ(control_media_action(2), "media_player.media_next_track");
  CHECK_EQ(control_media_action(3), "");
  CHECK_EQ(control_media_action(-1), "");
}

int main() {
  kinds();
  media();
  levels();
  availability();
  numbers();
  texts();
  actions();
  if (failures == 0)
    std::printf("OK\n");
  return failures == 0 ? 0 : 1;
}
