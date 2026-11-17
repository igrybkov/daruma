#pragma once

// Draws the Agenda (the coming days' events under day headings) into an app
// area and maps taps and the focus back to its rows. Knows nothing about
// fetching; CalendarApp hands it an AgendaViewState.

#include <ctime>
#include <string>
#include <vector>

#include "agenda.h"
#include "calendar_day.h"
#include "esphome/components/daruma/hub.h"
#include "esphome/components/daruma/focus.h"

namespace Daruma {

struct AgendaViewState {
  const CalendarDay *span{nullptr};   // Null while nothing is loaded.
  std::vector<AgendaRow> rows;        // From build_agenda().
  std::vector<std::string> headings;  // Text per day, by day index.
  bool loading{false};
  std::string error;  // Shown when there is nothing to show.
  time_t now{0};
  time_t today_end{0};  // Events before it are today's: past ones dim.
  // Words, so a theme can change them.
  std::string loading_text;
  std::string nothing_text;
  std::string all_day_text;
  std::string more_text;  // "+3 <more_text>"
  std::string untitled_text;
};

class AgendaView {
 public:
  void draw(AppView &v, const AgendaViewState &state);
  // The row under (x, y) in app-area coordinates, at the last draw; -1 for none.
  int row_at(int x, int y) const;

  // Rows that fit at the last draw.
  int rows() const { return this->fit_; }
  void reset() {
    this->scroll_ = 0;
    this->focus_.reset();
  }
  void scroll_by(int rows) { this->scroll_ += rows; }
  bool at_end() const { return this->scroll_ + this->fit_ >= this->count_; }
  void set_scroll(int row) { this->scroll_ = row; }

  // Boards without touch: the focused row, moved by NEXT and PREV.
  int focused() const { return this->focus_.index(); }
  bool move_focus(bool forward);

 protected:
  void draw_heading_(AppView &v, const std::string &text, int top, int right);
  void draw_event_(AppView &v, const AgendaViewState &state, const CalendarEvent &event, int top, int right);
  void draw_message_(AppView &v, const std::string &text);

  // Layout from the last draw, in screen pixels.
  int pad_{10};
  int row_h_{26};
  int time_w_{54};
  int top_{0};  // App-area y of the first row.
  int fit_{1};
  int scroll_{0};
  int count_{0};  // Rows at the last draw.
  FocusRing focus_{false};
};

}  // namespace Daruma
