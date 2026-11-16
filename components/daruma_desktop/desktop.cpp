#ifdef USE_HOST

#include "desktop.h"

#include <dlfcn.h>

#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <vector>

#include "esphome/components/daruma/synth.h"
#ifdef USE_API
#include "esphome/components/api/api_server.h"
#endif
#include "esphome/core/hal.h"
#include "esphome/core/log.h"

namespace Daruma {

static const char *const TAG = "daruma_desktop";

// Touch timing. A tap lifts well before the hub's hold time; a move step is
// about one touchscreen poll, so a swipe reads as a smooth drag.
static const uint32_t TAP_MS = 80;
static const uint32_t STEP_MS = 16;
// A gap between queued touches, so two taps never merge into one touch.
static const uint32_t GAP_MS = 120;
// Petting: legs this long, this many times, this fast.
static const int STROKE_LEG = 60;
static const int STROKE_LEGS = 5;
static const uint32_t STROKE_LEG_MS = 200;

void Desktop::setup() {
  UiTree::enable(true);
#ifdef USE_API
  // A runner may start several programs from one build at once: each one
  // listens on the port in DARUMA_API_PORT. This runs before the API
  // server's setup, which opens the port.
  const char *port = getenv("DARUMA_API_PORT");
  if (port != nullptr && port[0] != '\0' && esphome::api::global_api_server != nullptr)
    esphome::api::global_api_server->set_port(static_cast<uint16_t>(atoi(port)));
#endif
  // Buttons start released. A sensor's first state is not reported as a
  // change, so without this the first scripted press would be lost.
  for (auto &b : this->buttons_)
    b.second->publish_initial_state(false);
  // A runner's clock (demos/fakeclock.c), when it is loaded.
  this->clock_latch_ = reinterpret_cast<void (*)()>(dlsym(RTLD_DEFAULT, "daruma_clock_latch"));
  if (this->clock_latch_ != nullptr) {
    ESP_LOGI(TAG, "The clock is driven by a runner");
    // Every component loops on every turn of the main loop. The runner's
    // clock stands still between steps, and the loop's own pacing would
    // then hold the components back until time moves. (The library caps
    // each wait at 2 ms, so this does not spin hard.)
    this->high_freq_.start();
  }
}

void Desktop::dump_config() {
  ESP_LOGCONFIG(TAG, "Daruma desktop: scripted input and recorder");
  for (const auto &b : this->buttons_)
    ESP_LOGCONFIG(TAG, "  Button: %s", b.first.c_str());
}

uint32_t Desktop::queue_start_() {
  const uint32_t now = esphome::millis();
  if (this->points_.empty())
    return now;
  return std::max(now, this->points_.back().at + GAP_MS);
}

void Desktop::tap(int x, int y) { this->hold(x, y, TAP_MS); }

void Desktop::hold(int x, int y, uint32_t ms) {
  const uint32_t t = this->queue_start_();
  this->add_point_(t, x, y, true);
  this->add_point_(t + ms, x, y, false);
}

void Desktop::swipe(int x1, int y1, int x2, int y2, uint32_t ms) {
  const uint32_t t = this->queue_start_();
  const int steps = std::max<int>(1, ms / STEP_MS);
  for (int i = 0; i <= steps; i++) {
    this->add_point_(t + i * ms / steps, x1 + (x2 - x1) * i / steps, y1 + (y2 - y1) * i / steps, true);
  }
  this->add_point_(t + ms + STEP_MS, x2, y2, false);
}

void Desktop::stroke(int x, int y) {
  const uint32_t t = this->queue_start_();
  const int steps = std::max<int>(1, STROKE_LEG_MS / STEP_MS);
  int from = x - STROKE_LEG / 2;
  uint32_t at = t;
  for (int leg = 0; leg < STROKE_LEGS; leg++) {
    const int to = leg % 2 == 0 ? x + STROKE_LEG / 2 : x - STROKE_LEG / 2;
    for (int i = 0; i <= steps; i++) {
      this->add_point_(at + i * STROKE_LEG_MS / steps, from + (to - from) * i / steps, y, true);
    }
    at += STROKE_LEG_MS;
    from = to;
  }
  this->add_point_(at + STEP_MS, from, y, false);
}

bool Desktop::press(const std::string &name, uint32_t ms) {
  auto it = this->buttons_.find(name);
  if (it == this->buttons_.end()) {
    ESP_LOGW(TAG, "No button named %s", name.c_str());
    return false;
  }
  it->second->publish_state(true);
  this->releases_.push_back(Release{esphome::millis() + std::max<uint32_t>(ms, 30), it->second});
  return true;
}

void Desktop::loop() {
  // A new time from the runner takes effect here, at the start of a turn of
  // the main loop, before any other component's loop. So it never changes
  // halfway through one, and the same steps give the same frames.
  if (this->clock_latch_ != nullptr)
    this->clock_latch_();
  const uint32_t now = esphome::millis();
  while (!this->points_.empty() && static_cast<int32_t>(now - this->points_.front().at) >= 0) {
    const Point &p = this->points_.front();
    if (this->display_ != nullptr) {
      this->display_->mouse_x = p.x;
      this->display_->mouse_y = p.y;
      this->display_->mouse_down = p.down;
    }
    this->points_.pop_front();
  }
  while (!this->releases_.empty() && static_cast<int32_t>(now - this->releases_.front().at) >= 0) {
    this->releases_.front().sensor->publish_state(false);
    this->releases_.pop_front();
  }
}

bool Desktop::record_start(const std::string &dir) {
  std::error_code ec;
  std::filesystem::create_directories(dir, ec);
  if (ec) {
    ESP_LOGE(TAG, "Can't make %s: %s", dir.c_str(), ec.message().c_str());
    return false;
  }
  // The snapshot component writes under this directory; it reads the
  // variable on every snapshot.
  setenv("ESPHOME_SNAPSHOT_DIR", dir.c_str(), 1);  // NOLINT(concurrency-mt-unsafe)
  this->dir_ = dir;
  this->start_ms_ = esphome::millis();
  this->frames_ = 0;
  this->sounds_ = 0;
  this->paused_ = false;
  this->recording_ = true;
  ESP_LOGI(TAG, "Recording to %s", dir.c_str());
  // The screen as it is now is the first frame: nothing may redraw for a while.
  this->frame();
  return true;
}

void Desktop::record_stop() {
  if (!this->recording_)
    return;
  // The last picture again, so the recording knows how long it stayed.
  this->paused_ = false;
  this->frame();
  this->recording_ = false;
  ESP_LOGI(TAG, "Recorded %u frames and %u sounds in %u ms", (unsigned) this->frames_, (unsigned) this->sounds_,
           (unsigned) (esphome::millis() - this->start_ms_));
}

void Desktop::frame() {
  if (!this->recording_ || this->paused_ || this->display_ == nullptr)
    return;
  char name[48];
  snprintf(name, sizeof(name), "f_%08u_%06u.bmp", (unsigned) (esphome::millis() - this->start_ms_),
           (unsigned) this->frames_);
  if (this->display_->take_snapshot(name)) {
    this->frames_++;
  } else {
    ESP_LOGW(TAG, "Frame %s not saved", name);
  }
}

bool Desktop::screenshot(const std::string &dir, const std::string &name) {
  if (this->display_ == nullptr)
    return false;
  std::error_code ec;
  std::filesystem::create_directories(dir, ec);
  // The snapshot component writes under this directory and never over a file.
  setenv("ESPHOME_SNAPSHOT_DIR", dir.c_str(), 1);  // NOLINT(concurrency-mt-unsafe)
  std::filesystem::remove(dir + "/" + name + ".bmp", ec);
  const bool ok = this->display_->take_snapshot((name + ".bmp").c_str());
  if (this->recording_)
    setenv("ESPHOME_SNAPSHOT_DIR", this->dir_.c_str(), 1);  // NOLINT(concurrency-mt-unsafe)
  return ok;
}

void Desktop::describe(JsonObject root) const {
  auto list = root["ui"].to<JsonArray>();
  for (const UiNode &n : UiTree::nodes()) {
    auto o = list.add<JsonObject>();
    o["role"] = n.role;
    o["name"] = n.name;
    o["x"] = n.rect.x;
    o["y"] = n.rect.y;
    o["w"] = n.rect.w;
    o["h"] = n.rect.h;
    o["focused"] = n.focused;
    o["value"] = n.value;
  }
}

static void put_le(uint8_t *p, uint32_t v, int bytes) {
  for (int i = 0; i < bytes; i++)
    p[i] = static_cast<uint8_t>(v >> (8 * i));
}

void Desktop::sound(Hub *hub, const std::string &name) {
  const uint32_t at = esphome::millis() - this->start_ms_;
  ESP_LOGI(TAG, "Sound %s", name.c_str());
  if (!this->recording_ || this->paused_)
    return;
  Persona *persona = hub != nullptr ? hub->persona() : nullptr;
  const std::vector<Synth::Step> steps = persona != nullptr ? persona->sound(name) : Synth::sound(name);
  if (steps.empty()) {
    ESP_LOGW(TAG, "No sound named %s", name.c_str());
    return;
  }
  const std::vector<int16_t> pcm = Synth::render(steps);
  const uint32_t data_bytes = pcm.size() * 2;
  uint8_t header[44];
  memcpy(header, "RIFF", 4);
  put_le(header + 4, 36 + data_bytes, 4);
  memcpy(header + 8, "WAVEfmt ", 8);
  put_le(header + 16, 16, 4);
  put_le(header + 20, 1, 2);  // PCM
  put_le(header + 22, 1, 2);  // mono
  put_le(header + 24, Synth::RATE, 4);
  put_le(header + 28, Synth::RATE * 2, 4);
  put_le(header + 32, 2, 2);
  put_le(header + 34, 16, 2);
  memcpy(header + 36, "data", 4);
  put_le(header + 40, data_bytes, 4);

  char file[64];
  snprintf(file, sizeof(file), "/s_%08u_%s.wav", (unsigned) at, name.c_str());
  const std::string path = this->dir_ + file;
  FILE *f = fopen(path.c_str(), "wb");
  if (f == nullptr) {
    ESP_LOGW(TAG, "Can't write %s", path.c_str());
    return;
  }
  // The host is little-endian, like WAV.
  const bool ok = fwrite(header, 1, sizeof(header), f) == sizeof(header) &&
                  fwrite(pcm.data(), 2, pcm.size(), f) == pcm.size();
  fclose(f);
  if (ok)
    this->sounds_++;
}

}  // namespace Daruma

#endif
