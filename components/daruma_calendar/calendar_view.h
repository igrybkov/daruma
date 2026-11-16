#pragma once

// Draws one day of events into an app area and maps taps back to it. Knows
// nothing about fetching; CalendarApp hands it a CalendarViewState.

#include <ctime>
#include <string>

#include "calendar_day.h"
#include "esphome/components/daruma/hub.h"

namespace Daruma {

struct CalendarViewState {
  std::string label;  // "Today", "Tomorrow", "Mon 17"
  std::string date;   // Small text next to the label: "Sun 15"
  const CalendarDay *day{nullptr};  // Null while nothing is loaded.
  bool loading{false};
  std::string error;  // Shown when there is no day to show.
  bool can_go_back{true};
  bool can_go_forward{true};
  bool is_today{false};  // Mark the event in progress and the current time.
  time_t now{0};
  // Words, so a theme can change them.
  std::string loading_text;
  std::string empty_text;
  std::string all_day_text;
  std::string more_text;  // "+3 <more_text>"
  std::string untitled_text;
};

enum class CalendarHit { NONE, PREVIOUS, NEXT, LABEL, LIST };

class CalendarView {
 public:
  void draw(AppView &v, const CalendarViewState &state);
  // x, y relative to the app area, as the app's input gets them.
  CalendarHit hit(int x, int y) const;

  // Rows that fit the list at the last draw.
  int rows() const { return this->rows_; }
  // First row shown. Clamped to the rows on the next draw.
  int scroll() const { return this->scroll_; }
  void set_scroll(int row) { this->scroll_ = row; }
  void scroll_by(int rows) { this->scroll_ += rows; }
  // Puts row near the top of the list on the next draw.
  void scroll_to(int row) { this->scroll_ = row - 1; }
  // The last row of the list was on screen at the last draw.
  bool at_end() const { return this->scroll_ + this->rows_ >= this->items_; }

 protected:
  void draw_bar_(AppView &v, const CalendarViewState &state);
  void draw_list_(AppView &v, const CalendarViewState &state);
  void draw_message_(AppView &v, const std::string &text, int top);
  void draw_row_(AppView &v, const CalendarViewState &state, const CalendarEvent &event, bool next, int top,
                 int right);

  // Layout, in app-area pixels, scaled to the screen at each draw. Kept from
  // the last draw for hit().
  int pad_{10};
  int bar_h_{34};
  int row_h_{28};
  int time_w_{54};
  int arrow_w_{46};
  int w_{0};
  int h_{0};
  int rows_{1};
  int scroll_{0};
  int items_{0};  // Rows in the list at the last draw.
};

}  // namespace Daruma
