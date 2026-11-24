#include "sprite_persona.h"

#include <algorithm>
#include <utility>

#include "esphome/core/hal.h"
#include "esphome/core/helpers.h"
#include "esphome/core/log.h"

namespace Daruma {

static const char *const TAG = "daruma_sprites";
static const uint32_t BLINK_MS = 160;
static const uint32_t WINK_MS = 450;

static inline uint16_t to_565(const esphome::Color &c) {
  return (uint16_t) (((c.r >> 3) << 11) | ((c.g >> 2) << 5) | (c.b >> 3));
}

void SpritePersona::add_frame(int index, int frame, uint32_t ms) {
  Animation &anim = this->anims_[index];
  anim.frames.push_back(Frame{(int16_t) frame, ms});
  anim.total_ms += ms;
}

const SpritePersona::Animation &SpritePersona::animation_(StateId state, bool live) const {
  return this->mapped_(live && this->interluding_(state) ? this->interlude_ : this->animation_for(state));
}

const SpritePersona::Animation &SpritePersona::mapped_(int animation) const {
  // The build checks every index; animation 0 is only a safety net.
  size_t index = (size_t) animation;
  const size_t goal = (size_t) this->signals_ref_().goal;
  if (goal < this->goal_maps_.size() && index < this->goal_maps_[goal].size())
    index = (size_t) this->goal_maps_[goal][index];
  return this->anims_[index < this->anims_.size() ? index : 0];
}

int SpritePersona::current_(StateId state) {
  const Animation &anim = this->animation_(state, true);
  const bool interlude = this->interluding_(state);
  const uint32_t now = esphome::millis();
  // A new animation, or the interlude set again: start it from the top.
  if (&anim != this->playing_ || (interlude && this->played_serial_ != this->interlude_serial_)) {
    this->playing_ = &anim;
    this->played_serial_ = this->interlude_serial_;
    this->epoch_ = now;
  }
  if (anim.wink >= 0 && (int32_t) (this->wink_until_ - now) > 0)
    return anim.wink;
  if (anim.blink >= 0 && (int32_t) (this->blink_until_ - now) > 0)
    return anim.blink;

  const uint32_t elapsed = now - this->epoch_;
  if ((anim.once || (interlude && this->interlude_once_)) && elapsed >= anim.total_ms)
    return anim.frames.back().frame;
  uint32_t t = anim.total_ms > 0 ? elapsed % anim.total_ms : 0;
  for (const auto &frame : anim.frames) {
    if (t < frame.ms)
      return frame.frame;
    t -= frame.ms;
  }
  return anim.frames.back().frame;
}

static inline int mod(int a, int n) { return ((a % n) + n) % n; }

SpritePersona::View SpritePersona::view_(esphome::display::Display &display, int w, int h, bool extend) const {
  View v;
  v.stage = this->stage_(display);
  int s = std::max(1, std::min(v.stage.w / std::max(w, 1), v.stage.h / std::max(h, 1)));
  if (this->max_scale_ > 0)
    s = std::min(s, this->max_scale_);
  v.scale = s;
  const int core_x = v.stage.x + (v.stage.w - w * s) / 2;
  // A room stands on the bottom; extra height goes above it, onto the wall.
  const int core_y = extend ? v.stage.bottom() - h * s : v.stage.y + (v.stage.h - h * s) / 2;
  if (extend) {
    // Whole scene pixels only, and only where a margin has room for one, so
    // a scene that nearly fits keeps its thin background edge.
    auto cells = [s](int margin) { return margin >= s ? (margin + s - 1) / s : 0; };
    if (this->strips_[0].valid() && this->strips_[1].valid()) {
      v.left = cells(core_x - v.stage.x);
      v.right = cells(v.stage.right() - (core_x + w * s));
    }
    if (this->strips_[2].valid())
      v.top = cells(core_y - v.stage.y);
  }
  v.w = v.left + w + v.right;
  v.h = v.top + h;
  v.sx = core_x - v.left * s;
  v.sy = core_y - v.top * s;
  v.covers =
      v.sx <= v.stage.x && v.sy <= v.stage.y && v.sx + v.w * s >= v.stage.right() && v.sy + v.h * s >= v.stage.bottom();
  return v;
}

void SpritePersona::decode_strips_() {
  if (this->strips_decoded_)
    return;
  this->strips_decoded_ = true;
  const uint16_t empty = to_565(this->background_);
  for (int i = 0; i < 3; i++) {
    const Sprite *sprite = this->strip_sprites_[i];
    if (sprite == nullptr)
      continue;
    Strip &strip = this->strips_[i];
    strip.w = sprite->width();
    strip.h = sprite->height();
    strip.px.resize((size_t) strip.w * strip.h);
    Sprite::Rows rows(*sprite);
    for (int y = 0; y < strip.h; y++) {
      const uint8_t *row = rows.next();
      for (int x = 0; x < strip.w; x++)
        strip.px[(size_t) y * strip.w + x] = sprite->is_clear(row[x]) ? empty : sprite->color(row[x]);
    }
  }
  // Side strips come as a pair, and must match the backdrop's height.
  if (this->backdrop_ != nullptr) {
    if (this->strips_[0].h != this->backdrop_->height() || this->strips_[1].h != this->backdrop_->height())
      this->strips_[0] = this->strips_[1] = Strip{};
    if (this->strips_[2].w != this->backdrop_->width())
      this->strips_[2] = Strip{};
  }
}

void SpritePersona::blit_(esphome::display::Display &display, const Sprite *image) {
  const View v = this->view_(display, image->width(), image->height(), false);
  if (!v.covers)
    display.fill(this->background_);
  image->draw(display, v.sx, v.sy, v.scale);
}

void SpritePersona::blit_diff_(esphome::display::Display &display, const Sprite *image, const Sprite *previous) {
  const int w = image->width();
  const int h = image->height();
  const View v = this->view_(display, w, h, false);
  const int s = v.scale;
  const int ox = v.sx;
  const int oy = v.sy;
  const uint16_t empty = to_565(this->background_);
  auto color = [empty](const Sprite *sprite, uint8_t index) {
    return sprite->is_clear(index) ? empty : sprite->color(index);
  };
  Sprite::Rows now_rows(*image), old_rows(*previous);
  for (int y = 0; y < h; y++) {
    const uint8_t *row = now_rows.next();
    const uint8_t *old = old_rows.next();
    int x = 0;
    while (x < w) {
      const uint16_t c = color(image, row[x]);
      if (c == color(previous, old[x])) {
        x++;
        continue;
      }
      int run = 1;
      while (x + run < w && color(image, row[x + run]) == c && color(previous, old[x + run]) != c)
        run++;
      display.filled_rectangle(ox + x * s, oy + y * s, run * s, s, from_565(c));
      x += run;
    }
  }
}

// --- Layered drawing ----------------------------------------------------------

static inline uint16_t hex_to_565(uint32_t rgb) {
  return to_565(esphome::Color((rgb >> 16) & 0xFF, (rgb >> 8) & 0xFF, rgb & 0xFF));
}

void SpritePersona::set_recolor(std::vector<uint32_t> colors, std::vector<std::vector<uint32_t>> by_weekday) {
  this->recolor_from_.clear();
  for (uint32_t c : colors)
    this->recolor_from_.push_back(hex_to_565(c));
  this->recolor_by_day_.clear();
  for (const auto &day : by_weekday) {
    std::vector<uint16_t> out;
    for (uint32_t c : day)
      out.push_back(hex_to_565(c));
    this->recolor_by_day_.push_back(out);
  }
}

uint32_t SpritePersona::window_step_() const {
  return this->has_window_ ? window_step(this->signals_ref_().sky, esphome::millis()) : 0;
}

SpritePersona::Under SpritePersona::under_now_() const {
  const Signals &signals = this->signals_ref_();
  Under u;
  u.step = this->window_step_();
  u.sky = (uint8_t) signals.sky;
  if (!this->plant_.empty()) {
    // Progress 0..10 over the stages, rounded up: the first bit of progress
    // already shows a sprout.
    const size_t last = this->plant_.size() - 1;
    u.plant = (uint8_t) std::min<size_t>(last, (signals.progress * last + 9) / 10);
    u.wilted = signals.behind || (signals.wellbeing >= 0 && signals.wellbeing <= 2);
  }
  // Param rug: 0 = by weekday, 1 = plain.
  u.day = this->param("rug") == 0 ? signals.weekday : 0;
  return u;
}

bool SpritePersona::buffers_() {
  const int size = this->view_now_.w * this->view_now_.h;
  if (this->frame_ != nullptr && this->buf_size_ >= size)
    return true;
  if (this->no_memory_)
    return false;
  esphome::RAMAllocator<uint16_t> allocator;
  if (this->frame_ != nullptr) {
    allocator.deallocate(this->under_, this->buf_size_);
    allocator.deallocate(this->frame_, this->buf_size_);
    allocator.deallocate(this->shown_, this->buf_size_);
  }
  this->buf_size_ = size;
  this->under_ = allocator.allocate(size);
  this->frame_ = allocator.allocate(size);
  this->shown_ = allocator.allocate(size);
  this->shown_valid_ = this->under_valid_ = false;
  if (this->under_ == nullptr || this->frame_ == nullptr || this->shown_ == nullptr) {
    ESP_LOGE(TAG, "%s: no memory for the frame buffers", this->name_.c_str());
    this->no_memory_ = true;  // Draw the persona alone from now on.
    this->under_ = this->frame_ = this->shown_ = nullptr;
    return false;
  }
  return true;
}

void SpritePersona::compose_under_(const Under &under) {
  const View &v = this->view_now_;
  const int w = v.w;
  const int h = v.h;
  const int bw = this->backdrop_->width();
  uint16_t *buf = this->under_;

  // The window and the room's own pixels are placed in room coordinates;
  // the view adds the extension around them.
  const int L = v.left, T = v.top;
  if (this->has_window_) {
    Pane pane = this->window_;
    pane.x += L;
    pane.y += T;
    paint_window(buf, w, pane, (Sky) under.sky, under.step);
  }

  const uint16_t empty = to_565(this->background_);
  const int slot = weekday_slot(under.day, this->recolor_by_day_.size());
  const std::vector<uint16_t> *swap = slot >= 0 ? &this->recolor_by_day_[slot] : nullptr;
  auto recolor = [this, swap](uint16_t c) {
    if (swap != nullptr) {
      for (size_t i = 0; i < this->recolor_from_.size() && i < swap->size(); i++) {
        if (c == this->recolor_from_[i])
          return (*swap)[i];
      }
    }
    return c;
  };
  const Strip &left = this->strips_[0], &right = this->strips_[1], &top = this->strips_[2];
  Sprite::Rows rows(*this->backdrop_);
  const uint8_t *row = nullptr;
  for (int y = 0; y < h; y++) {
    const int by = y - T;
    if (by >= 0)
      row = rows.next();
    // Above the room, the top strip repeats; its rows are room rows.
    const int sy = by >= 0 ? by : mod(by, top.h);
    for (int x = 0; x < w; x++) {
      const int bx = x - L;
      uint16_t &out = buf[y * w + x];
      if (by >= 0 && bx >= 0 && bx < bw) {
        if (!this->backdrop_->is_clear(row[bx])) {
          out = recolor(this->backdrop_->color(row[bx]));
        } else if (!this->has_window_ || bx < this->window_.x || by < this->window_.y ||
                   bx >= this->window_.x + this->window_.w || by >= this->window_.y + this->window_.h) {
          out = empty;  // A hole with no window behind it.
        }
      } else if (bx < 0) {
        out = recolor(left.at(mod(bx, left.w), sy));
      } else if (bx >= bw) {
        out = recolor(right.at((bx - bw) % right.w, sy));
      } else {
        out = recolor(top.at(bx, sy));
      }
    }
  }

  if (!this->plant_.empty()) {
    const Sprite *plant = under.wilted ? this->plant_wilted_img_[under.plant] : this->plant_[under.plant];
    Sprite::Rows plant_rows(*plant);
    for (int y = 0; y < plant->height(); y++) {
      const uint8_t *prow = plant_rows.next();
      const int fy = this->plant_y_ + T + y;
      if (fy < 0 || fy >= h)
        continue;
      for (int x = 0; x < plant->width(); x++) {
        const int fx = this->plant_x_ + L + x;
        if (fx >= 0 && fx < w && !plant->is_clear(prow[x]))
          buf[fy * w + fx] = plant->color(prow[x]);
      }
    }
  }

  // Gray and mono screens: the sky and the room as the screen shows them.
  // The persona's pixels come reduced from the build.
  const ColorMode mode = this->color_mode_();
  if (mode != ColorMode::FULL) {
    for (int i = 0; i < w * h; i++) {
      const uint16_t c = buf[i];
      const int gray = quantize_gray(mode, (c >> 11) << 3, ((c >> 5) & 0x3F) << 2, (c & 0x1F) << 3);
      buf[i] = to_565(esphome::Color(gray, gray, gray));
    }
  }
  this->under_key_ = under;
  this->under_valid_ = true;
}

void SpritePersona::compose_frame_() {
  const View &v = this->view_now_;
  const int w = v.w;
  std::copy(this->under_, this->under_ + w * v.h, this->frame_);
  const int ox = this->sprite_x_ + v.left, oy = this->sprite_y_ + v.top;
  for (int y = 0; y < this->canvas_.height(); y++) {
    const int fy = oy + y;
    if (fy < 0 || fy >= v.h)
      continue;
    for (int x = 0; x < this->canvas_.width(); x++) {
      const int fx = ox + x;
      if (fx >= 0 && fx < w && !this->canvas_.is_clear(x, y))
        this->frame_[fy * w + fx] = this->canvas_.at(x, y);
    }
  }
}

Rect SpritePersona::screen_rect_(int x, int y, int w, int h) const {
  // Clipped to the stage: the outer scene pixels of an extension may stick
  // out past it.
  const View &v = this->view_now_;
  const int s = v.scale;
  const int x0 = std::max(v.sx + x * s, v.stage.x), y0 = std::max(v.sy + y * s, v.stage.y);
  const int x1 = std::min(v.sx + (x + w) * s, v.stage.right()), y1 = std::min(v.sy + (y + h) * s, v.stage.bottom());
  return Rect{x0, y0, std::max(0, x1 - x0), std::max(0, y1 - y0)};
}

void SpritePersona::present_(esphome::display::Display &display, bool full) {
  const View &v = this->view_now_;
  const int w = v.w;
  const int h = v.h;
  if (full && !v.covers)
    display.fill(this->background_);
  Rect painted;
  for (int y = 0; y < h; y++) {
    const uint16_t *row = this->frame_ + y * w;
    const uint16_t *old = this->shown_ + y * w;
    int x = 0;
    while (x < w) {
      const uint16_t c = row[x];
      if (!full && c == old[x]) {
        x++;
        continue;
      }
      int run = 1;
      while (x + run < w && row[x + run] == c && (full || old[x + run] != c))
        run++;
      const Rect r = this->screen_rect_(x, y, run, 1);
      if (!r.empty()) {
        display.filled_rectangle(r.x, r.y, r.w, r.h, from_565(c));
        painted = unite(painted, r);
      }
      x += run;
    }
  }
  std::swap(this->frame_, this->shown_);
  this->shown_valid_ = true;
  this->delta_area_ = painted;
}

void SpritePersona::present_box_(esphome::display::Display &display, const Rect &box) {
  const View &v = this->view_now_;
  const int w = v.w;
  const int ox = this->sprite_x_ + v.left, oy = this->sprite_y_ + v.top;
  Rect painted;
  for (int y = box.y; y < box.bottom(); y++) {
    const int fy = oy + y;
    if (fy < 0 || fy >= v.h)
      continue;
    uint16_t *shown = this->shown_ + fy * w;
    const uint16_t *under = this->under_ + fy * w;
    auto value = [&](int x) -> uint16_t {
      return this->canvas_.is_clear(x, y) ? under[ox + x] : this->canvas_.at(x, y);
    };
    int x = std::max(box.x, -ox);
    const int end = std::min(box.right(), w - ox);
    while (x < end) {
      const uint16_t c = value(x);
      if (c == shown[ox + x]) {
        x++;
        continue;
      }
      int run = 1;
      while (x + run < end && value(x + run) == c && shown[ox + x + run] != c)
        run++;
      for (int i = 0; i < run; i++)
        shown[ox + x + i] = c;
      const Rect r = this->screen_rect_(ox + x, fy, run, 1);
      if (!r.empty()) {
        display.filled_rectangle(r.x, r.y, r.w, r.h, from_565(c));
        painted = unite(painted, r);
      }
      x += run;
    }
  }
  this->delta_area_ = painted;
}

void SpritePersona::draw_canvas_flat_(esphome::display::Display &display) {
  const View v = this->view_(display, this->canvas_.width(), this->canvas_.height(), false);
  if (!v.covers)
    display.fill(this->background_);
  for (int y = 0; y < this->canvas_.height(); y++) {
    for (int x = 0; x < this->canvas_.width(); x++) {
      if (!this->canvas_.is_clear(x, y))
        display.filled_rectangle(v.sx + x * v.scale, v.sy + y * v.scale, v.scale, v.scale,
                                 from_565(this->canvas_.at(x, y)));
    }
  }
}

void SpritePersona::draw_layered_(esphome::display::Display &display, int frame, bool idle) {
  this->decode_strips_();
  this->canvas_.show(this->frames_, frame);
  this->view_now_ = this->view_(display, this->backdrop_->width(), this->backdrop_->height(), this->has_strips_());
  if (!this->buffers_()) {
    this->draw_canvas_flat_(display);
    return;
  }
  this->compose_under_(this->under_now_());
  this->compose_frame_();
  this->present_(display, true);
  // A pose gets overlays painted on top; the next idle frame must start over.
  if (!idle)
    this->shown_valid_ = false;
}

bool SpritePersona::draw_delta(esphome::display::Display &display, StateId state) {
  this->delta_area_ = Rect{};
  if (this->layered_()) {
    if (!this->shown_valid_ || this->drawn_ < 0 || this->canvas_.held() != this->drawn_)
      return false;
    // A new screen size needs a full frame.
    const View v = this->view_(display, this->backdrop_->width(), this->backdrop_->height(), this->has_strips_());
    if (v.sx != this->view_now_.sx || v.sy != this->view_now_.sy || v.w != this->view_now_.w ||
        v.h != this->view_now_.h || v.scale != this->view_now_.scale)
      return false;
    const int frame = this->current_(state);
    const Under under = this->under_now_();
    const bool same_room = this->under_valid_ && under == this->under_key_;
    if (frame == this->drawn_ && same_room)
      return true;
    const Rect box = this->canvas_.show(this->frames_, frame);
    if (same_room) {
      // Only the persona moved: send the box its patches touched.
      this->present_box_(display, box);
    } else {
      this->compose_under_(under);
      this->compose_frame_();
      this->present_(display, false);
    }
    this->drawn_ = frame;
    return true;
  }
  const int frame = this->current_(state);
  if (this->drawn_ < 0)
    return false;
  const Sprite *image = this->frames_[frame].image;
  const Sprite *drawn = this->frames_[this->drawn_].image;
  if (image->width() != drawn->width() || image->height() != drawn->height())
    return false;
  if (image != drawn)
    this->blit_diff_(display, image, drawn);
  this->drawn_ = frame;
  return true;
}

void SpritePersona::draw(esphome::display::Display &display, StateId state, float look_y) {
  // look_y is ignored: the scene stays put and the bubble overlays it.
  const int frame = this->current_(state);
  if (this->layered_()) {
    this->draw_layered_(display, frame, true);
  } else {
    this->blit_(display, this->frames_[frame].image);
  }
  this->drawn_ = frame;
}

void SpritePersona::draw_still(esphome::display::Display &display, StateId state) {
  const int frame = this->animation_(state, false).frames.front().frame;
  if (this->layered_()) {
    this->draw_layered_(display, frame, false);
  } else {
    this->blit_(display, this->frames_[frame].image);
  }
  this->drawn_ = -1;  // Force the next idle frame.
}

bool SpritePersona::needs_redraw(StateId state) {
  if (this->current_(state) != this->drawn_)
    return true;
  return this->layered_() && !(this->under_now_() == this->under_key_);
}

void SpritePersona::blink() { this->blink_until_ = esphome::millis() + BLINK_MS; }

void SpritePersona::wink() { this->wink_until_ = esphome::millis() + WINK_MS; }

}  // namespace Daruma
