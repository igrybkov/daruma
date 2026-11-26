#pragma once

#include <string>
#include <vector>

#include "esphome/components/daruma/hub.h"
#include "esphome/core/component.h"
#include "quick_grid.h"

namespace Daruma {

// Two-level menu, styled by the current persona's theme and placed by the
// hub's Layout (any screen size):
//
//   dock   a panel over the bottom of the persona: one named menu's buttons
//          (daruma: menus:), five at most; a longer menu shows four and
//          "Next" for the rest. `main` opens on a tap and ends with "More";
//   board  the apps, grid_cols x grid_rows per page (2x2, 3x2 on wide
//          screens), swipe left/right for more pages;
//   app    one app in the content area, under a header with a back arrow;
//   quick  a panel that hangs from the top over the persona: one round
//          tile per Settings row (Hub::settings()). A tap flips it.
//
// Touch boards tap and swipe. Boards without touch move a focus ring with
// NEXT and PREV and press SELECT; an open app gets them first (App::input).
// The board's `back` input goes back one level; `close` closes the menu.
// As a module it offers the actions menu.open (main, or `menu.open:<name>`),
// menu.app (the app board, or `menu.app:<id>` for one app), menu.quick (the
// quick panel), menu.back and menu.close.
class MenuController : public esphome::Component, public Module {
 public:
  MenuController() : Module("menu") {}
  void set_fonts(esphome::display::BaseFont *text, esphome::display::BaseFont *small,
                 esphome::display::BaseFont *icons) {
    this->text_font_ = text;
    this->small_font_ = small;
    this->icon_font_ = icons;
  }
  void set_timeout(uint32_t ms) { this->dock_timeout_ms_ = ms; }
  void set_app_timeout(uint32_t ms) { this->app_timeout_ms_ = ms; }
  // The label of the button that pages to the rest of a long menu.
  void set_next_label(const std::string &label) { this->next_label_ = label; }
  void setup(Hub &hub) override;
  void loop() override;

  bool is_open() const { return this->level_ != Level::CLOSED; }
  // Opens the main menu.
  void open() { this->open_menu("main"); }
  // Opens a named menu as the first level. An unknown name logs and does nothing.
  void open_menu(const std::string &name);
  void close();
  void back();
  // Opens an app on its own, from outside the menu (a tap on the plaque or
  // the badge): back closes it. An unknown or switched-off app logs and
  // does nothing. "" opens the app board.
  void open_app(const std::string &id);
  // Opens the quick panel. A message bubble on screen closes instead, so a
  // swipe down still clears it. With no settings it does nothing.
  void open_quick();

 protected:
  enum class Level { CLOSED, DOCK, BOARD, APP, QUICK };

  // Buttons the dock lays out; a longer menu shows one fewer and "Next".
  static const int MAX_BUTTONS = 5;

  bool draw_(esphome::display::Display &display);
  bool on_input_(Input input, int x, int y);
  bool on_dock_input_(Input input, int x, int y);
  bool on_board_input_(Input input, int x, int y);
  bool on_app_input_(Input input, int x, int y);
  bool on_quick_input_(Input input, int x, int y);
  bool on_quick_focus_(Input input);
  void touch_();  // Something happened: push the timeout back and redraw.

  // Dock.
  // The menu on top of the stack, from its first page.
  void show_menu_();
  // At most MAX_BUTTONS; the last one pages to the rest.
  std::vector<MenuItem> paginate_(std::vector<MenuItem> items) const;
  void show_dock_(const std::string &title, std::vector<MenuItem> items);
  void draw_dock_(esphome::display::Display &display, const Theme &theme);
  int dock_slot_(int x, int y) const;
  void select_dock_(int slot);

  // Board and apps.
  int pages_() const;
  void draw_board_(esphome::display::Display &display, const Theme &theme);
  void draw_tile_(esphome::display::Display &display, const Theme &theme, const App &app, const Rect &tile);
  void draw_app_(esphome::display::Display &display, const Theme &theme, App &app);
  // The open app; null when none is open (or it was switched off).
  App *app_() const;
  void open_app_(App *app);
  void leave_app_();
  void draw_frame_(esphome::display::Display &display, const Theme &theme, const std::string &title);
  void draw_card_(esphome::display::Display &display, const Theme &theme, const Rect &card);
  void draw_focus_(esphome::display::Display &display, const Theme &theme, const Rect &around, int radius);
  // Quick panel (quick_panel.cpp).
  QuickGrid quick_grid_() const;
  int quick_count_() const { return (int) this->hub_->settings().size(); }
  void flip_quick_(int index);
  void page_quick_(int step);
  int quick_room_(esphome::display::Display &display, const QuickGrid &g, int slot, int index);
  void draw_quick_(esphome::display::Display &display, const Theme &theme);
  void draw_quick_tile_(esphome::display::Display &display, const Theme &theme, const Setting &s, int cx, int top,
                        int room, bool focused);
  void print_icon_(esphome::display::Display &display, int x, int y, const std::string &icon, esphome::Color color,
                   esphome::Color background);
  std::string app_name_(const App &app, const Theme &theme) const;
  std::string app_icon_(const App &app, const Theme &theme) const;
  const Layout &layout_() const { return this->hub_->layout(); }

  Hub *hub_{nullptr};
  esphome::display::BaseFont *text_font_{nullptr};
  esphome::display::BaseFont *small_font_{nullptr};
  esphome::display::BaseFont *icon_font_{nullptr};
  uint32_t dock_timeout_ms_{10000};
  uint32_t app_timeout_ms_{60000};
  uint32_t until_{0};

  Level level_{Level::CLOSED};
  std::string title_;
  std::vector<MenuItem> items_;  // Dock buttons now shown.
  bool submenu_{false};          // The dock shows a button's submenu.
  // Menus opened, the first at the bottom; back pops one.
  std::vector<std::string> stack_;
  bool app_from_dock_{false};  // Back from the open app returns to the dock.
  bool app_alone_{false};      // Opened from outside the menu: back closes it.
  std::string next_label_{"Next"};
  int page_{0};
  std::string app_id_;  // The open app.
  // Boards without touch: the focused dock button and app.
  FocusRing dock_focus_;
  FocusRing board_focus_;
  FocusRing quick_focus_;
};

}  // namespace Daruma
