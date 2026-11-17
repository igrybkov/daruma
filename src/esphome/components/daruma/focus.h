#pragma once

// The focus ring for boards without touch: which item NEXT, PREV and SELECT
// act on. The menu keeps one for the dock and one for the app board; an app
// with a list can keep its own (Tasks does).
//
// Plain C++ with no ESPHome includes, so a host test can check it
// (tests/test_layout.cpp).
//
//   FocusRing focus;              // in the app
//   focus.set_count(items.size());
//   case Input::NEXT: focus.next(); first = focus.keep_visible(first, rows); return true;
//   case Input::SELECT: toggle(focus.index()); return true;
//   ... draw a ring around row focus.index() when AppView::focus is true.

#include <algorithm>

namespace Daruma {

class FocusRing {
 public:
  explicit FocusRing(bool wrap = true) : wrap_(wrap) {}

  // How many items there are. The focus stays on a valid one; with none it
  // is -1.
  void set_count(int count) {
    this->count_ = std::max(0, count);
    this->index_ = this->count_ == 0 ? -1 : std::max(0, std::min(this->index_, this->count_ - 1));
  }
  int count() const { return this->count_; }
  int index() const { return this->index_; }
  bool valid() const { return this->index_ >= 0; }
  void set(int index) { this->index_ = this->count_ == 0 ? -1 : std::max(0, std::min(index, this->count_ - 1)); }
  void reset() { this->set(0); }

  // Moves on by one. At the end it wraps around (or stays, without wrap).
  // Returns true when the focus moved.
  bool next() { return this->step_(1); }
  bool prev() { return this->step_(-1); }

  // The page (of `per_page` items) the focus is on.
  int page(int per_page) const { return per_page > 0 && this->index_ > 0 ? this->index_ / per_page : 0; }

  // The first row to show so the focused row is in a window of `rows` rows
  // starting at `first`: unchanged when it already is.
  int keep_visible(int first, int rows) const {
    if (this->index_ < 0 || rows <= 0)
      return first;
    if (this->index_ < first)
      return this->index_;
    if (this->index_ >= first + rows)
      return this->index_ - rows + 1;
    return first;
  }

 protected:
  bool step_(int d) {
    if (this->count_ == 0)
      return false;
    int i = this->index_ < 0 ? 0 : this->index_ + d;
    if (i < 0 || i >= this->count_) {
      if (!this->wrap_)
        return false;
      i = (i + this->count_) % this->count_;
    }
    const bool moved = i != this->index_;
    this->index_ = i;
    return moved;
  }

  int count_{0};
  int index_{-1};
  bool wrap_;
};

}  // namespace Daruma
