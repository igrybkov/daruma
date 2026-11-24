#pragma once

#include <map>
#include <string>
#include <vector>

#include "esphome/components/daruma/hub.h"
#include "esphome/core/component.h"
#include "esphome/core/helpers.h"
#include "prompt_layout.h"
#include "prompt_stack.h"

namespace Daruma {

// Full-screen cards that Home Assistant shows, updates and closes, and the
// answers that go back (see prompt_stack.h for the rules).
//
// On screen: urgent and game prompts draw over the menu and apps; info
// prompts draw under them, so an open menu hides them until it closes. A
// tap outside the card or the red circle (navigation `back`) dismisses;
// NEXT, PREV and SELECT move a focus ring on boards without touch. A
// prompt plays its state on the persona (activity owner "prompts")
// while it is on top, and its sound when it first shows: `notify`, or
// `urgent`, which repeats every 15 s while nobody answers.
//
// As a module it offers prompts.dismiss.
class PromptController : public esphome::Component, public Module {
 public:
  PromptController() : Module("prompts") {}

  void set_fonts(esphome::display::BaseFont *title, esphome::display::BaseFont *text) {
    this->title_font_ = title;
    this->text_font_ = text;
  }
  // Info prompts wait while any owner holds this activity (focus), and
  // while the hub holds cards (Do not disturb).
  void add_hold_back(StateId activity) { this->hold_back_.push_back(activity); }
  // (prompt id, choice, index, reason) for every answer, except a close from HA.
  template<typename F> void add_on_answer_callback(F &&callback) {
    this->answer_callback_.add(std::forward<F>(callback));
  }
  // (prompt id, style, sound or "") the first time a prompt is drawn. The
  // controller plays the sound itself.
  template<typename F> void add_on_shown_callback(F &&callback) {
    this->shown_callback_.add(std::forward<F>(callback));
  }

  void setup(Hub &hub) override;
  void loop() override;
  void dump_config() override;

  // --- API actions. Each returns "" or what was wrong with the call. ----------
  // An empty string or list, or 0 for the timeout, keeps a field's default
  // (see docs/prompts.md).
  std::string show(const std::string &id, const std::string &layout, const std::string &title, const std::string &body,
                   const std::vector<std::string> &options, const std::vector<std::string> &marks,
                   const std::string &style, int timeout_s, const std::string &state, const std::string &sound,
                   bool dismissable, uint32_t ask = 0);
  std::string update(const std::string &id, const std::string &body, const std::vector<std::string> &marks,
                     int countdown_s);
  std::string close(const std::string &id);
  // What a show or update call found wrong, kept by its API call id until
  // its api.respond reads it: call_error() for success, then take_call_error().
  void set_call_error(uint32_t call_id, std::string error) {
    if (!error.empty())
      this->call_errors_[call_id] = std::move(error);
  }
  std::string call_error(uint32_t call_id) const {
    auto it = this->call_errors_.find(call_id);
    return it == this->call_errors_.end() ? std::string() : it->second;
  }
  std::string take_call_error(uint32_t call_id) {
    std::string error = this->call_error(call_id);
    this->call_errors_.erase(call_id);
    return error;
  }

  // `ask`: shows the prompt and keeps its answer for this API call.
  void ask(uint32_t call_id, const std::string &id, const std::string &layout, const std::string &title,
           const std::string &body, const std::vector<std::string> &options, const std::vector<std::string> &marks,
           const std::string &style, int timeout_s, const std::string &state, const std::string &sound,
           bool dismissable);
  // True once the call has an answer, or failed.
  bool ask_done(uint32_t call_id) const;
  // "" unless the call was invalid.
  std::string ask_error(uint32_t call_id) const;
  struct Reply {
    std::string id;
    std::string choice;
    int index{-1};
    std::string reason;
  };
  // The call's answer, which it forgets. A call still waiting ends now, as a timeout.
  Reply take_ask(uint32_t call_id);

  // The prompt on screen goes, unless it is not dismissable.
  void dismiss();

  // An API list argument (FixedVector or std::vector) as a std::vector.
  template<typename L> static std::vector<std::string> list(const L &items) {
    return std::vector<std::string>(items.begin(), items.end());
  }

 protected:
  struct AskState {
    bool done{false};
    std::string error;
    Answer answer;
  };

  bool holding_info_() const;
  Prompt *current_();
  void flush_();
  void changed_();
  std::string shown_text_(esphome::display::BaseFont *font, const std::string &text, size_t max_bytes) const;
  std::string sound_for_(const Prompt &p) const;

  // Sound: the first one, and the urgent repeats.
  void play_(const Prompt &p);
  void replay_urgent_(const Prompt *p, uint32_t now);

  // Input.
  bool on_input_(bool urgent_layer, Input input, int x, int y);
  void focus_on_(Prompt &p);
  void move_focus_(Prompt &p, int step);
  // The red circle, or a tap outside the card. Not dismissable: nothing.
  void dismiss_(Prompt *p);

  // Drawing.
  bool draw_(esphome::display::Display &display, bool urgent_layer);
  PromptMetrics metrics_(esphome::display::Display &display) const;
  PromptGeometry geometry_(esphome::display::Display &display, const PromptMetrics &m, const Prompt &p) const;
  void draw_prompt_(esphome::display::Display &display, Prompt &p);

  Hub *hub_{nullptr};
  esphome::display::BaseFont *title_font_{nullptr};
  esphome::display::BaseFont *text_font_{nullptr};
  std::vector<StateId> hold_back_;
  bool was_holding_{false};
  esphome::CallbackManager<void(const std::string &, const std::string &, int, const std::string &)> answer_callback_;
  esphome::CallbackManager<void(const std::string &, const std::string &, const std::string &)> shown_callback_;

  PromptStack stack_;
  std::map<uint32_t, AskState> asks_;
  std::map<uint32_t, std::string> call_errors_;
  StateId attention_{static_cast<StateId>(0)};

  uint32_t active_seq_{0};    // The prompt whose state the persona plays.
  uint32_t drawn_seq_{0};     // The prompt drawn last.
  uint32_t announce_seq_{0};  // Drawn for the first time; loop() plays its sound.
  uint32_t focus_seq_{0};     // The prompt the focus and scroll belong to.
  FocusRing focus_;           // Drawn only on boards that use a focus.
  int first_{0};              // List: the option in the first row.
  int list_fit_{1};           // List: rows that fit.
  ListScroll scroll_;         // List: when it last changed page.
  int32_t drawn_tick_{-1};    // The countdown second (minute on slow screens) last drawn.
  PromptGeometry geometry_drawn_;
  uint32_t replay_seq_{0};  // The urgent prompt whose sound repeats.
  uint32_t replay_at_{0};
  uint8_t played_{0};  // Times its sound played.

  // An urgent prompt plays its sound this often while unanswered, this
  // many times in all.
  static const uint32_t URGENT_REPEAT_MS = 15000;
  static const uint8_t URGENT_PLAYS = 3;
};

}  // namespace Daruma
