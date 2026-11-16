#pragma once

// Prompts that Home Assistant puts on screen, as a stack. Plain C++ with no
// ESPHome parts, so a host test can check the rules
// (tests/test_prompts.cpp).
//
// Rules:
// - The prompt on screen is the one with the highest style (urgent, then
//   game, then info), and the newest among equals. The others wait, and come
//   back when it closes.
// - Timeouts: 0 means the default of 60 s, -1 means none
//   (timeout_ms()). An `ask` always ends within 25 s.
// - While `hold_info` is true (a focus session), info prompts wait.
// - A new prompt with the id of an existing one replaces it. The old one
//   ends with reason REPLACED, unless it was already answered.
// - A timeout starts when the prompt first comes on screen. An `ask` also
//   has a hard deadline from the moment it was asked.
// - Choosing an option of a `choice` prompt marks it selected and locks the
//   prompt; it stays until HA updates, replaces or closes it. Other layouts
//   close on an answer.
// - Every ending is queued as an Answer (take_answers()), except a close
//   from HA, which only ends a waiting ask (reason CLOSED).

#include <algorithm>
#include <cstdint>
#include <string>
#include <utility>
#include <vector>

#include "esphome/components/daruma/states.h"

namespace Daruma {

enum class PromptLayout : uint8_t { MESSAGE, CHOICE, LIST };
enum class PromptStyle : uint8_t { INFO, GAME, URGENT };
enum class Mark : uint8_t { NONE, SELECTED, CORRECT, WRONG, HIDDEN };
enum class Reason : uint8_t { CHOSEN, DISMISSED, TIMEOUT, REPLACED, CLOSED };

inline const char *reason_name(Reason r) {
  static const char *const NAMES[] = {"chosen", "dismissed", "timeout", "replaced", "closed"};
  return NAMES[static_cast<uint8_t>(r)];
}

inline bool parse_layout(const std::string &s, PromptLayout *out) {
  if (s == "message" || s.empty()) {
    *out = PromptLayout::MESSAGE;
  } else if (s == "choice") {
    *out = PromptLayout::CHOICE;
  } else if (s == "list") {
    *out = PromptLayout::LIST;
  } else {
    return false;
  }
  return true;
}

inline bool parse_style(const std::string &s, PromptStyle *out) {
  if (s == "info" || s.empty()) {
    *out = PromptStyle::INFO;
  } else if (s == "game") {
    *out = PromptStyle::GAME;
  } else if (s == "urgent") {
    *out = PromptStyle::URGENT;
  } else {
    return false;
  }
  return true;
}

inline bool parse_mark(const std::string &s, Mark *out) {
  if (s.empty() || s == "none") {
    *out = Mark::NONE;
  } else if (s == "selected") {
    *out = Mark::SELECTED;
  } else if (s == "correct") {
    *out = Mark::CORRECT;
  } else if (s == "wrong") {
    *out = Mark::WRONG;
  } else if (s == "hidden") {
    *out = Mark::HIDDEN;
  } else {
    return false;
  }
  return true;
}

struct Prompt {
  std::string id;
  PromptLayout layout{PromptLayout::MESSAGE};
  PromptStyle style{PromptStyle::INFO};
  std::string title;
  std::string body;
  std::vector<std::string> options;
  std::vector<Mark> marks;  // One per option.
  uint32_t timeout_ms{0};   // 0: none.
  StateId state{static_cast<StateId>(0)};
  std::string sound;  // "": the state's sound; "none": silent.
  bool dismissable{true};
  uint32_t ask{0};  // The API call waiting for the answer; 0 for none.

  // Text as drawn: the font's glyphs only. Filled by the controller.
  std::string title_shown;
  std::string body_shown;
  std::vector<std::string> options_shown;

  // Run time.
  uint32_t seq{0};        // Arrival order; newer is higher.
  bool shown{false};      // Has been on screen (its sound played).
  bool timing{false};     // The timeout runs.
  uint32_t ends_at{0};    // When the timeout runs out.
  uint32_t ask_ends_at{0};
  bool answered{false};   // A choice prompt that took its answer and waits for HA.

  // Needs no answer: an info message with no button or one OK-style
  // button. Any tap dismisses it, its button included.
  bool quiet() const {
    return this->layout == PromptLayout::MESSAGE && this->style == PromptStyle::INFO && this->options.size() <= 1;
  }
  Mark mark(size_t i) const { return i < this->marks.size() ? this->marks[i] : Mark::NONE; }
  // Can this option be chosen now?
  bool choosable(int i) const {
    return !this->answered && i >= 0 && i < (int) this->options.size() && this->mark(i) != Mark::HIDDEN;
  }
  // Milliseconds left on the timeout, or -1 when none runs.
  int32_t left_ms(uint32_t now) const {
    if (!this->timing)
      return -1;
    const int32_t left = (int32_t) (this->ends_at - now);
    return left > 0 ? left : 0;
  }
};

struct Answer {
  std::string id;
  std::string choice;  // The option's text; "" when none was chosen.
  int index{-1};
  Reason reason{Reason::DISMISSED};
  uint32_t ask{0};
};

// A prompt's timeout when HA passes 0.
static const int DEFAULT_TIMEOUT_S = 60;

class PromptStack {
 public:
  static const size_t MAX_PROMPTS = 8;
  // How long an ask may wait. Home Assistant (aioesphomeapi) and the API
  // server both give up on an action response after 30 s.
  static const uint32_t ASK_LIMIT_MS = 25000;

  // Adds a prompt, or replaces the one with its id.
  void show(Prompt prompt, uint32_t now) {
    this->remove_(prompt.id, Reason::REPLACED);
    prompt.seq = ++this->seq_;
    prompt.shown = false;
    prompt.timing = false;
    prompt.answered = false;
    prompt.marks.resize(prompt.options.size(), Mark::NONE);
    if (prompt.ask != 0)
      prompt.ask_ends_at = now + ASK_LIMIT_MS;
    this->prompts_.push_back(std::move(prompt));
    // Over the cap: the lowest, oldest prompt goes.
    while (this->prompts_.size() > MAX_PROMPTS) {
      auto low = std::min_element(this->prompts_.begin(), this->prompts_.end(),
                                  [](const Prompt &a, const Prompt &b) { return rank_(a) < rank_(b); });
      this->end_(low, Reason::REPLACED, -1);
    }
  }

  // Changes a prompt's body or marks, or restarts its countdown: seconds
  // left, 0 to stop it, -1 to leave it. Null leaves a field as it is.
  bool update(const std::string &id, const std::string *body, const std::vector<Mark> *marks, int countdown_s,
              uint32_t now) {
    Prompt *p = this->find(id);
    if (p == nullptr)
      return false;
    if (body != nullptr)
      p->body = *body;
    if (marks != nullptr) {
      p->marks = *marks;
      p->marks.resize(p->options.size(), Mark::NONE);
    }
    if (countdown_s == 0) {
      p->timeout_ms = 0;
      p->timing = false;
    } else if (countdown_s > 0) {
      p->timeout_ms = (uint32_t) countdown_s * 1000;
      p->timing = p->shown;
      p->ends_at = now + p->timeout_ms;
    }
    return true;
  }

  // Closes a prompt for HA ("" closes all). A waiting ask ends as CLOSED.
  bool close(const std::string &id) {
    bool found = false;
    for (auto it = this->prompts_.begin(); it != this->prompts_.end();) {
      if (!id.empty() && it->id != id) {
        ++it;
        continue;
      }
      found = true;
      if (it->ask != 0 && !it->answered)
        this->answers_.push_back(Answer{it->id, "", -1, Reason::CLOSED, it->ask});
      it = this->prompts_.erase(it);
    }
    return found;
  }

  // The prompt on screen, or null. While hold_info is true, info prompts wait.
  Prompt *top(bool hold_info) {
    Prompt *best = nullptr;
    for (auto &p : this->prompts_) {
      if (hold_info && p.style == PromptStyle::INFO)
        continue;
      if (best == nullptr || rank_(p) > rank_(*best))
        best = &p;
    }
    return best;
  }

  // The prompt came on screen: its timeout starts the first time. Returns
  // true the first time, when its sound should play.
  bool on_screen(Prompt *p, uint32_t now) {
    if (p == nullptr || p->shown)
      return false;
    p->shown = true;
    if (p->timeout_ms > 0) {
      p->timing = true;
      p->ends_at = now + p->timeout_ms;
    }
    return true;
  }

  // Ends prompts whose time is up. Returns true when one ended.
  bool tick(uint32_t now) {
    bool ended = false;
    for (auto it = this->prompts_.begin(); it != this->prompts_.end();) {
      const bool timed_out = it->timing && (int32_t) (now - it->ends_at) >= 0;
      const bool ask_over = it->ask != 0 && !it->answered && (int32_t) (now - it->ask_ends_at) >= 0;
      if (timed_out || ask_over) {
        // An answered prompt only waits for HA; its time running out says nothing new.
        if (!it->answered)
          this->answers_.push_back(Answer{it->id, "", -1, Reason::TIMEOUT, it->ask});
        it = this->prompts_.erase(it);
        ended = true;
      } else {
        ++it;
      }
    }
    return ended;
  }

  // The user chose option `index` of prompt p. Returns false when it can't be chosen.
  bool choose(Prompt *p, int index) {
    if (p == nullptr || !p->choosable(index))
      return false;
    this->answers_.push_back(Answer{p->id, p->options[index], index, Reason::CHOSEN, p->ask});
    if (p->layout == PromptLayout::CHOICE) {
      p->answered = true;
      p->timing = false;
      p->ask = 0;
      if (p->mark(index) == Mark::NONE)
        p->marks[index] = Mark::SELECTED;
    } else {
      this->erase_(p);
    }
    return true;
  }

  // The user dismissed prompt p. An answered one just goes; one that is not
  // dismissable stays. Returns true when it went.
  bool dismiss(Prompt *p) {
    if (p == nullptr)
      return false;
    if (p->answered) {
      this->erase_(p);
      return true;
    }
    if (!p->dismissable)
      return false;
    this->answers_.push_back(Answer{p->id, "", -1, Reason::DISMISSED, p->ask});
    this->erase_(p);
    return true;
  }

  // The caller of an ask stopped waiting: the prompt ends as a timeout.
  bool expire_ask(uint32_t ask) {
    for (auto it = this->prompts_.begin(); it != this->prompts_.end(); ++it) {
      if (it->ask == ask && !it->answered) {
        this->answers_.push_back(Answer{it->id, "", -1, Reason::TIMEOUT, ask});
        this->prompts_.erase(it);
        return true;
      }
    }
    return false;
  }

  Prompt *find(const std::string &id) {
    for (auto &p : this->prompts_) {
      if (p.id == id)
        return &p;
    }
    return nullptr;
  }
  bool empty() const { return this->prompts_.empty(); }
  size_t size() const { return this->prompts_.size(); }

  std::vector<Answer> take_answers() {
    std::vector<Answer> out;
    out.swap(this->answers_);
    return out;
  }

 protected:
  static uint64_t rank_(const Prompt &p) { return ((uint64_t) p.style << 32) | p.seq; }

  void end_(std::vector<Prompt>::iterator it, Reason reason, int index) {
    if (!it->answered)
      this->answers_.push_back(Answer{it->id, "", index, reason, it->ask});
    this->prompts_.erase(it);
  }
  void remove_(const std::string &id, Reason reason) {
    for (auto it = this->prompts_.begin(); it != this->prompts_.end(); ++it) {
      if (it->id == id) {
        this->end_(it, reason, -1);
        return;
      }
    }
  }
  void erase_(Prompt *p) {
    for (auto it = this->prompts_.begin(); it != this->prompts_.end(); ++it) {
      if (&*it == p) {
        this->prompts_.erase(it);
        return;
      }
    }
  }

  std::vector<Prompt> prompts_;
  std::vector<Answer> answers_;
  uint32_t seq_{0};
};

// The timeout from the API field, in ms: 0 is the default, -1 none, else
// seconds. An ask can't outlast ASK_LIMIT_MS, so its countdown is capped
// there and the bar runs out when the prompt does.
inline uint32_t timeout_ms(int timeout_s, bool ask) {
  uint32_t ms = timeout_s == 0 ? DEFAULT_TIMEOUT_S * 1000u : timeout_s < 0 ? 0u : (uint32_t) timeout_s * 1000u;
  if (ask && (ms == 0 || ms > PromptStack::ASK_LIMIT_MS))
    ms = PromptStack::ASK_LIMIT_MS;
  return ms;
}

}  // namespace Daruma
