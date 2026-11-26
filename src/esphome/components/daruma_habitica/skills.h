#pragma once

// The Character app's Skills: the class's skills from the skills script,
// a question before a cast, a picker for a task skill, and the cast.
//
// The package runs the script through the hub's gate (habitica.yaml):
// {op: list} for the list, {op: cast, id, task} for a cast. A cast plays
// `cast` and takes its MP off at once; the next real number replaces the
// guess. An error puts the MP back.

#include <functional>
#include <string>
#include <utility>
#include <vector>

#include "esphome/components/daruma/focus.h"
#include "esphome/components/daruma/hub.h"
#include "habitica.h"

namespace Daruma {

class HabiticaApp;

class HabiticaSkills {
 public:
  using Fetch = std::function<void(int generation)>;
  using Cast = std::function<void(int seq, const std::string &id, const std::string &task)>;
  // (id, title) of the tasks a task skill may target.
  using Tasks = std::function<std::vector<std::pair<std::string, std::string>>()>;

  explicit HabiticaSkills(HabiticaApp *app) : app_(app) {}

  void set_fetcher(Fetch f) { this->fetch_ = std::move(f); }
  void set_caster(Cast c) { this->cast_ = std::move(c); }
  // True: ask before a self or party skill.
  void set_ask(std::function<bool()> ask) { this->ask_ = std::move(ask); }
  void set_tasks(Tasks tasks) { this->tasks_ = std::move(tasks); }
  void set_timeout(uint32_t ms) { this->timeout_ms_ = ms; }
  bool enabled() const { return static_cast<bool>(this->fetch_); }

  // The list comes on screen, and is fetched again.
  void open();
  void close() { this->view_ = View::NONE; }
  bool active() const { return this->view_ != View::NONE; }
  // The header while a view is up: "Skills", or the skill being aimed.
  std::string title() const;
  // One view back: the picker or the question to the list, the list away.
  bool back();
  void loop(uint32_t now);

  void on_list(int generation, const std::string &text);
  void on_list_error(int generation);
  void on_cast(int seq, const std::string &text);
  void on_cast_error(int seq, const std::string &error);

  void draw(AppView &v);
  bool input(Input input, int x, int y);
  // The cast's news, or a failure, for a few seconds; "" for none.
  std::string notice(uint32_t now) const;
  const std::vector<HabiticaSkill> &skills() const { return this->skills_; }

 protected:
  enum class View { NONE, LIST, ASK, PICK };
  struct Target {
    Rect rect;
    int index;  // A skill, a task, or -1 for Cancel.
  };

  std::string word_(const std::string &key) const;
  void refresh_();
  const Target *focused_target_() const;
  void act_(const Target &t);
  void tap_skill_(int index);
  void cast_now_(int index, const std::string &task);
  void finish_(bool ok);
  void notify_(const std::string &text);
  void changed_();
  void draw_list_(AppView &v);
  void draw_row_(AppView &v, const Rect &r, const HabiticaSkill &k, bool focused);
  void draw_ask_(AppView &v);
  void draw_pick_(AppView &v);
  void draw_message_(AppView &v, const std::string &text);
  void draw_pill_(AppView &v, const Rect &r, const std::string &label, bool focused, bool primary);
  bool scroll_(Input input, int total);
  void draw_scroll_(AppView &v, const Rect &area, int total);
  int count_() const;

  HabiticaApp *app_;
  Fetch fetch_;
  Cast cast_;
  std::function<bool()> ask_;
  Tasks tasks_;
  uint32_t timeout_ms_{10000};

  View view_{View::NONE};
  std::vector<HabiticaSkill> skills_;
  bool loaded_{false};
  bool failed_{false};
  bool fetching_{false};
  uint32_t fetch_at_{0};
  int generation_{0};

  int chosen_{-1};  // The skill being asked about or aimed.
  std::vector<std::pair<std::string, std::string>> picks_;
  bool casting_{false};
  int seq_{0};
  uint32_t cast_at_{0};
  float mp_before_{-1};
  std::string casting_name_;

  std::string notice_;
  uint32_t notice_at_{0};
  std::string shown_notice_;

  FocusRing focus_;
  int first_{0};
  int rows_{1};
  std::vector<Target> targets_;
};

}  // namespace Daruma
