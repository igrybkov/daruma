#pragma once

#include <string>
#include <utility>
#include <vector>

#include "esphome/components/select/select.h"
#include "esphome/core/component.h"
#include "esphome/core/preferences.h"
#include "esphome/components/daruma/hub.h"

namespace Daruma {

// The Persona select. It stores the chosen persona by its id (a hash), so a new
// persona anywhere in the list, or a new name, keeps the choice. Without one
// stored, the first persona is shown.
class PersonaSelect : public esphome::select::Select, public esphome::Component {
 public:
  void set_hub(Hub *hub) { this->hub_ = hub; }
  // Each option's persona id, in option order.
  void set_keys(std::vector<std::string> keys) { this->keys_ = std::move(keys); }
  // The option list of builds that stored a position instead of an id.
  void set_legacy_options(std::vector<std::string> options) { this->legacy_ = std::move(options); }
  // The preference key of a build where this select had another name, so a
  // rename keeps the stored choice. 0: the key of the current name.
  void set_restore_key(uint32_t key) { this->restore_key_ = key; }
  void setup() override;
  float get_setup_priority() const override { return esphome::setup_priority::LATE; }

 protected:
  void control(size_t index) override;
  void save_(size_t index);
  uint32_t key_(size_t index) const;

  Hub *hub_{nullptr};
  std::vector<std::string> keys_;
  std::vector<std::string> legacy_;
  uint32_t restore_key_{0};
  esphome::ESPPreferenceObject pref_;
};

}  // namespace Daruma
