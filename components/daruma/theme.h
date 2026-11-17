#pragma once

#include <cstdint>
#include <map>
#include <string>

#include "esphome/core/color.h"
#include "profile.h"

namespace Daruma {

// How the menu, the app board and the app screens look for one persona. Each
// persona may carry one (the `theme:` option, see theme.py); personas without one
// use default_theme().
enum class ThemeStyle : uint8_t {
  OUTLINE,  // Flat background, rounded cards with an accent outline.
  WOOD,     // Plank frame, cream cards with a dark wood edge.
  PAPER,    // Office wall with a header bar, paper cards pinned up.
};

// Where this persona puts the info line (Layout::info): at the bottom, at the
// top, or nowhere when the persona has no room.
enum class InfoPlace : uint8_t { BOTTOM, TOP, OFF };

struct Theme {
  ThemeStyle style{ThemeStyle::OUTLINE};
  InfoPlace info_line{InfoPlace::BOTTOM};
  esphome::Color frame{14, 16, 20};     // Behind everything.
  esphome::Color edge{60, 66, 76};      // Card edges, the paper header bar.
  esphome::Color panel{30, 34, 42};     // Cards and the app area.
  esphome::Color ink{232, 236, 240};    // Text on cards.
  esphome::Color muted{150, 156, 166};  // Secondary text on cards.
  esphome::Color title{232, 236, 240};  // Text on the frame (headers).
  esphome::Color accent{0, 200, 220};   // Outlines, pins, highlights.
  esphome::Color dot{60, 66, 76};       // Inactive page dots.
  esphome::Color dock{30, 34, 42};      // The dock panel over the persona.
  esphome::Color dock_ink{232, 236, 240};
  esphome::Color dock_muted{150, 156, 166};
  // When set, every app icon on the board uses it instead of the app's color.
  bool has_icon_color{false};
  esphome::Color icon_color;
  // The focus ring on boards without touch. Without it: the accent.
  bool has_focus{false};
  esphome::Color focus;
  // The screen's colors: FULL, or the gray/mono variant this theme was
  // derived for (see for_mode()).
  ColorMode mode{ColorMode::FULL};

  // An app as this persona shows it: another name or icon (both optional).
  struct AppLook {
    std::string name;
    std::string icon;
  };
  std::map<std::string, AppLook> apps;
  // Text apps show, by key, when the persona wants other words (see word()).
  std::map<std::string, std::string> words;
  // Colors of modules, by key under the module's name ("pomodoro.focus").
  std::map<std::string, esphome::Color> colors;

  const std::string &word(const std::string &key, const std::string &fallback) const {
    auto it = this->words.find(key);
    return it != this->words.end() ? it->second : fallback;
  }
  // A module word: this persona's, else the module's default.
  const std::string &word(const std::string &key) const;
  // A module color: this persona's, else the module's default (black, and a
  // log line, for a key no module declares).
  esphome::Color color(const std::string &key) const;

  esphome::Color focus_color() const { return this->has_focus ? this->focus : this->accent; }
  // A color as this theme's screen shows it: unchanged on FULL, else its
  // gray or black/white.
  esphome::Color fit(esphome::Color color) const;
  // `fg` fitted, and flipped to black or white when it would vanish on
  // `background` (an icon on a button, text on a card).
  esphome::Color on(esphome::Color background, esphome::Color fg) const;
  // The theme for a gray4 or mono screen: every color by its luminance,
  // with ink, titles and the focus kept readable on their backgrounds, then
  // the theme's own `mono:` colors on top.
  Theme for_mode(ColorMode mode) const;

  // Module defaults, from each module's declaration at build time.
  static void set_default_color(const std::string &key, uint32_t rgb);
  static void set_default_word(const std::string &key, const std::string &text);

  // For codegen.
  void set_style(int style) { this->style = static_cast<ThemeStyle>(style); }
  void set_info_line(int place) { this->info_line = static_cast<InfoPlace>(place); }
  void set_color(const std::string &key, uint32_t rgb);
  void set_app(const std::string &id, const std::string &name, const std::string &icon) {
    this->apps[id] = AppLook{name, icon};
  }
  void set_word(const std::string &key, const std::string &text) { this->words[key] = text; }
  void set_module_color(const std::string &key, uint32_t rgb);
  // A color the theme wants on gray and mono screens instead of the derived one.
  void set_mono_color(const std::string &key, uint32_t rgb) { this->mono_colors[key] = rgb; }
  std::map<std::string, uint32_t> mono_colors;
};

const Theme &default_theme();

// The color scaled toward black (k < 1) or white-capped brighter (k > 1).
esphome::Color shade(esphome::Color color, float k);

}  // namespace Daruma
