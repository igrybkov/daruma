#pragma once

// Chiptune synthesizer for Daruma's sound effects: square and pulse
// waves with pitch slides, like an old handheld game. Plain C++ with no
// ESPHome parts, so sounds/preview.cpp can build it on a computer
// and write the sounds as WAV files to listen to.
//
// sound() holds the built-in sounds. A persona may replace any of them with
// its own (the `sounds:` option, see sounds.py); daruma_sounds plays them.

#include <cstdint>
#include <string>
#include <vector>

namespace Daruma {
namespace Synth {

static const int RATE = 48000;  // The speaker's rate: no resampling.

// One step of a sound: a tone, or silence when f0 is 0.
struct Step {
  float f0{0};          // Start pitch in Hz.
  float f1{0};          // End pitch (exponential glide); 0 = no glide.
  float seconds{0};
  float duty{0.5f};     // Share of each cycle that is high: 0.5 square, less is thinner.
  float attack{0.004f};
  float release{0.03f};
  float vibrato{0};     // Wobble speed in Hz, 3% deep; 0 = none.
};

// "A4" -> 440 Hz. Sharps as "C#5".
float note(const char *name);

Step tone(const char *from, float seconds, const char *to = nullptr, float duty = 0.5f, float release = 0.03f,
          float vibrato = 0);
Step rest(float seconds);
// Quick run of notes; the last one rings longer (`last`, or twice the step).
std::vector<Step> arp(std::initializer_list<const char *> names, float step, float duty = 0.5f, float last = 0);

// Built-in sound effects: start, pause, stop, focus_done, goal, break_over,
// pet, timer, notify, urgent. Empty for an unknown name.
std::vector<Step> sound(const std::string &name);
const std::vector<std::string> &sound_names();

// Renders steps to 16-bit mono PCM at RATE: softened square edges, a quiet
// level that leaves headroom, and a short silent tail for the DAC. Writes
// length(steps) samples to `out` with no other memory.
size_t length(const std::vector<Step> &steps);
void render(const std::vector<Step> &steps, int16_t *out);
std::vector<int16_t> render(const std::vector<Step> &steps);

}  // namespace Synth
}  // namespace Daruma
