#pragma once

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

#include "esphome/components/display/display.h"

namespace Daruma {
    namespace Utilities {
        class Text {
        public:
            // Split text into lines that fit maxWidth. Breaks on spaces only.
            static std::vector<std::string> wrap(
                esphome::display::Display &display,
                esphome::display::BaseFont *font,
                const std::string &text,
                int maxWidth
            );

            // Rounded box with wrapped text, centered horizontally.
            // anchorBottom=false: y is the top edge. true: y is the bottom edge.
            // Returns the box height.
            static int bubble(
                esphome::display::Display &display,
                esphome::display::BaseFont *font,
                const std::string &text,
                int y,
                bool anchorBottom,
                int maxLines,
                esphome::Color background,
                esphome::Color foreground
            );
        };
    }
}

namespace Daruma {

// --- Text from outside (titles from Home Assistant) ---------------------------

// Reads one UTF-8 code point at text[*i] and moves *i past it. Returns 0 for
// a broken sequence, and skips one byte.
uint32_t next_code_point(const std::string &text, size_t *i);

// True when the font can draw this code point. font must be an ESPHome
// `font:` font.
bool has_glyph(esphome::display::BaseFont *font, uint32_t code_point);

// Text made safe to print: control characters become spaces, characters the
// font has no glyph for (emoji and the like) are dropped, and runs of spaces
// are squeezed. Stops before max_bytes. font must be an ESPHome `font:` font.
std::string drawable_text(esphome::display::BaseFont *font, const std::string &text, size_t max_bytes = SIZE_MAX);

// Width of text in pixels.
int text_width(esphome::display::Display &display, esphome::display::BaseFont *font, const std::string &text);

// The text cut at a character boundary and ended with an ellipsis ("…", or
// "..." when the font lacks it) so it fits max_width pixels. Returned as is
// when it already fits.
std::string fit_text(esphome::display::Display &display, esphome::display::BaseFont *font, const std::string &text,
                     int max_width);

// A comma-separated theme word as its parts: "M,T,W" -> M, T, W.
inline std::vector<std::string> split_words(const std::string &text, char sep = ',') {
  std::vector<std::string> out;
  size_t from = 0;
  while (true) {
    const size_t at = text.find(sep, from);
    out.push_back(text.substr(from, at == std::string::npos ? std::string::npos : at - from));
    if (at == std::string::npos)
      return out;
    from = at + 1;
  }
}

// A theme word with {name} filled in: fill("{done} of {goal}", "done", "2").
// Words come from themes, so they never go through printf.
inline std::string fill(std::string text, const std::string &name, const std::string &value) {
  const std::string key = "{" + name + "}";
  for (size_t at = text.find(key); at != std::string::npos; at = text.find(key, at + value.size()))
    text.replace(at, key.size(), value);
  return text;
}

}  // namespace Daruma
