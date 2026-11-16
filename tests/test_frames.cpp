// Host test of the frame decoder the device runs (frame_chain.h, sprite.h)
// against frame sets the build encoder made (sprite_codec.py), written by
// frames_fixture.py.
//
//   uv run --with pillow python tests/frames_fixture.py /tmp/frames.txt [--personas]
//   c++ -std=c++17 -Wall -Wextra -I components/daruma \
//       tests/test_frames.cpp -o /tmp/test_frames && /tmp/test_frames /tmp/frames.txt
//
// For every set it checks that:
// - each frame, drawn on its own (from its keyframe), gives exactly the
//   pixels of its source picture;
// - each play order, drawn frame after frame on one canvas, gives the same,
//   and nothing changes outside the box show() reports;
// - no chain is deeper than the encoder's limit.
//
// test_frames.py runs all of this.

#include <cstdio>
#include <cstring>
#include <memory>
#include <string>
#include <vector>

#include "frame_chain.h"
#include "sprite.h"

using namespace Daruma;

static const int MAX_CHAIN = 5;  // sprite_codec.MAX_DEPTH patches on a keyframe.

struct Stored {
  std::vector<uint16_t> palette;
  std::vector<uint8_t> data;
  std::unique_ptr<Sprite> sprite;
};

struct Set {
  std::string label;
  int w{0}, h{0};
  std::vector<std::unique_ptr<Stored>> stored;
  std::vector<FrameRef> frames;
  std::vector<std::vector<int>> expected;  // Per frame; -1 for see-through.
  std::vector<std::vector<int>> sequences;
};

static int failures = 0;

static bool same(const FrameCanvas &canvas, const std::vector<int> &want, const std::string &what) {
  for (int y = 0; y < canvas.height(); y++) {
    for (int x = 0; x < canvas.width(); x++) {
      const int got = canvas.is_clear(x, y) ? -1 : canvas.at(x, y);
      const int exp = want[(size_t) y * canvas.width() + x];
      if (got != exp) {
        printf("FAIL %s: pixel (%d, %d) is %d, want %d\n", what.c_str(), x, y, got, exp);
        failures++;
        return false;
      }
    }
  }
  return true;
}

static std::vector<int> snapshot(const FrameCanvas &canvas) {
  std::vector<int> out;
  for (int y = 0; y < canvas.height(); y++)
    for (int x = 0; x < canvas.width(); x++)
      out.push_back(canvas.is_clear(x, y) ? -1 : canvas.at(x, y));
  return out;
}

static void check(const Set &set, int *frames_checked, int *steps_checked) {
  // Chain depth.
  for (size_t i = 0; i < set.frames.size(); i++) {
    int depth = 1;
    for (int at = (int) i; set.frames[at].base >= 0; at = set.frames[at].base)
      depth++;
    if (depth > MAX_CHAIN) {
      printf("FAIL %s: frame %zu draws %d pictures\n", set.label.c_str(), i, depth);
      failures++;
    }
  }
  // Each frame on its own.
  for (size_t i = 0; i < set.frames.size(); i++) {
    if (set.expected[i].empty())
      continue;
    FrameCanvas canvas;
    canvas.show(set.frames, (int) i);
    if (canvas.width() != set.w || canvas.height() != set.h) {
      printf("FAIL %s: frame %zu is %dx%d\n", set.label.c_str(), i, canvas.width(), canvas.height());
      failures++;
      continue;
    }
    same(canvas, set.expected[i], set.label + " frame " + std::to_string(i));
    (*frames_checked)++;
  }
  // Play orders on one canvas, as the device plays them: twice round, so
  // the loop back to the first frame is covered.
  FrameCanvas canvas;
  for (size_t s = 0; s < set.sequences.size(); s++) {
    const auto &seq = set.sequences[s];
    for (int round = 0; round < 2; round++) {
      for (int frame : seq) {
        const std::vector<int> before = snapshot(canvas);
        const bool had = canvas.width() == set.w && canvas.height() == set.h;
        const Rect box = canvas.show(set.frames, frame);
        const std::string what = set.label + " seq " + std::to_string(s) + " frame " + std::to_string(frame);
        if (!same(canvas, set.expected[frame], what))
          return;
        if (had) {
          for (int y = 0; y < set.h; y++) {
            for (int x = 0; x < set.w; x++) {
              const size_t i = (size_t) y * set.w + x;
              if (before[i] != set.expected[frame][i] && !box.contains(x, y)) {
                printf("FAIL %s: (%d, %d) changed outside the box\n", what.c_str(), x, y);
                failures++;
                return;
              }
            }
          }
        }
        (*steps_checked)++;
      }
    }
  }
}

static bool read_set(FILE *f, Set *set) {
  char kind[16];
  long pos = ftell(f);
  while (fscanf(f, "%15s", kind) == 1) {
    if (strcmp(kind, "set") == 0) {
      if (!set->label.empty()) {
        fseek(f, pos, SEEK_SET);
        return true;
      }
      char label[128];
      int n;
      if (fscanf(f, "%127s %d %d %d", label, &set->w, &set->h, &n) != 4)
        return false;
      set->label = label;
      set->expected.assign(n, {});
    } else if (strcmp(kind, "frame") == 0) {
      int base, x, y, w, h, bits, clear, colors, ndata;
      if (fscanf(f, "%d %d %d %d %d %d %d %d %d", &base, &x, &y, &w, &h, &bits, &clear, &colors, &ndata) != 9)
        return false;
      auto st = std::make_unique<Stored>();
      st->palette.resize(colors);
      st->data.resize(ndata);
      for (int i = 0; i < colors; i++) {
        int v;
        if (fscanf(f, "%d", &v) != 1)
          return false;
        st->palette[i] = (uint16_t) v;
      }
      for (int i = 0; i < ndata; i++) {
        int v;
        if (fscanf(f, "%d", &v) != 1)
          return false;
        st->data[i] = (uint8_t) v;
      }
      st->sprite = std::make_unique<Sprite>(w, h, bits, clear, colors, st->palette.data(), st->data.data(),
                                            base >= 0);
      set->frames.push_back(FrameRef{st->sprite.get(), (int16_t) base, (int16_t) x, (int16_t) y});
      set->stored.push_back(std::move(st));
    } else if (strcmp(kind, "expect") == 0) {
      int frame;
      if (fscanf(f, "%d", &frame) != 1)
        return false;
      auto &px = set->expected[frame];
      px.resize((size_t) set->w * set->h);
      for (auto &v : px) {
        if (fscanf(f, "%d", &v) != 1)
          return false;
      }
    } else if (strcmp(kind, "seq") == 0) {
      int n;
      if (fscanf(f, "%d", &n) != 1)
        return false;
      std::vector<int> seq(n);
      for (auto &v : seq) {
        if (fscanf(f, "%d", &v) != 1)
          return false;
      }
      set->sequences.push_back(seq);
    } else {
      return false;
    }
    pos = ftell(f);
  }
  return !set->label.empty();
}

int main(int argc, char **argv) {
  if (argc < 2) {
    fprintf(stderr, "usage: %s FIXTURE\n", argv[0]);
    return 2;
  }
  FILE *f = fopen(argv[1], "r");
  if (f == nullptr) {
    perror(argv[1]);
    return 2;
  }
  int sets = 0, frames = 0, steps = 0;
  while (true) {
    Set set;
    if (!read_set(f, &set))
      break;
    check(set, &frames, &steps);
    sets++;
  }
  fclose(f);
  if (sets == 0) {
    printf("FAIL: no sets in %s\n", argv[1]);
    return 1;
  }
  printf("%d sets, %d frames decoded on their own, %d played in order: %s\n", sets, frames, steps,
         failures ? "FAILED" : "all match");
  return failures ? 1 : 0;
}
