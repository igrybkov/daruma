#pragma once

// The Controls app: a grid of Home Assistant entities with their live
// state. A tap toggles a light, runs a scene or plays and pauses music.
//
// Each tile subscribes to its entity's state and one attribute (controls.h)
// in setup(), so HA pushes every change while it is connected. A tap runs
// the actor: the package's script with `homeassistant.action`
// (daruma/app_controls.yaml). It wants no reply, so it skips the hub's
// gate for HA calls.

#include <functional>
#include <string>
#include <vector>

#include "controls.h"
#include "esphome/components/daruma/focus.h"
#include "esphome/components/daruma/hub.h"
#include "esphome/core/component.h"

namespace Daruma {

class ControlsApp : public esphome::Component {
 public:
  // Performs HA's `action` on `entity` ("light.toggle", "light.desk").
  using Actor = std::function<void(const std::string &action, const std::string &entity)>;
  // Sets a light's brightness or a fan's speed, in percent.
  using Leveler = std::function<void(const std::string &entity, int level)>;

  struct Tile {
    std::string entity;
    std::string label;
    std::string icon;  // UTF-8 MDI glyph.
    ControlKind kind{ControlKind::UNKNOWN};
    TileState state;
  };

  void set_hub(Hub *hub) { this->hub_ = hub; }
  void set_actor(Actor actor) { this->actor_ = std::move(actor); }
  void set_leveler(Leveler leveler) { this->leveler_ = std::move(leveler); }
  // The theme keys' prefix: the app's id ("controls.on").
  void set_theme_prefix(const std::string &prefix) { this->prefix_ = prefix; }
  void set_check_icon(const std::string &icon) { this->check_icon_ = icon; }
  // Tiles show the icon alone, smaller, so more fit on a page.
  void set_icons_only(bool icons_only) { this->icons_only_ = icons_only; }
  void add_tile(const std::string &entity, const std::string &label, const std::string &icon);

  void setup() override;
  void loop() override;

  // App hooks, for Daruma::App.
  std::string status();
  void draw(AppView &v);
  bool input(Input input, int x, int y);
  void on_open();
  void on_close();
  // Back from a level panel to the tiles. False on the tiles.
  bool back();

  const std::vector<Tile> &tiles() const { return this->tiles_; }

 protected:
  struct Grid {
    int cols{2}, rows{2}, gap{8};
    Rect area;                     // Where the tiles go; the page dots go under it.
    int origin_x{0}, origin_y{0};  // The app area's corner.
    int per_page() const { return this->cols * this->rows; }
  };

  // How one tile is drawn this frame.
  struct TileLook {
    esphome::Color fill, icon_color, label_color, state_color;
    std::string icon, state;
    bool available{false};
  };

  Grid grid_(const AppView &v) const;
  static void centre_(Grid &g, int count);
  int pages_(const Grid &g) const;
  void changed_();
  void act_(int index);
  void page_to_focus_();
  int tile_at_(int x, int y) const;
  ControlWords words_() const;
  std::string word_(const char *key) const;
  void draw_tile_(AppView &v, const Tile &tile, const Rect &r, bool focused, const ControlWords &w);
  bool panel_input_(Input input, int x, int y);
  void open_panel_(int index);
  void set_level_(int level);
  void draw_panel_(AppView &v, const Tile &tile);
  void draw_icon_only_(AppView &v, const Rect &r, ControlKind kind, const TileLook &look);
  void draw_words_(AppView &v, const Rect &r, const std::string &label, const TileLook &look);
  void draw_dots_(AppView &v, const Grid &g, int pages);

  Hub *hub_{nullptr};
  Actor actor_;
  Leveler leveler_;
  std::string prefix_{"controls"};
  std::string check_icon_;
  bool icons_only_{false};
  std::vector<Tile> tiles_;

  FocusRing focus_;
  int page_{0};
  bool open_{false};
  bool connected_{false};
  // A scene or script tile shows a check mark for a moment after a tap.
  int check_index_{-1};
  uint32_t check_until_ms_{0};
  // The last grid drawn, for taps.
  Grid last_grid_;
  // The level panel: which tile, the bar and the top row as last drawn (in
  // app-area coordinates), and the level a tap set until HA confirms it.
  int panel_index_{-1};
  Rect bar_, head_;
  int pending_level_{-1};
  uint32_t pending_until_ms_{0};
};

}  // namespace Daruma
