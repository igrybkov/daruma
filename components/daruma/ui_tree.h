#pragma once

// What is on screen, as a list of named parts: buttons, tiles, rows, a
// prompt's card. Screens add their parts while they draw. A test or demo
// runner on the host reads the list to find a button by its text and tap
// its middle (demos/harness.py).
//
// Off unless a host board turns it on (UiTree::enable), so on a device each
// add() is a single check of a flag.

#include <string>
#include <vector>

#include "layout.h"

namespace Daruma {

struct UiNode {
  std::string role;   // button, tile, row, dialog, heading, text, app
  std::string name;   // The text it shows, or what it is ("Back")
  Rect rect;
  bool focused{false};
  std::string value;  // Extra state: a mark ("selected", "correct"), "done"
};

class UiTree {
 public:
  static void enable(bool on) { enabled_() = on; }
  static bool enabled() { return enabled_(); }
  // A new full frame starts: forget the parts of the last one.
  static void clear() { nodes_().clear(); }
  static void add(const std::string &role, const std::string &name, const Rect &rect, bool focused = false,
                  const std::string &value = "") {
    if (!enabled_())
      return;
    nodes_().push_back(UiNode{role, name, rect, focused, value});
  }
  static const std::vector<UiNode> &nodes() { return nodes_(); }

 protected:
  static bool &enabled_() {
    static bool on = false;
    return on;
  }
  static std::vector<UiNode> &nodes_() {
    static std::vector<UiNode> list;
    return list;
  }
};

}  // namespace Daruma
