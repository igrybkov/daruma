#pragma once

#ifdef USE_HOST

#include <cstdint>
#include <deque>
#include <map>
#include <string>

#include "esphome/components/binary_sensor/binary_sensor.h"
#include "esphome/components/daruma/hub.h"
#include "esphome/components/daruma/ui_tree.h"
#include "esphome/components/json/json_util.h"
#include "esphome/components/sdl/sdl_esphome.h"
#include "esphome/core/component.h"

namespace Daruma {

// Daruma on a computer (see __init__.py): scripted touch and button
// input, and a recorder for frames and sounds.
class Desktop : public esphome::Component {
 public:
  void set_display(esphome::sdl::Sdl *display) { this->display_ = display; }
  void set_hub(Hub *hub) { this->hub_ = hub; }
  void add_button(const std::string &name, esphome::binary_sensor::BinarySensor *sensor) {
    this->buttons_[name] = sensor;
  }

  void setup() override;
  void loop() override;
  void dump_config() override;
  // First of all components, so its loop() runs first in each turn of the
  // main loop: that is where a runner's clock moves on (see loop()).
  float get_setup_priority() const override { return 10000.0f; }

  // --- Touch, in screen pixels. Each one starts after the touches queued
  // before it have ended.
  void tap(int x, int y);
  void hold(int x, int y, uint32_t ms);
  // A straight drag from (x1, y1) to (x2, y2) over `ms` milliseconds.
  void swipe(int x1, int y1, int x2, int y2, uint32_t ms);
  // Back and forth across (x, y), as when petting the screen.
  void stroke(int x, int y);

  // --- Buttons by the names given in `buttons:`. False for an unknown name.
  bool press(const std::string &name, uint32_t ms);

  // --- Recording. Frames and sounds go to `dir`, which is made if missing.
  // Names start with the milliseconds since the recording started.
  bool record_start(const std::string &dir);
  void record_stop();
  // While paused, frames and sounds are not saved (a runner skips ahead).
  void record_pause(bool paused) { this->paused_ = paused; }
  bool recording() const { return this->recording_; }
  // The display lambda calls begin_frame() before the hub draws and frame()
  // after: the parts on screen are listed anew, and the screen is saved.
  void begin_frame() { UiTree::clear(); }
  void frame();
  // Saves the screen as it is now to <dir>/<name>.bmp.
  bool screenshot(const std::string &dir, const std::string &name);
  // True while queued touches or button presses are still running.
  bool touch_busy() const { return !this->points_.empty() || !this->releases_.empty(); }
  // The parts on screen (UiTree) as root["ui"]: [{role, name, x, y, w, h, focused, value}],
  // the turns of the main loop: root["loops"] (all) and root["turns"] (see turns_),
  // and root["idle"], the last turn that started with nothing due (see idle_loop_).
  void describe(JsonObject root) const;
  // Renders the current persona's sound `name` to a WAV file, when recording.
  void sound(Hub *hub, const std::string &name);

 protected:
  struct Point {
    uint32_t at;  // millis() when it applies
    int x;
    int y;
    bool down;
  };
  struct Release {
    uint32_t at;
    esphome::binary_sensor::BinarySensor *sensor;
  };

  uint32_t queue_start_();
  void add_point_(uint32_t at, int x, int y, bool down) { this->points_.push_back(Point{at, x, y, down}); }

  // Nothing is due at `now`: no timer, no frame and no HA call.
  bool idle_(uint32_t now);

  esphome::sdl::Sdl *display_{nullptr};
  Hub *hub_{nullptr};
  std::map<std::string, esphome::binary_sensor::BinarySensor *> buttons_;
  std::deque<Point> points_;
  std::deque<Release> releases_;

  esphome::HighFrequencyLoopRequester high_freq_;
  void (*clock_latch_)(){nullptr};
  // Turns of the main loop that started after the one that took the current
  // time. ESPHome runs its timers at the start of a turn, before any
  // component's loop(), so they see a new time one turn after the latch.
  // From 1 on, every component has run at this time, and the timers run
  // at it on the turn that starts now.
  uint32_t turns_{0};
  uint32_t turns_ms_{0};
  // All turns of the main loop so far.
  uint32_t loops_{0};
  // The last turn that started with a whole turn already run at its time
  // and nothing due at that time: no timer, no frame, no Home Assistant
  // call to send or answer to wait for. Whatever a runner sent before the
  // turn that handled it is done by an idle turn two turns later: every
  // component has run once since, and nothing it started is left over.
  uint32_t idle_loop_{0};
  bool recording_{false};
  bool paused_{false};
  std::string dir_;
  uint32_t start_ms_{0};
  uint32_t frames_{0};
  uint32_t sounds_{0};
};

}  // namespace Daruma

#endif
