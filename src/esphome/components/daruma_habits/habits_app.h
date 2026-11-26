#pragma once

// The Habits app: habits with plus and minus from one HA script, and the
// scores a tap sends back. The data lives in a HabitList (habits.h); this
// class wires it to ESPHome and draws it.
//
// The package (packages/app_habits.yaml) runs the script through the hub's
// gate for HA calls. Other modules may add a header row over the list
// (set_header) and hear every reply (add_on_reply). The habitica module
// uses both, when it is in the build.

#include <functional>
#include <string>
#include <vector>

#include "esphome/components/daruma/focus.h"
#include "esphome/components/daruma/hub.h"
#include "esphome/components/json/json_util.h"
#include "esphome/core/component.h"
#include "habits.h"

namespace Daruma {

class HabitsApp : public esphome::Component {
 public:
  using Header = std::function<void(AppView &v, const Rect &row)>;
  using ReplyListener = std::function<void(const HabitReply &)>;

  HabitList &list() { return this->list_; }
  void set_hub(Hub *hub) { this->hub_ = hub; }
  void set_limits(int max_waiting, int per_minute, uint32_t timeout_ms) {
    this->list_.set_limits(max_waiting, per_minute, timeout_ms);
  }
  void set_max_items(int n) { this->list_.set_max_items(n); }
  // Draws a row over the list, such as the hero's stats.
  void set_header(Header header) { this->header_ = std::move(header); }
  // Hears each score HA did, and each list that carries stats.
  void add_on_reply(ReplyListener listener) { this->listeners_.push_back(std::move(listener)); }
  // The script entity from the setting. Anything but a script.* id is no source.
  void set_source(const std::string &entity);
  void set_enabled(bool enabled) { this->enabled_ = enabled; }

  void setup() override;
  void loop() override;
  float get_setup_priority() const override { return esphome::setup_priority::DATA; }

  // Replies of the package's scripts.
  void on_list(int generation, ArduinoJson::JsonObjectConst reply);
  void on_list_error(int generation) { this->list_.on_list_error(generation); }
  void on_score(int seq, ArduinoJson::JsonObjectConst reply);
  void on_score_error(int seq, const std::string &error);
  // A background refresh, for the tile: skipped while scores are on the way.
  void refresh_idle();

  // App hooks, for Daruma::App.
  std::string status();
  void draw(AppView &v);
  bool input(Input input, int x, int y);
  void on_open();
  void on_close() { this->open_ = false; }

 protected:
  void changed_();
  void score_(size_t index, bool up);
  void select_(uint32_t now);
  std::string word_(const char *key) const;
  int rows_fit_() const;
  void draw_message_(AppView &v, const std::string &text);
  void draw_row_(AppView &v, const Rect &r, size_t index, bool focused);
  void draw_button_(AppView &v, const Rect &r, bool up, const std::string &name);
  std::string notice_text_(uint32_t now) const;
  void draw_notice_(AppView &v);
  void draw_scroll_(AppView &v, const Rect &area, int total);
  bool tap_(int x, int y);
  void move_focus_(bool forward);

  Hub *hub_{nullptr};
  HabitList list_;
  Header header_;
  std::vector<ReplyListener> listeners_;
  bool open_{false};
  bool enabled_{true};
  FocusRing focus_;
  HabitSelect select_timer_;
  int first_{0};  // First row shown.
  std::string shown_notice_;
  std::string drop_;  // The last drop's words, and when it came.
  uint32_t drop_at_{0};

  // From the last draw, for taps (app-area coordinates).
  struct Target {
    Rect rect;
    size_t index;
    bool up;
  };
  std::vector<Target> targets_;
  int rows_{1};
};

}  // namespace Daruma
