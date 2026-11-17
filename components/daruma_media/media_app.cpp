#include "media_app.h"

#include <algorithm>
#include <array>

#include "esphome/components/api/api_connection.h"
#include "esphome/components/api/api_server.h"
#include "esphome/components/daruma/draw.h"
#include "esphome/components/daruma/text.h"
#include "esphome/components/daruma/ui_tree.h"
#include "esphome/core/hal.h"
#include "esphome/core/log.h"

namespace Daruma {

using esphome::Color;
using esphome::display::TextAlign;
using Utilities::Draw;

static const char *const TAG = "daruma_media";

// Home Assistant subscribes to device actions a moment after it connects.
static const uint32_t CONNECT_GRACE_MS = 5000;
static const uint32_t TICK_MS = 250;
// How long the volume shows in place of the position after a change.
static const uint32_t VOLUME_SHOWN_MS = 2000;
static const size_t MAX_PLAYERS = 12;
// The focus item after the buttons: the players.
static const int PLAYERS_ITEM = MEDIA_BUTTONS;

static const char *const ICON_PREVIOUS = "\U000F04AE";  // skip-previous
static const char *const ICON_NEXT = "\U000F04AD";      // skip-next
static const char *const ICON_PLAY = "\U000F040A";      // play
static const char *const ICON_PAUSE = "\U000F03E4";     // pause
static const char *const ICON_STOP = "\U000F04DB";      // stop
static const char *const ICON_POWER = "\U000F0425";     // power
static const char *const ICON_QUIETER = "\U000F075E";   // volume-minus
static const char *const ICON_LOUDER = "\U000F075D";    // volume-plus
static const char *const ICON_VOLUME = "\U000F057E";    // volume-high
static const char *const ICON_MUSIC = "\U000F075A";     // music

static float number(ArduinoJson::JsonVariantConst v) { return v.is<float>() ? v.as<float>() : NAN; }

static std::string text(ArduinoJson::JsonVariantConst v) {
  const char *s = v.as<const char *>();
  return s != nullptr ? s : "";
}

static bool expired(uint32_t now_ms, uint32_t at_ms) { return (int32_t) (now_ms - at_ms) >= 0; }

// --- Settings and hooks ---------------------------------------------------------

void MediaApp::set_players(const std::string &players) {
  if (players == this->players_setting_)
    return;
  this->players_setting_ = players;
  this->area_.clear();
  this->players_.clear();
  this->have_players_ = false;
  this->current_.clear();
  this->chosen_ = false;
  this->failure_ = Failure::NONE;
  this->want_fetch_ = true;
  this->update_cover_();
  this->redraw_();
}

void MediaApp::add_to(Hub &hub, App app) {
  this->app_name_ = app.name;
  app.status = [this]() { return this->status(); };
  app.title = [this]() { return this->title(); };
  app.draw = [this](AppView &v) { this->draw(v); };
  app.input = [this](Input input, int x, int y) { return this->input(input, x, y); };
  app.on_open = [this]() { this->on_open(); };
  app.on_close = [this]() { this->on_close(); };
  app.on_enable = [this](bool on) { this->set_enabled(on); };
  hub.add_app(app);

  // Menu buttons for the moment: Pause while it plays, and none that the
  // player can't use. Before the first reply, every button shows.
  hub.set_action_button(this->prefix_ + ".play_pause", [this](MenuItem &item) {
    const MediaPlayer *p = this->shown();
    if (p == nullptr)
      return true;
    switch (media_middle(*p)) {
      case MediaMiddle::PAUSE:
        item.label = this->word_("button_pause");
        item.icon = ICON_PAUSE;
        return true;
      case MediaMiddle::STOP:
        item.label = this->word_("button_stop");
        item.icon = ICON_STOP;
        return true;
      case MediaMiddle::POWER:
        item.label = this->word_("button_power");
        item.icon = ICON_POWER;
        return true;
      case MediaMiddle::PLAY:
        return true;
      default:
        return false;
    }
  });
  const std::pair<const char *, MediaButton> others[] = {{".next", MediaButton::NEXT},
                                                         {".previous", MediaButton::PREVIOUS},
                                                         {".volume_up", MediaButton::LOUDER},
                                                         {".volume_down", MediaButton::QUIETER}};
  for (const auto &other : others) {
    const MediaButton button = other.second;
    hub.set_action_button(this->prefix_ + other.first, [this, button](MenuItem &) {
      const MediaPlayer *p = this->shown();
      return p == nullptr || media_can(*p, button);
    });
  }
}

// Something the app shows changed. With nothing of it on screen (no
// menu, no app), the persona's frames stay as they were.
void MediaApp::redraw_() {
  if (this->hub_ != nullptr && (this->open_ || this->hub_->ui_open()))
    this->hub_->request_redraw();
}

std::string MediaApp::word_(const char *key) const { return this->hub_->theme().word(this->prefix_ + "." + key); }

// Text from HA, without the glyphs the font lacks.
std::string MediaApp::safe_(const std::string &text) const {
  return this->text_font_ != nullptr ? drawable_text(this->text_font_, text, 160) : text.substr(0, 160);
}

const MediaPlayer *MediaApp::shown() const {
  const int i = media_find(this->players_, this->current_);
  return i >= 0 ? &this->players_[i] : nullptr;
}

std::string MediaApp::status() {
  const MediaPlayer *p = this->shown();
  if (p == nullptr)
    return "";
  if (p->running())
    return this->safe_(p->title.empty() ? p->name : p->title);
  return p->state == MediaState::PAUSED ? this->word_("paused") : std::string();
}

std::string MediaApp::title() {
  const MediaPlayer *p = this->shown();
  return p != nullptr ? this->safe_(p->name) : this->app_name_;
}

void MediaApp::on_open() {
  this->open_ = true;
  this->want_fetch_ = true;
  // The playing player again, and the area looked up again: the device
  // may have moved.
  this->chosen_ = false;
  this->area_.clear();
  this->cover_failed_.clear();
  this->focus_ = static_cast<int>(MediaButton::MIDDLE);
  this->update_cover_();
}

void MediaApp::on_close() {
  this->open_ = false;
  this->volume_until_ms_ = 0;
}

// --- Fetching ---------------------------------------------------------------------

bool MediaApp::due_(uint32_t now_ms) const {
  if (!this->enabled_ || this->pending_ || !this->fetcher_)
    return false;
  if (this->want_fetch_ && (this->open_ || this->queued_ || this->idle_refresh_ms_ > 0))
    return true;
  if (this->fetch_soon_ && expired(now_ms, this->next_fetch_ms_))
    return true;
  const uint32_t every = this->open_ ? this->refresh_ms_ : this->idle_refresh_ms_;
  if (every == 0)
    return false;
  return this->fetched_ms_ == 0 || now_ms - this->fetched_ms_ >= every;
}

// HA is there, and has had time to subscribe to the device's actions.
bool MediaApp::linked_(uint32_t now_ms) {
  auto *api = esphome::api::global_api_server;
  if (api == nullptr || !api->is_connected()) {
    this->connected_ms_ = 0;
    if (this->open_ && this->failure_ != Failure::OFFLINE) {
      this->failure_ = Failure::OFFLINE;
      this->redraw_();
    }
    return false;
  }
  if (this->connected_ms_ == 0)
    this->connected_ms_ = now_ms | 1;  // Never 0 while connected.
  return now_ms - this->connected_ms_ >= CONNECT_GRACE_MS;
}

void MediaApp::loop() {
  const uint32_t now_ms = esphome::millis();
  if (now_ms - this->tick_ms_ < TICK_MS)
    return;
  this->tick_ms_ = now_ms;
  this->tick_(now_ms);
  if (this->due_(now_ms) && this->linked_(now_ms))
    this->send_();
}

// The clock on screen: a timeout, the position each second, the volume
// going back to the position.
void MediaApp::tick_(uint32_t now_ms) {
  if (this->pending_ && now_ms - this->sent_ms_ >= this->timeout_ms_) {
    ESP_LOGW(TAG, "No reply from Home Assistant in %" PRIu32 " s", this->timeout_ms_ / 1000);
    this->pending_ = false;
    this->fetched_ms_ = now_ms | 1;
    this->failure_ = Failure::OFFLINE;
    this->redraw_();
  }
  if (this->volume_until_ms_ != 0 && expired(now_ms, this->volume_until_ms_)) {
    this->volume_until_ms_ = 0;
    this->redraw_();
  }
  if (this->open_ && now_ms - this->second_ms_ >= 1000) {
    this->second_ms_ = now_ms;
    const MediaPlayer *p = this->shown();
    if (p != nullptr && p->running())
      this->redraw_();
  }
}

void MediaApp::send_() {
  this->want_fetch_ = false;
  this->fetch_soon_ = false;
  this->pending_ = true;
  this->request_++;
  this->sent_ms_ = esphome::millis();
  ESP_LOGD(TAG, "Request %d: players '%s', area '%s'", this->request_, this->players_setting_.c_str(),
           this->area_.c_str());
  this->fetcher_(this->request_, this->players_setting_, this->area_);
}

void MediaApp::on_reply(int request, ArduinoJson::JsonObjectConst reply) {
  if (!this->pending_ || request != this->request_) {
    ESP_LOGD(TAG, "Dropped a late reply to request %d", request);
    return;
  }
  this->pending_ = false;
  this->fetched_ms_ = esphome::millis() | 1;
  ArduinoJson::JsonVariantConst body = reply["response"];
  // HA turns the rendered template back into an object when it can; if it
  // could not, the object arrives as JSON text.
  ArduinoJson::JsonDocument text_doc;
  if (body.is<const char *>()) {
    text_doc = esphome::json::parse_json(std::string(body.as<const char *>()));
    body = text_doc.as<ArduinoJson::JsonVariantConst>();
  }
  if (!body["p"].is<ArduinoJson::JsonArrayConst>()) {
    ESP_LOGW(TAG, "Reply to request %d has an unexpected shape", request);
    this->failure_ = Failure::ERROR;
    this->redraw_();
    return;
  }
  this->parse_(body);
  this->failure_ = Failure::NONE;
  if (this->queued_) {
    this->queued_ = false;
    this->press(this->queued_button_);
  }
  this->update_cover_();
  this->redraw_();
}

// Rows: [entity, name, state, title, artist, album, picture, duration,
// position, volume, features]. Missing values are null.
void MediaApp::parse_(ArduinoJson::JsonVariantConst body) {
  this->area_ = text(body["a"]);
  const uint32_t now_ms = esphome::millis();
  std::vector<MediaPlayer> fresh;
  bool held = false;
  for (ArduinoJson::JsonArrayConst row : body["p"].as<ArduinoJson::JsonArrayConst>()) {
    if (row.size() < 11 || fresh.size() >= MAX_PLAYERS)
      continue;
    MediaPlayer p;
    p.entity = text(row[0]);
    if (p.entity.empty())
      continue;
    p.name = text(row[1]);
    p.state = media_state(text(row[2]));
    p.title = text(row[3]);
    p.artist = text(row[4]);
    p.album = text(row[5]);
    p.picture = text(row[6]);
    p.duration = number(row[7]);
    p.position = number(row[8]);
    p.position_ms = now_ms;
    p.volume = number(row[9]);
    p.features = row[10].as<uint32_t>();
    held = media_hold(p, this->hold_, now_ms) || held;
    fresh.push_back(std::move(p));
  }
  this->players_ = std::move(fresh);
  this->have_players_ = true;
  // HA has not caught up with a command yet: ask again when the hold ends.
  if (held) {
    this->fetch_soon_ = true;
    this->next_fetch_ms_ = this->hold_.until_ms;
  }
  const int pick = media_pick(this->players_, this->current_, this->chosen_);
  const std::string picked = pick >= 0 ? this->players_[pick].entity : std::string();
  if (picked != this->current_) {
    this->chosen_ = false;
    this->current_ = picked;
  }
  ESP_LOGD(TAG, "%u players; on screen: '%s'", (unsigned) this->players_.size(), this->current_.c_str());
}

void MediaApp::on_error(int request, const std::string &error) {
  if (!this->pending_ || request != this->request_)
    return;
  ESP_LOGW(TAG, "Request %d failed: %s", request, error.c_str());
  this->pending_ = false;
  this->fetched_ms_ = esphome::millis() | 1;
  this->failure_ = Failure::ERROR;
  this->queued_ = false;
  this->redraw_();
}

// --- Commands ----------------------------------------------------------------------

void MediaApp::press(MediaButton button) {
  const MediaPlayer *p = this->shown();
  if (p == nullptr) {
    // Nothing known yet (a binding before the first reply): after it.
    if (!this->have_players_ || this->pending_) {
      this->queued_ = true;
      this->queued_button_ = button;
      this->want_fetch_ = true;
    }
    return;
  }
  this->run_(media_command(*p, button, this->volume_step_));
}

void MediaApp::run_(const MediaCommand &command) {
  const int i = media_find(this->players_, this->current_);
  if (i < 0 || command.action.empty() || !this->commander_)
    return;
  MediaPlayer &p = this->players_[i];
  const uint32_t now_ms = esphome::millis();
  const MediaState before = p.state;
  media_expect(p, command, now_ms);
  this->hold_.entity = p.entity;
  this->hold_.expected = p;
  this->hold_.state = p.state != before;
  this->hold_.volume = command.action == "media_player.volume_set";
  this->hold_.until_ms = now_ms + this->hold_ms_;
  if (command.action.rfind("media_player.volume_", 0) == 0)
    this->volume_until_ms_ = (now_ms + VOLUME_SHOWN_MS) | 1;
  ESP_LOGD(TAG, "%s on %s", command.action.c_str(), p.entity.c_str());
  this->commander_(command.action, p.entity, command.value);
  this->fetch_soon_ = true;
  this->next_fetch_ms_ = now_ms + this->command_refresh_ms_;
  this->redraw_();
}

void MediaApp::show_(int index) {
  if (index < 0 || index >= (int) this->players_.size())
    return;
  this->current_ = this->players_[index].entity;
  this->chosen_ = true;
  this->volume_until_ms_ = 0;
  this->update_cover_();
  this->redraw_();
}

void MediaApp::step_player_(int direction) {
  const int n = (int) this->players_.size();
  if (n < 2)
    return;
  const int i = std::max(media_find(this->players_, this->current_), 0);
  this->show_((i + direction + n) % n);
}

// --- The cover ---------------------------------------------------------------------

// HA's base URL: the setting, or the address HA connects from.
std::string MediaApp::base_url_now_() const {
  if (!this->base_url_.empty())
    return this->base_url_;
  auto *api = esphome::api::global_api_server;
  if (api == nullptr)
    return "";
  std::string found;
  for (const auto &client : api->active_clients()) {
    std::array<char, esphome::socket::SOCKADDR_STR_LEN> buf{};
    const std::string peer = client->get_peername_to(buf);
    const char *name = client->get_name();
    const bool ha = name != nullptr && std::string(name).rfind("Home Assistant", 0) == 0;
    if (found.empty() || ha)
      found = media_base_url(peer, this->ha_port_);
    if (ha)
      break;
  }
  return found;
}

// Loads the cover of the player on screen, while the app is open. One
// download at a time; the newest wish goes next.
void MediaApp::update_cover_() {
  const MediaPlayer *p = this->shown();
  // A photo on a gray or mono screen is noise: the music note shows there.
  const bool color = this->hub_->profile().colors == ColorMode::FULL;
  this->cover_want_ =
      p != nullptr && this->open_ && color ? media_cover_url(this->base_url_now_(), p->picture) : std::string();
  if (!this->cover_loader_ || this->cover_busy_ || this->cover_want_.empty())
    return;
  if (media_cover_key(this->cover_want_) == this->cover_loaded_ || this->cover_want_ == this->cover_failed_)
    return;
  this->cover_busy_ = true;
  this->cover_loading_ = this->cover_want_;
  ESP_LOGD(TAG, "Cover: %s", media_cover_key(this->cover_loading_).c_str());
  this->cover_loader_(this->cover_loading_);
}

void MediaApp::on_cover(bool ok) {
  this->cover_busy_ = false;
  this->cover_loaded_ = ok ? media_cover_key(this->cover_loading_) : std::string();
  if (!ok)
    this->cover_failed_ = this->cover_loading_;
  this->cover_loading_.clear();
  this->update_cover_();
  this->redraw_();
}

// --- Input -------------------------------------------------------------------------

int MediaApp::focus_count_() const { return MEDIA_BUTTONS + (this->players_.size() > 1 ? 1 : 0); }

bool MediaApp::can_press_(int item) const {
  if (item == PLAYERS_ITEM)
    return this->players_.size() > 1;
  const MediaPlayer *p = this->shown();
  return p != nullptr && media_can(*p, static_cast<MediaButton>(item));
}

bool MediaApp::press_item_(int item) {
  if (item == PLAYERS_ITEM)
    this->step_player_(1);
  else if (this->can_press_(item))
    this->press(static_cast<MediaButton>(item));
  return true;
}

// A tap on an error tries again at once.
bool MediaApp::retry_() {
  if (this->failure_ == Failure::NONE || this->pending_)
    return false;
  this->failure_ = Failure::NONE;
  this->want_fetch_ = true;
  this->redraw_();
  return true;
}

bool MediaApp::input(Input input, int x, int y) {
  if (this->shown() == nullptr)
    return (input == Input::TAP || input == Input::SELECT) && this->retry_();
  switch (input) {
    case Input::SWIPE_LEFT:
    case Input::SWIPE_RIGHT:
      if (this->players_.size() < 2)
        return false;
      this->step_player_(input == Input::SWIPE_LEFT ? 1 : -1);
      return true;
    case Input::NEXT:
    case Input::PREV:
      this->move_focus_(input == Input::NEXT ? 1 : -1);
      return true;
    case Input::SELECT:
      return this->press_item_(this->focus_);
    case Input::TAP:
      return this->tap_(x + this->origin_x_, y + this->origin_y_);
    default:
      return false;
  }
}

// The focus moves over what can act now.
void MediaApp::move_focus_(int direction) {
  const int n = this->focus_count_();
  const int step = direction > 0 ? 1 : n - 1;
  for (int i = 0, f = this->focus_; i < n; i++) {
    f = (f + step) % n;
    if (this->can_press_(f)) {
      this->focus_ = f;
      break;
    }
  }
  this->redraw_();
}

// A tap at (x, y) on the screen: a button, the bar, or the next player.
bool MediaApp::tap_(int x, int y) {
  for (int i = 0; i < MEDIA_BUTTONS; i++) {
    if (this->geometry_.buttons[i].contains(x, y))
      return this->press_item_(i);
  }
  const Rect &bar = this->geometry_.bar;
  if (bar.contains(x, y)) {
    this->run_(media_seek_command(*this->shown(), (float) (x - bar.x) / (float) std::max(bar.w, 1)));
    return true;
  }
  if (this->geometry_.dots.contains(x, y) || this->geometry_.cover.contains(x, y)) {
    this->step_player_(1);
    return this->players_.size() > 1;
  }
  return false;
}

// --- Drawing -----------------------------------------------------------------------

void MediaApp::draw_message_(AppView &v, const std::string &message) {
  const int pad = v.px(12);
  v.display.print(v.x + v.w / 2, v.y + v.h / 2, v.small, v.theme.muted, TextAlign::CENTER,
                  fit_text(v.display, v.small, message, v.w - 2 * pad).c_str(), v.theme.panel);
  UiTree::add("text", message, Rect{v.x, v.y + v.h / 2 - v.px(10), v.w, v.px(20)});
}

void MediaApp::draw(AppView &v) {
  this->text_font_ = v.text;
  this->origin_x_ = v.x;
  this->origin_y_ = v.y;
  this->geometry_ = Geometry{};
  const MediaPlayer *p = this->shown();
  if (p == nullptr) {
    const char *key = "loading";
    if (this->failure_ == Failure::OFFLINE)
      key = "offline";
    else if (this->failure_ == Failure::ERROR)
      key = "error";
    else if (this->have_players_)
      key = this->players_setting_.empty() ? "empty_room" : "empty";
    this->draw_message_(v, this->word_(key));
    return;
  }

  const int pad = v.px(10);
  const int size = std::max(v.px(32), std::min(this->cover_size_, v.h - v.px(88)));
  this->geometry_.cover = Rect{v.x + pad, v.y + pad, size, size};
  this->draw_cover_(v, *p);
  const int tx = this->geometry_.cover.right() + v.px(12);
  this->draw_text_(v, *p, tx, v.x + v.w - pad - tx);
  if (this->players_.size() > 1)
    this->draw_dots_(v, tx, this->geometry_.cover.bottom() - v.px(4));

  const int bar_y = this->geometry_.cover.bottom() + v.px(14);
  if (this->volume_until_ms_ != 0)
    this->draw_volume_(v, *p, bar_y);
  else
    this->draw_bar_(v, *p, bar_y);
  this->draw_buttons_(v, *p, bar_y + (v.y + v.h - bar_y) / 2 + v.px(4));
}

void MediaApp::draw_cover_(AppView &v, const MediaPlayer &p) {
  auto &it = v.display;
  const Theme &t = v.theme;
  const Rect &c = this->geometry_.cover;
  const Color tile = t.fit(t.color(this->prefix_ + ".cover"));
  auto *image = this->cover_image_;
  const bool ready = image != nullptr && !this->cover_want_.empty() &&
                     media_cover_key(this->cover_want_) == this->cover_loaded_ && image->get_width() > 0;
  if (ready) {
    const int iw = image->get_width(), ih = image->get_height();
    if (iw != c.w || ih != c.h)
      it.filled_rectangle(c.x, c.y, c.w, c.h, tile);
    it.image(c.x + (c.w - iw) / 2, c.y + (c.h - ih) / 2, image);
  } else {
    Draw::roundedRectangle(&it, c.x, c.y, c.w, c.h, v.px(8), tile);
    it.print(c.cx(), c.cy(), v.icons, t.on(tile, t.color(this->prefix_ + ".note")), TextAlign::CENTER, ICON_MUSIC,
             tile);
  }
  UiTree::add("image", "cover", c, false, ready ? "loaded" : (this->cover_busy_ ? "loading" : ""));
}

void MediaApp::draw_text_(AppView &v, const MediaPlayer &p, int tx, int tw) {
  auto &it = v.display;
  const Theme &t = v.theme;
  std::string title = p.title, artist = p.artist, album = p.album;
  if (p.state == MediaState::OFF) {
    title = this->word_("off");
    artist = album = "";
  } else if (title.empty()) {
    title = this->word_(p.active() ? "playing" : "idle");
  }
  title = drawable_text(v.text, title);
  // The title on up to two lines; the rest goes on the second.
  std::vector<std::string> lines = Utilities::Text::wrap(it, v.text, title, tw);
  int y = this->geometry_.cover.y + v.px(9);
  for (size_t i = 0; i < lines.size() && i < 2; i++) {
    std::string line = lines[i];
    for (size_t j = i + 1; i == 1 && j < lines.size(); j++)
      line += " " + lines[j];
    it.print(tx, y, v.text, t.ink, TextAlign::CENTER_LEFT, fit_text(it, v.text, line, tw).c_str(), t.panel);
    y += v.px(21);
  }
  UiTree::add("text", title, Rect{tx, this->geometry_.cover.y, tw, y - this->geometry_.cover.y}, false, "title");
  y += v.px(1);
  for (const std::string *line : {&artist, &album}) {
    if (line->empty())
      continue;
    const std::string shown = drawable_text(v.small, *line);
    it.print(tx, y, v.small, line == &artist ? t.ink : t.muted, TextAlign::CENTER_LEFT,
             fit_text(it, v.small, shown, tw).c_str(), t.panel);
    UiTree::add("text", shown, Rect{tx, y - v.px(9), tw, v.px(18)}, false, line == &artist ? "artist" : "album");
    y += v.px(18);
  }
}

void MediaApp::draw_bar_(AppView &v, const MediaPlayer &p, int y) {
  auto &it = v.display;
  const Theme &t = v.theme;
  const int pad = v.px(10), label = v.px(40);
  const Rect track{v.x + pad + label, y - v.px(2), v.w - 2 * (pad + label), std::max(v.px(4), 2)};
  const float at = p.active() ? media_position(p, esphome::millis()) : NAN;
  const bool known = !std::isnan(p.duration) && p.duration > 0.0f;
  Draw::roundedRectangle(&it, track.x, track.y, track.w, track.h, track.h / 2.0f, t.fit(t.edge));
  if (known && !std::isnan(at)) {
    const int filled = (int) std::lround(track.w * std::min(at / p.duration, 1.0f));
    if (filled > 0)
      Draw::roundedRectangle(&it, track.x, track.y, filled, track.h, track.h / 2.0f,
                             t.on(t.panel, t.color(this->prefix_ + ".play")));
  }
  const std::string now = media_time(at), total = known && p.active() ? media_time(p.duration) : "";
  if (!now.empty())
    it.print(v.x + pad, y, v.small, t.muted, TextAlign::CENTER_LEFT, now.c_str(), t.panel);
  if (!total.empty())
    it.print(v.x + v.w - pad, y, v.small, t.muted, TextAlign::CENTER_RIGHT, total.c_str(), t.panel);
  if (known && p.supports(MEDIA_SEEK) && p.active())
    this->geometry_.bar = Rect{track.x, y - v.px(12), track.w, v.px(24)};
  UiTree::add("slider", "position", Rect{track.x, y - v.px(10), track.w, v.px(20)}, false,
              total.empty() ? now : now + " / " + total);
}

void MediaApp::draw_volume_(AppView &v, const MediaPlayer &p, int y) {
  auto &it = v.display;
  const Theme &t = v.theme;
  const int pad = v.px(10), label = v.px(40);
  const Rect track{v.x + pad + label, y - v.px(2), v.w - 2 * (pad + label), std::max(v.px(4), 2)};
  it.print(v.x + pad + v.px(14), y, v.icons, t.muted, TextAlign::CENTER, ICON_VOLUME, t.panel);
  Draw::roundedRectangle(&it, track.x, track.y, track.w, track.h, track.h / 2.0f, t.fit(t.edge));
  std::string level;
  if (!std::isnan(p.volume)) {
    const int filled = (int) std::lround(track.w * std::max(0.0f, std::min(p.volume, 1.0f)));
    if (filled > 0)
      Draw::roundedRectangle(&it, track.x, track.y, filled, track.h, track.h / 2.0f,
                             t.on(t.panel, t.color(this->prefix_ + ".play")));
    level = fill(this->word_("volume"), "level", std::to_string((int) std::lround(p.volume * 100.0f)));
    it.print(v.x + v.w - pad, y, v.small, t.muted, TextAlign::CENTER_RIGHT, level.c_str(), t.panel);
  }
  UiTree::add("slider", "volume", Rect{track.x, y - v.px(10), track.w, v.px(20)}, false, level);
}

void MediaApp::draw_buttons_(AppView &v, const MediaPlayer &p, int cy) {
  auto &it = v.display;
  const Theme &t = v.theme;
  const Color play = t.on(t.panel, t.color(this->prefix_ + ".play"));
  const Color off = t.fit(t.edge);
  const MediaMiddle middle = media_middle(p);
  const char *middle_icon = ICON_PLAY;
  const char *middle_word = "button_play";
  if (middle == MediaMiddle::PAUSE) {
    middle_icon = ICON_PAUSE;
    middle_word = "button_pause";
  } else if (middle == MediaMiddle::STOP) {
    middle_icon = ICON_STOP;
    middle_word = "button_stop";
  } else if (middle == MediaMiddle::POWER) {
    middle_icon = ICON_POWER;
    middle_word = "button_power";
  }
  const char *icons[MEDIA_BUTTONS] = {ICON_PREVIOUS, middle_icon, ICON_NEXT, ICON_QUIETER, ICON_LOUDER};
  const char *words[MEDIA_BUTTONS] = {"button_previous", middle_word, "button_next", "button_quieter", "button_louder"};
  const int slot = v.w / MEDIA_BUTTONS, reach = v.px(26);
  for (int i = 0; i < MEDIA_BUTTONS; i++) {
    const MediaButton button = static_cast<MediaButton>(i);
    const int cx = v.x + slot * i + slot / 2;
    const bool can = media_can(p, button);
    const bool big = button == MediaButton::MIDDLE;
    const int r = v.px(big ? 22 : 18);
    if (big) {
      it.filled_circle(cx, cy, r, can ? play : off);
      it.print(cx, cy, v.icons, t.on(can ? play : off, t.panel), TextAlign::CENTER, icons[i], can ? play : off);
    } else {
      it.print(cx, cy, v.icons, can ? t.ink : off, TextAlign::CENTER, icons[i], t.panel);
    }
    const bool focused = v.focus && this->focus_ == i;
    if (focused) {
      it.circle(cx, cy, r + v.px(3), t.focus_color());
      it.circle(cx, cy, r + v.px(4), t.focus_color());
    }
    this->geometry_.buttons[i] = Rect{cx - slot / 2, cy - reach, slot, 2 * reach};
    UiTree::add("button", this->word_(words[i]), Rect{cx - r, cy - r, 2 * r, 2 * r}, focused, can ? "" : "disabled");
  }
}

// One dot per player, the one on screen filled.
void MediaApp::draw_dots_(AppView &v, int x, int y) {
  const Theme &t = v.theme;
  const int n = (int) this->players_.size();
  const int r = std::max(v.px(3), 2), step = v.px(11);
  const int shown = media_find(this->players_, this->current_);
  for (int i = 0; i < n; i++)
    v.display.filled_circle(x + r + i * step, y, r, i == shown ? t.ink : t.fit(t.dot));
  const Rect &d = this->geometry_.dots = Rect{x - v.px(4), y - v.px(10), (n - 1) * step + 2 * r + v.px(8), v.px(20)};
  const bool focused = v.focus && this->focus_ == PLAYERS_ITEM;
  if (focused) {
    v.display.rectangle(d.x, d.y, d.w, d.h, t.focus_color());
    v.display.rectangle(d.x + 1, d.y + 1, d.w - 2, d.h - 2, t.focus_color());
  }
  UiTree::add("pager", this->word_("players"), this->geometry_.dots, focused,
              std::to_string(shown + 1) + "/" + std::to_string(n));
}

}  // namespace Daruma
