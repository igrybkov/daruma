#include "task_list.h"

#include <cmath>
#include <cstring>

#include "esphome/components/api/api_server.h"
#include "esphome/core/hal.h"
#include "esphome/core/log.h"
#include "esphome/components/daruma/text.h"

namespace Daruma {

static const char *const TAG = "daruma_tasks";

using ArduinoJson::JsonArrayConst;
using ArduinoJson::JsonDocument;
using ArduinoJson::JsonObjectConst;
using ArduinoJson::JsonVariantConst;

static bool ha_connected() {
  return esphome::api::global_api_server != nullptr && esphome::api::global_api_server->is_connected();
}

static bool expired(uint32_t until) { return (int32_t) (esphome::millis() - until) >= 0; }

// A plain entity ID in the source's domain ("todo.home" for a to-do list,
// "script.task_list" for a script): lower-case letters, digits and
// underscores after the dot. It names the HA action or its target, so
// nothing else is let through.
static bool valid_source(bool todo, const std::string &id) {
  if (id.rfind(todo ? "todo." : "script.", 0) != 0)
    return false;
  const size_t dot = id.find('.');
  if (dot + 1 >= id.size() || id.size() > 120)
    return false;
  for (size_t i = dot + 1; i < id.size(); i++) {
    const char c = id[i];
    if (!((c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '_'))
      return false;
  }
  return true;
}

void TaskList::dump_config() {
  ESP_LOGCONFIG(TAG, "Tasks:\n  Source: %s (%s)\n  Timeout: %u ms", this->source_.c_str(),
                !this->source_valid_ ? "invalid" : (this->is_todo() ? "to-do list" : "read only"),
                (unsigned) this->timeout_ms_);
}

void TaskList::set_source(bool todo, const std::string &entity_id) {
  if (entity_id == this->source_ && todo == this->todo_)
    return;
  this->source_ = entity_id;
  this->todo_ = todo;
  this->source_valid_ = valid_source(todo, entity_id);
  this->items_.clear();
  this->pending_.clear();
  this->open_count_ = -1;
  this->fetching_ = false;
  this->generation_++;  // Replies for the old source are dropped.
  ESP_LOGI(TAG, "Task source: %s %s", todo ? "to-do list" : "script", entity_id.c_str());
  if (!this->source_valid_) {
    ESP_LOGW(TAG, "The entity must be a %s entity ID", todo ? "todo.*" : "script.*");
    this->error_ = todo ? "The entity must be a todo.* list" : "The entity must be a script.*";
    this->state_ = State::FAILED;
  } else {
    this->state_ = State::EMPTY;
    if (ha_connected())
      this->refresh();
  }
  this->changed_();
}

void TaskList::refresh_idle() {
  if (this->silent_ || !this->pending_.empty())
    return;
  if (this->last_toggle_ != 0 && esphome::millis() - this->last_toggle_ < QUIET_MS)
    return;
  if (ha_connected())
    this->refresh();
}

void TaskList::loop() {
  if (!this->notice_.empty() && expired(this->notice_until_)) {
    this->notice_.clear();
    this->changed_();
  }
  if (this->fetching_ && expired(this->fetch_until_)) {
    // HA drops an action it may not run without a reply, so silence most
    // often means "Allow the device to perform Home Assistant actions" is off.
    ESP_LOGW(TAG, "No answer to the task fetch");
    this->fetching_ = false;
    this->silent_ = true;
    this->error_ = "No answer from Home Assistant";
    if (this->state_ == State::LOADING)
      this->state_ = State::FAILED;
    if (this->state_ == State::READY)
      this->notify_("Could not refresh");
    this->changed_();
  }
  for (auto it = this->pending_.begin(); it != this->pending_.end();) {
    if (!expired(it->until)) {
      ++it;
      continue;
    }
    ESP_LOGW(TAG, "No answer to a check-off; undoing it");
    const Pending gone = *it;
    it = this->pending_.erase(it);
    this->set_done_(gone.id, !gone.done, false);
    this->notify_("Not saved: no answer");
    this->changed_();
  }
}

void TaskList::refresh() {
  if (!this->enabled_ || this->fetching_ || !this->fetch_)
    return;
  if (!this->source_valid_) {
    this->state_ = State::FAILED;
    this->changed_();
    return;
  }
  if (!ha_connected()) {
    this->error_ = "Home Assistant is not connected";
    if (this->state_ == State::READY) {
      this->notify_("Home Assistant is not connected");
    } else {
      this->state_ = State::FAILED;
    }
    this->changed_();
    return;
  }
  this->fetching_ = true;
  this->fetch_until_ = esphome::millis() + this->timeout_ms_;
  if (this->state_ != State::READY)
    this->state_ = State::LOADING;
  this->changed_();
  this->fetch_(this->generation_);
}

void TaskList::on_fetch_response(int generation, JsonObjectConst response) {
  if (generation != this->generation_) {
    ESP_LOGD(TAG, "Dropping a reply for an old task source");
    return;
  }
  this->fetching_ = false;
  this->silent_ = false;
  JsonVariantConst body = response["response"];
  bool ok;
  if (body.is<const char *>()) {
    const char *text = body.as<const char *>();
    JsonDocument doc = esphome::json::parse_json(reinterpret_cast<const uint8_t *>(text), strlen(text));
    ok = this->parse_(doc.as<JsonVariantConst>());
  } else {
    ok = this->parse_(body);
  }
  if (!ok) {
    ESP_LOGW(TAG, "Task reply has no list");
    this->error_ = "Home Assistant sent no list";
    if (this->state_ != State::READY)
      this->state_ = State::FAILED;
  }
  this->changed_();
}

void TaskList::on_fetch_error(int generation, const std::string &error) {
  if (generation != this->generation_)
    return;
  ESP_LOGW(TAG, "Task fetch failed: %s", error.c_str());
  this->fetching_ = false;
  this->silent_ = false;
  this->error_ = "Home Assistant said no";
  if (this->state_ == State::READY) {
    this->notify_("Could not refresh");
  } else {
    this->state_ = State::FAILED;
  }
  this->changed_();
}

bool TaskList::parse_(JsonVariantConst body) {
  JsonArrayConst rows = body["t"];
  if (rows.isNull())
    return false;
  std::vector<TaskItem> items;
  items.reserve(std::min(rows.size(), MAX_ITEMS));
  int open = 0;
  for (JsonArrayConst row : rows) {
    if (items.size() >= MAX_ITEMS)
      break;
    TaskItem item;
    item.id = row[0] | "";
    item.title = this->clean_title_(row[1] | "");
    if (item.title.empty())
      item.title = "(no title)";
    for (const char *flag = row[2] | ""; *flag != '\0'; flag++) {
      switch (*flag) {
        case 'x':
          item.done = true;
          break;
        case 'f':
          item.flagged = true;
          break;
        case 'o':
          item.overdue = true;
          break;
        case 'd':
          item.due_today = true;
          break;
        default:
          break;
      }
    }
    // A check-off still on its way wins over what HA had a moment ago.
    for (const Pending &p : this->pending_) {
      if (p.id == item.id) {
        item.done = p.done;
        item.pending = true;
      }
    }
    if (!item.done)
      open++;
    items.push_back(std::move(item));
  }
  this->items_ = std::move(items);
  this->open_count_ = std::max(body["n"] | open, open);
  this->state_ = State::READY;
  this->error_.clear();
  ESP_LOGD(TAG, "Got %u tasks, %d open", (unsigned) this->items_.size(), this->open_count_);
  return true;
}

// Keeps what the font can draw: emoji and other missing glyphs would show as
// boxes. Line breaks and tabs become spaces; runs of spaces become one.
std::string TaskList::clean_title_(const char *text) const { return drawable_text(this->font_, text, MAX_TITLE_BYTES); }

void TaskList::set_open_count(float count) {
  this->open_count_ = std::isnan(count) ? -1 : std::max(0, (int) lroundf(count));
  this->changed_();
}

int TaskList::hidden_open() const {
  int listed = 0;
  for (const TaskItem &item : this->items_)
    listed += item.done ? 0 : 1;
  return std::max(0, this->open_count_ - listed);
}

bool TaskList::toggle(size_t index) {
  if (index >= this->items_.size())
    return false;
  if (!this->is_todo() || !this->check_) {
    this->notify_("Read-only list");
    this->changed_();
    return false;
  }
  TaskItem &item = this->items_[index];
  if (item.pending || item.id.empty())
    return false;
  if (!ha_connected()) {
    this->notify_("Home Assistant is not connected");
    this->changed_();
    return false;
  }
  const std::string id = item.id;
  const bool done = !item.done;
  this->last_toggle_ = std::max<uint32_t>(esphome::millis(), 1);
  this->pending_.push_back(Pending{id, done, esphome::millis() + this->timeout_ms_});
  this->set_done_(id, done, true);
  this->changed_();
  this->check_(id, done);
  return true;
}

void TaskList::on_check_result(const std::string &id, bool done, bool ok) {
  bool was_pending = false;
  for (auto it = this->pending_.begin(); it != this->pending_.end(); ++it) {
    if (it->id == id && it->done == done) {
      this->pending_.erase(it);
      was_pending = true;
      break;
    }
  }
  if (ok) {
    // Late success after a timeout undid it: put it back.
    this->set_done_(id, done, false);
  } else if (was_pending) {
    ESP_LOGW(TAG, "HA refused a check-off; undoing it");
    this->set_done_(id, !done, false);
    this->notify_("Not saved");
  }
  this->changed_();
}

// Sets one item's state, and moves the open count with it.
void TaskList::set_done_(const std::string &id, bool done, bool pending) {
  for (TaskItem &item : this->items_) {
    if (item.id != id)
      continue;
    if (item.done != done && this->open_count_ >= 0)
      this->open_count_ = std::max(0, this->open_count_ + (done ? -1 : 1));
    item.done = done;
    item.pending = pending;
    return;
  }
}

bool TaskList::has_glyph(uint32_t code_point) const { return Daruma::has_glyph(this->font_, code_point); }

void TaskList::notify_(const char *text) {
  this->notice_ = text;
  this->notice_until_ = esphome::millis() + NOTICE_MS;
}

void TaskList::changed_() {
  if (this->on_change_)
    this->on_change_();
}

}  // namespace Daruma
