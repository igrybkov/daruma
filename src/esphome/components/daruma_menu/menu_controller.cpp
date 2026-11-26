#include "menu_controller.h"

#include <algorithm>

#include "esphome/core/hal.h"
#include "esphome/core/log.h"
#include "esphome/components/daruma/draw.h"
#include "esphome/components/daruma/text.h"
#include "esphome/components/daruma/ui_tree.h"

namespace Daruma {

using esphome::Color;
using esphome::display::Display;
using esphome::display::TextAlign;

// Draws above every other screen; handles taps before the core's pet fallback.
static const int SCREEN_PRIORITY = 100;
static const int INPUT_PRIORITY = 50;
static const char *const MORE_ICON = "\U000F15FC";  // dots-grid
static const char *const BACK_ICON = "\U000F0141";  // chevron-left
static const char *const NEXT_ICON = "\U000F0142";  // chevron-right (the rest of a long menu)
static const char *const MENU_ICON = "\U000F035C";  // menu (another menu)

void MenuController::setup(Hub &hub) {
  this->hub_ = &hub;
  hub.add_screen(SCREEN_PRIORITY, [this](Display &display) { return this->draw_(display); });
  hub.add_input_handler(INPUT_PRIORITY, [this](Input input, int x, int y) { return this->on_input_(input, x, y); });
  hub.add_action("menu.open", [this]() { this->open(); });
  hub.add_arg_action("menu.open", [this](const std::string &menu) { this->open_menu(menu); });
  hub.add_action("menu.app", [this]() { this->open_app(""); });
  hub.add_arg_action("menu.app", [this](const std::string &app) { this->open_app(app); });
  hub.add_action("menu.quick", [this]() { this->open_quick(); });
  hub.add_action("menu.back", [this]() { this->back(); });
  hub.add_action("menu.close", [this]() { this->close(); });
}

App *MenuController::app_() const {
  if (this->level_ != Level::APP)
    return nullptr;
  App *app = this->hub_->find_app(this->app_id_);
  return app != nullptr && app->enabled ? app : nullptr;
}

void MenuController::open_app_(App *app) {
  this->app_id_ = app->id;
  this->level_ = Level::APP;
  if (app->on_open)
    app->on_open();
}

void MenuController::open_app(const std::string &id) {
  if (id.empty()) {
    this->leave_app_();
    this->stack_.assign(1, "main");
    this->level_ = Level::BOARD;
    this->page_ = 0;
    this->board_focus_.set_count(this->hub_->apps().size());
    this->board_focus_.reset();
    this->hub_->set_ui_open(true);
    this->touch_();
    return;
  }
  App *app = this->hub_->find_app(id);
  if (app == nullptr || !app->enabled) {
    ESP_LOGW("daruma_menu", "No app '%s' to open (or it is switched off)", id.c_str());
    return;
  }
  this->leave_app_();
  this->stack_.assign(1, "main");
  this->open_app_(app);
  this->app_alone_ = true;
  this->hub_->set_ui_open(true);
  this->touch_();
}

void MenuController::leave_app_() {
  if (this->level_ != Level::APP)
    return;
  this->app_from_dock_ = false;
  this->app_alone_ = false;
  App *app = this->hub_->find_app(this->app_id_);
  this->app_id_.clear();
  this->level_ = Level::BOARD;
  if (app != nullptr && app->on_close)
    app->on_close();
}

void MenuController::loop() {
  if (this->is_open() && (int32_t) (esphome::millis() - this->until_) >= 0)
    this->close();
}

void MenuController::touch_() {
  const bool dock = this->level_ == Level::DOCK || this->level_ == Level::QUICK;
  this->until_ = esphome::millis() + (dock ? this->dock_timeout_ms_ : this->app_timeout_ms_);
  this->hub_->request_redraw();
}

void MenuController::open_menu(const std::string &name) {
  if (!this->hub_->has_menu(name)) {
    ESP_LOGW("daruma_menu", "No menu named '%s'", name.c_str());
    return;
  }
  this->leave_app_();
  this->stack_.assign(1, name);
  this->show_menu_();
}

void MenuController::show_menu_() {
  if (this->stack_.empty())
    this->stack_.push_back("main");
  const Theme &theme = this->hub_->theme();
  std::vector<MenuItem> items = this->hub_->menu_items(this->stack_.back());
  std::vector<MenuItem> shown;
  for (MenuItem &item : items) {
    if (item.board) {
      if (this->hub_->apps().empty())
        continue;  // Every app is switched off: no board to open.
      item.label = "More";
      item.icon = MORE_ICON;
    } else if (!item.app.empty()) {
      App *app = this->hub_->find_app(item.app);
      if (app == nullptr)
        continue;
      item.label = this->app_name_(*app, theme);
      item.icon = this->app_icon_(*app, theme);
    } else if (!item.menu.empty() && item.icon.empty()) {
      item.icon = MENU_ICON;
    }
    shown.push_back(std::move(item));
  }
  this->submenu_ = false;
  this->show_dock_(this->hub_->menu_title(), this->paginate_(std::move(shown)));
  this->hub_->set_ui_open(true);
}

std::vector<MenuItem> MenuController::paginate_(std::vector<MenuItem> items) const {
  if ((int) items.size() <= MAX_BUTTONS)
    return items;
  std::vector<MenuItem> rest(items.begin() + (MAX_BUTTONS - 1), items.end());
  items.resize(MAX_BUTTONS - 1);
  MenuItem next = MenuItem::make(this->next_label_, NEXT_ICON, this->hub_->theme().edge, Color::WHITE, nullptr);
  next.submenu_title = this->hub_->menu_title();
  next.submenu = this->paginate_(std::move(rest));
  items.push_back(std::move(next));
  return items;
}

void MenuController::close() {
  if (!this->is_open())
    return;
  this->leave_app_();
  this->level_ = Level::CLOSED;
  this->items_.clear();
  this->stack_.clear();
  this->hub_->set_ui_open(false);
  this->hub_->request_redraw();
}

void MenuController::show_dock_(const std::string &title, std::vector<MenuItem> items) {
  this->title_ = title;
  this->items_ = std::move(items);
  this->level_ = Level::DOCK;
  this->dock_focus_.set_count(this->items_.size());
  this->dock_focus_.reset();
  this->touch_();
}

void MenuController::back() {
  switch (this->level_) {
    case Level::APP: {
      App *app = this->app_();
      if (app == nullptr || !app->back || !app->back()) {
        // An app opened from a dock button goes back to that dock; one
        // opened from the persona closes.
        const bool to_dock = this->app_from_dock_;
        if (this->app_alone_) {
          this->close();
          break;
        }
        this->leave_app_();
        if (to_dock) {
          this->show_menu_();
          break;
        }
      }
      this->touch_();
      break;
    }
    case Level::BOARD:
      this->show_menu_();
      break;
    case Level::DOCK:
      if (this->submenu_) {
        this->show_menu_();
      } else if (this->stack_.size() > 1) {
        this->stack_.pop_back();
        this->show_menu_();
      } else {
        this->close();
      }
      break;
    case Level::QUICK:
      this->close();
      break;
    case Level::CLOSED:
      break;
  }
}

// --- Input ------------------------------------------------------------------

bool MenuController::on_input_(Input input, int x, int y) {
  if (input == Input::DISMISS) {
    this->close();
    return false;  // Let other handlers see it too.
  }
  if (!this->is_open())
    return false;

  // The board's navigation inputs: back one level, or all the way out.
  if (input == Input::CLOSE) {
    this->close();
    return true;
  }
  if (input == Input::BACK) {
    this->back();
    return true;
  }

  switch (this->level_) {
    case Level::DOCK:
      return this->on_dock_input_(input, x, y);
    case Level::BOARD:
      return this->on_board_input_(input, x, y);
    case Level::APP:
      return this->on_app_input_(input, x, y);
    case Level::QUICK:
      return this->on_quick_input_(input, x, y);
    case Level::CLOSED:
      break;
  }
  return false;
}

bool MenuController::on_dock_input_(Input input, int x, int y) {
  switch (input) {
    case Input::NEXT:
      this->dock_focus_.next();
      this->touch_();
      return true;
    case Input::PREV:
      this->dock_focus_.prev();
      this->touch_();
      return true;
    case Input::SELECT:
      this->select_dock_(this->dock_focus_.index());
      return true;
    case Input::SWIPE_DOWN:
      this->back();
      return true;
    case Input::TAP:
      if (y < this->layout_().dock.y) {
        this->close();  // A tap on the persona above the dock.
      } else {
        this->select_dock_(this->dock_slot_(x, y));
      }
      return true;
    default:
      return true;  // Keep the persona under the dock as it is.
  }
}

bool MenuController::on_board_input_(Input input, int x, int y) {
  const Layout &l = this->layout_();
  const int pages = this->pages_();
  const auto apps = this->hub_->apps();
  this->board_focus_.set_count(apps.size());
  switch (input) {
    case Input::NEXT:
    case Input::PREV:
      if (input == Input::NEXT) {
        this->board_focus_.next();
      } else {
        this->board_focus_.prev();
      }
      this->page_ = this->board_focus_.page(l.tiles_per_page());
      this->touch_();
      return true;
    case Input::SELECT:
      if (this->board_focus_.valid())
        this->open_app_(apps[this->board_focus_.index()]);
      this->touch_();
      return true;
    case Input::SWIPE_LEFT:
      if (this->page_ + 1 < pages) {
        this->page_++;
        this->touch_();
      }
      return true;
    case Input::SWIPE_RIGHT:
      if (this->page_ > 0) {
        this->page_--;
        this->touch_();
      }
      return true;
    case Input::TAP: {
      if (l.back.contains(x, y)) {
        this->back();
        return true;
      }
      const int tile = l.tile_at(x, y);
      const int index = this->page_ * l.tiles_per_page() + tile;
      if (tile >= 0 && index < (int) apps.size()) {
        this->board_focus_.set(index);
        this->open_app_(apps[index]);
      }
      this->touch_();
      return true;
    }
    default:
      return input != Input::HOLD && input != Input::LONG_HOLD;
  }
}

bool MenuController::on_app_input_(Input input, int x, int y) {
  const Layout &l = this->layout_();
  if (input == Input::TAP && l.back.contains(x, y)) {
    this->back();
    return true;
  }
  App *app = this->app_();
  if (app == nullptr) {
    this->back();
    return true;
  }
  // Taps and every swipe go to the app (Calendar pages days with left and
  // right). Board paging lives one level up, so nothing clashes. Touch comes
  // in app-area coordinates; buttons carry no point.
  if (app->input) {
    const bool point = x >= 0 && y >= 0;
    const int ax = point ? x - l.content.x : -1;
    const int ay = point ? y - l.content.y : -1;
    const bool used = app->input(input, ax, ay);
    // NEXT and PREV the app left alone scroll it.
    if (!used && input == Input::NEXT)
      app->input(Input::SWIPE_UP, -1, -1);
    if (!used && input == Input::PREV)
      app->input(Input::SWIPE_DOWN, -1, -1);
  }
  this->touch_();
  return true;
}

// --- Dock -------------------------------------------------------------------

int MenuController::dock_slot_(int x, int y) const {
  const Rect &dock = this->layout_().dock;
  if (this->items_.empty() || y < dock.y)
    return -1;
  const int span = dock.w / (int) this->items_.size();
  const int slot = (x - dock.x) / span;
  return (x < dock.x || slot >= (int) this->items_.size()) ? -1 : slot;
}

void MenuController::select_dock_(int slot) {
  if (slot < 0 || slot >= (int) this->items_.size())
    return;
  MenuItem item = this->items_[slot];  // Copy: the page may be replaced below.
  if (item.board) {
    this->level_ = Level::BOARD;
    this->page_ = 0;
    this->board_focus_.set_count(this->hub_->apps().size());
    this->board_focus_.reset();
    this->touch_();
    return;
  }
  if (!item.app.empty()) {
    App *app = this->hub_->find_app(item.app);
    if (app != nullptr && app->enabled) {
      this->open_app_(app);
      this->app_from_dock_ = true;
      this->touch_();
    }
    return;
  }
  if (!item.menu.empty()) {
    this->stack_.push_back(item.menu);
    this->show_menu_();
    return;
  }
  if (!item.submenu.empty()) {
    this->submenu_ = true;
    this->show_dock_(item.submenu_title, item.submenu);
    return;
  }
  this->close();
  if (item.action)
    item.action();
}

void MenuController::print_icon_(Display &display, int x, int y, const std::string &icon, Color color,
                                 Color background) {
  // Material Design Icons sit in Unicode's private area (4-byte UTF-8);
  // anything else is short text such as "25".
  const bool glyph = !icon.empty() && (uint8_t) icon[0] >= 0xF0;
  display.print(x, y, glyph ? this->icon_font_ : this->text_font_, color, TextAlign::CENTER, icon.c_str(), background);
}

// A ring around a card or button, with a gap so it reads apart from the
// card's own edge.
void MenuController::draw_focus_(Display &display, const Theme &theme, const Rect &around, int radius) {
  const Layout &l = this->layout_();
  const int out = l.px(6), gap = l.px(3);
  const Color ring = theme.on(theme.frame, theme.focus_color());
  Utilities::Draw::roundedRectangle(&display, around.x - out, around.y - out, around.w + 2 * out, around.h + 2 * out,
                                    radius + out, ring);
  Utilities::Draw::roundedRectangle(&display, around.x - gap, around.y - gap, around.w + 2 * gap, around.h + 2 * gap,
                                    radius + gap, theme.frame);
}

void MenuController::draw_dock_(Display &display, const Theme &theme) {
  const Layout &l = this->layout_();
  const Rect &dock = l.dock;
  const int top = dock.y, left = dock.x, width = dock.w, height = dock.h;
  const int border = l.px(2);
  if (theme.style == ThemeStyle::OUTLINE) {
    Utilities::Draw::roundedRectangle(&display, left, top, width, height, l.px(18), theme.accent);
    Utilities::Draw::roundedRectangle(&display, left + border, top + border, width - 2 * border, height - 2 * border,
                                      l.px(16), theme.dock);
  } else {
    Utilities::Draw::roundedRectangle(&display, left, top, width, height, l.px(18), theme.dock);
  }
  if (!this->title_.empty()) {
    display.print(dock.cx(), top + l.px(14), this->small_font_, theme.dock_muted, TextAlign::CENTER,
                  this->title_.c_str(), theme.dock);
    UiTree::add("heading", this->title_, Rect{left, top, width, l.px(28)});
  }
  const int n = this->items_.size();
  if (n == 0)
    return;
  const int span = width / n;
  // Buttons shrink on narrow docks so they keep apart.
  const int r = std::min(n <= 4 ? l.px(26) : l.px(23), span / 2 - l.px(3));
  const bool focus = this->hub_->uses_focus();
  // A label gets its slot, plus room its neighbours' shorter labels leave
  // on both sides ("Calendar" between "Tasks" and "More" on five buttons).
  // The outer two keep to their slot.
  const int slot = span - l.px(2);
  std::vector<int> widths(n);
  for (int i = 0; i < n; i++)
    widths[i] = text_width(display, this->small_font_, this->items_[i].label);
  auto spare = [&](int i) { return i < 0 || i >= n ? 0 : std::max(0, (slot - widths[i]) / 2); };
  for (int i = 0; i < n; i++) {
    const MenuItem &item = this->items_[i];
    const int room = slot + 2 * std::min(spare(i - 1), spare(i + 1));
    const int cx = left + span * i + span / 2;
    const int cy = top + l.px(52);
    if (focus && i == this->dock_focus_.index()) {
      const Color ring = theme.on(theme.dock, theme.focus_color());
      for (int k = l.px(3); k <= l.px(5); k++)
        display.circle(cx, cy, r + k, ring);
    }
    const Color bg = theme.fit(item.background);
    display.filled_circle(cx, cy, r, bg);
    // Gray screens: a button the same gray as the dock gets an edge.
    if (theme.mode != ColorMode::FULL && bg.raw_32 == theme.dock.raw_32)
      display.circle(cx, cy, r, theme.dock_ink);
    print_icon_(display, cx, cy, item.icon, theme.on(bg, item.foreground), bg);
    if (UiTree::enabled()) {
      // A button showing short text ("25") is named with it: "25 min".
      const bool glyph = !item.icon.empty() && (uint8_t) item.icon[0] >= 0xF0;
      UiTree::add("button", glyph || item.icon.empty() ? item.label : item.icon + " " + item.label,
                  Rect{cx - r, cy - r, 2 * r, 2 * r}, focus && i == this->dock_focus_.index());
    }
    display.print(cx, cy + r + l.px(13), this->small_font_, theme.dock_ink, TextAlign::CENTER,
                  fit_text(display, this->small_font_, item.label, room).c_str(), theme.dock);
  }
}

// --- Board and apps ---------------------------------------------------------

int MenuController::pages_() const {
  const int n = this->hub_->apps().size();
  const int per = this->layout_().tiles_per_page();
  return std::max(1, (n + per - 1) / per);
}

std::string MenuController::app_name_(const App &app, const Theme &theme) const {
  auto it = theme.apps.find(app.id);
  return it != theme.apps.end() && !it->second.name.empty() ? it->second.name : app.name;
}

std::string MenuController::app_icon_(const App &app, const Theme &theme) const {
  auto it = theme.apps.find(app.id);
  return it != theme.apps.end() && !it->second.icon.empty() ? it->second.icon : app.icon;
}

void MenuController::draw_frame_(Display &display, const Theme &theme, const std::string &title) {
  const Layout &l = this->layout_();
  const int W = l.width, H = l.height, header_h = l.header.h;
  Color header_bg = theme.frame;
  switch (theme.style) {
    case ThemeStyle::WOOD: {
      const int rim = l.px(5);
      display.fill(theme.edge);
      display.filled_rectangle(rim, rim, W - 2 * rim, H - 2 * rim, theme.frame);
      for (int y = rim; y < H - rim; y += l.px(9))
        display.horizontal_line(rim, y, W - 2 * rim, theme.fit(shade(theme.frame, 0.9f)));
      break;
    }
    case ThemeStyle::PAPER:
      display.fill(theme.frame);
      for (int x = 0; x < W; x += l.px(24))
        display.vertical_line(x, header_h, H - header_h, theme.fit(shade(theme.frame, 0.95f)));
      display.filled_rectangle(0, 0, W, header_h - l.px(2), theme.edge);
      display.filled_rectangle(0, header_h - l.px(2), W, l.px(3), theme.accent);
      header_bg = theme.edge;
      break;
    case ThemeStyle::OUTLINE:
      display.fill(theme.frame);
      break;
  }
  const Color title_ink = theme.on(header_bg, theme.title);
  display.print(W / 2, header_h / 2, this->text_font_, title_ink, TextAlign::CENTER, title.c_str(), header_bg);
  display.print(l.px(22), header_h / 2, this->icon_font_, title_ink, TextAlign::CENTER, BACK_ICON, header_bg);
  UiTree::add("heading", title, Rect{0, 0, W, header_h});
  UiTree::add("button", "Back", l.back);
}

void MenuController::draw_card_(Display &display, const Theme &theme, const Rect &card) {
  const Layout &l = this->layout_();
  const int x = card.x, y = card.y, w = card.w, h = card.h;
  switch (theme.style) {
    case ThemeStyle::WOOD: {
      const int rim = l.px(3);
      display.filled_rectangle(x, y, w, h, theme.edge);
      display.filled_rectangle(x + rim, y + rim, w - 2 * rim, h - 2 * rim, theme.panel);
      display.filled_rectangle(x + rim, y + h - l.px(7), w - 2 * rim, l.px(4), theme.fit(shade(theme.panel, 0.88f)));
      break;
    }
    case ThemeStyle::PAPER: {
      const int drop = l.px(3);
      display.filled_rectangle(x + drop, y + drop, w, h, theme.fit(shade(theme.frame, 0.75f)));  // Shadow.
      display.filled_rectangle(x, y, w, h, theme.panel);
      display.filled_circle(x + w / 2, y + 1, l.px(4), theme.accent);  // Push pin.
      break;
    }
    case ThemeStyle::OUTLINE: {
      const int border = l.px(2);
      Utilities::Draw::roundedRectangle(&display, x, y, w, h, l.px(14), theme.accent);
      Utilities::Draw::roundedRectangle(&display, x + border, y + border, w - 2 * border, h - 2 * border, l.px(12),
                                        theme.panel);
      break;
    }
  }
}

// An app's tile: icon left and words right on roomy tiles; icon over the
// words on narrow ones (square and wide screens).
void MenuController::draw_tile_(Display &display, const Theme &theme, const App &app, const Rect &tile) {
  const Layout &l = this->layout_();
  const Color icon_color = theme.on(theme.panel, theme.has_icon_color ? theme.icon_color : app.color);
  const std::string name = this->app_name_(app, theme);
  const std::string status = app.status ? app.status() : std::string();
  if (tile.w >= l.px(130)) {
    const int tx = tile.x + l.px(54);
    const int room = tile.right() - tx - l.px(4);
    print_icon_(display, tile.x + l.px(30), tile.y + tile.h / 2 - l.px(2), this->app_icon_(app, theme), icon_color,
                theme.panel);
    display.print(tx, tile.y + l.px(30), this->text_font_, theme.ink, TextAlign::CENTER_LEFT,
                  fit_text(display, this->text_font_, name, room).c_str(), theme.panel);
    if (app.status) {
      display.print(tx, tile.y + l.px(54), this->small_font_, theme.muted, TextAlign::CENTER_LEFT,
                    fit_text(display, this->small_font_, status, room).c_str(), theme.panel);
    }
    return;
  }
  const int room = tile.w - l.px(10);
  print_icon_(display, tile.cx(), tile.y + tile.h * 33 / 100, this->app_icon_(app, theme), icon_color, theme.panel);
  display.print(tile.cx(), tile.y + tile.h * 66 / 100, this->text_font_, theme.ink, TextAlign::CENTER,
                fit_text(display, this->text_font_, name, room).c_str(), theme.panel);
  if (!status.empty()) {
    display.print(tile.cx(), tile.y + tile.h * 86 / 100, this->small_font_, theme.muted, TextAlign::CENTER,
                  fit_text(display, this->small_font_, status, room).c_str(), theme.panel);
  }
}

void MenuController::draw_board_(Display &display, const Theme &theme) {
  const Layout &l = this->layout_();
  this->draw_frame_(display, theme, theme.word("menu.apps", "Apps"));
  const auto &apps = this->hub_->apps();
  const int per = l.tiles_per_page();
  this->board_focus_.set_count(apps.size());
  const bool focus = this->hub_->uses_focus();
  for (int i = 0; i < per; i++) {
    const int index = this->page_ * per + i;
    if (index >= (int) apps.size())
      break;
    const Rect tile = l.tile(i);
    if (focus && index == this->board_focus_.index())
      this->draw_focus_(display, theme, tile, l.px(14));
    this->draw_card_(display, theme, tile);
    this->draw_tile_(display, theme, *apps[index], tile);
    if (UiTree::enabled())
      UiTree::add("tile", this->app_name_(*apps[index], theme), tile, focus && index == this->board_focus_.index(),
                  apps[index]->status ? apps[index]->status() : std::string());
  }
  const int pages = this->pages_();
  if (pages > 1) {
    const int step = l.px(14);
    const int x0 = l.width / 2 - (pages - 1) * step / 2;
    for (int p = 0; p < pages; p++)
      display.filled_circle(x0 + p * step, l.dots_y, l.px(4), p == this->page_ ? theme.title : theme.dot);
  }
}

void MenuController::draw_app_(Display &display, const Theme &theme, App &app) {
  const Layout &l = this->layout_();
  this->draw_frame_(display, theme, app.title ? app.title() : this->app_name_(app, theme));
  const Rect &c = l.content;
  const int x = c.x, y = c.y, w = c.w, h = c.h;
  switch (theme.style) {
    case ThemeStyle::OUTLINE: {
      const int border = l.px(2);
      Utilities::Draw::roundedRectangle(&display, x, y, w, h, l.px(14), theme.accent);
      Utilities::Draw::roundedRectangle(&display, x + border, y + border, w - 2 * border, h - 2 * border, l.px(12),
                                        theme.panel);
      break;
    }
    case ThemeStyle::PAPER: {
      const int drop = l.px(3);
      display.filled_rectangle(x + drop, y + drop, w, h, theme.fit(shade(theme.frame, 0.75f)));
      display.filled_rectangle(x, y, w, h, theme.panel);
      break;
    }
    case ThemeStyle::WOOD:
      display.filled_rectangle(x, y, w, h, theme.panel);
      break;
  }
  UiTree::add("app", this->app_name_(app, theme), c);
  if (app.draw) {
    AppView view{display,
                 theme,
                 x,
                 y,
                 w,
                 h,
                 this->text_font_,
                 this->small_font_,
                 this->icon_font_,
                 &l,
                 this->hub_->uses_focus()};
    app.draw(view);
  }
}

bool MenuController::draw_(Display &display) {
  if (!this->is_open())
    return false;
  const Theme &theme = this->hub_->theme();
  switch (this->level_) {
    case Level::DOCK:
      this->hub_->draw_persona(display);
      this->draw_dock_(display, theme);
      break;
    case Level::BOARD:
      this->draw_board_(display, theme);
      break;
    case Level::APP: {
      App *app = this->app_();
      if (app == nullptr) {
        this->level_ = Level::BOARD;
        this->draw_board_(display, theme);
      } else {
        this->draw_app_(display, theme, *app);
      }
      break;
    }
    case Level::QUICK:
      this->hub_->draw_persona(display);
      this->draw_quick_(display, theme);
      break;
    case Level::CLOSED:
      return false;
  }
  return true;
}

}  // namespace Daruma
