// Host test of the Media app's players and buttons (daruma_media/media.h).
//
//   c++ -std=c++17 -Wall -Wextra -I components/daruma_media \
//       tests/test_media.cpp -o /tmp/test_media && /tmp/test_media

#include <cmath>
#include <cstdio>
#include <string>
#include <vector>

#include "esphome/components/daruma_media/media.h"

using namespace Daruma;

static int failures = 0;

#define CHECK(cond) \
  do { \
    if (!(cond)) { \
      std::printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond); \
      failures++; \
    } \
  } while (0)

static bool near(float a, float b) { return std::fabs(a - b) < 0.001f; }

static MediaPlayer player(const char *entity, MediaState state, uint32_t features = 0) {
  MediaPlayer p;
  p.entity = entity;
  p.state = state;
  p.features = features;
  return p;
}

static const uint32_t ALL = MEDIA_PAUSE | MEDIA_SEEK | MEDIA_VOLUME_SET | MEDIA_PREVIOUS | MEDIA_NEXT | MEDIA_TURN_ON |
                            MEDIA_VOLUME_STEP | MEDIA_STOP | MEDIA_PLAY;

// The bits are HA's MediaPlayerEntityFeature values.
static void test_features() {
  CHECK(MEDIA_PAUSE == 1);
  CHECK(MEDIA_SEEK == 2);
  CHECK(MEDIA_VOLUME_SET == 4);
  CHECK(MEDIA_PREVIOUS == 16);
  CHECK(MEDIA_NEXT == 32);
  CHECK(MEDIA_TURN_ON == 128);
  CHECK(MEDIA_VOLUME_STEP == 1024);
  CHECK(MEDIA_STOP == 4096);
  CHECK(MEDIA_PLAY == 16384);
  // A player HA says nothing about can do nothing.
  const MediaPlayer none;
  CHECK(none.features == 0);
  CHECK(none.position_ms == 0);
  CHECK(!media_can(none, MediaButton::MIDDLE));
  // The row has a slot for every button.
  CHECK(MEDIA_BUTTONS == static_cast<int>(MediaButton::LOUDER) + 1);
}

static void test_states() {
  CHECK(media_state("playing") == MediaState::PLAYING);
  CHECK(media_state("paused") == MediaState::PAUSED);
  CHECK(media_state("buffering") == MediaState::BUFFERING);
  CHECK(media_state("off") == MediaState::OFF);
  CHECK(media_state("standby") == MediaState::OFF);
  CHECK(media_state("idle") == MediaState::IDLE);
  CHECK(media_state("on") == MediaState::IDLE);
  CHECK(media_state("unknown") == MediaState::IDLE);

  CHECK(player("a", MediaState::PLAYING).running());
  CHECK(player("a", MediaState::BUFFERING).running());
  CHECK(!player("a", MediaState::PAUSED).running());
  CHECK(player("a", MediaState::PAUSED).active());
  CHECK(!player("a", MediaState::IDLE).active());
  CHECK(player("a", MediaState::IDLE, MEDIA_NEXT).supports(MEDIA_NEXT));
  CHECK(!player("a", MediaState::IDLE, MEDIA_NEXT).supports(MEDIA_PREVIOUS));
}

// The position runs on while playing, stands still otherwise, and stops at
// the end of the track.
static void test_position() {
  MediaPlayer p = player("a", MediaState::PLAYING);
  CHECK(std::isnan(media_position(p, 5000)));
  p.position = 10.0f;
  p.position_ms = 1000;
  p.duration = 200.0f;
  CHECK(near(media_position(p, 1000), 10.0f));
  CHECK(near(media_position(p, 3500), 12.5f));
  CHECK(near(media_position(p, 1000 + 500000), 200.0f));
  // millis() wraps around.
  p.position_ms = 0xFFFFFC18;  // 1 s before the wrap.
  CHECK(near(media_position(p, 1000), 12.0f));
  p.position_ms = 1000;
  p.state = MediaState::PAUSED;
  CHECK(near(media_position(p, 9000), 10.0f));
  p.state = MediaState::BUFFERING;
  CHECK(near(media_position(p, 9000), 10.0f));
  // No duration (a radio stream): no end.
  p.state = MediaState::PLAYING;
  p.duration = NAN;
  CHECK(near(media_position(p, 1000 + 500000), 510.0f));
  p.duration = 0.0f;
  CHECK(near(media_position(p, 1000 + 500000), 510.0f));
  // A jingle under a second still ends.
  p.duration = 0.5f;
  CHECK(near(media_position(p, 3000), 0.5f));
  p.position = -3.0f;
  p.state = MediaState::PAUSED;
  CHECK(near(media_position(p, 1000), 0.0f));
  p.position = 0.25f;
  CHECK(near(media_position(p, 1000), 0.25f));
}

static void test_time() {
  CHECK(media_time(0.0f) == "0:00");
  CHECK(media_time(5.9f) == "0:05");
  CHECK(media_time(59.0f) == "0:59");
  CHECK(media_time(60.0f) == "1:00");
  CHECK(media_time(754.0f) == "12:34");
  CHECK(media_time(3599.0f) == "59:59");
  CHECK(media_time(3600.0f) == "1:00:00");
  CHECK(media_time(3723.0f) == "1:02:03");
  CHECK(media_time(-1.0f).empty());
  CHECK(media_time(NAN).empty());
}

static void test_pick() {
  std::vector<MediaPlayer> none;
  CHECK(media_find(none, "x") == -1);
  CHECK(media_pick(none, "", false) == -1);
  CHECK(media_pick(none, "x", true) == -1);

  std::vector<MediaPlayer> ps = {player("off", MediaState::OFF), player("idle", MediaState::IDLE),
                                 player("paused", MediaState::PAUSED), player("playing", MediaState::PLAYING),
                                 player("loading", MediaState::BUFFERING)};
  // Nothing shown yet: the first that plays.
  CHECK(media_pick(ps, "", false) == 3);
  CHECK(media_pick(ps, "gone", false) == 3);
  // The one shown stays while it plays; buffering counts.
  CHECK(media_pick(ps, "loading", false) == 4);
  // Shown but not playing: one that plays wins...
  CHECK(media_pick(ps, "paused", false) == 3);
  // ...unless the person picked it.
  CHECK(media_pick(ps, "paused", true) == 2);
  CHECK(media_pick(ps, "off", true) == 0);
  // A pick that is gone falls back to the rules.
  CHECK(media_pick(ps, "gone", true) == 3);

  // Nothing plays: the one shown stays, else the first paused, else the
  // first on, else the first.
  ps[3].state = MediaState::IDLE;
  ps[4].state = MediaState::IDLE;
  CHECK(media_pick(ps, "idle", false) == 1);
  CHECK(media_pick(ps, "", false) == 2);
  ps[2].state = MediaState::IDLE;
  CHECK(media_pick(ps, "", false) == 1);
  std::vector<MediaPlayer> dark = {player("a", MediaState::OFF), player("b", MediaState::OFF)};
  CHECK(media_pick(dark, "", false) == 0);
  CHECK(media_pick(dark, "b", false) == 1);
  CHECK(media_find(dark, "b") == 1);
  CHECK(media_find(dark, "c") == -1);

  // The first player counts too: playing, shown, paused, on.
  std::vector<MediaPlayer> first = {player("a", MediaState::PLAYING), player("b", MediaState::PAUSED)};
  CHECK(media_pick(first, "", false) == 0);
  first[0].state = MediaState::IDLE;
  CHECK(media_pick(first, "a", false) == 0);
  first = {player("a", MediaState::PAUSED), player("b", MediaState::PAUSED)};
  CHECK(media_pick(first, "", false) == 0);
  first = {player("a", MediaState::IDLE), player("b", MediaState::IDLE)};
  CHECK(media_pick(first, "", false) == 0);
  first = {player("a", MediaState::OFF), player("b", MediaState::IDLE)};
  CHECK(media_pick(first, "", false) == 1);
}

static void test_middle() {
  // Off: power, when it can turn on.
  CHECK(media_middle(player("a", MediaState::OFF, MEDIA_TURN_ON)) == MediaMiddle::POWER);
  CHECK(media_middle(player("a", MediaState::OFF, ALL & ~MEDIA_TURN_ON)) == MediaMiddle::NONE);
  // Playing: pause, else stop.
  CHECK(media_middle(player("a", MediaState::PLAYING, ALL)) == MediaMiddle::PAUSE);
  CHECK(media_middle(player("a", MediaState::BUFFERING, MEDIA_PAUSE)) == MediaMiddle::PAUSE);
  CHECK(media_middle(player("a", MediaState::PLAYING, MEDIA_STOP | MEDIA_PLAY)) == MediaMiddle::STOP);
  CHECK(media_middle(player("a", MediaState::PLAYING, MEDIA_PLAY)) == MediaMiddle::NONE);
  // Paused or idle: play, with PLAY or PAUSE.
  CHECK(media_middle(player("a", MediaState::PAUSED, MEDIA_PLAY)) == MediaMiddle::PLAY);
  CHECK(media_middle(player("a", MediaState::IDLE, MEDIA_PAUSE)) == MediaMiddle::PLAY);
  CHECK(media_middle(player("a", MediaState::IDLE, MEDIA_NEXT)) == MediaMiddle::NONE);
}

static void test_can() {
  MediaPlayer p = player("a", MediaState::PLAYING, MEDIA_PREVIOUS);
  CHECK(media_can(p, MediaButton::PREVIOUS));
  CHECK(!media_can(p, MediaButton::NEXT));
  CHECK(!media_can(p, MediaButton::MIDDLE));
  p.features = MEDIA_NEXT;
  CHECK(media_can(p, MediaButton::NEXT));
  CHECK(!media_can(p, MediaButton::PREVIOUS));
  // Volume: set with a known volume, or steps.
  p.features = MEDIA_VOLUME_SET;
  CHECK(!media_can(p, MediaButton::LOUDER));
  p.volume = 0.5f;
  CHECK(media_can(p, MediaButton::LOUDER));
  CHECK(media_can(p, MediaButton::QUIETER));
  p.volume = NAN;
  p.features = MEDIA_VOLUME_STEP;
  CHECK(media_can(p, MediaButton::QUIETER));
  // Off: only power.
  MediaPlayer off = player("a", MediaState::OFF, ALL);
  off.volume = 0.5f;
  CHECK(media_can(off, MediaButton::MIDDLE));
  CHECK(!media_can(off, MediaButton::PREVIOUS));
  CHECK(!media_can(off, MediaButton::NEXT));
  CHECK(!media_can(off, MediaButton::LOUDER));
}

static void test_volume() {
  CHECK(near(media_volume_step(0.5f, 0.05f, 1), 0.55f));
  CHECK(near(media_volume_step(0.5f, 0.05f, -1), 0.45f));
  // Onto the step's grid.
  CHECK(near(media_volume_step(0.33f, 0.05f, 1), 0.40f));
  CHECK(near(media_volume_step(0.33f, 0.05f, -1), 0.30f));
  // Within 0..1.
  CHECK(near(media_volume_step(0.98f, 0.05f, 1), 1.0f));
  CHECK(near(media_volume_step(1.0f, 0.05f, 1), 1.0f));
  CHECK(near(media_volume_step(0.02f, 0.05f, -1), 0.0f));
  CHECK(near(media_volume_step(0.0f, 0.1f, -1), 0.0f));
  CHECK(std::isnan(media_volume_step(NAN, 0.05f, 1)));
  CHECK(std::isnan(media_volume_step(NAN, 0.05f, -1)));
  CHECK(std::isnan(media_volume_step(0.5f, 0.0f, 1)));
}

static void test_commands() {
  MediaPlayer p = player("a", MediaState::PLAYING, ALL);
  p.volume = 0.5f;
  CHECK(media_command(p, MediaButton::MIDDLE, 0.05f).action == "media_player.media_pause");
  CHECK(media_command(p, MediaButton::PREVIOUS, 0.05f).action == "media_player.media_previous_track");
  CHECK(media_command(p, MediaButton::NEXT, 0.05f).action == "media_player.media_next_track");
  const MediaCommand up = media_command(p, MediaButton::LOUDER, 0.05f);
  CHECK(up.action == "media_player.volume_set");
  CHECK(near(up.value, 0.55f));
  const MediaCommand down = media_command(p, MediaButton::QUIETER, 0.1f);
  CHECK(near(down.value, 0.4f));
  // Only steps: volume_up and volume_down, with no value.
  p.features = MEDIA_VOLUME_STEP;
  CHECK(media_command(p, MediaButton::LOUDER, 0.05f).action == "media_player.volume_up");
  CHECK(media_command(p, MediaButton::QUIETER, 0.05f).action == "media_player.volume_down");
  CHECK(std::isnan(media_command(p, MediaButton::QUIETER, 0.05f).value));
  // A button that can't act sends nothing.
  CHECK(media_command(p, MediaButton::NEXT, 0.05f).action.empty());
  CHECK(media_command(p, MediaButton::MIDDLE, 0.05f).action.empty());

  CHECK(media_middle_action(player("a", MediaState::PAUSED, MEDIA_PLAY)) == "media_player.media_play");
  CHECK(media_middle_action(player("a", MediaState::PAUSED, MEDIA_PAUSE)) == "media_player.media_play_pause");
  CHECK(media_middle_action(player("a", MediaState::PLAYING, MEDIA_STOP)) == "media_player.media_stop");
  CHECK(media_middle_action(player("a", MediaState::OFF, MEDIA_TURN_ON)) == "media_player.turn_on");
  CHECK(media_middle_action(player("a", MediaState::OFF)).empty());
}

// The screen answers before HA does.
static void test_expect() {
  MediaPlayer p = player("a", MediaState::PLAYING, ALL);
  p.position = 10.0f;
  p.position_ms = 0;
  p.volume = 0.5f;
  media_expect(p, MediaCommand{"media_player.media_pause"}, 4000);
  CHECK(p.state == MediaState::PAUSED);
  CHECK(near(p.position, 14.0f));
  CHECK(p.position_ms == 4000);
  CHECK(near(media_position(p, 9000), 14.0f));
  media_expect(p, MediaCommand{"media_player.media_play"}, 9000);
  CHECK(p.state == MediaState::PLAYING);
  CHECK(near(media_position(p, 10000), 15.0f));
  media_expect(p, MediaCommand{"media_player.media_stop"}, 10000);
  CHECK(p.state == MediaState::PAUSED);
  media_expect(p, MediaCommand{"media_player.media_play_pause"}, 10000);
  CHECK(p.state == MediaState::PLAYING);
  media_expect(p, MediaCommand{"media_player.media_next_track"}, 12000);
  CHECK(near(p.position, 0.0f));
  CHECK(p.position_ms == 12000);
  CHECK(p.state == MediaState::PLAYING);
  media_expect(p, MediaCommand{"media_player.media_previous_track"}, 13000);
  CHECK(near(p.position, 0.0f));
  media_expect(p, MediaCommand{"media_player.volume_set", 0.65f}, 13000);
  CHECK(near(p.volume, 0.65f));
  CHECK(p.state == MediaState::PLAYING);
  // Power and steps wait for HA.
  media_expect(p, MediaCommand{"media_player.turn_on"}, 20000);
  CHECK(p.state == MediaState::PLAYING);
  CHECK(p.position_ms == 13000);
  // No position: a new track has none either.
  p.position = NAN;
  media_expect(p, MediaCommand{"media_player.media_next_track"}, 20000);
  CHECK(std::isnan(p.position));
}

static void test_seek() {
  MediaPlayer p = player("a", MediaState::PLAYING, MEDIA_SEEK);
  CHECK(media_seek_command(p, 0.5f).action.empty());  // No length.
  p.duration = 200.0f;
  const MediaCommand half = media_seek_command(p, 0.5f);
  CHECK(half.action == "media_player.media_seek");
  CHECK(near(half.value, 100.0f));
  CHECK(near(media_seek_command(p, 0.3333f).value, 67.0f));
  CHECK(near(media_seek_command(p, -1.0f).value, 0.0f));
  CHECK(near(media_seek_command(p, 2.0f).value, 200.0f));
  // A track under a second can be sought too.
  p.duration = 0.6f;
  CHECK(near(media_seek_command(p, 1.0f).value, 1.0f));
  CHECK(near(media_seek_command(p, 0.4f).value, 0.0f));
  p.duration = 200.0f;
  p.state = MediaState::PAUSED;
  CHECK(!media_seek_command(p, 0.5f).action.empty());
  p.state = MediaState::IDLE;
  CHECK(media_seek_command(p, 0.5f).action.empty());
  p.state = MediaState::PLAYING;
  p.duration = 0.0f;
  CHECK(media_seek_command(p, 0.5f).action.empty());
  p.duration = 200.0f;
  p.features = MEDIA_PAUSE;
  CHECK(media_seek_command(p, 0.5f).action.empty());

  p.features = MEDIA_SEEK;
  p.position = 5.0f;
  media_expect(p, media_seek_command(p, 0.25f), 7000);
  CHECK(near(p.position, 50.0f));
  CHECK(p.position_ms == 7000);
  CHECK(p.state == MediaState::PLAYING);
}

// Until HA catches up, a reply keeps what the command expects.
static void test_hold() {
  MediaHold hold;
  hold.entity = "a";
  hold.expected = player("a", MediaState::PAUSED);
  hold.expected.position = 42.0f;
  hold.expected.position_ms = 1000;
  hold.expected.volume = 0.6f;
  hold.state = true;
  hold.until_ms = 3000;

  MediaPlayer fresh = player("a", MediaState::PLAYING);
  fresh.position = 40.0f;
  fresh.volume = 0.5f;
  CHECK(media_hold(fresh, hold, 2000));
  CHECK(fresh.state == MediaState::PAUSED);
  CHECK(near(fresh.position, 42.0f));
  CHECK(fresh.position_ms == 1000);
  CHECK(near(fresh.volume, 0.5f));  // The command left the volume alone.

  // HA caught up: nothing to keep.
  MediaPlayer caught = player("a", MediaState::PAUSED);
  caught.position = 43.0f;
  CHECK(!media_hold(caught, hold, 2000));
  CHECK(near(caught.position, 43.0f));
  // Too late, or another player.
  MediaPlayer late = player("a", MediaState::PLAYING);
  CHECK(!media_hold(late, hold, 3000));
  CHECK(late.state == MediaState::PLAYING);
  MediaPlayer other = player("b", MediaState::PLAYING);
  CHECK(!media_hold(other, hold, 2000));
  CHECK(other.state == MediaState::PLAYING);

  // A volume command keeps the volume, not the state.
  hold.state = false;
  hold.volume = true;
  MediaPlayer loud = player("a", MediaState::PLAYING);
  loud.volume = 0.5f;
  CHECK(media_hold(loud, hold, 2999));
  CHECK(near(loud.volume, 0.6f));
  CHECK(loud.state == MediaState::PLAYING);
  loud.volume = 0.6f;
  CHECK(!media_hold(loud, hold, 2000));
  hold.expected.volume = NAN;
  loud.volume = 0.5f;
  CHECK(!media_hold(loud, hold, 2000));
  CHECK(near(loud.volume, 0.5f));
  // millis() wraps around.
  hold.expected.volume = 0.6f;
  hold.until_ms = 1000;
  CHECK(media_hold(loud, hold, 0xFFFFFF00));
}

static void test_urls() {
  const std::string path = "/api/media_player_proxy/media_player.kitchen?token=abc&cache=1f";
  CHECK(media_cover_url("http://ha.local:8123", path) == "http://ha.local:8123" + path);
  CHECK(media_cover_url("http://ha.local:8123//", path) == "http://ha.local:8123" + path);
  CHECK(media_cover_url("http://ha.local:8123", "local/x.png") == "http://ha.local:8123/local/x.png");
  CHECK(media_cover_url("http://ha.local:8123", "https://img.example/a.jpg") == "https://img.example/a.jpg");
  CHECK(media_cover_url("", "http://img.example/a.jpg") == "http://img.example/a.jpg");
  CHECK(media_cover_url("", path).empty());
  CHECK(media_cover_url("/", path).empty());
  CHECK(media_cover_url("ha.local:8123", path).empty());
  CHECK(media_cover_url("https://ha.example", path) == "https://ha.example" + path);
  CHECK(media_cover_url("ftp://ha.local", "ftp://img/a.jpg").empty());
  CHECK(media_is_http("http://a"));
  CHECK(media_is_http("https://a"));
  CHECK(!media_is_http("httpx://a"));
  CHECK(!media_is_http(" http://a"));

  // The access token changes; the key does not.
  CHECK(media_cover_key("http://h/p?token=abc&cache=1f") == "http://h/p?cache=1f");
  CHECK(media_cover_key("http://h/p?token=xyz&cache=1f") == "http://h/p?cache=1f");
  CHECK(media_cover_key("http://h/p?cache=1f&token=abc") == "http://h/p?cache=1f");
  CHECK(media_cover_key("http://h/p?a=1&token=abc&b=2") == "http://h/p?a=1&b=2");
  CHECK(media_cover_key("http://h/p?mytoken=1") == "http://h/p?mytoken=1");
  CHECK(media_cover_key("http://h/p?token=1") == "http://h/p?");
  CHECK(media_cover_key("http://h/p?xtoken=1&token=2") == "http://h/p?xtoken=1");
  CHECK(media_cover_key("http://h/p?a=1&&b=2&") == "http://h/p?a=1&b=2");
  CHECK(media_cover_key("http://h/p.jpg") == "http://h/p.jpg");
  CHECK(media_cover_key("").empty());
  CHECK(media_cover_url("http://ha.local:8123", "").empty());

  CHECK(media_base_url("192.168.1.5", 8123) == "http://192.168.1.5:8123");
  CHECK(media_base_url("::ffff:192.168.1.5", 8123) == "http://192.168.1.5:8123");
  CHECK(media_base_url("fe80::1%wlan0", 8123) == "http://[fe80::1]:8123");
  CHECK(media_base_url("::ffff:abcd", 80) == "http://[::ffff:abcd]:80");
  CHECK(media_base_url("", 8123).empty());
  CHECK(media_base_url(":ffff:1.2.3.4", 80) == "http://[:ffff:1.2.3.4]:80");
  CHECK(media_base_url("%x", 8123).empty());
}

int main() {
  test_features();
  test_states();
  test_position();
  test_time();
  test_pick();
  test_middle();
  test_can();
  test_volume();
  test_commands();
  test_expect();
  test_seek();
  test_hold();
  test_urls();
  if (failures == 0)
    std::printf("All media checks passed\n");
  return failures == 0 ? 0 : 1;
}
