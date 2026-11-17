#pragma once

// Today's tasks for the Daruma Tasks app: the data, without drawing.
//
// HA trims the list before it reaches the device (see app_tasks.yaml), and
// this class keeps at most MAX_ITEMS of it. Check-offs are optimistic: the
// row flips at once, and flips back if HA says no or does not answer.

#include <cstdint>
#include <functional>
#include <string>
#include <vector>

#include "esphome/components/font/font.h"
#include "esphome/components/json/json_util.h"
#include "esphome/core/component.h"

namespace Daruma {

struct TaskItem {
  std::string id;     // The source's own ID; the to-do item's uid.
  std::string title;  // Only glyphs the font has.
  bool done{false};
  bool flagged{false};
  bool overdue{false};
  bool due_today{false};
  bool pending{false};  // A check-off was sent and HA has not answered yet.
};

class TaskList : public esphome::Component {
 public:
  static constexpr size_t MAX_ITEMS = 30;
  static constexpr size_t MAX_TITLE_BYTES = 200;
  static constexpr uint32_t NOTICE_MS = 3000;

  enum class State : uint8_t {
    EMPTY,    // Nothing fetched yet.
    LOADING,  // First fetch on the way.
    READY,    // A list is here (it may be empty).
    FAILED,   // The last fetch failed and there is no list to show.
  };

  // --- Setup ------------------------------------------------------------------
  void set_font(esphome::font::Font *font) { this->font_ = font; }
  void set_timeout(uint32_t ms) { this->timeout_ms_ = ms; }
  // Starts a fetch in HA. The answer comes back through on_fetch_*() with
  // the same generation, so a reply for an older source is ignored.
  void set_fetcher(std::function<void(int generation)> fetch) { this->fetch_ = std::move(fetch); }
  // Asks HA to mark one item done or not done. The answer comes back through
  // on_check_result().
  void set_checker(std::function<void(const std::string &id, bool done)> check) { this->check_ = std::move(check); }
  // Called after anything a screen shows changed.
  void set_on_change(std::function<void()> on_change) { this->on_change_ = std::move(on_change); }

  void loop() override;
  void dump_config() override;
  float get_setup_priority() const override { return esphome::setup_priority::DATA; }

  // --- Source -------------------------------------------------------------------
  // Where the tasks come from: an HA to-do list (todo = true, entity
  // todo.*; tasks can be checked off) or an HA script that returns the
  // list (entity script.*; read only). A change drops the list and fetches
  // the new one when HA is connected.
  void set_source(bool todo, const std::string &entity_id);
  const std::string &source() const { return this->source_; }
  bool source_valid() const { return this->source_valid_; }
  bool is_todo() const { return this->source_valid_ && this->todo_; }

  // --- Data path ----------------------------------------------------------------
  // The app's switch: off stops every fetch.
  void set_enabled(bool enabled) { this->enabled_ = enabled; }
  // Fetch the list unless a fetch is already on the way.
  void refresh();
  // A background refresh: skipped while a check-off waits for HA, or soon
  // after one, so rows do not move under a finger. Also skipped after a
  // fetch got no answer, until HA answers again: HA keeps no record of a
  // call it may not run, but the device keeps one per call.
  void refresh_idle();
  // The same, from the main loop (safe to call while drawing).
  void refresh_soon() {
    this->defer([this]() { this->refresh(); });
  }
  // The parsed reply of an HA action. The list is under "response", either
  // as JSON or as a string that holds JSON (HA parses template output when
  // it can).
  void on_fetch_response(int generation, ArduinoJson::JsonObjectConst response);
  void on_fetch_error(int generation, const std::string &error);
  // The open count from the source entity's state. NaN when unknown.
  void set_open_count(float count);
  // Tap on an item: flip it now, then ask HA. False when it cannot.
  bool toggle(size_t index);
  // HA's answer to a check-off. ok = HA did it.
  void on_check_result(const std::string &id, bool done, bool ok);

  // --- Reading ------------------------------------------------------------------
  State state() const { return this->state_; }
  bool can_check() const { return this->is_todo(); }
  const std::vector<TaskItem> &items() const { return this->items_; }
  // Open tasks in the source (may be more than items() holds). -1 = unknown.
  int open_count() const { return this->open_count_; }
  // Open tasks that HA left out of the trimmed list.
  int hidden_open() const;
  // A short reason for the last failure, for the screen.
  const std::string &error() const { return this->error_; }
  // A short message for a few seconds after something did not work. Empty
  // when there is none.
  const std::string &notice() const { return this->notice_; }
  // True when the font can draw this code point.
  bool has_glyph(uint32_t code_point) const;

 protected:
  struct Pending {
    std::string id;
    bool done;
    uint32_t until;
  };

  bool parse_(ArduinoJson::JsonVariantConst body);
  std::string clean_title_(const char *text) const;
  void set_done_(const std::string &id, bool done, bool pending);
  void changed_();
  void notify_(const char *text);

  static constexpr uint32_t QUIET_MS = 60000;  // refresh_idle() waits this long after a tap.

  esphome::font::Font *font_{nullptr};
  std::string source_;
  bool todo_{false};
  bool source_valid_{false};
  uint32_t last_toggle_{0};
  uint32_t timeout_ms_{10000};
  std::function<void(int)> fetch_;
  std::function<void(const std::string &, bool)> check_;
  std::function<void()> on_change_;

  State state_{State::EMPTY};
  std::vector<TaskItem> items_;
  std::vector<Pending> pending_;
  int open_count_{-1};
  std::string error_;
  std::string notice_;
  uint32_t notice_until_{0};
  bool fetching_{false};
  bool enabled_{true};
  bool silent_{false};  // The last fetch timed out; HA has not answered since.
  int generation_{0};   // Goes up with each source change.
  uint32_t fetch_until_{0};
};

}  // namespace Daruma
