#pragma once

// What a Controls tile does and shows, by its entity's domain. Plain C++
// with no ESPHome includes, so a host test can check it
// (tests/test_controls.cpp).
//
//   Kind k = control_kind("light.desk");             // TOGGLE
//   TileState s; s.state = "on"; s.extra = "153";    // brightness 0..255
//   control_text(k, s, words);                       // "On · 60%"
//   control_action("light.desk", s);                 // "light.toggle"

#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <string>

namespace Daruma {

enum class ControlKind { UNKNOWN, TOGGLE, SCENE, MEDIA, COVER, SENSOR };

// The domain of an entity id: "light" for "light.desk".
inline std::string control_domain(const std::string &entity) {
  const size_t dot = entity.find('.');
  return dot == std::string::npos ? std::string() : entity.substr(0, dot);
}

inline ControlKind control_kind(const std::string &entity) {
  const std::string d = control_domain(entity);
  if (d == "light" || d == "switch" || d == "fan" || d == "input_boolean")
    return ControlKind::TOGGLE;
  if (d == "scene" || d == "script")
    return ControlKind::SCENE;
  if (d == "media_player")
    return ControlKind::MEDIA;
  if (d == "cover")
    return ControlKind::COVER;
  if (d == "sensor")
    return ControlKind::SENSOR;
  return ControlKind::UNKNOWN;
}

// The one attribute a tile reads besides the state, or "" for none.
inline const char *control_attribute(const std::string &entity) {
  const std::string d = control_domain(entity);
  if (d == "light")
    return "brightness";
  if (d == "fan")
    return "percentage";
  if (d == "media_player")
    return "media_title";
  if (d == "cover")
    return "current_position";
  if (d == "sensor")
    return "unit_of_measurement";
  return "";
}

// What HA last said about a tile's entity.
struct TileState {
  bool known{false};  // A state came since HA connected.
  std::string state;  // "on", "playing", "21.5", "unavailable", ...
  std::string extra;  // The attribute: brightness, percentage, title, position or unit.
  int scale{0};       // What `extra` counts to as a level: 255 for a light, 100 for a fan, else 0.
  std::string step;   // A fan's percentage_step: 33.3 for three speeds.
};

// The full scale of an entity's level: a light's brightness goes to 255, a
// fan's percentage to 100. 0 for an entity without a level.
inline int control_scale(const std::string &entity) {
  const std::string d = control_domain(entity);
  if (d == "light")
    return 255;
  return d == "fan" ? 100 : 0;
}

// A tile's state before HA sends anything.
inline TileState control_fresh(const std::string &entity) {
  TileState s;
  s.scale = control_scale(entity);
  return s;
}

// The words a tile shows. Theme words under the app id fill them.
struct ControlWords {
  std::string on{"On"}, off{"Off"};
  std::string playing{"Playing"}, paused{"Paused"}, idle{"Idle"};
  std::string open{"Open"}, closed{"Closed"}, opening{"Opening"}, closing{"Closing"};
  std::string unavailable{"Unavailable"};
};

// A tile greys out until HA sends a state, and while the entity is away.
inline bool control_available(const TileState &s) { return s.known && s.state != "unavailable"; }

// The tile looks lit: a light on, music playing, a cover open.
inline bool control_active(ControlKind kind, const TileState &s) {
  if (!control_available(s))
    return false;
  switch (kind) {
    case ControlKind::TOGGLE:
      return s.state == "on";
    case ControlKind::MEDIA:
      return s.state == "playing";
    case ControlKind::COVER:
      return s.state == "open" || s.state == "opening" || s.state == "closing";
    default:
      return false;
  }
}

// A number as HA sends it, at most one decimal: "21.53" is "21.5", "40.0" is
// "40". Text that is not a number comes back as it is.
inline std::string control_number(const std::string &text) {
  if (text.empty())
    return text;
  char *end = nullptr;
  const double v = std::strtod(text.c_str(), &end);
  if (end == nullptr || *end != '\0' || !std::isfinite(v))
    return text;
  if (std::fabs(v) >= 1e15)
    return text;
  // In tenths, so "-0.01" comes out as "0", not "-0".
  const long long tenths = std::llround(v * 10.0);
  const long long whole = std::llabs(tenths) / 10, tenth = std::llabs(tenths) % 10;
  std::string out = tenths < 0 ? "-" : "";
  out += std::to_string(whole);
  if (tenth != 0)
    out += "." + std::to_string(tenth);
  return out;
}

// The level HA sent, in percent: brightness 153 of 255 is 60. -1 without one.
inline int control_percent(const TileState &s) {
  if (s.scale == 0 || s.extra.empty())
    return -1;
  char *end = nullptr;
  const double v = std::strtod(s.extra.c_str(), &end);
  if (*end != '\0' || !std::isfinite(v))
    return -1;
  const long long raw = std::max(0LL, std::min((long long) s.scale, std::llround(v)));
  // No brightness lands on a half, so any offset near 127 rounds the same.
  const long long half = s.scale / 2;  // pragma: no mutate
  return (int) ((raw * 100 + half) / s.scale);
}

// "On · 60%" for a light at brightness 153 of 255; "On" without one.
inline std::string control_toggle_text(const TileState &s, const ControlWords &w) {
  if (s.state == "off")
    return w.off;
  if (s.state != "on")
    return s.state;
  const int pct = control_percent(s);
  return pct < 0 ? w.on : w.on + " · " + std::to_string(pct) + "%";
}

// A light or a fan: a long press opens its level.
inline bool control_has_level(const std::string &entity) { return control_scale(entity) != 0; }

// The level the bar shows: 0 while off, 100 while on without a level.
inline int control_level(const TileState &s) {
  if (s.state != "on")
    return 0;
  const int pct = control_percent(s);
  return pct < 0 ? 100 : pct;
}

// A fan's speed step in percent, 1 to 100; 1 (any level) without one.
inline double control_step(const TileState &s) {
  char *end = nullptr;
  const double v = std::strtod(s.step.c_str(), &end);
  if (*end != '\0' || !std::isfinite(v))
    return 1.0;
  return std::min(100.0, std::max(1.0, v));
}

// The level for a tap `offset` pixels into a bar `width` wide: 1 to 100, on
// a fan's speed step. The left end is the lowest level, not off.
inline int control_level_at(int offset, int width, const TileState &s) {
  const long w = std::max(1, width);
  const long clamped = std::max(0L, std::min((long) offset, w));
  const long pct = (clamped * 100 + w / 2) / w;
  // On a step: a step of 1 leaves the level as it is.
  const double step = control_step(s);
  const long speeds = std::max(1L, std::lround(pct / step));
  return (int) std::min(100L, std::lround(speeds * step));
}

// The title while playing, else "Playing", "Paused", "Idle" or "Off".
inline std::string control_media_text(const TileState &s, const ControlWords &w) {
  if (s.state == "playing")
    return s.extra.empty() ? w.playing : s.extra;
  if (s.state == "paused")
    return w.paused;
  if (s.state == "idle")
    return w.idle;
  if (s.state == "off" || s.state == "standby")
    return w.off;
  return s.state;
}

// "Open", "Closed", "40%" part way, "Opening" or "Closing" while it moves.
inline std::string control_cover_text(const TileState &s, const ControlWords &w) {
  if (s.state == "opening")
    return w.opening;
  if (s.state == "closing")
    return w.closing;
  if (s.state == "closed")
    return w.closed;
  if (s.state != "open")
    return s.state;
  const std::string pos = control_number(s.extra);
  if (pos.empty() || pos == "100")
    return w.open;
  if (pos == "0")
    return w.closed;
  return pos + "%";
}

// "21°" for degrees, "640 ppm" for the rest, the bare value without a unit.
inline std::string control_sensor_text(const TileState &s) {
  std::string value = control_number(s.state);
  if (s.extra.empty())
    return value;
  if (s.extra == "°C" || s.extra == "°F")
    return value + "°";
  if (s.extra == "%")
    return value + "%";
  return value + " " + s.extra;
}

// The state line under a tile's label. Scenes and scripts have none. An
// entity HA has not sent (it is away, or the id has a typo) reads as
// unavailable.
inline std::string control_text(ControlKind kind, const TileState &s, const ControlWords &w) {
  if (!control_available(s))
    return w.unavailable;
  switch (kind) {
    case ControlKind::TOGGLE:
      return control_toggle_text(s, w);
    case ControlKind::MEDIA:
      return control_media_text(s, w);
    case ControlKind::COVER:
      return control_cover_text(s, w);
    case ControlKind::SENSOR:
      return control_sensor_text(s);
    default:
      return "";
  }
}

// The HA action a tap performs on the entity, or "" when a tap does
// nothing (a sensor, an entity that is away).
inline std::string control_action(const std::string &entity, const TileState &s) {
  if (!control_available(s))
    return "";
  const std::string d = control_domain(entity);
  switch (control_kind(entity)) {
    case ControlKind::TOGGLE:
      return d + ".toggle";
    case ControlKind::SCENE:
      return d + ".turn_on";
    case ControlKind::MEDIA:
      return "media_player.media_play_pause";
    case ControlKind::COVER:
      if (s.state == "opening" || s.state == "closing")
        return "cover.stop_cover";
      return s.state == "closed" ? "cover.open_cover" : "cover.close_cover";
    default:
      return "";
  }
}

}  // namespace Daruma
