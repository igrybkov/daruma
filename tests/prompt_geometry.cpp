// Prints the prompt card geometry (daruma_prompts/prompt_layout.h) as JSON,
// so prompt_preview.py draws from the same rectangles as the device. The
// screen's regions come from the hub's Layout (daruma/layout.h).
//
//   prompt_geometry <message|choice|list> <width> <height> <title_line> <text_line>
//                   <options> <urgent 0|1> <title 0|1> <bar 0|1> [body_lines focus first]
//
// With "width" as the only layout argument it prints the card's inner width:
//   prompt_geometry width <width> <height> <urgent 0|1>

// The tap rules need the prompt types; one state is enough for them.
#define DARUMA_STATE_LIST X(NEUTRAL, "neutral", MOOD, -1, 0, false)

#include <cstdio>
#include <cstdlib>
#include <cstring>

#include "esphome/components/daruma_prompts/prompt_layout.h"

using namespace Daruma;

static void rect(const char *name, const Rect &r, bool comma = true) {
  std::printf("\"%s\": [%d, %d, %d, %d]%s", name, r.x, r.y, r.w, r.h, comma ? ", " : "");
}

int main(int argc, char **argv) {
  if (argc == 5 && std::strcmp(argv[1], "width") == 0) {
    const Layout l = Layout::compute(std::atoi(argv[2]), std::atoi(argv[3]));
    std::printf("%d\n", prompt_layout::inner_width(l, std::atoi(argv[4]) != 0));
    return 0;
  }
  if (argc < 10) {
    std::fprintf(stderr, "usage: see the top of prompt_geometry.cpp\n");
    return 2;
  }
  const Layout l = Layout::compute(std::atoi(argv[2]), std::atoi(argv[3]));
  PromptMetrics m;
  m.title_line = std::atoi(argv[4]);
  m.text_line = std::atoi(argv[5]);
  const int n = std::atoi(argv[6]);
  const bool urgent = std::atoi(argv[7]) != 0;
  const bool title = std::atoi(argv[8]) != 0;
  const bool bar = std::atoi(argv[9]) != 0;
  const int body_lines = argc > 10 ? std::atoi(argv[10]) : 0;
  const int focus = argc > 11 ? std::atoi(argv[11]) : -1;
  const int first = argc > 12 ? std::atoi(argv[12]) : 0;

  PromptGeometry g;
  if (std::strcmp(argv[1], "choice") == 0) {
    g = prompt_layout::choice(l, m, n, body_lines, urgent, title, bar);
  } else if (std::strcmp(argv[1], "list") == 0) {
    g = prompt_layout::list(l, m, n, focus, first, body_lines, urgent, title, bar);
  } else {
    g = prompt_layout::message(l, m, n, body_lines, urgent, title, bar);
  }
  std::printf("{\"unit\": %d, \"border\": %d, \"first\": %d, ", g.unit_px, g.border, g.first);
  rect("card", g.card);
  rect("title", g.title);
  rect("body", g.body);
  rect("bar", g.bar);
  rect("scroll", g.scroll);
  std::printf("\"options\": [");
  for (size_t i = 0; i < g.options.size(); i++) {
    const Rect &r = g.options[i];
    std::printf("%s[%d, %d, %d, %d]", i ? ", " : "", r.x, r.y, r.w, r.h);
  }
  std::printf("]}\n");
  return 0;
}
