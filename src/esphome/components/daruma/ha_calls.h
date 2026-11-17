#pragma once

// One gate for Home Assistant actions that wait for a reply (a
// `homeassistant.action` with capture_response, on_success or on_error).
//
// Why: in ESPHome 2026.10.2, each homeassistant.action template keeps its
// own `static uint32_t call_id_counter` (api/homeassistant_service.h), so
// two actions hand out the same call ids. APIServer::handle_action_response
// (api_server.cpp) runs the FIRST callback registered under an id. A call
// sent before HA subscribes to device actions is dropped ("client has not
// subscribed to actions (yet)"), but its callback stays registered. Later,
// another action reaches that id, and HA's reply goes to the stale
// callback: a to-do check-off was answered as an old todo.get_items fetch,
// never confirmed, and flipped back.
//
// So every such call goes through here:
//   - nothing is sent until HA has been connected, with its subscription,
//     for a short settle time; calls asked for earlier wait and go then;
//   - one call is in flight at a time, so two actions can't hold one id
//     at once; the rest queue;
//   - a call with no answer frees the gate after a timeout.
// A call cut off by a disconnect can still leave a stale callback behind.
// Drop this gate when ESPHome gives call ids from one shared counter and
// forgets callbacks of dropped calls.
//
// Plain C++ with no ESPHome includes, so a host test can check it
// (tests/test_ha_calls.cpp). The hub ticks it from its loop.

#include <cstdint>
#include <deque>
#include <functional>
#include <string>
#include <utility>

namespace Daruma {

class HaCalls {
 public:
  // Sends the call. `token` must come back through done(token) from the
  // action's on_success and on_error.
  using Send = std::function<void(uint32_t token)>;

  void set_settle_ms(uint32_t ms) { this->settle_ms_ = ms; }
  void set_timeout_ms(uint32_t ms) { this->timeout_ms_ = ms; }

  // Queues a call. It goes when the gate is ready and nothing else is in
  // flight. `what` names it in logs. Past `max_queued`, the oldest waiting
  // call is dropped (its owner times out and asks again).
  void call(const std::string &what, Send send) {
    if (this->queue_.size() >= MAX_QUEUED) {
      this->dropped_++;
      this->queue_.pop_front();
    }
    this->queue_.push_back(Job{what, std::move(send)});
  }

  // The call with this token got its answer (success or error).
  void done(uint32_t token) {
    if (this->busy_ && token == this->token_)
      this->busy_ = false;
  }

  // Call often. `link`: HA is connected and subscribed to the device.
  // Returns the name of a call it sent now, or nullptr.
  const std::string *tick(uint32_t now, bool link) {
    if (!link) {
      this->linked_ = false;
      this->busy_ = false;  // Its answer can't come on a new connection.
      return nullptr;
    }
    if (!this->linked_) {
      this->linked_ = true;
      this->link_since_ = now;
    }
    if (this->busy_ && now - this->sent_at_ >= this->timeout_ms_) {
      this->busy_ = false;
      this->timeouts_++;
    }
    if (!this->ready(now) || this->busy_ || this->queue_.empty())
      return nullptr;
    this->sending_ = std::move(this->queue_.front());
    this->queue_.pop_front();
    this->busy_ = true;
    this->sent_at_ = now;
    this->token_ = ++this->next_token_;
    this->sending_.send(this->token_);
    return &this->sending_.what;
  }

  // HA has been linked for the settle time.
  bool ready(uint32_t now) const { return this->linked_ && now - this->link_since_ >= this->settle_ms_; }
  bool busy() const { return this->busy_; }
  // Nothing to do at `now`: no call waits for its answer, and none is ready
  // to go. Calls held back until HA has settled wait for time to pass.
  bool idle(uint32_t now) const { return !this->busy_ && (this->queue_.empty() || !this->ready(now)); }
  size_t queued() const { return this->queue_.size(); }
  uint32_t timeouts() const { return this->timeouts_; }
  uint32_t dropped() const { return this->dropped_; }

 protected:
  static const size_t MAX_QUEUED = 16;
  struct Job {
    std::string what;
    Send send;
  };
  std::deque<Job> queue_;
  Job sending_;
  uint32_t settle_ms_{3000};
  // Under the apps' own 10 s (a Tasks check-off flips back, Calendar fails
  // the fetch), so a call queued behind a lost one still gets its turn.
  uint32_t timeout_ms_{8000};
  bool linked_{false};
  uint32_t link_since_{0};
  bool busy_{false};
  uint32_t sent_at_{0};
  uint32_t token_{0};
  uint32_t next_token_{0};
  uint32_t timeouts_{0};
  uint32_t dropped_{0};
};

}  // namespace Daruma
