#include "random_events_component.h"

#ifdef USE_DARUMA_RANDOM_EVENTS

#include "esphome/core/hal.h"
#include "esphome/core/helpers.h"
#include "esphome/core/log.h"

namespace Daruma {

using RandomEvents::Phase;

static const char *const TAG = "daruma.random_events";
// How often eligible time is counted and the rolls are checked.
static const uint32_t SAMPLE_MS = 5000;
// Above the ringing timer's filter (100), so any gesture ends an event.
static const int INPUT_FILTER_PRIORITY = 110;
static const int SAY_SECONDS = 4;

void RandomEventsComponent::add_pool(Persona *persona, const char *id, const RandomEvents::EventDef *events,
                                     uint8_t count) {
  this->pools_.push_back(Pool{persona, id, events, count, std::vector<RandomEvents::EventState>(count), {}});
}

void RandomEventsComponent::setup() {
  // Its own stream: a draw from random_uint32() would move every later blink.
  esphome::random_bytes(reinterpret_cast<uint8_t *>(&this->rng_.state), sizeof(this->rng_.state));
  for (auto &pool : this->pools_) {
    pool.stamps.resize(pool.count);
    for (uint8_t i = 0; i < pool.count; i++) {
      if (pool.events[i].cooldown_s == 0)
        continue;
      pool.stamps[i] = esphome::global_preferences->make_preference<uint32_t>(pool.events[i].key);
      pool.stamps[i].load(&pool.states[i].last_epoch);
    }
  }
  // Any gesture ends a playing event at once. The filter only watches: the
  // gesture goes on to the other filters and the bindings as usual.
  this->hub_->add_gesture_filter(INPUT_FILTER_PRIORITY, [this](const GestureEvent &) {
    if (this->playback_.phase() != Phase::IDLE)
      this->stop_();
    return false;
  });
  this->register_service(&RandomEventsComponent::play, "play_random_event", {"name"});
  const uint32_t now = esphome::millis();
  this->sampled_ms_ = now;
  this->next_roll_ms_ = now + this->wait_ms_();
  this->follow_persona_();
}

void RandomEventsComponent::dump_config() {
  ESP_LOGCONFIG(TAG, "Random events: rolls every %u to %u s", (unsigned) (this->tick_min_ms_ / 1000),
                (unsigned) (this->tick_max_ms_ / 1000));
  for (const auto &pool : this->pools_)
    ESP_LOGCONFIG(TAG, "  %s: %u events", pool.id, (unsigned) pool.count);
}

void RandomEventsComponent::loop() {
  const uint32_t now = esphome::millis();
  this->follow_persona_();
  if (this->playback_.phase() != Phase::IDLE) {
    if (this->screen_blocked_()) {
      this->stop_();
    } else if (this->playback_.tick(now)) {
      this->show_();
    }
  }
  if (now - this->sampled_ms_ >= SAMPLE_MS)
    this->step_(now);
}

void RandomEventsComponent::step_(uint32_t now) {
  const RandomEvents::Context ctx = this->context_(true);
  this->engine_.sample(ctx, now - this->sampled_ms_);
  this->sampled_ms_ = now;
  int index = this->engine_.roll_at(ctx, this->rng_);
  if (index < 0 && (int32_t) (now - this->next_roll_ms_) >= 0) {
    index = this->engine_.roll(ctx, this->rng_);
    this->next_roll_ms_ = this->engine_.next_roll_ms(now, this->wait_ms_(), ctx);
  }
  if (index >= 0)
    this->start_(index, false, now);
}

void RandomEventsComponent::play(std::string name) {
  this->follow_persona_();
  const char *who = this->pool_ != nullptr ? this->pool_->id : "this persona";
  if (!name.empty() && (this->pool_ == nullptr || this->engine_.find(name.c_str()) < 0)) {
    ESP_LOGW(TAG, "play_random_event: %s has no event '%s'", who, name.c_str());
    return;
  }
  const RandomEvents::Context ctx = this->context_(false);
  if (ctx.blocked) {
    ESP_LOGW(TAG, "play_random_event: not now; the screen is busy");
    return;
  }
  const int index = name.empty() ? this->engine_.pick(ctx, this->rng_) : this->engine_.find(name.c_str());
  if (index < 0) {
    ESP_LOGW(TAG, "play_random_event: no event of %s can play now", who);
    return;
  }
  this->start_(index, true, esphome::millis());
}

bool RandomEventsComponent::screen_blocked_() const {
  Hub &hub = *this->hub_;
  if (hub.ui_open() || hub.screen_shown() || !hub.motion_open() || !hub.ha_linked())
    return true;
  if (state_info(hub.state()).kind == StateKind::REACTION)
    return true;
  for (StateId activity : this->quiet_) {
    if (hub.holds_activity(activity))
      return true;
  }
  return false;
}

RandomEvents::Context RandomEventsComponent::context_(bool rolls) const {
  RandomEvents::Context ctx{};
  ctx.blocked = this->screen_blocked_() || this->playback_.phase() != Phase::IDLE || (rolls && !this->enabled_);
  ctx.mood = this->hub_->mood();
  // A manual play ignores Liveliness.
  ctx.liveliness = rolls ? this->liveliness_ : 1.0f;
  ctx.min_gap_ms = this->min_gap_ms_;
  ctx.animate = this->hub_->profile().animate;
  if (this->clock_ != nullptr) {
    const esphome::ESPTime t = this->clock_->now();
    ctx.clock = t.is_valid();
    ctx.epoch = (uint32_t) t.timestamp;
    ctx.month_day = (uint16_t) (t.month * 100 + t.day_of_month);
    ctx.weekday = t.day_of_week;
    ctx.minute = (uint16_t) (t.hour * 60 + t.minute);
  }
  return ctx;
}

void RandomEventsComponent::follow_persona_() {
  Persona *persona = this->hub_->persona();
  if (persona == this->persona_)
    return;
  // The interlude belongs to the persona it was set on.
  if (this->playback_.phase() != Phase::IDLE)
    this->stop_();
  this->persona_ = persona;
  this->pool_ = nullptr;
  for (auto &pool : this->pools_) {
    if (pool.persona == persona)
      this->pool_ = &pool;
  }
  if (this->pool_ != nullptr) {
    this->engine_.set_pool(this->pool_->events, this->pool_->count, this->pool_->states.data());
  } else {
    this->engine_.set_pool(nullptr, 0, nullptr);
  }
}

void RandomEventsComponent::start_(int index, bool manual, uint32_t now) {
  const RandomEvents::EventDef &event = this->pool_->events[index];
  const RandomEvents::Context ctx = this->context_(false);
  ESP_LOGI(TAG, "Random event: %s (%s%s)", event.name, this->pool_->id, manual ? ", manual" : "");
  const Persona &persona = *this->persona_;
  this->playback_.start(event, now, persona.animation_ms(event.enter), persona.animation_ms(event.animation),
                        persona.animation_ms(event.exit));
  if (this->playback_.phase() != Phase::IDLE)
    this->show_();
  this->engine_.played(index, ctx);
  if (event.cooldown_s != 0 && ctx.clock)
    this->pool_->stamps[index].save(&this->pool_->states[index].last_epoch);
  this->next_roll_ms_ = this->engine_.next_roll_ms(now, this->wait_ms_(), ctx);
  // Muted: the device is asleep and makes no sound.
  if (event.sound[0] != '\0' && !this->hub_->muted())
    this->hub_->play_sound(event.sound);
  if (event.say_count > 0)
    this->hub_->show_message(event.say[this->rng_.below(event.say_count)], SAY_SECONDS);
  this->announce_(event, manual);
}

void RandomEventsComponent::announce_(const RandomEvents::EventDef &event, bool manual) {
  if (this->event_ != nullptr)
    this->event_->trigger("random_event");
  this->fire_homeassistant_event("esphome.daruma_random_event", {
                                                                    {"name", event.name},
                                                                    {"persona", this->pool_->id},
                                                                    {"manual", manual ? "true" : "false"},
                                                                });
}

void RandomEventsComponent::show_() {
  const int16_t animation = this->playback_.animation();
  if (animation >= 0) {
    this->persona_->set_interlude(animation, this->playback_.once());
  } else {
    this->persona_->clear_interlude();
  }
  this->hub_->request_redraw();
}

void RandomEventsComponent::stop_() {
  this->playback_.stop();
  this->persona_->clear_interlude();
  this->hub_->request_redraw();
}

uint32_t RandomEventsComponent::wait_ms_() {
  return this->tick_min_ms_ + this->rng_.below(this->tick_max_ms_ - this->tick_min_ms_ + 1);
}

}  // namespace Daruma

#endif  // USE_DARUMA_RANDOM_EVENTS
