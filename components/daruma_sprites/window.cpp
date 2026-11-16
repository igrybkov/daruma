#include "window.h"

namespace Daruma {

namespace {

constexpr uint16_t rgb(uint8_t r, uint8_t g, uint8_t b) {
  return (uint16_t) (((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3));
}

// Three sky bands, top to bottom.
struct Palette {
  uint16_t band[3];
};

constexpr Palette CLEAR_SKY{{rgb(122, 190, 236), rgb(150, 206, 240), rgb(184, 224, 246)}};
constexpr Palette CLOUDY_SKY{{rgb(128, 148, 170), rgb(142, 162, 182), rgb(158, 176, 194)}};
constexpr Palette RAIN_SKY{{rgb(88, 100, 116), rgb(100, 112, 128), rgb(114, 126, 142)}};
constexpr Palette SNOW_SKY{{rgb(168, 176, 190), rgb(182, 190, 202), rgb(198, 204, 214)}};
constexpr Palette NIGHT_SKY{{rgb(14, 20, 50), rgb(22, 30, 66), rgb(34, 42, 84)}};

constexpr uint16_t WHITE = rgb(255, 255, 255);
constexpr uint16_t CLOUD_GREY = rgb(226, 230, 236);
constexpr uint16_t CLOUD_SHADE = rgb(190, 198, 210);
constexpr uint16_t RAIN_CLOUD = rgb(70, 78, 92);
constexpr uint16_t RAIN_DROP = rgb(172, 194, 222);
constexpr uint16_t STAR = rgb(250, 244, 210);
constexpr uint16_t STAR_DIM = rgb(130, 136, 170);
constexpr uint16_t MOON = rgb(244, 236, 186);

// Small stable hash, for per-column randomness that stays put between frames.
uint32_t hash(uint32_t v) {
  v ^= v >> 16;
  v *= 0x7feb352d;
  v ^= v >> 15;
  v *= 0x846ca68b;
  v ^= v >> 16;
  return v;
}

class Painter {
 public:
  Painter(uint16_t *frame, int stride, const Pane &pane) : frame_(frame), stride_(stride), pane_(pane) {}

  // Pane-local coordinates; anything outside the pane is dropped.
  void dot(int x, int y, uint16_t c) {
    if (x < 0 || y < 0 || x >= this->pane_.w || y >= this->pane_.h)
      return;
    this->frame_[(this->pane_.y + y) * this->stride_ + this->pane_.x + x] = c;
  }
  void row(int x0, int x1, int y, uint16_t c) {
    for (int x = x0; x <= x1; x++)
      this->dot(x, y, c);
  }

  // Bands split like the room art: rows [0, h/3), [h/3, 2h/3), rest, with h
  // one short of the pane so the bands line up with the original window.
  void sky(const Palette &p) {
    const int span = this->pane_.h - 1;
    const int b1 = span / 3;
    const int b2 = 2 * span / 3;
    for (int y = 0; y < this->pane_.h; y++)
      this->row(0, this->pane_.w - 1, y, p.band[y >= b2 ? 2 : (y >= b1 ? 1 : 0)]);
  }

  // The little cloud from the room art: 7x3 body with a 4-wide top.
  void cloud(int x, int y, uint16_t body, uint16_t shade) {
    this->row(x + 2, x + 5, y, body);
    this->row(x, x + 6, y + 1, body);
    this->row(x, x + 6, y + 2, body);
    this->row(x, x + 6, y + 3, shade == body ? body : shade);
  }

  int w() const { return this->pane_.w; }
  int h() const { return this->pane_.h; }

 private:
  uint16_t *frame_;
  int stride_;
  Pane pane_;
};

// A pane taller than this (a tall window) gets more sky: another cloud,
// more cloud lanes, more stars. Shorter panes look as they always did.
constexpr int TALL_PANE = 30;

// Clouds drift right one pixel per step and wrap around.
int drift(uint32_t step, int offset, int width) {
  const int lane = width + 10;
  return (int) ((step + offset) % lane) - 8;
}

}  // namespace

uint32_t window_step(Sky sky, uint32_t now) {
  switch (sky) {
    case Sky::CLOUDY:
      return now / 2500;
    case Sky::RAIN:
      return now / 90;
    case Sky::SNOW:
      return now / 260;
    case Sky::NIGHT:
      return now / 1700;
    default:
      return 0;  // Still.
  }
}

void paint_window(uint16_t *frame, int stride, const Pane &pane, Sky sky, uint32_t step) {
  Painter p(frame, stride, pane);
  switch (sky) {
    case Sky::CLEAR:
      p.sky(CLEAR_SKY);
      // Same cloud as the room art, 4 px in from the top-left of the glass.
      p.row(6, 9, 4, WHITE);
      p.row(4, 10, 5, WHITE);
      p.row(4, 10, 6, WHITE);
      p.row(4, 10, 7, WHITE);
      if (p.h() > TALL_PANE) {  // A second one lower down, a little to the right.
        p.row(7, 10, 22, WHITE);
        p.row(5, 11, 23, WHITE);
        p.row(5, 11, 24, WHITE);
        p.row(5, 11, 25, WHITE);
      }
      break;

    case Sky::CLOUDY:
      p.sky(CLOUDY_SKY);
      // Two lanes, one above and one below the middle of the glass, where a
      // window's cross bar usually runs.
      p.cloud(drift(step, 0, p.w()), 2, CLOUD_GREY, CLOUD_SHADE);
      p.cloud(drift(step, 17, p.w()), 13, CLOUD_GREY, CLOUD_SHADE);
      if (p.h() > TALL_PANE) {  // Two more lanes on the way down.
        p.cloud(drift(step, 9, p.w()), 24, CLOUD_GREY, CLOUD_SHADE);
        p.cloud(drift(step, 26, p.w()), 35, CLOUD_GREY, CLOUD_SHADE);
      }
      break;

    case Sky::RAIN: {
      p.sky(RAIN_SKY);
      for (int x = 0; x < p.w(); x++) {  // Low, heavy cloud along the top.
        p.dot(x, 0, RAIN_CLOUD);
        if (hash(x) % 3)
          p.dot(x, 1, RAIN_CLOUD);
      }
      // Every other column carries a drop falling 2 px per step.
      const int lane = p.h() + 4;
      for (int x = (int) (hash(7) % 2); x < p.w(); x += 2) {
        const int y = (int) ((step * 2 + hash(x) % lane) % lane) - 2;
        p.dot(x, y, RAIN_DROP);
        p.dot(x, y + 1, RAIN_DROP);
      }
      break;
    }

    case Sky::SNOW: {
      p.sky(SNOW_SKY);
      // A flake in every third column, falling 1 px per step and swaying.
      const int lane = p.h() + 2;
      for (int x = 1; x < p.w(); x += 3) {
        const uint32_t seed = hash(x);
        const int y = (int) ((step + seed % lane) % lane) - 1;
        const int sway = ((step + seed) / 4) % 2;
        p.dot(x + sway, y, WHITE);
      }
      for (int x = 0; x < p.w(); x++)  // Snow piling up on the sill.
        p.dot(x, p.h() - 1, WHITE);
      break;
    }

    case Sky::NIGHT: {
      p.sky(NIGHT_SKY);
      // Crescent moon, top right, opening to the right.
      static const char *const MOON_ART[] = {".XX.", "XX..", "X...", "XX..", ".XX."};
      const int mx = p.w() - 7, my = 2;
      for (int dy = 0; dy < 5; dy++) {
        for (int dx = 0; dx < 4; dx++) {
          if (MOON_ART[dy][dx] == 'X')
            p.dot(mx + dx, my + dy, MOON);
        }
      }
      // A few stars; one of them twinkles.
      static const int STARS[][2] = {{2, 2}, {7, 5}, {4, 11}, {11, 2}, {14, 9}, {9, 15}, {19, 13}, {2, 17}};
      const uint32_t twinkle = step % 8;
      for (uint32_t i = 0; i < sizeof(STARS) / sizeof(STARS[0]); i++)
        p.dot(STARS[i][0], STARS[i][1], i == twinkle ? STAR_DIM : STAR);
      if (p.h() > TALL_PANE) {  // Stars down the rest of a tall window.
        static const int LOW_STARS[][2] = {{3, 21}, {9, 24}, {6, 29}, {1, 33}, {10, 36}, {4, 40}};
        const uint32_t low_twinkle = (step + 3) % 7;
        for (uint32_t i = 0; i < sizeof(LOW_STARS) / sizeof(LOW_STARS[0]); i++)
          p.dot(LOW_STARS[i][0], LOW_STARS[i][1], i == low_twinkle ? STAR_DIM : STAR);
      }
      break;
    }
  }
}

}  // namespace Daruma
