#pragma once

// A module is one feature (pomodoro, calendar, the menu, ...). Including its
// package turns it on. In setup() it registers what it adds with the Hub:
// apps, menu items, layers, screens, input handlers, actions, gesture
// filters and progress values. States, theme keys, app ids, action names
// and default bindings are declared for the build as well, so the build can
// check them (see registry.py and the `daruma: modules:` option).
//
// Hub::setup() calls every module's setup() before the first draw, in the
// order the modules were added.

#include <functional>
#include <string>
#include <utility>

namespace Daruma {

class Hub;

class Module {
 public:
  explicit Module(std::string name) : name_(std::move(name)) {}
  virtual ~Module() = default;
  const std::string &module_name() const { return this->name_; }
  virtual void setup(Hub &hub) = 0;

 protected:
  std::string name_;
};

// A module whose setup is a lambda (a package's `setup:`).
class LambdaModule : public Module {
 public:
  LambdaModule(std::string name, std::function<void(Hub &)> setup)
      : Module(std::move(name)), setup_(std::move(setup)) {}
  void setup(Hub &hub) override {
    if (this->setup_)
      this->setup_(hub);
  }

 protected:
  std::function<void(Hub &)> setup_;
};

}  // namespace Daruma
