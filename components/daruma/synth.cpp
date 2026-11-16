#include "synth.h"

#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <cstring>

namespace Daruma {
namespace Synth {

static const float LEVEL = 0.32f;           // Square waves are loud.
static const float SOFTEN_HZ = 6000.0f;     // Low-pass that takes the fizz off.
static const float TAIL_SECONDS = 0.03f;

float note(const char *name) {
  static const int STEPS[7] = {0, 2, -9, -7, -5, -4, -2};  // A B C D E F G from A.
  int semis = STEPS[name[0] - 'A'];
  const char *rest = name + 1;
  if (*rest == '#') {
    semis++;
    rest++;
  }
  const int octave = std::atoi(rest);
  return 440.0f * std::pow(2.0f, (semis + 12 * (octave - 4)) / 12.0f);
}

Step tone(const char *from, float seconds, const char *to, float duty, float release, float vibrato) {
  Step s;
  s.f0 = note(from);
  s.f1 = to != nullptr ? note(to) : 0;
  s.seconds = seconds;
  s.duty = duty;
  s.release = release;
  s.vibrato = vibrato;
  return s;
}

Step rest(float seconds) {
  Step s;
  s.seconds = seconds;
  return s;
}

std::vector<Step> arp(std::initializer_list<const char *> names, float step, float duty, float last) {
  std::vector<Step> out;
  const size_t n = names.size();
  size_t i = 0;
  for (const char *name : names) {
    if (++i < n) {
      out.push_back(tone(name, step, nullptr, duty, 0.012f));
    } else {
      out.push_back(tone(name, last > 0 ? last : step * 2, nullptr, duty, 0.08f));
    }
  }
  return out;
}

static void append(std::vector<Step> &to, const std::vector<Step> &from) { to.insert(to.end(), from.begin(), from.end()); }

std::vector<Step> sound(const std::string &name) {
  std::vector<Step> s;
  if (name == "start") {  // Pomodoro started or resumed: two quick rising blips.
    s = {tone("C5", 0.06f, nullptr, 0.25f), rest(0.02f), tone("G5", 0.09f, nullptr, 0.25f)};
  } else if (name == "pause") {  // Paused: the same, falling.
    s = {tone("G5", 0.06f, nullptr, 0.25f), rest(0.02f), tone("C5", 0.09f, nullptr, 0.25f)};
  } else if (name == "stop") {  // Focus block given up: a sad slide down.
    s = {tone("E5", 0.35f, "A3", 0.5f, 0.1f)};
  } else if (name == "focus_done") {  // Focus block done: a cheerful little run.
    s = arp({"C5", "E5", "G5", "C6"}, 0.07f, 0.25f, 0.22f);
  } else if (name == "goal") {  // Daily goal (or a bonus tomato): a longer fanfare.
    append(s, arp({"G4", "C5", "E5", "G5"}, 0.07f, 0.25f, 0.12f));
    s.push_back(rest(0.04f));
    append(s, arp({"E5", "G5", "C6"}, 0.07f, 0.5f, 0.12f));
    s.push_back(rest(0.04f));
    s.push_back(tone("C6", 0.4f, nullptr, 0.25f, 0.2f, 7));
  } else if (name == "break_over") {  // Break over: "wee-woo", twice.
    s = {tone("A5", 0.14f, "E6", 0.5f, 0.01f), tone("E6", 0.14f, "A5", 0.5f, 0.02f), rest(0.08f),
         tone("A5", 0.14f, "E6", 0.5f, 0.01f), tone("E6", 0.18f, "A5", 0.5f, 0.06f)};
  } else if (name == "pet") {  // Petted: "wee-wee", two quick upward sweeps.
    s = {tone("C6", 0.09f, "G6", 0.25f, 0.02f), rest(0.04f), tone("D6", 0.11f, "A6", 0.25f, 0.04f)};
  } else if (name == "timer") {  // Timer done: a bright "ding-dong", three times. Repeats while ringing.
    for (int i = 0; i < 3; i++) {
      s.push_back(tone("A5", 0.1f, nullptr, 0.25f, 0.05f));
      s.push_back(tone("E6", 0.16f, nullptr, 0.25f, 0.1f));
      s.push_back(rest(0.06f));
    }
  } else if (name == "notify") {  // Something to read: a soft "bing-bong" up a fourth.
    s = {tone("D6", 0.07f, nullptr, 0.5f, 0.015f), rest(0.03f), tone("G6", 0.3f, nullptr, 0.5f, 0.22f)};
  } else if (name == "urgent") {  // Needs an answer now: a bright, quick pair, three times.
    for (int i = 0; i < 3; i++) {
      s.push_back(tone("E6", 0.07f, nullptr, 0.25f, 0.01f));
      s.push_back(tone("A6", 0.09f, nullptr, 0.25f, 0.02f));
      if (i < 2)
        s.push_back(rest(0.07f));
    }
  }
  return s;
}

const std::vector<std::string> &sound_names() {
  static const std::vector<std::string> NAMES = {"start", "pause", "stop",  "focus_done", "goal",
                                                 "break_over", "pet", "timer", "notify",     "urgent"};
  return NAMES;
}

size_t length(const std::vector<Step> &steps) {
  size_t n = (size_t) (RATE * TAIL_SECONDS);
  for (const Step &st : steps)
    n += (size_t) (RATE * st.seconds);
  return n;
}

void render(const std::vector<Step> &steps, int16_t *out) {
  const float k = std::exp(-2.0f * (float) M_PI * SOFTEN_HZ / RATE);
  float acc = 0;  // Low-pass state, carried across steps.
  auto emit = [&](float v) {
    acc = (1 - k) * v + k * acc;
    const float x = std::max(-1.0f, std::min(1.0f, acc * LEVEL));
    *out++ = (int16_t) std::lround(x * 32767.0f);
  };
  for (const Step &st : steps) {
    const int n = (int) (RATE * st.seconds);
    if (st.f0 <= 0) {  // Rest.
      for (int i = 0; i < n; i++)
        emit(0);
      continue;
    }
    const float f1 = st.f1 > 0 ? st.f1 : st.f0;
    const float ratio = f1 / st.f0;
    const int a = (int) (RATE * st.attack);
    const int r = (int) (RATE * st.release);
    double phase = 0;
    for (int i = 0; i < n; i++) {
      const float t = i / (float) RATE;
      float freq = st.f0 * std::pow(ratio, t / std::max(st.seconds, 1e-9f));
      if (st.vibrato > 0)
        freq *= 1.0f + 0.03f * std::sin(2.0f * (float) M_PI * st.vibrato * t);
      phase += freq / RATE;
      float v = std::fmod(phase, 1.0) < st.duty ? 1.0f : -1.0f;
      if (i < a)
        v *= a > 1 ? i / (float) (a - 1) : 0.0f;
      if (i >= n - r)
        v *= r > 1 ? (n - 1 - i) / (float) (r - 1) : 0.0f;
      emit(v);
    }
  }
  const int tail = (int) (RATE * TAIL_SECONDS);
  for (int i = 0; i < tail; i++)
    *out++ = 0;  // Silence, not the filter's decay: the same as before.
}

std::vector<int16_t> render(const std::vector<Step> &steps) {
  std::vector<int16_t> out(length(steps));
  render(steps, out.data());
  return out;
}

}  // namespace Synth
}  // namespace Daruma
