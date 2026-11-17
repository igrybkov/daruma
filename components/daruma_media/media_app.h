#pragma once

// The Media app: a remote for the Home Assistant media players in the
// device's room. The cover, the title, the artist and the album, the
// position, and a row of buttons: previous, play or pause, next, quieter,
// louder. With several players, a swipe changes the one on screen.
//
// Fetching is a YAML script (daruma/app_media.yaml) that this class runs
// through the fetcher, through the hub's gate for HA calls (ha_calls.h).
// HA renders the players into one reply. The buttons call media_player
// actions through the commander. The cover comes from HA over HTTP, into
// an online_image, through the cover loader.
//
// The rules (which player, which buttons, the position clock) are plain
// C++ in media.h.

#include <functional>
#include <string>
#include <vector>

#include "esphome/components/daruma/hub.h"
#include "esphome/components/json/json_util.h"
#include "esphome/core/component.h"
#include "media.h"

namespace Daruma {

class MediaApp : public esphome::Component {
 public:
  // Asks HA for the players: `players` is the setting (entity ids and
  // areas, comma-separated; empty for the device's own area), `area` the
  // area found last time ("" looks again). The reply goes to on_reply() or
  // on_error() with the same request number.
  using Fetcher = std::function<void(int request, const std::string &players, const std::string &area)>;
  // Runs one media_player action on one entity. `value` goes with
  // volume_set and media_seek; NAN for none.
  using Commander = std::function<void(const std::string &action, const std::string &entity, float value)>;
  // Downloads a cover into the image; "" lets it go.
  using CoverLoader = std::function<void(const std::string &url)>;

  void set_hub(Hub *hub) { this->hub_ = hub; }
  void set_refresh_interval(uint32_t ms) { this->refresh_ms_ = ms; }
  void set_idle_refresh(uint32_t ms) { this->idle_refresh_ms_ = ms; }
  void set_command_refresh(uint32_t ms) { this->command_refresh_ms_ = ms; }
  void set_hold(uint32_t ms) { this->hold_ms_ = ms; }
  void set_timeout(uint32_t ms) { this->timeout_ms_ = ms; }
  void set_volume_step(float step) { this->volume_step_ = step; }
  void set_cover_size(int size) { this->cover_size_ = size; }
  void set_fetcher(Fetcher fetcher) { this->fetcher_ = std::move(fetcher); }
  void set_commander(Commander commander) { this->commander_ = std::move(commander); }
  void set_cover_loader(CoverLoader loader) { this->cover_loader_ = std::move(loader); }
  void set_cover_image(esphome::display::BaseImage *image) { this->cover_image_ = image; }
  // The theme keys' prefix and the actions' module: the app's id.
  void set_theme_prefix(const std::string &prefix) { this->prefix_ = prefix; }
  // The "Media players" setting.
  void set_players(const std::string &players);
  // The "Home Assistant URL" setting; "" for HA's address on port `port`.
  void set_base_url(const std::string &url) { this->base_url_ = url; }
  void set_ha_port(int port) { this->ha_port_ = port; }

  void loop() override;
  float get_setup_priority() const override { return esphome::setup_priority::LATE; }

  // Fills in the app's hooks and adds it. The package's actions
  // (<prefix>.play_pause, .next, ...) get button hooks: Pause while a
  // player plays, and no button the player can't use.
  void add_to(Hub &hub, App app);

  // App hooks, for Daruma::App.
  std::string status();
  std::string title();
  void draw(AppView &v);
  bool input(Input input, int x, int y);
  void on_open();
  void on_close();
  void set_enabled(bool enabled) { this->enabled_ = enabled; }

  // A button of the player on screen, as a binding or a menu runs it. With
  // no players yet, it runs after the next reply.
  void press(MediaButton button);

  // Fetch results.
  void on_reply(int request, ArduinoJson::JsonObjectConst reply);
  void on_error(int request, const std::string &error);
  // The cover loader's download ended.
  void on_cover(bool ok);

  const std::vector<MediaPlayer> &players() const { return this->players_; }
  const MediaPlayer *shown() const;

 protected:
  enum class Failure { NONE, OFFLINE, ERROR };
  // What the screen shows where: computed by draw(), used by input().
  struct Geometry {
    Rect cover;
    Rect bar;  // The position bar, with room to tap around it.
    Rect buttons[MEDIA_BUTTONS];
    Rect dots;
  };

  bool due_(uint32_t now_ms) const;
  void tick_(uint32_t now_ms);
  bool linked_(uint32_t now_ms);
  void send_();
  void parse_(ArduinoJson::JsonVariantConst body);
  void show_(int index);
  void step_player_(int direction);
  void run_(const MediaCommand &command);
  void update_cover_();
  std::string base_url_now_() const;
  std::string word_(const char *key) const;
  std::string safe_(const std::string &text) const;
  bool can_press_(int item) const;
  bool press_item_(int item);
  int focus_count_() const;
  void move_focus_(int direction);
  bool retry_();
  void redraw_();
  bool tap_(int x, int y);

  void draw_message_(AppView &v, const std::string &message);
  void draw_cover_(AppView &v, const MediaPlayer &p);
  void draw_text_(AppView &v, const MediaPlayer &p, int tx, int tw);
  void draw_bar_(AppView &v, const MediaPlayer &p, int top);
  void draw_volume_(AppView &v, const MediaPlayer &p, int top);
  void draw_buttons_(AppView &v, const MediaPlayer &p, int cy);
  void draw_dots_(AppView &v, int x, int y);

  Hub *hub_{nullptr};
  Fetcher fetcher_;
  Commander commander_;
  CoverLoader cover_loader_;
  esphome::display::BaseImage *cover_image_{nullptr};
  std::string prefix_{"media"};
  std::string players_setting_;
  std::string base_url_;
  int ha_port_{8123};
  uint32_t refresh_ms_{5000};
  uint32_t idle_refresh_ms_{60000};
  uint32_t command_refresh_ms_{1000};
  uint32_t hold_ms_{3000};
  uint32_t timeout_ms_{10000};
  float volume_step_{0.05f};
  int cover_size_{96};

  std::vector<MediaPlayer> players_;
  bool have_players_{false};
  std::string area_;     // The device's area, as HA found it.
  std::string current_;  // The player on screen.
  bool chosen_{false};   // The person picked it.
  MediaHold hold_;

  bool pending_{false};
  int request_{0};
  uint32_t sent_ms_{0};
  uint32_t fetched_ms_{0};
  bool fetch_soon_{false};     // A fetch sooner than the refresh (after a command)...
  uint32_t next_fetch_ms_{0};  // ...at this time.
  bool want_fetch_{false};
  Failure failure_{Failure::NONE};
  bool queued_{false};  // A button waits for the first reply.
  MediaButton queued_button_{MediaButton::MIDDLE};

  std::string cover_want_;     // The URL for the player on screen.
  std::string cover_loading_;  // Downloading now.
  std::string cover_loaded_;   // In the image (its key, without the token).
  bool cover_busy_{false};
  std::string cover_failed_;  // A URL that failed; a new token tries again.

  uint32_t volume_until_ms_{0};  // The volume shows instead of the position.
  int focus_{1};                 // The focused item: a button, or the players (5).
  Geometry geometry_;
  int origin_x_{0};  // The app area's corner: input comes relative to it.
  int origin_y_{0};
  esphome::display::BaseFont *text_font_{nullptr};  // For names outside draw().
  std::string app_name_;

  bool open_{false};
  bool enabled_{true};
  uint32_t connected_ms_{0};
  uint32_t tick_ms_{0};
  uint32_t second_ms_{0};
};

}  // namespace Daruma
