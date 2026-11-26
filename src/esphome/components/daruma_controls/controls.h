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
#include <cstdio>
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
  std::string extra;  // The attribute: brightness, title, position or unit.
};

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
  const double r = std::round(v * 10.0) / 10.0;
  char buf[24];
  if (r == std::floor(r)) {
    std::snprintf(buf, sizeof buf, "%.0f", r);
  } else {
    std::snprintf(buf, sizeof buf, "%.1f", r);
  }
  // "-0" reads oddly.
  return std::string(buf) == "-0" ? std::string("0") : std::string(buf);
}

// "On · 60%" for a light at brightness 153 of 255; "On" without one.
inline std::string control_toggle_text(const TileState &s, const ControlWords &w) {
  if (s.state == "off")
    return w.off;
  if (s.state != "on")
    return s.state;
  char *end = nullptr;
  const long b = std::strtol(s.extra.c_str(), &end, 10);
  if (s.extra.empty() || end == nullptr || *end != '\0')
    return w.on;
  const long pct = std::lround(std::max(0L, std::min(255L, b)) * 100.0 / 255.0);
  return w.on + " · " + std::to_string(pct) + "%";
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
  const std::string value = control_number(s.state);
  if (s.extra.empty())
    return value;
  if (s.extra == "°C" || s.extra == "°F")
    return value + "°";
  if (s.extra == "%")
    return value + "%";
  return value + " " + s.extra;
}

// The state line under a tile's label. Scenes and scripts have none.
inline std::string control_text(ControlKind kind, const TileState &s, const ControlWords &w) {
  if (!s.known)
    return "";
  if (s.state == "unavailable")
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
