#include "text.h"

#include <algorithm>

#include "draw.h"
#include "esphome/components/font/font.h"

namespace Daruma {
    namespace Utilities {
        static int textWidth(esphome::display::Display &display, esphome::display::BaseFont *font, const std::string &text) {
            int x1, y1, width, height;
            display.get_text_bounds(0, 0, text.c_str(), font, esphome::display::TextAlign::TOP_LEFT, &x1, &y1, &width, &height);
            return width;
        }

        std::vector<std::string> Text::wrap(
            esphome::display::Display &display,
            esphome::display::BaseFont *font,
            const std::string &text,
            int maxWidth
        ) {
            std::vector<std::string> lines;
            size_t paragraphStart = 0;

            while (paragraphStart <= text.size()) {
                size_t paragraphEnd = text.find('\n', paragraphStart);
                if (paragraphEnd == std::string::npos) {
                    paragraphEnd = text.size();
                }
                std::string paragraph = text.substr(paragraphStart, paragraphEnd - paragraphStart);

                std::string line;
                size_t wordStart = 0;
                while (wordStart < paragraph.size()) {
                    size_t wordEnd = paragraph.find(' ', wordStart);
                    if (wordEnd == std::string::npos) {
                        wordEnd = paragraph.size();
                    }
                    std::string word = paragraph.substr(wordStart, wordEnd - wordStart);
                    wordStart = wordEnd + 1;
                    if (word.empty()) {
                        continue;
                    }

                    std::string candidate = line.empty() ? word : line + " " + word;
                    if (line.empty() || textWidth(display, font, candidate) <= maxWidth) {
                        line = candidate;
                    } else {
                        lines.push_back(line);
                        line = word;
                    }
                }
                if (!line.empty()) {
                    lines.push_back(line);
                }

                paragraphStart = paragraphEnd + 1;
            }

            return lines;
        }

        int Text::bubble(
            esphome::display::Display &display,
            esphome::display::BaseFont *font,
            const std::string &text,
            int y,
            bool anchorBottom,
            int maxLines,
            esphome::Color background,
            esphome::Color foreground
        ) {
            if (text.empty()) {
                return 0;
            }

            const int margin = 8;
            const int padding = 8;
            const int boxWidth = display.get_width() - 2 * margin;
            const int textMaxWidth = boxWidth - 2 * padding;

            // The font has no U+02BC (the Ukrainian apostrophe, as in "м'ята").
            // Show U+2019, which looks the same.
            std::string shown = text;
            for (size_t at; (at = shown.find("\xCA\xBC")) != std::string::npos;) {
                shown.replace(at, 2, "\xE2\x80\x99");
            }

            std::vector<std::string> lines = wrap(display, font, shown, textMaxWidth);
            if (lines.empty()) {
                return 0;
            }

            if ((int)lines.size() > maxLines) {
                lines.resize(maxLines);
                std::string &last = lines.back();
                // Drop whole words until the ellipsis fits.
                while (!last.empty() && textWidth(display, font, last + "...") > textMaxWidth) {
                    size_t cut = last.rfind(' ');
                    last = cut == std::string::npos ? "" : last.substr(0, cut);
                }
                last += "...";
            }

            int x1, y1, width, lineHeight;
            display.get_text_bounds(0, 0, "Ay", font, esphome::display::TextAlign::TOP_LEFT, &x1, &y1, &width, &lineHeight);
            lineHeight += 2;

            const int boxHeight = (int)lines.size() * lineHeight + 2 * padding - 2;
            const int top = anchorBottom ? y - boxHeight : y;

            Draw::roundedRectangle(&display, margin, top, boxWidth, boxHeight, 10, background);
            for (size_t i = 0; i < lines.size(); i++) {
                display.print(display.get_width() / 2, top + padding + (int)i * lineHeight, font, foreground,
                              esphome::display::TextAlign::TOP_CENTER, lines[i].c_str(), background);
            }

            return boxHeight;
        }
    

    }
}

namespace Daruma {

uint32_t next_code_point(const std::string &text, size_t *i) {
  const uint8_t b0 = (uint8_t) text[*i];
  size_t len = 1;
  uint32_t cp = b0;
  if (b0 >= 0xF0 && b0 < 0xF8) {
    len = 4;
    cp = b0 & 0x07;
  } else if (b0 >= 0xE0 && b0 < 0xF0) {
    len = 3;
    cp = b0 & 0x0F;
  } else if (b0 >= 0xC0 && b0 < 0xE0) {
    len = 2;
    cp = b0 & 0x1F;
  } else if (b0 >= 0x80) {
    *i += 1;
    return 0;  // A stray continuation byte, or not UTF-8 at all.
  }
  if (*i + len > text.size()) {
    *i += 1;
    return 0;
  }
  for (size_t k = 1; k < len; k++) {
    const uint8_t b = (uint8_t) text[*i + k];
    if ((b & 0xC0) != 0x80) {
      *i += 1;
      return 0;
    }
    cp = (cp << 6) | (b & 0x3F);
  }
  *i += len;
  return cp;
}

bool has_glyph(esphome::display::BaseFont *font, uint32_t code_point) {
  return font == nullptr || static_cast<esphome::font::Font *>(font)->find_glyph(code_point) != nullptr;
}

std::string drawable_text(esphome::display::BaseFont *font, const std::string &text, size_t max_bytes) {
  std::string out;
  out.reserve(std::min(text.size(), max_bytes));
  size_t i = 0;
  while (i < text.size()) {
    const size_t start = i;
    uint32_t cp = next_code_point(text, &i);
    if (cp == 0)
      continue;
    if (cp < 0x20 || cp == 0x7F)
      cp = ' ';
    if (cp == ' ') {
      if (!out.empty() && out.back() != ' ' && out.size() < max_bytes)
        out.push_back(' ');
      continue;
    }
    if (!has_glyph(font, cp))
      continue;
    if (out.size() + (i - start) > max_bytes)
      break;
    out.append(text, start, i - start);
  }
  while (!out.empty() && out.back() == ' ')
    out.pop_back();
  return out;
}

int text_width(esphome::display::Display &display, esphome::display::BaseFont *font, const std::string &text) {
  int x1, y1, width, height;
  display.get_text_bounds(0, 0, text.c_str(), font, esphome::display::TextAlign::TOP_LEFT, &x1, &y1, &width, &height);
  return width;
}

std::string fit_text(esphome::display::Display &display, esphome::display::BaseFont *font, const std::string &text,
                     int max_width) {
  if (max_width <= 0)
    return "";
  if (text_width(display, font, text) <= max_width)
    return text;
  const std::string dots = has_glyph(font, 0x2026) ? "\u2026" : "...";
  // Byte offsets where a code point starts, so a cut never splits one.
  std::vector<size_t> cuts;
  for (size_t i = 1; i < text.size(); i++) {
    if (((uint8_t) text[i] & 0xC0) != 0x80)
      cuts.push_back(i);
  }
  auto head = [&](int k) {
    std::string out = text.substr(0, cuts[k]);
    while (!out.empty() && out.back() == ' ')
      out.pop_back();
    return out;
  };
  // Longest prefix that fits with the dots: a binary search over the cuts.
  int lo = 0, hi = (int) cuts.size() - 1, best = -1;
  while (lo <= hi) {
    const int mid = (lo + hi) / 2;
    if (text_width(display, font, head(mid) + dots) <= max_width) {
      best = mid;
      lo = mid + 1;
    } else {
      hi = mid - 1;
    }
  }
  return best < 0 ? dots : head(best) + dots;
}

}  // namespace Daruma
