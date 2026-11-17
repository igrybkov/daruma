#include "image_persona.h"

#include <algorithm>

#include "esphome/core/hal.h"

namespace Daruma {

static const uint32_t BLINK_MS = 160;
static const uint32_t WINK_MS = 450;

const ImagePersona::Frames &ImagePersona::frames_for_(StateId state) const {
  // The build checks every index; picture 0 is only a safety net.
  const size_t index = (size_t) this->animation_for(state);
  return this->frames_[index < this->frames_.size() ? index : 0];
}

const Sprite *ImagePersona::pick_(const Frames &frames) {
  const uint32_t now = esphome::millis();
  if (frames.wink != nullptr && (int32_t) (this->wink_until_ - now) > 0)
    return frames.wink;
  if (frames.blink != nullptr && (int32_t) (this->blink_until_ - now) > 0)
    return frames.blink;
  return frames.main;
}

esphome::Color ImagePersona::fill_for_(const Sprite *image) {
  if (this->has_background_ || image == nullptr)
    return this->background_;
  if (image != this->corner_of_) {
    // The top-left pixel: the art's own background, carried to the edges.
    Sprite::Rows rows(*image);
    const uint8_t index = rows.next()[0];
    this->corner_ = image->is_clear(index) ? this->background_ : from_565(image->color(index));
    this->corner_of_ = image;
  }
  return this->corner_;
}

void ImagePersona::show_(esphome::display::Display &display, const Sprite *image) {
  // The picture at 1:1, centered on the stage; the rest in its corner color.
  display.fill(this->fill_for_(image));
  if (image != nullptr) {
    const Rect stage = this->stage_(display);
    image->draw(display, stage.x + (stage.w - image->width()) / 2, stage.y + (stage.h - image->height()) / 2, 1);
  }
}

void ImagePersona::draw(esphome::display::Display &display, StateId state, float look_y) {
  // look_y is ignored: a full picture stays put and the bubble overlays it.
  const Sprite *image = this->pick_(this->frames_for_(state));
  this->show_(display, image);
  this->drawn_ = image;
}

void ImagePersona::draw_still(esphome::display::Display &display, StateId state) {
  this->show_(display, this->frames_for_(state).main);
  this->drawn_ = nullptr;  // Force the next idle frame.
}

bool ImagePersona::needs_redraw(StateId state) { return this->pick_(this->frames_for_(state)) != this->drawn_; }

bool ImagePersona::draw_delta(esphome::display::Display &display, StateId state) {
  this->delta_ = Rect{};
  const Frames &frames = this->frames_for_(state);
  const Sprite *image = this->pick_(frames);
  if (image == this->drawn_)
    return true;
  // Only a change within one set (main, blink, wink) is a small change.
  const Sprite *drawn = this->drawn_;
  if (drawn == nullptr || image == nullptr || (drawn != frames.main && drawn != frames.blink && drawn != frames.wink))
    return false;
  const Rect box = this->diff_box_(drawn, image);
  if (!box.empty()) {
    const Rect stage = this->stage_(display);
    const int x = stage.x + (stage.w - image->width()) / 2;
    const int y = stage.y + (stage.h - image->height()) / 2;
    const Rect screen{x + box.x, y + box.y, box.w, box.h};
    display.start_clipping(esphome::display::Rect(screen.x, screen.y, screen.w, screen.h));
    display.filled_rectangle(screen.x, screen.y, screen.w, screen.h, this->fill_for_(image));
    image->draw(display, x, y, 1);
    display.end_clipping();
    this->delta_ = screen;
  }
  this->drawn_ = image;
  return true;
}

Rect ImagePersona::diff_box_(const Sprite *a, const Sprite *b) {
  for (const auto &diff : this->diffs_) {
    if ((diff.a == a && diff.b == b) || (diff.a == b && diff.b == a))
      return diff.box;
  }
  Rect box{0, 0, a->width(), a->height()};  // Unknown: the whole picture.
  if (a->width() == b->width() && a->height() == b->height()) {
    int x0 = a->width(), y0 = a->height(), x1 = -1, y1 = -1;
    Sprite::Rows ra(*a), rb(*b);
    for (int y = 0; y < a->height(); y++) {
      const uint8_t *pa = ra.next();
      const uint8_t *pb = rb.next();
      for (int x = 0; x < a->width(); x++) {
        const bool same =
            a->is_clear(pa[x]) ? b->is_clear(pb[x]) : !b->is_clear(pb[x]) && a->color(pa[x]) == b->color(pb[x]);
        if (!same) {
          x0 = std::min(x0, x);
          x1 = std::max(x1, x);
          y0 = std::min(y0, y);
          y1 = std::max(y1, y);
        }
      }
    }
    box = x1 < 0 ? Rect{} : Rect{x0, y0, x1 - x0 + 1, y1 - y0 + 1};
  }
  this->diffs_.push_back(Diff{a, b, box});
  return box;
}

void ImagePersona::blink() { this->blink_until_ = esphome::millis() + BLINK_MS; }

void ImagePersona::wink() { this->wink_until_ = esphome::millis() + WINK_MS; }

}  // namespace Daruma
