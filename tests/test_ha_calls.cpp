// Host test of the gate for Home Assistant calls that wait for a reply
// (daruma/ha_calls.h).
//
//   c++ -std=c++17 -Wall -Wextra -I src/esphome/components/daruma \
//       tests/test_ha_calls.cpp -o /tmp/test_ha_calls && /tmp/test_ha_calls

#include <cstdio>
#include <string>
#include <vector>

#include "ha_calls.h"

using namespace Daruma;

static int failures = 0;

#define CHECK(cond) \
  do { \
    if (!(cond)) { \
      std::printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond); \
      failures++; \
    } \
  } while (0)

struct Log {
  std::vector<std::string> sent;
  std::vector<uint32_t> tokens;
  HaCalls::Send send(const std::string &what) {
    return [this, what](uint32_t token) {
      this->sent.push_back(what);
      this->tokens.push_back(token);
    };
  }
};

// Calls asked for at boot wait for HA and its settle time, then go one at a
// time: the boot fetches never go out before HA listens.
static void test_waits_for_ha_then_one_at_a_time() {
  HaCalls gate;
  gate.set_settle_ms(3000);
  Log log;
  gate.call("calendar", log.send("calendar"));
  gate.call("tasks", log.send("tasks"));
  gate.tick(100, false);
  gate.tick(2000, false);
  CHECK(log.sent.empty());
  gate.tick(5000, true);  // Connected: the settle time starts.
  gate.tick(7000, true);
  CHECK(log.sent.empty());
  gate.tick(8000, true);
  CHECK(log.sent.size() == 1 && log.sent[0] == "calendar");
  gate.tick(8100, true);  // Still in flight: tasks waits.
  CHECK(log.sent.size() == 1);
  gate.done(log.tokens[0]);
  gate.tick(8200, true);
  CHECK(log.sent.size() == 2 && log.sent[1] == "tasks");
  CHECK(gate.busy() && gate.queued() == 0);
}

// The check-off that went wrong: a fetch, then todo.update_item. Each goes
// alone, so each reply meets its own call.
static void test_update_waits_for_the_fetch() {
  HaCalls gate;
  gate.set_settle_ms(0);
  Log log;
  gate.tick(1, true);
  gate.call("fetch", log.send("fetch"));
  gate.call("update", log.send("update"));
  gate.tick(2, true);
  gate.tick(3, true);
  CHECK(log.sent.size() == 1);
  gate.done(log.tokens[0]);
  gate.tick(4, true);
  CHECK(log.sent.size() == 2 && log.sent[1] == "update");
}

// A late answer of a timed-out call must not free the next one.
static void test_timeout_and_late_answer() {
  HaCalls gate;
  gate.set_settle_ms(0);
  gate.set_timeout_ms(1000);
  Log log;
  gate.tick(1, true);
  gate.call("a", log.send("a"));
  gate.call("b", log.send("b"));
  gate.tick(10, true);
  gate.tick(1010, true);  // a timed out; b goes.
  CHECK(gate.timeouts() == 1);
  CHECK(log.sent.size() == 2);
  gate.done(log.tokens[0]);  // a's late answer.
  CHECK(gate.busy());
  gate.done(log.tokens[1]);
  CHECK(!gate.busy());
}

// A disconnect frees the gate and starts the settle time over; waiting calls stay.
static void test_disconnect() {
  HaCalls gate;
  gate.set_settle_ms(3000);
  Log log;
  gate.tick(0, true);
  gate.call("a", log.send("a"));
  gate.call("b", log.send("b"));
  gate.tick(3000, true);
  CHECK(log.sent.size() == 1);
  gate.tick(3500, false);
  CHECK(!gate.busy() && gate.queued() == 1);
  gate.tick(4000, true);
  gate.tick(6000, true);
  CHECK(log.sent.size() == 1);  // Settling again.
  gate.tick(7000, true);
  CHECK(log.sent.size() == 2 && log.sent[1] == "b");
}

static void test_queue_limit() {
  HaCalls gate;
  Log log;
  for (int i = 0; i < 20; i++)
    gate.call("c" + std::to_string(i), log.send("c" + std::to_string(i)));
  CHECK(gate.queued() == 16 && gate.dropped() == 4);
  gate.set_settle_ms(0);
  gate.tick(1, true);
  CHECK(log.sent.size() == 1 && log.sent[0] == "c4");  // The oldest went.
}

// A test runner moves the clock on only when the gate is idle: nothing in
// flight, and nothing ready to go at this time.
static void test_idle() {
  HaCalls gate;
  gate.set_settle_ms(3000);
  Log log;
  CHECK(gate.idle(0));
  gate.call("calendar", log.send("calendar"));
  CHECK(gate.idle(0));  // HA isn't linked: the call waits for time.
  gate.tick(1000, true);
  CHECK(gate.idle(1000));   // Linked, but HA is still settling.
  CHECK(!gate.idle(4000));  // Settled: the call is due.
  CHECK(gate.next() == "calendar");
  gate.tick(4000, true);
  CHECK(!gate.idle(4000));  // Sent: waiting for the answer.
  CHECK(gate.in_flight() == "calendar");
  gate.done(log.tokens[0]);
  CHECK(gate.idle(4000));
}

int main() {
  test_waits_for_ha_then_one_at_a_time();
  test_update_waits_for_the_fetch();
  test_timeout_and_late_answer();
  test_disconnect();
  test_queue_limit();
  test_idle();
  if (failures == 0)
    std::printf("ha calls: all passed\n");
  return failures == 0 ? 0 : 1;
}
