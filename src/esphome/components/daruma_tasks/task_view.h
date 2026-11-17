#pragma once

// The Tasks app screen: a checklist that pages with vertical swipes. Draws
// a TaskList and turns taps into check-offs. All layout comes from the
// AppView rectangle, so it fits any app area. Boards without touch move a
// focus over the rows (NEXT, PREV) and check the focused one off (SELECT).

#include <string>

#include "esphome/components/daruma/hub.h"
#include "esphome/components/daruma/focus.h"
#include "task_list.h"

namespace Daruma {

class TaskView {
 public:
  explicit TaskView(TaskList *list) : list_(list) {}

  // The app came on screen: back to the top, and fetch the list again.
  void on_open() {
    this->first_ = 0;
    this->focus_.set_count(this->list_->items().size());
    this->focus_.reset();
    this->list_->refresh_soon();
  }
  // The tile line: "3 left", "All done", or "" while unknown.
  std::string status() const;

  void draw(AppView &v);
  // Input in app-area coordinates. True when used.
  bool input(Input input, int x, int y);

 protected:
  struct Layout {
    int left, top, width, height;  // The list, inside the app area.
    int row_h;
    int rows;  // Rows that fit.
  };

  Layout layout_(const AppView &v, int text_h) const;
  int total_rows_() const;
  void clamp_scroll_();
  void draw_row_(AppView &v, const Layout &l, int y, const TaskItem &item, bool focused);
  bool move_focus_(bool forward);
  void draw_check_(AppView &v, int cx, int cy, int r, const TaskItem &item);
  void draw_marks_(AppView &v, int right, int cy, const TaskItem &item);
  void draw_scroll_bar_(AppView &v, const Layout &l);
  void draw_message_(AppView &v, const std::string &text, int text_h);
  void draw_notice_(AppView &v, int text_h);

  TaskList *list_;
  int first_{0};     // First row shown.
  FocusRing focus_;  // The focused row, on boards without touch.
  // From the last draw, for taps (app-area coordinates).
  int list_top_{0};
  int row_h_{0};
  int rows_{0};
};

}  // namespace Daruma
