#pragma once

// The Settings page: one row per setting the modules offer (Hub::settings()),
// each with its icon, its label and a switch. A tap on a row flips it.
// Boards without touch move a focus over the rows (NEXT, PREV) and flip the
// focused one (SELECT). More rows than fit scroll with vertical swipes.

#include <string>

#include "esphome/components/daruma/focus.h"
#include "esphome/components/daruma/hub.h"
#include "esphome/core/component.h"
#include "settings_rows.h"

namespace Daruma {

class SettingsApp : public esphome::Component {
 public:
  void set_hub(Hub *hub) { this->hub_ = hub; }
  void set_theme_prefix(const std::string &prefix) { this->prefix_ = prefix; }

  void on_open();
  void draw(AppView &v);
  bool input(Input input, int x, int y);

 protected:
  std::string word_(const Theme &theme, const char *key) const;
  int count_() const { return this->hub_ != nullptr ? (int) this->hub_->settings().size() : 0; }
  void flip_(int index);
  bool move_focus_(bool forward);
  void scroll_(int rows);
  void draw_row_(AppView &v, const Setting &s, int y, bool focused);
  void draw_switch_(AppView &v, int right, int cy, bool on, bool held);
  void draw_scroll_bar_(AppView &v);

  Hub *hub_{nullptr};
  std::string prefix_{"settings"};
  int first_{0};
  FocusRing focus_;
  SettingsRows rows_;  // From the last draw, for taps.
};

}  // namespace Daruma
