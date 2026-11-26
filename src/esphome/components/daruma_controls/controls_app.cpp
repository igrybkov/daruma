#include "controls_app.h"

#include <algorithm>

#include "esphome/components/api/api_server.h"
#include "esphome/components/daruma/draw.h"
#include "esphome/components/daruma/text.h"
#include "esphome/components/daruma/ui_tree.h"
#include "esphome/core/hal.h"
#include "esphome/core/log.h"

namespace Daruma {

using esphome::Color;
using esphome::display::TextAlign;

static const char *const TAG = "daruma_controls";

// How long a scene or script tile shows its check mark.
static const uint32_t CHECK_MS = 1200;
// How long the bar shows a level a tap set before HA confirms it.
static const uint32_t PENDING_MS = 3000;

void ControlsApp::add_tile(const std::string &entity, const std::string &label, const std::string &icon) {
  Tile t;
  t.entity = entity;
  t.label = label;
  t.icon = icon;
  t.kind = control_kind(entity);
  t.state = control_fresh(entity);
  this->tiles_.push_back(std::move(t));
}

void ControlsApp::setup() {
  auto *api = esphome::api::global_api_server;
  if (api == nullptr)
    return;
  // HA learns the subscriptions when it connects, so they are made once,
  // here, for the life of the device.
  for (size_t i = 0; i < this->tiles_.size(); i++) {
    const std::string &entity = this->tiles_[i].entity;
    api->subscribe_home_assistant_state(entity, {}, [this, i](esphome::StringRef s) {
      TileState &st = this->tiles_[i].state;
      st.state = std::string(s.c_str(), s.size());
      st.known = true;
      this->changed_();
    });
    const std::string attribute = control_attribute(entity);
    if (attribute.empty())
      continue;
    api->subscribe_home_assistant_state(entity, attribute, [this, i](esphome::StringRef s) {
      this->tiles_[i].state.extra = std::string(s.c_str(), s.size());
      this->changed_();
    });
    const std::string domain = control_domain(entity);
    if (domain == "fan")
      this->follow_(i, "percentage_step", &TileState::step);
    if (domain == "media_player") {
      this->follow_(i, "media_artist", &TileState::artist);
      this->follow_(i, "volume_level", &TileState::volume);
      this->follow_(i, "supported_features", &TileState::features);
    }
  }
  ESP_LOGD(TAG, "%u tiles", (unsigned) this->tiles_.size());
}

// One more attribute of tile i, into one field of its state.
void ControlsApp::follow_(size_t i, const char *attribute, std::string TileState::*field) {
  esphome::api::global_api_server->subscribe_home_assistant_state(
      this->tiles_[i].entity, std::string(attribute), [this, i, field](esphome::StringRef s) {
        this->tiles_[i].state.*field = std::string(s.c_str(), s.size());
        this->changed_();
      });
}

void ControlsApp::loop() {
  auto *api = esphome::api::global_api_server;
  const bool connected = api != nullptr && api->is_connected();
  if (connected != this->connected_) {
    this->connected_ = connected;
    // Without HA every tile is stale; HA sends them all again on connect.
    if (!connected) {
      for (Tile &t : this->tiles_)
        t.state = control_fresh(t.entity);
      this->changed_();
    }
  }
  if (this->check_index_ >= 0 && (int32_t) (esphome::millis() - this->check_until_ms_) >= 0) {
    this->check_index_ = -1;
    this->changed_();
  }
  if (this->pending_level_ >= 0 && (int32_t) (esphome::millis() - this->pending_until_ms_) >= 0) {
    this->pending_level_ = -1;
    this->changed_();
  }
}

void ControlsApp::changed_() {
  if (this->open_ && this->hub_ != nullptr)
    this->hub_->request_redraw();
}

void ControlsApp::on_open() {
  this->open_ = true;
  this->focus_.set_count(this->tiles_.size());
}

void ControlsApp::on_close() {
  this->open_ = false;
  this->panel_index_ = -1;
}

bool ControlsApp::back() {
  if (this->panel_index_ < 0)
    return false;
  this->panel_index_ = -1;
  this->changed_();
  return true;
}

void ControlsApp::open_panel_(int index) {
  if (index < 0 || index >= (int) this->tiles_.size())
    return;
  const Tile &t = this->tiles_[index];
  if (!control_has_panel(t.entity) || !control_available(t.state) || !this->leveler_)
    return;
  this->panel_index_ = index;
  this->pending_level_ = -1;
  this->changed_();
}

void ControlsApp::set_level_(int level) {
  const Tile &t = this->tiles_[this->panel_index_];
  ESP_LOGD(TAG, "%s to %d%%", t.entity.c_str(), level);
  this->leveler_(t.entity, level);
  this->pending_level_ = level;
  this->pending_until_ms_ = esphome::millis() + PENDING_MS;
  this->changed_();
}

// The level panel: a tap on the bar sets the level there; a tap on the top
// row toggles the entity. Every other input stays here.
bool ControlsApp::panel_input_(Input input, int x, int y) {
  if (input != Input::TAP)
    return input != Input::BACK && input != Input::CLOSE;
  const Tile &tile = this->tiles_[this->panel_index_];
  for (int b = 0; b < 3; b++) {
    if (this->buttons_[b].w > 0 && this->buttons_[b].contains(x, y)) {
      ESP_LOGD(TAG, "%s %s", control_media_action(b), tile.entity.c_str());
      this->actor_(control_media_action(b), tile.entity);
      return true;
    }
  }
  if (this->bar_.w > 0 && this->bar_.contains(x, y)) {
    this->set_level_(control_level_at(x - this->bar_.x, this->bar_.w, tile.state));
  } else if (this->head_.contains(x, y)) {
    this->act_(this->panel_index_);
  }
  return true;
}

std::string ControlsApp::word_(const char *key) const { return this->hub_->theme().word(this->prefix_ + "." + key); }

ControlWords ControlsApp::words_() const {
  ControlWords w;
  w.on = this->word_("on");
  w.off = this->word_("off");
  w.playing = this->word_("playing");
  w.paused = this->word_("paused");
  w.idle = this->word_("idle");
  w.open = this->word_("open");
  w.closed = this->word_("closed");
  w.opening = this->word_("opening");
  w.closing = this->word_("closing");
  w.unavailable = this->word_("unavailable");
  return w;
}

// "2 on": how many tiles are lit, for the board.
std::string ControlsApp::status() {
  int lit = 0;
  for (const Tile &t : this->tiles_)
    lit += control_active(t.kind, t.state) ? 1 : 0;
  return lit == 0 ? std::string() : fill(this->word_("status_on"), "count", std::to_string(lit));
}

ControlsApp::Grid ControlsApp::grid_(const AppView &v) const {
  Grid g;
  if (v.layout != nullptr) {
    g.cols = v.layout->grid_cols;
    g.rows = v.layout->grid_rows;
    g.gap = v.layout->gap;
  } else {
    g.gap = v.px(8);
  }
  // Icons alone take less room: twice the columns and one more row.
  if (this->icons_only_) {
    g.cols *= 2;
    g.rows += 1;
  }
  g.origin_x = v.x;
  g.origin_y = v.y;
  const int pad = v.px(8);
  g.area = Rect{v.x + pad, v.y + pad, v.w - 2 * pad, v.h - 2 * pad};
  if ((int) this->tiles_.size() > g.per_page()) {
    g.area.h -= v.px(14);
  } else if (this->icons_only_) {
    centre_(g, (int) this->tiles_.size());
  }
  return g;
}

// A few icons on one page: keep their size and put them in the middle.
void ControlsApp::centre_(Grid &g, int count) {
  const int cols = std::max(1, std::min(count, g.cols));
  const int rows = std::max(1, (count + cols - 1) / cols);
  const int cw = (g.area.w - g.gap * (g.cols - 1)) / g.cols;
  const int ch = (g.area.h - g.gap * (g.rows - 1)) / g.rows;
  const int w = cols * cw + (cols - 1) * g.gap;
  const int h = rows * ch + (rows - 1) * g.gap;
  g.area = Rect{g.area.x + (g.area.w - w) / 2, g.area.y + (g.area.h - h) / 2, w, h};
  g.cols = cols;
  g.rows = rows;
}

int ControlsApp::pages_(const Grid &g) const {
  const int per = std::max(1, g.per_page());
  return std::max(1, ((int) this->tiles_.size() + per - 1) / per);
}

// The tile under a touch, or -1. Touch comes in app-area coordinates; the
// grid is in screen ones.
int ControlsApp::tile_at_(int x, int y) const {
  const Grid &g = this->last_grid_;
  const int cell = g.area.cell_at(x + g.origin_x, y + g.origin_y, g.cols, g.rows, g.gap);
  return cell < 0 ? -1 : this->page_ * g.per_page() + cell;
}

void ControlsApp::page_to_focus_() { this->page_ = this->focus_.page(this->last_grid_.per_page()); }

void ControlsApp::act_(int index) {
  if (index < 0 || index >= (int) this->tiles_.size())
    return;
  const Tile &t = this->tiles_[index];
  const std::string action = control_action(t.entity, t.state);
  if (action.empty() || !this->actor_)
    return;
  ESP_LOGD(TAG, "%s %s", action.c_str(), t.entity.c_str());
  this->actor_(action, t.entity);
  if (t.kind == ControlKind::SCENE) {
    this->check_index_ = index;
    this->check_until_ms_ = esphome::millis() + CHECK_MS;
  }
  this->changed_();
}

bool ControlsApp::input(Input input, int x, int y) {
  if (this->panel_index_ >= 0)
    return this->panel_input_(input, x, y);
  const Grid &g = this->last_grid_;
  const int pages = this->pages_(g);
  this->focus_.set_count(this->tiles_.size());
  switch (input) {
    case Input::TAP: {
      const int index = this->tile_at_(x, y);
      if (index >= 0) {
        this->focus_.set(index);
        this->act_(index);
      }
      return true;
    }
    case Input::HOLD:
      // A long press on a light or a fan opens its level.
      this->open_panel_(this->tile_at_(x, y));
      return true;
    case Input::SELECT:
      if (this->focus_.valid())
        this->act_(this->focus_.index());
      return true;
    case Input::NEXT:
    case Input::PREV:
      if (input == Input::NEXT) {
        this->focus_.next();
      } else {
        this->focus_.prev();
      }
      this->page_to_focus_();
      this->changed_();
      return true;
    case Input::SWIPE_LEFT:
    case Input::SWIPE_RIGHT: {
      const int to = this->page_ + (input == Input::SWIPE_LEFT ? 1 : -1);
      if (to >= 0 && to < pages) {
        this->page_ = to;
        this->focus_.set(to * g.per_page());
        this->changed_();
      }
      return true;
    }
    default:
      return false;
  }
}

void ControlsApp::draw(AppView &v) {
  if (this->panel_index_ >= 0) {
    this->draw_panel_(v, this->tiles_[this->panel_index_]);
    return;
  }
  const Grid g = this->grid_(v);
  this->last_grid_ = g;
  const int pages = this->pages_(g);
  this->page_ = std::min(this->page_, pages - 1);
  const ControlWords w = this->words_();
  this->focus_.set_count(this->tiles_.size());
  const int per = g.per_page();
  for (int i = 0; i < per; i++) {
    const int index = this->page_ * per + i;
    if (index >= (int) this->tiles_.size())
      break;
    const bool focused = v.focus && index == this->focus_.index();
    this->draw_tile_(v, this->tiles_[index], g.area.cell(i, g.cols, g.rows, g.gap), focused, w);
  }
  if (pages > 1)
    this->draw_dots_(v, g, pages);
}

// A tile: its card, then the icon and the words. Lit while on; grey while
// its entity is away.
void ControlsApp::draw_tile_(AppView &v, const Tile &tile, const Rect &r, bool focused, const ControlWords &w) {
  auto &it = v.display;
  const Theme &t = v.theme;
  const bool available = control_available(tile.state);
  const bool active = control_active(tile.kind, tile.state);
  const int radius = v.px(10);
  const Color lit = t.on(t.panel, t.color(this->prefix_ + ".on"));
  if (focused)
    Utilities::Draw::roundedRectangle(&it, r.x - v.px(3), r.y - v.px(3), r.w + v.px(6), r.h + v.px(6), radius + v.px(3),
                                      t.on(t.panel, t.focus_color()));
  // A rim: lit while on, the card edge otherwise.
  const int rim = v.px(2);
  Utilities::Draw::roundedRectangle(&it, r.x, r.y, r.w, r.h, radius, active ? lit : t.fit(t.edge));
  TileLook look;
  look.fill = available ? t.panel : t.fit(shade(t.panel, 0.9f));
  Utilities::Draw::roundedRectangle(&it, r.x + rim, r.y + rim, r.w - 2 * rim, r.h - 2 * rim, radius - rim, look.fill);

  const int index = (int) (&tile - this->tiles_.data());
  const bool check = index == this->check_index_ && !this->check_icon_.empty();
  look.icon = check ? this->check_icon_ : tile.icon;
  look.available = available;
  look.label_color = t.on(look.fill, available ? t.ink : t.muted);
  look.icon_color = (active || check) ? lit : look.label_color;
  look.state_color = t.on(look.fill, t.muted);
  look.state = control_text(tile.kind, tile.state, w);
  if (this->icons_only_) {
    this->draw_icon_only_(v, r, tile.kind, look);
  } else {
    this->draw_words_(v, r, tile.label, look);
  }
  // The check mark reads as "done".
  UiTree::add("control", tile.label, r, focused, check ? "done" : look.state);
}

// The icon alone, in the middle. A sensor has nothing to light up, so it
// shows its value instead while it has one.
void ControlsApp::draw_icon_only_(AppView &v, const Rect &r, ControlKind kind, const TileLook &look) {
  auto &it = v.display;
  if (kind == ControlKind::SENSOR && look.available) {
    it.print(r.cx(), r.cy(), v.text, look.label_color, TextAlign::CENTER,
             fit_text(it, v.text, look.state, r.w - v.px(8)).c_str(), look.fill);
    return;
  }
  it.print(r.cx(), r.cy(), v.icons, look.icon_color, TextAlign::CENTER, look.icon.c_str(), look.fill);
}

// The icon left, the label and the state right. Narrow tiles put the icon
// over the words.
void ControlsApp::draw_words_(AppView &v, const Rect &r, const std::string &label, const TileLook &look) {
  auto &it = v.display;
  const bool has_state = !look.state.empty();
  if (r.w >= v.px(120)) {
    const int tx = r.x + v.px(42);
    const int room = r.right() - tx - v.px(6);
    it.print(r.x + v.px(22), r.cy(), v.icons, look.icon_color, TextAlign::CENTER, look.icon.c_str(), look.fill);
    const int label_y = has_state ? r.y + r.h * 38 / 100 : r.cy();
    it.print(tx, label_y, v.text, look.label_color, TextAlign::CENTER_LEFT, fit_text(it, v.text, label, room).c_str(),
             look.fill);
    if (has_state)
      it.print(tx, r.y + r.h * 68 / 100, v.small, look.state_color, TextAlign::CENTER_LEFT,
               fit_text(it, v.small, look.state, room).c_str(), look.fill);
    return;
  }
  const int room = r.w - v.px(8);
  it.print(r.cx(), r.y + r.h * 32 / 100, v.icons, look.icon_color, TextAlign::CENTER, look.icon.c_str(), look.fill);
  it.print(r.cx(), r.y + r.h * 64 / 100, v.small, look.label_color, TextAlign::CENTER,
           fit_text(it, v.small, label, room).c_str(), look.fill);
  if (has_state)
    it.print(r.cx(), r.y + r.h * 84 / 100, v.small, look.state_color, TextAlign::CENTER,
             fit_text(it, v.small, look.state, room).c_str(), look.fill);
}

// The level to show: the one a tap set, until HA's agrees or it times out.
int ControlsApp::shown_level_(int level) {
  if (this->pending_level_ >= 0 && level != this->pending_level_)
    return this->pending_level_;
  this->pending_level_ = -1;
  return level;
}

// A panel for one light, fan or player. Every part sets where taps land.
void ControlsApp::draw_panel_(AppView &v, const Tile &tile) {
  this->bar_ = Rect{};
  for (Rect &b : this->buttons_)
    b = Rect{};
  if (tile.kind == ControlKind::MEDIA) {
    this->draw_media_panel_(v, tile);
    return;
  }
  // A light or a fan: the level, and a wide bar under it.
  const int level = this->shown_level_(control_level(tile.state));
  const std::string pct = std::to_string(level) + "%";
  this->draw_head_(v, tile, pct, level > 0);
  const int bar_y = v.px(60);
  this->draw_bar_(v, tile, Rect{v.px(16), bar_y, v.w - v.px(32), std::min(v.px(72), v.h - v.px(16) - bar_y)}, level);
}

// A player: the title and artist, its buttons, and the volume.
void ControlsApp::draw_media_panel_(AppView &v, const Tile &tile) {
  auto &it = v.display;
  const Theme &t = v.theme;
  const TileState &s = tile.state;
  const int volume = control_volume(s);
  const bool has_volume = volume >= 0 && control_supports(s, MEDIA_VOLUME_SET);
  const int level = this->shown_level_(std::max(0, volume));
  this->draw_head_(v, tile, has_volume ? std::to_string(level) + "%" : "", s.state == "playing");

  const int pad = v.px(16);
  const std::string title = s.state == "playing" || s.state == "paused" ? s.extra : std::string();
  const std::string line = title.empty() ? control_text(tile.kind, s, this->words_()) : title;
  it.print(v.x + pad, v.y + v.px(58), v.text, t.on(t.panel, t.ink), TextAlign::CENTER_LEFT,
           fit_text(it, v.text, line, v.w - 2 * pad).c_str(), t.panel);
  UiTree::add("text", line, Rect{v.x + pad, v.y + v.px(48), v.w - 2 * pad, v.px(20)}, false, s.artist);
  if (!title.empty() && !s.artist.empty())
    it.print(v.x + pad, v.y + v.px(78), v.small, t.on(t.panel, t.muted), TextAlign::CENTER_LEFT,
             fit_text(it, v.small, s.artist, v.w - 2 * pad).c_str(), t.panel);

  this->draw_buttons_(v, s, v.px(112));
  if (has_volume) {
    const int bar_y = v.px(140);
    this->draw_bar_(v, tile, Rect{pad, bar_y, v.w - 2 * pad, std::min(v.px(26), v.h - v.px(8) - bar_y)}, level);
  }
}

// Previous, play or pause, and next, centered on `cy` (app-area). Previous
// and next show only when the player can do them.
void ControlsApp::draw_buttons_(AppView &v, const TileState &s, int cy) {
  auto &it = v.display;
  const Theme &t = v.theme;
  const Color lit = t.on(t.panel, t.color(this->prefix_ + ".on"));
  const bool playing = s.state == "playing";
  static const char *const ICONS[] = {"\U000F04AE", nullptr, "\U000F04AD"};  // skip-previous, skip-next
  static const char *const NAMES[] = {"Previous", nullptr, "Next"};
  const bool shown[] = {control_supports(s, MEDIA_PREVIOUS), true, control_supports(s, MEDIA_NEXT)};
  const int r = v.px(22);
  for (int b = 0; b < 3; b++) {
    if (!shown[b])
      continue;
    const int cx = v.w / 2 + (b - 1) * v.px(70);
    this->buttons_[b] = Rect{cx - r, cy - r, 2 * r, 2 * r};
    const Color fill = b == 1 ? lit : t.fit(t.edge);
    v.display.filled_circle(v.x + cx, v.y + cy, r, fill);
    const char *icon = b == 1 ? (playing ? "\U000F03E4" : "\U000F040A") : ICONS[b];  // pause, play
    it.print(v.x + cx, v.y + cy, v.icons, t.on(fill, b == 1 ? t.panel : t.ink), TextAlign::CENTER, icon, fill);
    const char *name = b == 1 ? (playing ? "Pause" : "Play") : NAMES[b];
    UiTree::add("button", name, Rect{v.x + cx - r, v.y + cy - r, 2 * r, 2 * r});
  }
}

// The top row: the icon (lit while on), the label, and `right` at the end.
// A tap on it toggles the entity.
void ControlsApp::draw_head_(AppView &v, const Tile &tile, const std::string &right, bool on) {
  auto &it = v.display;
  const Theme &t = v.theme;
  const int pad = v.px(16);
  const int top = v.y + v.px(30);
  const Color lit = t.on(t.panel, t.color(this->prefix_ + ".on"));
  const int right_w = right.empty() ? 0 : text_width(it, v.text, right) + v.px(8);
  it.print(v.x + pad + v.px(14), top, v.icons, on ? lit : t.on(t.panel, t.muted), TextAlign::CENTER, tile.icon.c_str(),
           t.panel);
  const int lx = v.x + pad + v.px(36);
  it.print(lx, top, v.text, t.on(t.panel, t.ink), TextAlign::CENTER_LEFT,
           fit_text(it, v.text, tile.label, v.x + v.w - pad - right_w - lx).c_str(), t.panel);
  if (!right.empty())
    it.print(v.x + v.w - pad, top, v.text, t.on(t.panel, t.ink), TextAlign::CENTER_RIGHT, right.c_str(), t.panel);
  this->head_ = Rect{pad, v.px(12), v.w - 2 * pad, v.px(36)};
  UiTree::add("button", tile.label, Rect{v.x + this->head_.x, v.y + this->head_.y, this->head_.w, this->head_.h});
}

// The level bar at `r` (app-area), filled to `level`. A fan with set
// speeds gets a notch between each two.
void ControlsApp::draw_bar_(AppView &v, const Tile &tile, const Rect &r, int level) {
  auto &it = v.display;
  const Theme &t = v.theme;
  const Rect bar{v.x + r.x, v.y + r.y, r.w, r.h};
  const int radius = std::min(v.px(12), bar.h / 2);
  Utilities::Draw::roundedRectangle(&it, bar.x, bar.y, bar.w, bar.h, radius, t.fit(t.edge));
  const int filled = bar.w * level / 100;
  if (filled > 0)
    Utilities::Draw::roundedRectangle(&it, bar.x, bar.y, std::max(filled, 2 * radius), bar.h, radius,
                                      t.on(t.panel, t.color(this->prefix_ + ".on")));
  const double step = control_step(tile.state);
  for (double at = step; step > 1.0 && at < 99.5; at += step)
    it.vertical_line(bar.x + (int) (bar.w * at / 100), bar.y + v.px(10), bar.h - v.px(20), t.panel);
  this->bar_ = r;
  UiTree::add("slider", tile.label, bar, false, std::to_string(level) + "%");
}

void ControlsApp::draw_dots_(AppView &v, const Grid &g, int pages) {
  const Theme &t = v.theme;
  const int step = v.px(14);
  const int y = g.area.bottom() + v.px(8);
  const int x0 = g.area.cx() - (pages - 1) * step / 2;
  for (int p = 0; p < pages; p++)
    v.display.filled_circle(x0 + p * step, y, v.px(3), p == this->page_ ? t.on(t.panel, t.accent) : t.fit(t.dot));
}

}  // namespace Daruma
