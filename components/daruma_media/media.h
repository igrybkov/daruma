#pragma once

// What the Media app knows about the players it controls, and the rules
// for its buttons. Plain C++ with no ESPHome includes, so a host test can
// check it (tests/test_media.cpp).
//
// A player is one Home Assistant media_player entity. Its state, features
// and attributes come from HA; the app keeps the list and picks the one on
// screen.

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <string>
#include <vector>

namespace Daruma {

// HA's MediaPlayerEntityFeature bits that the app's buttons need.
enum MediaFeature : uint32_t {
  MEDIA_PAUSE = 1,
  MEDIA_SEEK = 2,
  MEDIA_VOLUME_SET = 4,
  MEDIA_PREVIOUS = 16,
  MEDIA_NEXT = 32,
  MEDIA_TURN_ON = 128,
  MEDIA_VOLUME_STEP = 1024,
  MEDIA_STOP = 4096,
  MEDIA_PLAY = 16384,
};

enum class MediaState : uint8_t { OFF, IDLE, PLAYING, PAUSED, BUFFERING };

// HA's state of a media player. "standby" counts as off; "on", "idle" and
// anything new as idle.
inline MediaState media_state(const std::string &state) {
  if (state == "playing")
    return MediaState::PLAYING;
  if (state == "paused")
    return MediaState::PAUSED;
  if (state == "buffering")
    return MediaState::BUFFERING;
  if (state == "off" || state == "standby")
    return MediaState::OFF;
  return MediaState::IDLE;
}

struct MediaPlayer {
  std::string entity;  // media_player.kitchen
  std::string name;    // HA's friendly name.
  MediaState state{MediaState::IDLE};
  std::string title;
  std::string artist;
  std::string album;
  // The cover: HA's path ("/api/media_player_proxy/...") or a full URL;
  // empty for none.
  std::string picture;
  float duration{NAN};      // Seconds; NAN when HA has none.
  float position{NAN};      // Seconds, at position_ms.
  uint32_t position_ms{0};  // millis() when position was true.
  float volume{NAN};        // 0..1; NAN when HA has none.
  uint32_t features{0};

  bool supports(uint32_t feature) const { return (this->features & feature) != 0; }
  // Playing or about to: the position runs on.
  bool running() const { return this->state == MediaState::PLAYING || this->state == MediaState::BUFFERING; }
  // Something is loaded: playing, buffering or paused.
  bool active() const { return this->running() || this->state == MediaState::PAUSED; }
};

// The position now, in seconds: it runs on from the reply while the player
// plays, and stops at the duration. NAN when HA gave none.
inline float media_position(const MediaPlayer &p, uint32_t now_ms) {
  if (std::isnan(p.position))
    return NAN;
  float at = p.position;
  if (p.state == MediaState::PLAYING)
    at += (float) (uint32_t) (now_ms - p.position_ms) / 1000.0f;
  if (!std::isnan(p.duration) && p.duration > 0.0f)
    at = std::min(at, p.duration);
  return std::max(at, 0.0f);
}

// "0:05", "12:00", "1:02:03"; empty for NAN or less than zero.
inline std::string media_time(float seconds) {
  if (std::isnan(seconds) || seconds < 0.0f)
    return "";
  const long total = (long) seconds;
  char buf[24];  // pragma: no mutate (room to spare)
  if (total >= 3600)
    std::snprintf(buf, sizeof(buf), "%ld:%02ld:%02ld", total / 3600, total / 60 % 60, total % 60);
  else
    std::snprintf(buf, sizeof(buf), "%ld:%02ld", total / 60, total % 60);
  return buf;
}

inline int media_find(const std::vector<MediaPlayer> &players, const std::string &entity) {
  for (size_t i = 0; i < players.size(); i++) {
    if (players[i].entity == entity)
      return (int) i;
  }
  return -1;
}

// Which player to show; -1 for none. A player the person picked (`chosen`)
// stays while it is there. Otherwise the one shown stays while it plays,
// else the first that plays wins, then the one shown, then the first
// paused, then the first that is on.
inline int media_pick(const std::vector<MediaPlayer> &players, const std::string &current, bool chosen) {
  const int shown = media_find(players, current);
  if (shown >= 0 && (chosen || players[shown].running()))
    return shown;
  for (size_t i = 0; i < players.size(); i++) {
    if (players[i].running())
      return (int) i;
  }
  if (shown >= 0)
    return shown;
  for (size_t i = 0; i < players.size(); i++) {
    if (players[i].state == MediaState::PAUSED)
      return (int) i;
  }
  for (size_t i = 0; i < players.size(); i++) {
    if (players[i].state != MediaState::OFF)
      return (int) i;
  }
  return players.empty() ? -1 : 0;
}

// The row of buttons, left to right.
enum class MediaButton : uint8_t { PREVIOUS, MIDDLE, NEXT, QUIETER, LOUDER };
static const int MEDIA_BUTTONS = 5;

// What the middle button does now.
enum class MediaMiddle : uint8_t { NONE, PLAY, PAUSE, STOP, POWER };

inline MediaMiddle media_middle(const MediaPlayer &p) {
  if (p.state == MediaState::OFF)
    return p.supports(MEDIA_TURN_ON) ? MediaMiddle::POWER : MediaMiddle::NONE;
  if (p.running()) {
    if (p.supports(MEDIA_PAUSE))
      return MediaMiddle::PAUSE;
    return p.supports(MEDIA_STOP) ? MediaMiddle::STOP : MediaMiddle::NONE;
  }
  // HA's media_play_pause plays a paused player that only claims PAUSE.
  return p.supports(MEDIA_PLAY | MEDIA_PAUSE) ? MediaMiddle::PLAY : MediaMiddle::NONE;
}

// A button can act now. Off, only the middle one (power) can.
inline bool media_can(const MediaPlayer &p, MediaButton b) {
  if (b == MediaButton::MIDDLE)
    return media_middle(p) != MediaMiddle::NONE;
  if (p.state == MediaState::OFF)
    return false;
  switch (b) {
    case MediaButton::PREVIOUS:
      return p.supports(MEDIA_PREVIOUS);
    case MediaButton::NEXT:
      return p.supports(MEDIA_NEXT);
    default:
      return (p.supports(MEDIA_VOLUME_SET) && !std::isnan(p.volume)) || p.supports(MEDIA_VOLUME_STEP);
  }
}

// The volume one step up (direction 1) or down (-1), on the step's grid,
// within 0..1. NAN when the volume is unknown or the step is 0: NAN runs
// through the sum and every comparison.
inline float media_volume_step(float volume, float step, int direction) {
  const float next = std::round((volume + (float) direction * step) / step) * step;
  return std::min(std::max(next, 0.0f), 1.0f);
}

// The HA action for a button, and the volume to send with volume_set (NAN
// for none). Empty when the button can't act.
struct MediaCommand {
  std::string action;
  float value{NAN};
};

// The HA action of the middle button now.
inline std::string media_middle_action(const MediaPlayer &p) {
  switch (media_middle(p)) {
    case MediaMiddle::POWER:
      return "media_player.turn_on";
    case MediaMiddle::PAUSE:
      return "media_player.media_pause";
    case MediaMiddle::STOP:
      return "media_player.media_stop";
    case MediaMiddle::PLAY:
      return p.supports(MEDIA_PLAY) ? "media_player.media_play" : "media_player.media_play_pause";
    default:
      return "";
  }
}

inline MediaCommand media_command(const MediaPlayer &p, MediaButton b, float step) {
  if (!media_can(p, b))
    return {};
  switch (b) {
    case MediaButton::PREVIOUS:
      return {"media_player.media_previous_track"};
    case MediaButton::NEXT:
      return {"media_player.media_next_track"};
    case MediaButton::MIDDLE:
      return {media_middle_action(p)};
    default: {
      const bool louder = b == MediaButton::LOUDER;
      if (p.supports(MEDIA_VOLUME_SET) && !std::isnan(p.volume))
        return {"media_player.volume_set", media_volume_step(p.volume, step, louder ? 1 : -1)};
      return {louder ? "media_player.volume_up" : "media_player.volume_down"};
    }
  }
}

// A seek to a part of the track (0..1), when the player can seek and HA
// knows the track's length. Empty otherwise.
inline MediaCommand media_seek_command(const MediaPlayer &p, float fraction) {
  if (!p.supports(MEDIA_SEEK) || !p.active() || std::isnan(p.duration) || p.duration <= 0.0f)
    return {};
  return {"media_player.media_seek", std::round(std::min(std::max(fraction, 0.0f), 1.0f) * p.duration)};
}

// The player as it will be once HA has done the command, so the screen
// answers at once. The next reply from HA corrects it.
inline void media_expect(MediaPlayer &p, const MediaCommand &c, uint32_t now_ms) {
  const float at = media_position(p, now_ms);
  if (c.action == "media_player.media_pause" || c.action == "media_player.media_stop") {
    p.state = MediaState::PAUSED;
  } else if (c.action == "media_player.media_play" || c.action == "media_player.media_play_pause") {
    p.state = MediaState::PLAYING;
  } else if (c.action == "media_player.media_next_track" || c.action == "media_player.media_previous_track") {
    p.position = std::isnan(at) ? NAN : 0.0f;
    p.position_ms = now_ms;
    return;
  } else if (c.action == "media_player.volume_set") {
    p.volume = c.value;
    return;
  } else if (c.action == "media_player.media_seek") {
    p.position = c.value;
    p.position_ms = now_ms;
    return;
  } else {
    return;
  }
  p.position = at;
  p.position_ms = now_ms;
}

// What a command expects, kept while HA catches up. A reply that comes in
// before `until_ms` and still shows the old state or volume gets the
// expected one instead, so a button does not flip back and forth.
struct MediaHold {
  std::string entity;
  MediaPlayer expected;
  // A hold made before any command names no player; every player has one.
  bool state{false};     // The command changes the state. pragma: no mutate
  bool volume{false};    // The command changes the volume.
  uint32_t until_ms{0};  // pragma: no mutate
};

// Applies the hold to a fresh player from HA. Returns true when it kept
// something HA did not show yet.
inline bool media_hold(MediaPlayer &fresh, const MediaHold &hold, uint32_t now_ms) {
  if (fresh.entity != hold.entity || (int32_t) (now_ms - hold.until_ms) >= 0)
    return false;
  bool kept = false;
  if (hold.state && fresh.state != hold.expected.state) {
    fresh.state = hold.expected.state;
    fresh.position = hold.expected.position;
    fresh.position_ms = hold.expected.position_ms;
    kept = true;
  }
  if (hold.volume && !std::isnan(hold.expected.volume) && fresh.volume != hold.expected.volume) {
    fresh.volume = hold.expected.volume;
    kept = true;
  }
  return kept;
}

inline bool media_is_http(const std::string &url) {
  return url.rfind("http://", 0) == 0 || url.rfind("https://", 0) == 0;
}

// The cover's URL: HA's path joined to its base URL. A full URL stays as
// it is. Empty without a picture, or without an http(s) base for a path.
inline std::string media_cover_url(const std::string &base, const std::string &picture) {
  if (picture.empty())
    return "";
  if (media_is_http(picture))
    return picture;
  std::string root = base;
  while (!root.empty() && root.back() == '/')
    root.pop_back();
  if (!media_is_http(root))
    return "";
  return picture[0] == '/' ? root + picture : root + "/" + picture;
}

// The cover's URL without HA's access token, which changes every few
// minutes: the same cover keeps the same key.
inline std::string media_cover_key(const std::string &url) {
  const size_t query = url.find('?');
  if (query == std::string::npos)
    return url;
  std::string key = url.substr(0, query + 1);
  // Every part ends with '&'.
  const std::string rest = url.substr(query + 1) + "&";
  for (size_t from = 0, amp = rest.find('&'); amp != std::string::npos; from = amp + 1, amp = rest.find('&', from)) {
    const std::string part = rest.substr(from, amp - from);
    if (part.empty() || part.compare(0, 6, "token=") == 0)
      continue;
    key += (key.back() == '?' ? "" : "&") + part;
  }
  return key;
}

// HA's base URL from the address it connects to the device from:
// "http://192.168.1.5:8123". An IPv4 address in IPv6 form loses its prefix;
// an IPv6 address goes in brackets, without its zone. Empty for no address.
inline std::string media_base_url(std::string peer, int port) {
  const std::string mapped = "::ffff:";
  if (peer.compare(0, mapped.size(), mapped) == 0 && peer.find('.') != std::string::npos)
    peer = peer.substr(mapped.size());
  const size_t zone = peer.find('%');
  if (zone != std::string::npos)
    peer = peer.substr(0, zone);
  if (peer.empty())
    return "";
  if (peer.find(':') != std::string::npos)
    peer = "[" + peer + "]";
  return "http://" + peer + ":" + std::to_string(port);
}

}  // namespace Daruma
