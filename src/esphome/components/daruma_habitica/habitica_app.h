#pragma once

// The Habitica module's device side: the hero's stats, the reactions they
// play, and the Character app.
//
// Each stat entity is an HA state subscription made in setup(), so HA
// pushes every change while it is connected. Each push goes through
// apply_stats(), the same entry point a score reply can use. The model
// (habitica.h) decides what plays. A button on the sheet runs the presser:
// the package's script with `homeassistant.action: button.press`. It wants
// no reply, so it skips the hub's gate for HA calls.

#include <functional>
#include <string>
#include <vector>

#include "esphome/components/daruma/focus.h"
#include "esphome/components/daruma/hub.h"
#include "esphome/core/component.h"
#include "esphome/core/defines.h"
#include "esphome/core/preferences.h"
#include "habitica.h"

#ifdef USE_DARUMA_HABITS
#include "esphome/components/daruma_habits/habits_app.h"
#endif

namespace Daruma {

class HabiticaApp : public esphome::Component {
 public:
  // Presses an HA button entity.
  using Presser = std::function<void(const std::string &entity)>;

  void set_hub(Hub *hub) { this->hub_ = hub; }
  void set_presser(Presser presser) { this->presser_ = std::move(presser); }
  void set_hp_max(float hp) { this->hp_max_ = hp; }
  void set_hurt_threshold(float hp) { this->model_.set_hurt_threshold(hp); }
  void set_message_seconds(int seconds) { this->message_seconds_ = seconds; }
  // Follows an HA entity into one stat field ("health", "level", "inn"...).
  void follow(const std::string &field, const std::string &entity);
  // An HA button the sheet offers while it is available ("potion", ...).
  void add_button(const std::string &key, const std::string &entity);

  void setup() override;
  void loop() override;
  float get_setup_priority() const override { return esphome::setup_priority::LATE; }

  // New numbers from anywhere: the known fields of `news`. Plays what the
  // change calls for. Other modules (a score reply) call it too.
  // Returns how long the reaction it played lasts (0 for none).
  uint32_t apply_stats(const HabiticaStats &news);
  // An event numbers can't show: "drop" (a reaction and its words) or
  // "quest" (progress words). The message goes in the bubble.
  void event(const std::string &kind, const std::string &message);
  // A score reply: its numbers, then its drop once the numbers' reaction
  // (a level up) has played.
  void apply_reply(const HabiticaStats &news, const std::string &drop);
  // One row of the hero's stats in `row`: the level, three thin bars (HP,
  // XP, MP) and the gold. Other apps draw it as a header.
  void draw_header(AppView &v, const Rect &row);
#ifdef USE_DARUMA_HABITS
  // The Habits app shows the stats row, and its replies come here.
  void attach_habits(HabitsApp *habits);
#endif
  const HabiticaStats &stats() const { return this->model_.stats(); }

  // App hooks, for Daruma::App.
  std::string status();
  void draw(AppView &v);
  bool input(Input input, int x, int y);
  void on_open();
  void on_close();
  bool back();

 protected:
  struct Button {
    std::string key;  // Its theme word: habitica.<key>.
    std::string entity;
    bool available{false};
  };
  // What a tap on the sheet's buttons area may hit, in screen coordinates.
  struct Target {
    Rect rect;
    int button{-1};  // Index in buttons_; -1 for the confirm's Cancel.
  };
  struct Saved {
    float hp, hp_max, mp, mp_max, xp, xp_next, gold;
    int level;
    int cls;  // Index in CLASSES, or -1.
    int resting;
  };

  void changed_();
  void save_();
  void restore_();
  void hold_(HabiticaActivity activity);
  std::string word_(const char *key) const;
  std::vector<int> shown_buttons_() const;
  void press_(int button);
  void tap_target_(const Target &target);
  void draw_head_(AppView &v);
  void draw_bar_(AppView &v, int row, const char *label, float value, float max, const char *color);
  void draw_buttons_(AppView &v);
  void draw_confirm_(AppView &v);
  void draw_button_(AppView &v, const Rect &r, const std::string &label, bool focused, bool primary);
  Rect buttons_area_(const AppView &v) const;

  Hub *hub_{nullptr};
  Presser presser_;
  HabiticaModel model_;
  float hp_max_{-1};
  int message_seconds_{6};
  std::vector<std::pair<std::string, std::string>> follows_;  // (field, entity)
  std::vector<Button> buttons_;
  esphome::ESPPreferenceObject pref_;

  bool open_{false};
  bool connected_{false};
  bool confirm_{false};  // Asking before a potion.
  uint32_t confirm_until_ms_{0};
  FocusRing focus_;
  std::vector<Target> targets_;
};

}  // namespace Daruma
