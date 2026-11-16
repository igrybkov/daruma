#include "persona_select.h"

#include "esphome/core/helpers.h"

namespace Daruma {

void PersonaSelect::setup() {
  // The same key make_entity_preference() makes, from the old name's object id.
  this->pref_ = this->restore_key_ != 0
                    ? esphome::global_preferences->make_preference(sizeof(uint32_t), this->restore_key_)
                    : this->make_entity_preference<uint32_t>();
  size_t index = 0;
  uint32_t stored = 0;
  if (this->pref_.load(&stored)) {
    // The persona id's hash; older builds stored a position in the list they
    // had (legacy_options).
    bool found = false;
    for (size_t i = 0; i < this->size(); i++) {
      if (this->key_(i) == stored) {
        index = i;
        found = true;
        break;
      }
    }
    if (!found && stored < this->legacy_.size()) {
      auto at = this->index_of(this->legacy_[stored]);
      if (at.has_value())
        index = *at;
    }
  }
  this->hub_->set_persona(this->option_at(index));
  this->save_(index);
  this->publish_state(index);
}

void PersonaSelect::control(size_t index) {
  if (!this->has_index(index))
    return;
  this->hub_->set_persona(this->option_at(index));
  this->save_(index);
  this->publish_state(index);
}

uint32_t PersonaSelect::key_(size_t index) const {
  return esphome::fnv1a_hash(index < this->keys_.size() ? this->keys_[index] : std::string(this->option_at(index)));
}

void PersonaSelect::save_(size_t index) {
  // By id, so adding, moving or renaming personas keeps the choice.
  uint32_t stored = this->key_(index);
  this->pref_.save(&stored);
}

}  // namespace Daruma
