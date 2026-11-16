#pragma once

// The next event line on the device's own screen, shared by every Calendar
// copy that shows it. One line, one layer: the best event of all of them
// (running before upcoming), drawn at the hub's info line
// (Hub::info_line(): the layout's `info` region, or where the persona's
// theme puts it).
//
// It works from each copy's agenda (no HA calls of its own), checks once a
// minute, and redraws only when the text changes:
//   - new or changed text: only the line's area (Hub::request_area()); a
//     pill never gets narrower in such a redraw, so it always covers the
//     old one;
//   - the line goes away: a full frame, since the persona must show again.
// Full frames draw it at its own width.

#include <string>
#include <vector>

#include "esphome/components/daruma/hub.h"
#include "esphome/components/display/display.h"
#include "next_event.h"

namespace Daruma {

class CalendarApp;

class NextEventLine {
 public:
  static NextEventLine &get();

  // A copy shows its events on the line. The first one adds the layer.
  void add(Hub &hub, CalendarApp *app, esphome::display::BaseFont *font);
  // Something a copy shows changed (events, hours, on/off): look again.
  void changed() { this->dirty_ = true; }
  // From each copy's loop; does its work at most once a minute, or after
  // changed().
  void tick();

 protected:
  void draw_(esphome::display::Display &display);
  // The pill for text_ inside `region`, at its own width. The cut title and
  // the width are kept until the text or the region's width changes, so a
  // clipped pass (about ten a second on animated personas) measures nothing.
  Rect measure_(esphome::display::Display &display, const Rect &region);
  LineText compute_(const esphome::ESPTime &now) const;

  Hub *hub_{nullptr};
  std::vector<CalendarApp *> apps_;
  esphome::display::BaseFont *font_{nullptr};
  LineText text_;
  Rect drawn_;  // The pill on screen now; empty when none.
  std::string fitted_;     // text_.title cut to fit (measure_).
  int fitted_w_{0};        // The pill's own width for it.
  int fitted_for_{-1};     // The region width it was cut for; -1: measure again.
  const Persona *persona_{nullptr};
  int minute_{-1};
  bool dirty_{true};
};

}  // namespace Daruma
