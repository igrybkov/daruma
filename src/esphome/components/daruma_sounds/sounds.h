#pragma once

#include <string>

#include "esphome/components/audio/audio.h"
#include "esphome/components/daruma/hub.h"

namespace Daruma {

// The device's sound effects as playable WAV files, made on first use and
// kept in PSRAM within a size limit (see __init__.py).
class Sounds {
 public:
  static void set_cache_size(size_t bytes) { cache_size_ = bytes; }
  // The current persona's `name`, ready for play_file(). Null for an unknown
  // name or when there is no memory for it. Valid until two more sounds
  // have been fetched after it.
  static const esphome::audio::AudioFile *get(Hub *hub, const std::string &name);

 protected:
  static size_t cache_size_;
};

}  // namespace Daruma
