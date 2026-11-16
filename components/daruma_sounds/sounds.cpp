#include "sounds.h"

#include <algorithm>
#include <cstring>
#include <memory>
#include <vector>

#include "esphome/core/hal.h"
#include "esphome/core/helpers.h"
#include "esphome/core/log.h"

#ifdef USE_ESP32
#include <esp_heap_caps.h>
#endif

namespace Daruma {

static const char *const TAG = "daruma_sounds";
static const size_t WAV_HEADER = 44;
static const size_t KEEP_RECENT = 2;  // Never freed: one may still be playing.

size_t Sounds::cache_size_ = 384 * 1024;

namespace {

struct Entry {
  std::string key;  // Persona name + sound name.
  uint8_t *data;
  size_t size;
  uint32_t used;  // Fetch counter value at the last fetch.
  std::unique_ptr<esphome::audio::AudioFile> file;
};

std::vector<Entry> cache;
uint32_t fetches = 0;
size_t cached_bytes = 0;

// Free PSRAM and its largest free block, for the logs.
void psram_free(size_t *free, size_t *largest) {
#ifdef USE_ESP32
  *free = heap_caps_get_free_size(MALLOC_CAP_SPIRAM);
  *largest = heap_caps_get_largest_free_block(MALLOC_CAP_SPIRAM);
#else
  *free = *largest = 0;
#endif
}

void put_le(uint8_t *at, uint32_t value, int bytes) {
  for (int i = 0; i < bytes; i++)
    at[i] = (value >> (8 * i)) & 0xFF;
}

void free_entry(size_t index) {
  const Entry &e = cache[index];
  ESP_LOGD(TAG, "Freed %s: %u bytes, last played %u sounds ago", e.key.c_str(), (unsigned) e.size,
           (unsigned) (fetches - e.used));
  esphome::RAMAllocator<uint8_t> allocator;
  allocator.deallocate(e.data, e.size);
  cached_bytes -= e.size;
  cache.erase(cache.begin() + index);
}

// Frees the least recently fetched sounds, never the most recent ones,
// until `needed` more bytes fit.
void make_room(size_t needed, size_t limit) {
  while (cached_bytes + needed > limit && cache.size() > KEEP_RECENT) {
    std::vector<uint32_t> order;
    for (const Entry &e : cache)
      order.push_back(e.used);
    std::sort(order.begin(), order.end());
    const uint32_t newest_kept = order[order.size() - KEEP_RECENT];
    size_t oldest = cache.size();
    for (size_t i = 0; i < cache.size(); i++) {
      if (cache[i].used < newest_kept && (oldest == cache.size() || cache[i].used < cache[oldest].used))
        oldest = i;
    }
    if (oldest == cache.size())
      break;
    free_entry(oldest);
  }
  if (cached_bytes + needed > limit) {
    ESP_LOGW(TAG, "Cache over its %u-byte limit: %u cached + %u new (the %u most recent sounds are never freed)",
             (unsigned) limit, (unsigned) cached_bytes, (unsigned) needed, (unsigned) KEEP_RECENT);
  }
}

}  // namespace

const esphome::audio::AudioFile *Sounds::get(Hub *hub, const std::string &name) {
  Persona *persona = hub->persona();
  const std::string key = (persona != nullptr ? persona->get_name() : std::string()) + "/" + name;
  fetches++;
  for (Entry &e : cache) {
    if (e.key == key) {
      e.used = fetches;
      ESP_LOGV(TAG, "%s from the cache", key.c_str());
      return e.file.get();
    }
  }

  const std::vector<Synth::Step> steps = persona != nullptr ? persona->sound(name) : Synth::sound(name);
  if (steps.empty()) {
    ESP_LOGW(TAG, "No sound named %s", key.c_str());
    return nullptr;
  }
  const size_t samples = Synth::length(steps);
  const size_t size = WAV_HEADER + samples * 2;
  make_room(size, cache_size_);

  esphome::RAMAllocator<uint8_t> allocator;
  uint8_t *data = allocator.allocate(size);
  if (data == nullptr) {
    size_t free, largest;
    psram_free(&free, &largest);
    ESP_LOGE(TAG, "No memory for %s: needs %u bytes; PSRAM free %u, largest block %u; cache %u bytes in %u sounds",
             key.c_str(), (unsigned) size, (unsigned) free, (unsigned) largest, (unsigned) cached_bytes,
             (unsigned) cache.size());
    return nullptr;
  }

  // A plain PCM WAV header: mono, 16-bit, Synth::RATE.
  std::memcpy(data, "RIFF", 4);
  put_le(data + 4, size - 8, 4);
  std::memcpy(data + 8, "WAVEfmt ", 8);
  put_le(data + 16, 16, 4);
  put_le(data + 20, 1, 2);  // PCM
  put_le(data + 22, 1, 2);  // Mono
  put_le(data + 24, Synth::RATE, 4);
  put_le(data + 28, Synth::RATE * 2, 4);
  put_le(data + 32, 2, 2);
  put_le(data + 34, 16, 2);
  std::memcpy(data + 36, "data", 4);
  put_le(data + 40, samples * 2, 4);
  // The sample area is 2-byte aligned (header is 44 bytes); the chip is little-endian like WAV.
  const uint32_t started = esphome::millis();
  Synth::render(steps, reinterpret_cast<int16_t *>(data + WAV_HEADER));
  const uint32_t took = esphome::millis() - started;

  auto file = std::make_unique<esphome::audio::AudioFile>();
  file->data = data;
  file->length = size;
  file->file_type = esphome::audio::AudioFileType::WAV;
  cache.push_back(Entry{key, data, size, fetches, std::move(file)});
  cached_bytes += size;
  size_t free, largest;
  psram_free(&free, &largest);
  ESP_LOGD(TAG, "Made %s: %u bytes in %u ms; cache %u of %u bytes in %u sounds; PSRAM free %u", key.c_str(),
           (unsigned) size, (unsigned) took, (unsigned) cached_bytes, (unsigned) cache_size_, (unsigned) cache.size(),
           (unsigned) free);
  return cache.back().file.get();
}

}  // namespace Daruma
