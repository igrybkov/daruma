#pragma once

// Messages from Home Assistant that wait while cards are held (Do not
// disturb, or an activity such as focus). Plain C++, host-tested
// (tests/test_card_queue.cpp).
//
// - push() keeps at most `cap` messages: a new one past the cap drops the
//   oldest.
// - pop() gives the oldest that has not waited longer than `keep_ms`, and
//   drops the ones that have.
// - Times are millis(); the math wraps.

#include <cstdint>
#include <deque>
#include <string>

namespace Daruma {

struct CardLimits {
  int cap{5};                      // At most this many wait.
  uint32_t keep_ms{12 * 3600000};  // A card that waited longer drops.
};

struct QueuedMessage {
  std::string text;
  int seconds{0};
  uint32_t arrived{0};
};

class CardQueue {
 public:
  void push(const std::string &text, int seconds, uint32_t now, const CardLimits &limits) {
    if (limits.cap <= 0)
      return;
    this->queue_.push_back(QueuedMessage{text, seconds, now});
    while ((int) this->queue_.size() > limits.cap)
      this->queue_.pop_front();
  }

  // The oldest message still in time. False when none is left.
  bool pop(uint32_t now, const CardLimits &limits, QueuedMessage *out) {
    while (!this->queue_.empty()) {
      QueuedMessage m = this->queue_.front();
      this->queue_.pop_front();
      if (now - m.arrived <= limits.keep_ms) {
        *out = m;
        return true;
      }
    }
    return false;
  }

  bool empty() const { return this->queue_.empty(); }
  size_t size() const { return this->queue_.size(); }
  void clear() { this->queue_.clear(); }

 protected:
  std::deque<QueuedMessage> queue_;
};

}  // namespace Daruma
