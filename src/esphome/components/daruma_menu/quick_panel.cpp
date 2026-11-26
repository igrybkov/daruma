// The quick panel: the menu's level that hangs from the top of the screen
// over the persona, with one round tile per Settings row. A tap on a tile
// flips its switch and leaves the panel open. A tap under the panel, a
// swipe up or back closes it.

#include <algorithm>

#include "esphome/core/log.h"
#include "esphome/components/daruma/draw.h"
#include "esphome/components/daruma/text.h"
#include "esphome/components/daruma/ui_tree.h"
#include "menu_controller.h"

namespace Daruma {

using esphome::Color;
using esphome::display::Display;
using esphome::display::TextAlign;

static const int QUICK_ROWS = 2;  // Rows on a page; more tiles page sideways.

void MenuController::open_quick() {
  if (!this->hub_->message().empty()) {
    this->hub_->clear_message();
    return;
  }
  if (this->quick_count_() == 0) {
    ESP_LOGW("daruma_menu", "No settings for the quick panel");
    return;
  }
  this->leave_app_();
  this->stack_.assign(1, "main");
  this->level_ = Level::QUICK;
  this->page_ = 0;
  this->quick_focus_.set_count(this->quick_count_());
  this->quick_focus_.reset();
  this->hub_->set_ui_open(true);
  this->touch_();
}

QuickGrid MenuController::quick_grid_() const {
  const Layout &l = this->layout_();
  return quick_grid(l.width, this->quick_count_(), l.px(74), l.px(80), l.px(8), QUICK_ROWS, l.px(16));
}

void MenuController::flip_quick_(int index) {
  if (index < 0 || index >= this->quick_count_())
    return;
  Setting &s = this->hub_->settings()[index];
  if (s.set)
    s.set(!s.is_on());
}

void MenuController::page_quick_(int step) {
  const int pages = quick_pages(this->quick_count_(), this->quick_grid_().per_page());
  this->page_ = std::max(0, std::min(this->page_ + step, pages - 1));
}

bool MenuController::on_quick_focus_(Input input) {
  this->quick_focus_.set_count(this->quick_count_());
  if (input == Input::NEXT) {
    this->quick_focus_.next();
  } else if (input == Input::PREV) {
    this->quick_focus_.prev();
  } else if (this->quick_focus_.valid()) {
    this->flip_quick_(this->quick_focus_.index());
  }
  this->page_ = this->quick_focus_.page(this->quick_grid_().per_page());
  this->touch_();
  return true;
}

bool MenuController::on_quick_input_(Input input, int x, int y) {
  const QuickGrid g = this->quick_grid_();
  switch (input) {
    case Input::NEXT:
    case Input::PREV:
    case Input::SELECT:
      return this->on_quick_focus_(input);
    case Input::SWIPE_UP:
      this->close();
      return true;
    case Input::SWIPE_LEFT:
    case Input::SWIPE_RIGHT:
      this->page_quick_(input == Input::SWIPE_LEFT ? 1 : -1);
      this->touch_();
      return true;
    case Input::TAP: {
      if (y >= g.height) {
        this->close();  // A tap on the persona under the panel.
        return true;
      }
      const int slot = quick_slot_at(g, x, y);
      if (slot >= 0)
        this->flip_quick_(this->page_ * g.per_page() + slot);
      this->touch_();
      return true;
    }
    default:
      return true;  // Keep the persona under the panel as it is.
  }
}

// The panel: the dock's colors, open at the top edge, rounded at the
// bottom, with a handle (or page dots) under the tiles.
void MenuController::draw_quick_(Display &display, const Theme &theme) {
  const Layout &l = this->layout_();
  const QuickGrid g = this->quick_grid_();
  const int left = l.px(4), width = l.width - 2 * left, r = l.px(18);
  auto slab = [&](int inset, Color color) {
    const int x = left + inset, w = width - 2 * inset, h = g.height - inset;
    Utilities::Draw::roundedRectangle(&display, x, 0, w, h, std::max(1, r - inset), color);
    display.filled_rectangle(x, 0, w, r, color);  // Square corners at the top edge.
  };
  if (theme.style == ThemeStyle::OUTLINE) {
    slab(0, theme.accent);
    slab(l.px(2), theme.dock);
  } else {
    slab(0, theme.dock);
  }
  UiTree::add("panel", "Quick settings", Rect{left, 0, width, g.height});

  auto &settings = this->hub_->settings();
  const int count = (int) settings.size();
  this->quick_focus_.set_count(count);
  const bool focus = this->hub_->uses_focus();
  const int per = g.per_page();
  for (int slot = 0; slot < per; slot++) {
    const int index = this->page_ * per + slot;
    if (index >= count)
      break;
    this->draw_quick_tile_(display, theme, settings[index], quick_slot_cx(g, slot), quick_slot_top(g, slot),
                           this->quick_room_(display, g, slot, index), focus && index == this->quick_focus_.index());
  }

  const int pages = quick_pages(count, per);
  const int mark_y = g.height - l.px(9);
  if (pages > 1) {
    const int step = l.px(12);
    const int x0 = l.width / 2 - (pages - 1) * step / 2;
    for (int p = 0; p < pages; p++)
      display.filled_circle(x0 + p * step, mark_y, l.px(3), p == this->page_ ? theme.dock_ink : theme.dock_muted);
  } else {
    const int hw = l.px(16), hh = std::max(2, l.px(4));
    Utilities::Draw::roundedRectangle(&display, l.width / 2 - hw, mark_y - hh / 2, 2 * hw, hh, hh / 2,
                                      theme.dock_muted);
  }
}

// A label may use the room its neighbours in the row leave free; a tile at
// the edge keeps to the pad beside it.
int MenuController::quick_room_(Display &display, const QuickGrid &g, int slot, int index) {
  auto &settings = this->hub_->settings();
  const int count = (int) settings.size();
  const int col = slot % g.cols;
  auto spare = [&](int i) {
    return quick_spare(g.cell_w, i < count ? text_width(display, this->small_font_, settings[i].label) : 0);
  };
  const int left = col == 0 ? g.pad : spare(index - 1);
  const int right = col == g.cols - 1 ? g.pad : spare(index + 1);
  return quick_label_room(g.cell_w, left, right, this->layout_().px(4));
}

// A round tile: lit in the accent while on, grey while off. A held switch
// (off for now, not by the person) shows its icon faded.
void MenuController::draw_quick_tile_(Display &display, const Theme &theme, const Setting &s, int cx, int top, int room,
                                      bool focused) {
  const Layout &l = this->layout_();
  const bool on = s.is_on(), held = s.is_held();
  const int r = l.px(21);
  const int cy = top + l.px(24);
  const Color dock = theme.dock, muted = theme.dock_muted;
  const Color off((dock.r + muted.r) / 2, (dock.g + muted.g) / 2, (dock.b + muted.b) / 2);
  const Color bg = theme.fit(on ? theme.accent : off);
  if (focused) {
    const Color ring = theme.on(theme.dock, theme.focus_color());
    for (int k = l.px(3); k <= l.px(5); k++)
      display.circle(cx, cy, r + k, ring);
  }
  display.filled_circle(cx, cy, r, bg);
  // Gray screens: a tile the same gray as the panel gets an edge.
  if (theme.mode != ColorMode::FULL && bg.raw_32 == theme.fit(dock).raw_32)
    display.circle(cx, cy, r, theme.dock_ink);
  const Color ink = theme.on(bg, on ? Color::WHITE : theme.dock_ink);
  const Color icon = held && !on ? theme.on(bg, muted) : ink;
  this->print_icon_(display, cx, cy, s.icon, icon, bg);
  UiTree::add("switch", s.label, Rect{cx - r, cy - r, 2 * r, 2 * r}, focused, quick_value_word(on, held));
  auto width = [&](const std::string &text) { return text_width(display, this->small_font_, text); };
  int y = cy + r + l.px(11);
  for (const std::string &line : quick_label_lines(s.label, room, width)) {
    display.print(cx, y, this->small_font_, theme.dock_ink, TextAlign::CENTER,
                  fit_text(display, this->small_font_, line, room).c_str(), theme.dock);
    y += l.px(15);
  }
}

}  // namespace Daruma
