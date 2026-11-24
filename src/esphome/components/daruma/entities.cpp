#include "entities.h"

#include "esphome/core/helpers.h"

namespace Daruma {

// --- App switch ---------------------------------------------------------------

void AppSwitch::setup() {
  const bool on = this->get_initial_state_with_restore_mode().value_or(true);
  this->write_state(on);
}

void AppSwitch::write_state(bool state) {
  this->hub_->set_app_enabled(this->app_, state);
  this->publish_state(state);
}

// --- Binding select -------------------------------------------------------------

void BindingSelect::setup() {
  this->pref_ = this->make_entity_preference<uint32_t>();
  // Start from the yaml's choice; a stored one wins when it still exists.
  size_t index = this->index_of(this->hub_->binding_action(this->binding_)).value_or(0);
  uint32_t stored;
  if (this->pref_.load(&stored)) {
    for (size_t i = 0; i < this->size(); i++) {
      if (esphome::fnv1_hash(this->option_at(i)) == stored) {
        index = i;
        break;
      }
    }
  }
  this->hub_->set_binding_action(this->binding_, this->option_at(index));
  this->publish_state(index);
}

void BindingSelect::control(size_t index) {
  if (!this->has_index(index))
    return;
  this->hub_->set_binding_action(this->binding_, this->option_at(index));
  uint32_t stored = esphome::fnv1_hash(this->option_at(index));
  this->pref_.save(&stored);
  this->publish_state(index);
}

// --- Persona params ------------------------------------------------------------

void ParamSelect::setup() {
  this->pref_ = this->make_entity_preference<uint32_t>();
  uint32_t index = (uint32_t) this->persona_->param(this->param_);
  uint32_t stored;
  if (this->pref_.load(&stored) && this->has_index(stored))
    index = stored;
  this->persona_->set_param(this->param_, (int) index);
  this->publish_state(index);
}

void ParamSelect::control(size_t index) {
  if (!this->has_index(index))
    return;
  this->persona_->set_param(this->param_, (int) index);
  uint32_t stored = index;
  this->pref_.save(&stored);
  this->publish_state(index);
  this->hub_->request_redraw();
}

void ParamSwitch::setup() {
  const bool on = this->get_initial_state_with_restore_mode().value_or(this->persona_->param(this->param_) != 0);
  this->write_state(on);
}

void ParamSwitch::write_state(bool state) {
  this->persona_->set_param(this->param_, state ? 1 : 0);
  this->publish_state(state);
  this->hub_->request_redraw();
}

#ifdef USE_DARUMA_RANDOM_EVENTS
// --- Random events --------------------------------------------------------------

void RandomEventsSwitch::setup() { this->write_state(this->get_initial_state_with_restore_mode().value_or(true)); }

void RandomEventsSwitch::write_state(bool state) {
  this->engine_->set_enabled(state);
  this->publish_state(state);
}

void TunableNumber::setup() {
  this->pref_ = this->make_entity_preference<float>();
  float value = this->initial_;
  float stored;
  if (this->pref_.load(&stored) && stored >= this->traits.get_min_value() && stored <= this->traits.get_max_value())
    value = stored;
  this->apply_(value);
  this->publish_state(value);
}

void TunableNumber::control(float value) {
  this->apply_(value);
  this->pref_.save(&value);
  this->publish_state(value);
}
#endif

}  // namespace Daruma
