#include "prompt_controller.h"

#include <algorithm>
#include <cstdlib>

#include "esphome/components/daruma/draw.h"
#include "esphome/components/daruma/text.h"
#include "esphome/components/daruma/ui_tree.h"
#include "esphome/core/hal.h"
#include "esphome/core/log.h"

namespace Daruma {

using esphome::Color;
using esphome::display::BaseFont;
using esphome::display::Display;
using esphome::display::TextAlign;

static const char *const TAG = "daruma_prompts";
static const char *const OWNER = "prompts";

// Urgent and game prompts draw over the menu (screen 100, input 50); info
// prompts draw under it.
static const int URGENT_SCREEN = 200;
static const int INFO_SCREEN = 10;
static const int URGENT_INPUT = 80;
static const int INFO_INPUT = 40;

// Text limits, in bytes.
static const size_t MAX_ID = 64;
static const size_t MAX_TITLE = 120;
static const size_t MAX_BODY = 600;
static const size_t MAX_OPTION = 80;

static const char *style_name(PromptStyle s) {
  switch (s) {
    case PromptStyle::URGENT:
      return "urgent";
    case PromptStyle::GAME:
      return "game";
    default:
      return "info";
  }
}

void PromptController::setup(Hub &hub) {
  this->hub_ = &hub;
  if (!state_by_name("attention", &this->attention_))
    ESP_LOGE(TAG, "No 'attention' state");
  hub.add_screen(URGENT_SCREEN, [this](Display &d) { return this->draw_(d, true); });
  hub.add_screen(INFO_SCREEN, [this](Display &d) { return this->draw_(d, false); });
  hub.add_input_handler(URGENT_INPUT, [this](Input in, int x, int y) { return this->on_input_(true, in, x, y); });
  hub.add_input_handler(INFO_INPUT, [this](Input in, int x, int y) { return this->on_input_(false, in, x, y); });
  hub.add_action("prompts.dismiss", [this]() { this->dismiss(); });
}

void PromptController::dump_config() {
  ESP_LOGCONFIG(TAG, "Prompts:");
  for (StateId s : this->hold_back_)
    ESP_LOGCONFIG(TAG, "  Info prompts wait during: %s", state_name(s));
}

bool PromptController::holding_info_() const {
  for (StateId s : this->hold_back_) {
    if (this->hub_->holds_activity(s))
      return true;
  }
  return false;
}

Prompt *PromptController::current_() { return this->stack_.top(this->holding_info_()); }

void PromptController::changed_() {
  if (this->hub_ != nullptr)
    this->hub_->request_redraw();
}

std::string PromptController::sound_for_(const Prompt &p) const {
  if (p.sound == "none")
    return "";
  if (!p.sound.empty())
    return p.sound;
  return p.style == PromptStyle::URGENT ? "urgent" : "notify";
}

void PromptController::play_(const Prompt &p) {
  this->hub_->play_sound(this->sound_for_(p));
  this->replay_seq_ = p.style == PromptStyle::URGENT ? p.seq : 0;
  this->replay_at_ = esphome::millis() + URGENT_REPEAT_MS;
  this->played_ = 1;
}

void PromptController::replay_urgent_(const Prompt *p, uint32_t now) {
  if (this->replay_seq_ == 0)
    return;
  // Only while that prompt is on top and nobody has answered it.
  if (p == nullptr || p->seq != this->replay_seq_ || p->answered || this->played_ >= URGENT_PLAYS) {
    this->replay_seq_ = 0;
    return;
  }
  if ((int32_t) (now - this->replay_at_) < 0)
    return;
  this->hub_->play_sound(this->sound_for_(*p));
  this->played_++;
  this->replay_at_ = now + URGENT_REPEAT_MS;
}

void PromptController::loop() {
  if (this->hub_ == nullptr)
    return;
  const uint32_t now = esphome::millis();
  if (this->stack_.tick(now))
    this->changed_();
  this->flush_();

  Prompt *p = this->current_();
  this->hub_->set_prompt_open(p != nullptr);

  // The persona plays the state of the prompt on top. The prompt's own
  // sound plays instead of the activity's.
  const uint32_t seq = p != nullptr ? p->seq : 0;
  if (seq != this->active_seq_) {
    if (p != nullptr) {
      this->hub_->set_activity(OWNER, p->state, false);
    } else {
      this->hub_->clear_activity(OWNER);
    }
    this->active_seq_ = seq;
  }
  if (p != nullptr && this->announce_seq_ == p->seq) {
    this->announce_seq_ = 0;
    this->play_(*p);
    this->shown_callback_.call(p->id, style_name(p->style), this->sound_for_(*p));
  } else {
    this->replay_urgent_(p, now);
  }

  // The countdown bar moves once a second, or once a minute on a slow
  // screen.
  if (p != nullptr) {
    const int32_t step = this->hub_->profile().slow() ? 60000 : 1000;
    const int32_t left = p->left_ms(now);
    const int32_t tick = left < 0 ? -1 : left / step;
    if (tick != this->drawn_tick_) {
      this->drawn_tick_ = tick;
      this->changed_();
    }
  }
}

void PromptController::flush_() {
  for (const Answer &a : this->stack_.take_answers()) {
    ESP_LOGI(TAG, "Prompt '%s': %s %d '%s'", a.id.c_str(), reason_name(a.reason), a.index, a.choice.c_str());
    if (a.reason != Reason::CLOSED)
      this->answer_callback_.call(a.id, a.choice, a.index, reason_name(a.reason));
    if (a.ask != 0) {
      auto it = this->asks_.find(a.ask);
      if (it != this->asks_.end()) {
        it->second.done = true;
        it->second.answer = a;
      }
    }
    this->changed_();
  }
}

// --- API actions --------------------------------------------------------------

std::string PromptController::shown_text_(BaseFont *font, const std::string &text, size_t max_bytes) const {
  // The font lacks U+02BC (the Ukrainian apostrophe); U+2019 looks the same.
  std::string out = text;
  for (size_t at; (at = out.find("\xCA\xBC")) != std::string::npos;)
    out.replace(at, 2, "\xE2\x80\x99");
  return drawable_text(font, out, max_bytes);
}

static std::string check_marks(const std::vector<std::string> &marks, size_t options, std::vector<Mark> *out) {
  if (marks.size() > options)
    return esphome::str_sprintf("marks: %u given for %u options", (unsigned) marks.size(), (unsigned) options);
  out->clear();
  for (size_t i = 0; i < marks.size(); i++) {
    Mark m;
    if (!parse_mark(marks[i], &m))
      return esphome::str_sprintf("marks[%u]: '%s' is not one of '', selected, correct, wrong, hidden", (unsigned) i,
                                  marks[i].c_str());
    out->push_back(m);
  }
  return "";
}

std::string PromptController::show(const std::string &id, const std::string &layout, const std::string &title,
                                   const std::string &body, const std::vector<std::string> &options,
                                   const std::vector<std::string> &marks, const std::string &style, int timeout_s,
                                   const std::string &state, const std::string &sound, bool dismissable,
                                   uint32_t ask) {
  Prompt p;
  if (id.empty() || id.size() > MAX_ID)
    return "id: give 1 to 64 characters";
  p.id = id;
  if (!parse_layout(layout, &p.layout))
    return "layout: '" + layout + "' is not one of message, choice, list";
  if (!parse_style(style, &p.style))
    return "style: '" + style + "' is not one of info, game, urgent";
  const size_t n = options.size();
  switch (p.layout) {
    case PromptLayout::MESSAGE:
      if (n > 3)
        return "options: a message has 0 to 3 buttons";
      break;
    case PromptLayout::CHOICE:
      if (n < 2 || n > 7)
        return "options: a choice has 2 to 4 answers, then up to 3 extra buttons";
      break;
    case PromptLayout::LIST:
      if (n < 1 || n > 20)
        return "options: a list has 1 to 20 options";
      break;
  }
  for (size_t i = 0; i < n; i++) {
    if (options[i].empty())
      return esphome::str_sprintf("options[%u] is empty", (unsigned) i);
  }
  std::string error = check_marks(marks, n, &p.marks);
  if (!error.empty())
    return error;
  if (timeout_s < -1 || timeout_s > 86400)
    return "timeout: 0 (the default, 60 s), -1 (none) or seconds up to 86400";
  p.timeout_ms = timeout_ms(timeout_s, ask != 0);
  if (state.empty()) {
    p.state = this->attention_;
  } else if (!state_by_name(state.c_str(), &p.state)) {
    return "state: '" + state + "' is not a state of this device";
  } else if (state_info(p.state).kind != StateKind::ACTIVITY) {
    return "state: '" + state + "' is not an activity (try attention)";
  }
  p.sound = sound;
  p.dismissable = dismissable;
  p.ask = ask;
  p.title = title;
  p.body = body;
  p.options = options;
  p.title_shown = this->shown_text_(this->title_font_, title, MAX_TITLE);
  p.body_shown = this->shown_text_(this->text_font_, body, MAX_BODY);
  for (const auto &o : options)
    p.options_shown.push_back(this->shown_text_(this->text_font_, o, MAX_OPTION));

  ESP_LOGI(TAG, "Show '%s' (%s, %s, %u options)", id.c_str(), layout.c_str(), style_name(p.style), (unsigned) n);
  this->stack_.show(std::move(p), esphome::millis());
  this->flush_();
  this->changed_();
  return "";
}

std::string PromptController::update(const std::string &id, const std::string &body,
                                     const std::vector<std::string> &marks, int countdown_s) {
  Prompt *p = this->stack_.find(id);
  if (p == nullptr)
    return "no prompt '" + id + "'";
  std::vector<Mark> parsed;
  std::string error = check_marks(marks, p->options.size(), &parsed);
  if (!error.empty())
    return error;
  if (countdown_s < -1 || countdown_s > 86400)
    return "countdown: -1 (keep), 0 (stop) or seconds up to 86400";
  this->stack_.update(id, body.empty() ? nullptr : &body, marks.empty() ? nullptr : &parsed, countdown_s,
                      esphome::millis());
  if (!body.empty())
    p->body_shown = this->shown_text_(this->text_font_, body, MAX_BODY);
  this->changed_();
  return "";
}

std::string PromptController::close(const std::string &id) {
  if (this->stack_.close(id)) {
    ESP_LOGI(TAG, "Closed '%s'", id.c_str());
    this->flush_();
    this->changed_();
  }
  return "";
}

void PromptController::ask(uint32_t call_id, const std::string &id, const std::string &layout,
                           const std::string &title, const std::string &body, const std::vector<std::string> &options,
                           const std::vector<std::string> &marks, const std::string &style, int timeout_s,
                           const std::string &state, const std::string &sound, bool dismissable) {
  AskState &a = this->asks_[call_id];
  a.error = this->show(id, layout, title, body, options, marks, style, timeout_s, state, sound, dismissable, call_id);
  a.done = !a.error.empty();
}

bool PromptController::ask_done(uint32_t call_id) const {
  auto it = this->asks_.find(call_id);
  return it == this->asks_.end() || it->second.done;
}

std::string PromptController::ask_error(uint32_t call_id) const {
  auto it = this->asks_.find(call_id);
  return it == this->asks_.end() ? std::string() : it->second.error;
}

PromptController::Reply PromptController::take_ask(uint32_t call_id) {
  if (!this->ask_done(call_id)) {
    this->stack_.expire_ask(call_id);
    this->flush_();
  }
  Reply reply;
  auto it = this->asks_.find(call_id);
  if (it == this->asks_.end())
    return reply;
  const Answer &a = it->second.answer;
  reply.id = a.id;
  reply.choice = a.choice;
  reply.index = a.index;
  reply.reason = it->second.error.empty() ? reason_name(a.reason) : "";
  this->asks_.erase(it);
  return reply;
}

void PromptController::dismiss() {
  if (this->stack_.dismiss(this->current_())) {
    this->flush_();
    this->changed_();
  }
}

// --- Input ----------------------------------------------------------------------

void PromptController::focus_on_(Prompt &p) {
  // A new prompt: the focus starts on its first option that can be chosen.
  if (this->focus_seq_ == p.seq)
    return;
  this->focus_seq_ = p.seq;
  this->first_ = 0;
  this->scroll_ = ListScroll{};
  this->focus_.set_count(p.options.size());
  this->focus_.reset();
  if (!p.choosable(this->focus_.index()))
    this->move_focus_(p, 1);
}

void PromptController::move_focus_(Prompt &p, int step) {
  // Hidden and answered options are skipped; at most one lap.
  for (int tries = 0; tries < this->focus_.count(); tries++) {
    if (step > 0)
      this->focus_.next();
    else
      this->focus_.prev();
    if (p.choosable(this->focus_.index()))
      return;
  }
}

bool PromptController::on_input_(bool urgent_layer, Input input, int /*x*/, int /*y*/) {
  // The wake word, a ringing timer and apps going off send DISMISS. A prompt
  // from HA stays through those.
  if (input == Input::DISMISS)
    return false;
  Prompt *p = this->current_();
  if (p == nullptr || (p->style != PromptStyle::INFO) != urgent_layer)
    return false;
  this->focus_on_(*p);
  this->changed_();

  switch (input) {
    case Input::BACK:
    case Input::CLOSE:
      this->dismiss_(p);
      break;
    case Input::NEXT:
    case Input::PREV:
      this->move_focus_(*p, input == Input::NEXT ? 1 : -1);
      break;
    case Input::SELECT:
      // As with a tap: a quiet prompt goes, unless it may not; then its
      // button counts.
      if (p->quiet() && (p->dismissable || p->answered)) {
        this->dismiss_(p);
      } else if (p->choosable(this->focus_.index())) {
        this->stack_.choose(p, this->focus_.index());  // May end p.
      } else {
        this->move_focus_(*p, 1);
      }
      break;
    case Input::TAP: {
      // Only the card that is on screen can be hit.
      if (this->drawn_seq_ != p->seq)
        break;
      // A tap comes from the touch screen, at (x, y) where the finger came
      // down. The list rules need the rest of that touch too.
      const Tap tap = tap_result(*p, this->geometry_drawn_, this->hub_->last_touch(), this->scroll_);
      if (tap.action == TapAction::CHOOSE) {
        this->stack_.choose(p, tap.index);  // May end p.
      } else if (tap.action == TapAction::DISMISS) {
        this->dismiss_(p);
      }
      break;
    }
    case Input::SWIPE_UP:
    case Input::SWIPE_DOWN:
      if (p->layout == PromptLayout::LIST) {
        const int page = std::max(1, this->list_fit_);
        const int was = this->first_;
        this->first_ += input == Input::SWIPE_UP ? page : -page;
        this->first_ = std::max(0, std::min(this->first_, (int) p->options.size() - page));
        if (this->first_ != was)
          this->scroll_ = ListScroll{true, esphome::millis()};
      }
      break;
    default:
      break;  // Holds, strokes and side swipes do nothing here.
  }
  this->flush_();
  return true;
}

void PromptController::dismiss_(Prompt *p) {
  // The stack keeps one that is not dismissable, unless it was answered.
  this->stack_.dismiss(p);
}

// --- Drawing --------------------------------------------------------------------

static int line_height(Display &d, BaseFont *font) {
  int x1, y1, w, h;
  d.get_text_bounds(0, 0, "Ay", font, TextAlign::TOP_LEFT, &x1, &y1, &w, &h);
  return h;
}

PromptMetrics PromptController::metrics_(Display &d) const {
  PromptMetrics m;
  m.title_line = line_height(d, this->title_font_);
  m.text_line = line_height(d, this->text_font_);
  return m;
}

PromptGeometry PromptController::geometry_(Display &d, const PromptMetrics &m, const Prompt &p) const {
  const Layout &l = this->hub_->layout();
  const bool urgent = p.style == PromptStyle::URGENT;
  const bool title = !p.title_shown.empty();
  const bool bar = p.timeout_ms > 0 && !p.answered;
  const int n = p.options.size();
  // The body's lines at the card's width, so the card can grow to hold them.
  const int w = prompt_layout::inner_width(l, urgent);
  const int lines =
      p.body_shown.empty() ? 0 : (int) Utilities::Text::wrap(d, this->text_font_, p.body_shown, w).size();
  switch (p.layout) {
    case PromptLayout::CHOICE:
      return prompt_layout::choice(l, m, n, std::min(lines, 3), urgent, title, bar);
    case PromptLayout::LIST: {
      // With buttons the focused row stays in view; with touch, swipes scroll.
      const int focus = this->hub_->uses_focus() ? this->focus_.index() : -1;
      return prompt_layout::list(l, m, n, focus, this->first_, std::min(lines, 2), urgent, title, bar);
    }
    default:
      return prompt_layout::message(l, m, n, std::min(lines, 6), urgent, title, bar);
  }
}

bool PromptController::draw_(Display &d, bool urgent_layer) {
  Prompt *p = this->current_();
  if (p == nullptr || (p->style != PromptStyle::INFO) != urgent_layer)
    return false;
  if (this->stack_.on_screen(p, esphome::millis()))
    this->announce_seq_ = p->seq;
  this->draw_prompt_(d, *p);
  return true;
}

namespace {

// Black or white text, whichever reads better on this fill.
Color ink_on(Color fill) {
  const int luma = (299 * fill.r + 587 * fill.g + 114 * fill.b) / 1000;
  return luma > 150 ? Color(28, 28, 32) : Color(255, 255, 255);
}

// `preferred` when it stands out from `fill`, else black or white. A theme's
// title color can sit close to its edge color (dark teal on dark teal).
Color readable_on(Color fill, Color preferred) {
  const auto luma = [](Color c) { return (299 * c.r + 587 * c.g + 114 * c.b) / 1000; };
  return std::abs(luma(fill) - luma(preferred)) >= 90 ? preferred : ink_on(fill);
}

void ring(Display &d, const Rect &r, int t, Color c) {
  d.filled_rectangle(r.x, r.y, r.w, t, c);
  d.filled_rectangle(r.x, r.bottom() - t, r.w, t, c);
  d.filled_rectangle(r.x, r.y, t, r.h, c);
  d.filled_rectangle(r.x + r.w - t, r.y, t, r.h, c);
}

Rect grow(const Rect &r, int by) { return Rect{r.x - by, r.y - by, r.w + 2 * by, r.h + 2 * by}; }

struct Painter {
  Display &d;
  const Theme &t;
  BaseFont *title_font;
  BaseFont *text_font;
  int unit;

  void frame() {
    const int W = d.get_width(), H = d.get_height();
    switch (t.style) {
      case ThemeStyle::WOOD:
        d.fill(t.edge);
        d.filled_rectangle(unit, unit, W - 2 * unit, H - 2 * unit, t.frame);
        for (int y = unit; y < H - unit; y += unit + unit / 2)
          d.horizontal_line(unit, y, W - 2 * unit, shade(t.frame, 0.9f));
        break;
      case ThemeStyle::PAPER:
        d.fill(t.frame);
        for (int x = 0; x < W; x += 4 * unit)
          d.vertical_line(x, 0, H, shade(t.frame, 0.95f));
        break;
      case ThemeStyle::OUTLINE:
        d.fill(t.frame);
        break;
    }
  }

  void card(const PromptGeometry &g, Color border, bool bordered) {
    const Rect &c = g.card;
    const int b = g.border;
    switch (t.style) {
      case ThemeStyle::WOOD:
        d.filled_rectangle(c.x, c.y, c.w, c.h, border);
        d.filled_rectangle(c.x + b, c.y + b, c.w - 2 * b, c.h - 2 * b, t.panel);
        break;
      case ThemeStyle::PAPER:
        d.filled_rectangle(c.x + unit / 2, c.y + unit / 2, c.w, c.h, shade(t.frame, 0.75f));  // Shadow.
        d.filled_rectangle(c.x, c.y, c.w, c.h, t.panel);
        if (bordered)
          ring(d, c, b, border);
        d.filled_circle(c.x + c.w / 2, c.y + 1, std::max(3, unit * 2 / 3), t.accent);  // Push pin.
        break;
      case ThemeStyle::OUTLINE:
        Utilities::Draw::roundedRectangle(&d, c.x, c.y, c.w, c.h, 2 * unit, border);
        Utilities::Draw::roundedRectangle(&d, c.x + b, c.y + b, c.w - 2 * b, c.h - 2 * b, std::max(2, 2 * unit - b),
                                          t.panel);
        break;
    }
  }

  // A button or answer: its fill, edge and text color for a mark.
  void button_colors(Mark mark, Color *fill, Color *edge, Color *ink) const {
    switch (mark) {
      case Mark::SELECTED:
        *fill = t.color("prompts.selected");
        break;
      case Mark::CORRECT:
        *fill = t.color("prompts.correct");
        break;
      case Mark::WRONG:
        *fill = t.color("prompts.wrong");
        break;
      default:
        if (t.style == ThemeStyle::OUTLINE) {
          *fill = shade(t.panel, 1.6f);
          *edge = t.accent;
          *ink = t.ink;
        } else {
          *fill = t.edge;
          *edge = shade(t.edge, 0.7f);
          *ink = readable_on(t.edge, t.title);
        }
        return;
    }
    *edge = shade(*fill, 0.7f);
    *ink = ink_on(*fill);
  }

  void box(const Rect &r, Color fill, Color edge) {
    const int radius = t.style == ThemeStyle::OUTLINE ? std::min(r.h / 2, unit + unit / 2) : unit / 2;
    Utilities::Draw::roundedRectangle(&d, r.x, r.y, r.w, r.h, radius, edge);
    Utilities::Draw::roundedRectangle(&d, r.x + 2, r.y + 2, r.w - 4, r.h - 4, std::max(1, radius - 2), fill);
  }

  // A text line, cut to fit, vertically centered in r.
  void text(const Rect &r, BaseFont *font, const std::string &s, Color ink, Color bg, TextAlign align) {
    const std::string fitted = fit_text(d, font, s, r.w);
    const int h = line_height(d, font);
    const int y = r.y + (r.h - h) / 2;
    int x = r.x;
    if (align == TextAlign::TOP_CENTER)
      x = r.x + r.w / 2;
    else if (align == TextAlign::TOP_RIGHT)
      x = r.x + r.w;
    d.print(x, y, font, ink, align, fitted.c_str(), bg);
  }

  // Wrapped lines, as many as fit in r, centered as a block. The last line
  // ends with an ellipsis when text is left over.
  void wrapped(const Rect &r, BaseFont *font, const std::string &s, Color ink, Color bg, bool center,
               int max_lines = 99) {
    if (s.empty() || r.h <= 0)
      return;
    const int lh = line_height(d, font);
    std::vector<std::string> lines = Utilities::Text::wrap(d, font, s, r.w);
    const int fit = std::min(max_lines, std::max(1, r.h / lh));
    if ((int) lines.size() > fit) {
      // The next line no longer fits beside it, so fit_text cuts and adds the ellipsis.
      lines[fit - 1] = fit_text(d, font, lines[fit - 1] + " " + lines[fit], r.w);
      lines.resize(fit);
    }
    const int top = center ? r.y + (r.h - (int) lines.size() * lh) / 2 : r.y;
    for (size_t i = 0; i < lines.size(); i++) {
      const std::string line = fit_text(d, font, lines[i], r.w);
      d.print(center ? r.x + r.w / 2 : r.x, top + (int) i * lh, font, ink,
              center ? TextAlign::TOP_CENTER : TextAlign::TOP_LEFT, line.c_str(), bg);
    }
  }

  // How many lines s wraps to at this width.
  int lines(BaseFont *font, const std::string &s, int w) {
    return s.empty() ? 0 : (int) Utilities::Text::wrap(d, font, s, w).size();
  }
};

}  // namespace

void PromptController::draw_prompt_(Display &d, Prompt &p) {
  const Theme &t = this->hub_->theme();
  const PromptMetrics m = this->metrics_(d);
  this->focus_on_(p);
  PromptGeometry g = this->geometry_(d, m, p);
  if (p.layout == PromptLayout::LIST) {
    this->first_ = g.first;
    this->list_fit_ = std::max(1, (int) g.options.size());
  }
  this->geometry_drawn_ = g;
  this->drawn_seq_ = p.seq;

  Painter paint{d, t, this->title_font_, this->text_font_, g.unit_px};
  const bool urgent = p.style == PromptStyle::URGENT;
  const bool game = p.style == PromptStyle::GAME;
  const Color normal_border = t.style == ThemeStyle::OUTLINE ? t.accent : t.edge;
  const Color border = urgent ? t.color("prompts.urgent") : game ? t.color("prompts.game") : normal_border;
  paint.frame();
  paint.card(g, border, urgent || game);
  UiTree::add("dialog", p.id, g.card);
  if (g.title.h > 0)
    UiTree::add("heading", p.title_shown, g.title);
  if (g.body.h > 0)
    UiTree::add("text", p.body_shown, g.body);

  // Title.
  if (g.title.h > 0) {
    const bool header = p.layout == PromptLayout::CHOICE;
    const Color ink = urgent ? t.color("prompts.urgent") : (header ? t.muted : t.ink);
    paint.text(g.title, header ? this->text_font_ : this->title_font_, p.title_shown, ink, t.panel,
               TextAlign::TOP_CENTER);
  }

  // Body: the message, the question, or the list's note.
  switch (p.layout) {
    case PromptLayout::MESSAGE:
      paint.wrapped(g.body, this->text_font_, p.body_shown, t.ink, t.panel, true);
      break;
    case PromptLayout::CHOICE: {
      // The question in the title font when it fits, else the text font.
      const int tl = m.title_line;
      BaseFont *font =
          paint.lines(this->title_font_, p.body_shown, g.body.w) * tl <= g.body.h ? this->title_font_ : this->text_font_;
      paint.wrapped(g.body, font, p.body_shown, t.ink, t.panel, true);
      break;
    }
    case PromptLayout::LIST:
      paint.wrapped(g.body, this->text_font_, p.body_shown, t.muted, t.panel, false, 2);
      break;
  }

  // Options.
  const bool focus = this->hub_->uses_focus() && !p.answered;
  const int first = p.layout == PromptLayout::LIST ? g.first : 0;
  for (size_t r = 0; r < g.options.size(); r++) {
    const int i = first + (int) r;
    const Rect &box = g.options[r];
    const Mark mark = p.mark(i);
    if (mark == Mark::HIDDEN)
      continue;
    Color fill, edge, ink;
    paint.button_colors(mark, &fill, &edge, &ink);
    paint.box(box, fill, edge);
    const int pad = g.unit_px;
    if (p.layout == PromptLayout::CHOICE && i < 4) {
      // A to D in a round badge, then the answer.
      const int radius = std::max(6, box.h / 2 - pad);
      const int cx = box.x + pad + radius, cy = box.y + box.h / 2;
      const Color badge = mark == Mark::NONE ? t.accent : shade(fill, 0.75f);
      const Color letter_ink = ink_on(badge);
      d.filled_circle(cx, cy, radius, badge);
      const char letter[2] = {(char) ('A' + i), '\0'};
      d.print(cx, cy, this->title_font_, letter_ink, TextAlign::CENTER, letter, badge);
      const Rect label{cx + radius + pad, box.y, box.x + box.w - pad - (cx + radius + pad), box.h};
      paint.text(label, this->text_font_, p.options_shown[i], ink, fill, TextAlign::TOP_LEFT);
    } else if (p.layout == PromptLayout::LIST) {
      const Rect label{box.x + 2 * pad, box.y, box.w - 4 * pad, box.h};
      paint.text(label, this->text_font_, p.options_shown[i], ink, fill, TextAlign::TOP_LEFT);
    } else {
      const Rect label{box.x + pad, box.y, box.w - 2 * pad, box.h};
      paint.text(label, this->text_font_, p.options_shown[i], ink, fill, TextAlign::TOP_CENTER);
    }
    if (focus && i == this->focus_.index())
      ring(d, grow(box, 3), 2, t.on(t.panel, t.focus_color()));
    if (UiTree::enabled()) {
      static const char *const MARKS[] = {"", "selected", "correct", "wrong", "hidden"};
      UiTree::add("button", p.options_shown[i], box, focus && i == this->focus_.index(), MARKS[(int) mark]);
    }
  }

  // List scroll track.
  if (g.scroll.w > 0 && !p.options.empty()) {
    const int n = p.options.size();
    const int rows = std::max(1, (int) g.options.size());
    d.filled_rectangle(g.scroll.x, g.scroll.y, g.scroll.w, g.scroll.h, t.dot);
    const int thumb_h = std::max(g.scroll.w * 2, g.scroll.h * rows / n);
    const int thumb_y = g.scroll.y + (g.scroll.h - thumb_h) * g.first / std::max(1, n - rows);
    d.filled_rectangle(g.scroll.x, thumb_y, g.scroll.w, thumb_h, t.accent);
  }

  // Countdown bar: time left of the timeout.
  if (g.bar.h > 0) {
    const int32_t left = p.left_ms(esphome::millis());
    const float k = left < 0 ? 1.0f : std::min(1.0f, left / (float) std::max<uint32_t>(p.timeout_ms, 1));
    const Color c = urgent ? t.color("prompts.urgent") : t.color("prompts.countdown");
    d.filled_rectangle(g.bar.x, g.bar.y, g.bar.w, g.bar.h, shade(t.panel, 0.85f));
    d.filled_rectangle(g.bar.x, g.bar.y, (int) (g.bar.w * k), g.bar.h, c);
  }
}

}  // namespace Daruma
