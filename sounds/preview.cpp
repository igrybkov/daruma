// Writes every Daruma sound effect as a WAV file, to listen to on a
// computer. The device makes the same sounds with the same code
// (components/daruma/synth.cpp). Built-in sounds only;
// a persona's own `sounds:` are not included.
//
// From the repository root:
//
//   c++ -std=c++17 -O2 -Icomponents/daruma \
//       sounds/preview.cpp components/daruma/synth.cpp -o /tmp/daruma_sounds \
//       && /tmp/daruma_sounds OUT_DIR

#include <cstdio>
#include <string>

#include "synth.h"

using namespace Daruma::Synth;

static void put32(FILE *f, uint32_t v) { fwrite(&v, 4, 1, f); }
static void put16(FILE *f, uint16_t v) { fwrite(&v, 2, 1, f); }

int main(int argc, char **argv) {
  if (argc < 2) {
    fprintf(stderr, "usage: %s OUT_DIR\n", argv[0]);
    return 1;
  }
  for (const std::string &name : sound_names()) {
    const auto pcm = render(sound(name));
    const std::string path = std::string(argv[1]) + "/" + name + ".wav";
    FILE *f = fopen(path.c_str(), "wb");
    if (f == nullptr) {
      perror(path.c_str());
      return 1;
    }
    const uint32_t bytes = pcm.size() * 2;
    fwrite("RIFF", 1, 4, f);
    put32(f, 36 + bytes);
    fwrite("WAVEfmt ", 1, 8, f);
    put32(f, 16);
    put16(f, 1);  // PCM
    put16(f, 1);  // Mono
    put32(f, RATE);
    put32(f, RATE * 2);
    put16(f, 2);
    put16(f, 16);
    fwrite("data", 1, 4, f);
    put32(f, bytes);
    fwrite(pcm.data(), 2, pcm.size(), f);
    fclose(f);
    printf("%s: %.2f s\n", path.c_str(), pcm.size() / (float) RATE);
  }
  return 0;
}
