#include "theme.h"

#include <algorithm>

#include "esphome/core/log.h"

namespace Daruma {

void Theme::set_color(const std::string &key, uint32_t rgb) {
  const esphome::Color c((rgb >> 16) & 0xFF, (rgb >> 8) & 0xFF, rgb & 0xFF);
  if (key == "frame")
    this->frame = c;
  else if (key == "edge")
    this->edge = c;
  else if (key == "panel")
    this->panel = c;
  else if (key == "ink")
    this->ink = c;
  else if (key == "muted")
    this->muted = c;
  else if (key == "title")
    this->title = c;
  else if (key == "accent")
    this->accent = c;
  else if (key == "dot")
    this->dot = c;
  else if (key == "dock")
    this->dock = c;
  else if (key == "dock_ink")
    this->dock_ink = c;
  else if (key == "dock_muted")
    this->dock_muted = c;
  else if (key == "icon_color") {
    this->icon_color = c;
    this->has_icon_color = true;
  } else if (key == "focus") {
    this->focus = c;
    this->has_focus = true;
  }
}

esphome::Color Theme::fit(esphome::Color color) const {
  const int gray = quantize_gray(this->mode, color.r, color.g, color.b);
  if (gray < 0)
    return color;
  return esphome::Color(gray, gray, gray);
}

esphome::Color Theme::on(esphome::Color background, esphome::Color fg) const {
  const esphome::Color bg = this->fit(background);
  esphome::Color out = this->fit(fg);
  if (this->mode != ColorMode::FULL && out.r == bg.r) {
    const uint8_t v = bg.r >= 128 ? 0 : 255;
    out = esphome::Color(v, v, v);
  }
  return out;
}

Theme Theme::for_mode(ColorMode mode) const {
  Theme t = *this;
  t.mode = mode;
  if (mode == ColorMode::FULL)
    return t;
  for (esphome::Color *c : {&t.frame, &t.edge, &t.panel, &t.ink, &t.muted, &t.title, &t.accent, &t.dot, &t.dock,
                            &t.dock_ink, &t.dock_muted, &t.icon_color, &t.focus})
    *c = t.fit(*c);
  for (auto &entry : t.colors)
    entry.second = t.fit(entry.second);
  // Keep what must be read readable on what it sits on.
  t.ink = t.on(t.panel, t.ink);
  t.muted = t.on(t.panel, t.muted);
  t.title = t.on(t.frame, t.title);
  t.dock_ink = t.on(t.dock, t.dock_ink);
  t.dock_muted = t.on(t.dock, t.dock_muted);
  t.dot = t.on(t.frame, t.dot);
  if (t.has_icon_color)
    t.icon_color = t.on(t.panel, t.icon_color);
  // The focus ring sits on the frame, around a card or a button.
  t.focus = t.on(t.frame, t.focus_color());
  t.has_focus = true;
  for (const auto &entry : this->mono_colors)
    t.set_color(entry.first, entry.second);
  return t;
}

static esphome::Color from_hex(uint32_t rgb) {
  return esphome::Color((rgb >> 16) & 0xFF, (rgb >> 8) & 0xFF, rgb & 0xFF);
}

static std::map<std::string, esphome::Color> &default_colors() {
  static std::map<std::string, esphome::Color> colors;
  return colors;
}

static std::map<std::string, std::string> &default_words() {
  static std::map<std::string, std::string> words;
  return words;
}

void Theme::set_module_color(const std::string &key, uint32_t rgb) { this->colors[key] = from_hex(rgb); }

void Theme::set_default_color(const std::string &key, uint32_t rgb) { default_colors()[key] = from_hex(rgb); }

void Theme::set_default_word(const std::string &key, const std::string &text) { default_words()[key] = text; }

esphome::Color Theme::color(const std::string &key) const {
  auto it = this->colors.find(key);
  if (it != this->colors.end())
    return it->second;
  auto def = default_colors().find(key);
  if (def != default_colors().end())
    return this->fit(def->second);
  ESP_LOGW("daruma", "No module declares the theme color '%s'", key.c_str());
  return esphome::Color::BLACK;
}

const std::string &Theme::word(const std::string &key) const {
  static const std::string EMPTY;
  auto it = this->words.find(key);
  if (it != this->words.end())
    return it->second;
  auto def = default_words().find(key);
  return def != default_words().end() ? def->second : EMPTY;
}

const Theme &default_theme() {
  static const Theme theme;
  return theme;
}

esphome::Color shade(esphome::Color color, float k) {
  auto ch = [k](uint8_t v) { return (uint8_t) std::min(255.0f, std::max(0.0f, v * k)); };
  return esphome::Color(ch(color.r), ch(color.g), ch(color.b));
}

}  // namespace Daruma
