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
  CHECK_EQ(control_text(ControlKind::TOGGLE, state("on", "153"), w), "On · 60%");
  CHECK_EQ(control_text(ControlKind::TOGGLE, state("on", "255"), w), "On · 100%");
  CHECK_EQ(control_text(ControlKind::TOGGLE, state("on", "300"), w), "On · 100%");
  CHECK_EQ(control_text(ControlKind::TOGGLE, state("on", "-5"), w), "On · 0%");
  CHECK_EQ(control_text(ControlKind::TOGGLE, state("on", "None"), w), "On");
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
  CHECK_EQ(control_text(ControlKind::TOGGLE, state("on", "255"), de), "An · 100%");
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

int main() {
  kinds();
  availability();
  numbers();
  texts();
  actions();
  if (failures == 0)
    std::printf("OK\n");
  return failures == 0 ? 0 : 1;
}
