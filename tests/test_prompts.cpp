// Host test of the prompt stack (daruma_prompts/prompt_stack.h): priority,
// focus hold-back, replace, timeouts, answers and asks. Also the card
// geometry and what a tap does (prompt_layout.h).
//
//   uv run pytest tests/test_prompts.cpp   (pytest builds and runs it: tests/conftest.py)

#define DARUMA_STATE_LIST \
  X(NEUTRAL, "neutral", MOOD, -1, 0, false) \
  X(ATTENTION, "attention", ACTIVITY, 0, 0, false) \
  X(ALARM, "alarm", ACTIVITY, 0, 0, false)

#include <algorithm>
#include <cstdio>
#include <string>
#include <vector>

#include "esphome/components/daruma_prompts/prompt_layout.h"
#include "esphome/components/daruma_prompts/prompt_stack.h"

using namespace Daruma;

static int failures = 0;

#define CHECK(cond) \
  do { \
    if (!(cond)) { \
      std::printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond); \
      failures++; \
    } \
  } while (0)

static Prompt make(const std::string &id, PromptStyle style, std::vector<std::string> options = {"Yes", "No"},
                   PromptLayout layout = PromptLayout::MESSAGE, uint32_t timeout_ms = 0, uint32_t ask = 0) {
  Prompt p;
  p.id = id;
  p.style = style;
  p.layout = layout;
  p.options = std::move(options);
  p.timeout_ms = timeout_ms;
  p.ask = ask;
  return p;
}

static std::string top_id(PromptStack &s, bool hold = false) {
  Prompt *p = s.top(hold);
  return p == nullptr ? "" : p->id;
}

static void higher_style_wins_and_lower_comes_back() {
  PromptStack s;
  s.show(make("news", PromptStyle::INFO), 0);
  s.show(make("quiz", PromptStyle::GAME), 10);
  CHECK(top_id(s) == "quiz");
  s.show(make("door", PromptStyle::URGENT), 20);
  CHECK(top_id(s) == "door");
  // A newer game prompt still waits behind the urgent one.
  s.show(make("quiz2", PromptStyle::GAME), 30);
  CHECK(top_id(s) == "door");
  CHECK(s.dismiss(s.top(false)));
  CHECK(top_id(s) == "quiz2");
  CHECK(s.close("quiz2"));
  CHECK(top_id(s) == "quiz");
  CHECK(s.close("quiz"));
  CHECK(top_id(s) == "news");
  // Among equals, the newest is on top.
  s.show(make("news2", PromptStyle::INFO), 40);
  CHECK(top_id(s) == "news2");
}

static void focus_holds_back_info_only() {
  PromptStack s;
  s.show(make("news", PromptStyle::INFO), 0);
  CHECK(top_id(s, true).empty());
  CHECK(top_id(s, false) == "news");
  s.show(make("quiz", PromptStyle::GAME), 10);
  CHECK(top_id(s, true) == "quiz");
  s.close("quiz");
  CHECK(top_id(s, true).empty());
  // The held prompt's timeout has not started: it never was on screen.
  s.find("news")->timeout_ms = 1000;
  CHECK(!s.tick(100000));
  CHECK(s.find("news") != nullptr);
}

static void same_id_replaces() {
  PromptStack s;
  s.show(make("door", PromptStyle::URGENT), 0);
  s.show(make("other", PromptStyle::URGENT), 5);
  s.show(make("door", PromptStyle::URGENT, {"Unlock"}), 10);
  CHECK(s.size() == 2);
  CHECK(top_id(s) == "door");  // Replaced, and now the newest.
  CHECK(s.find("door")->options.size() == 1);
  auto answers = s.take_answers();
  CHECK(answers.size() == 1);
  CHECK(answers[0].id == "door" && answers[0].reason == Reason::REPLACED && answers[0].index == -1);
}

static void timeout_starts_on_screen() {
  PromptStack s;
  s.show(make("door", PromptStyle::URGENT, {"Ok"}, PromptLayout::MESSAGE, 5000), 0);
  CHECK(!s.tick(10000));  // Not on screen yet.
  CHECK(s.on_screen(s.top(false), 10000));
  CHECK(!s.on_screen(s.top(false), 10500));  // Only the first time counts.
  CHECK(s.top(false)->left_ms(12000) == 3000);
  CHECK(!s.tick(14999));
  CHECK(s.tick(15000));
  CHECK(s.empty());
  auto answers = s.take_answers();
  CHECK(answers.size() == 1 && answers[0].reason == Reason::TIMEOUT);
}

static void countdown_update() {
  PromptStack s;
  s.show(make("q", PromptStyle::GAME, {"A", "B", "C", "D"}, PromptLayout::CHOICE, 20000), 0);
  s.on_screen(s.top(false), 0);
  CHECK(s.update("q", nullptr, nullptr, 5, 1000));
  CHECK(s.top(false)->left_ms(1000) == 5000);
  CHECK(s.update("q", nullptr, nullptr, 0, 2000));  // Stop it.
  CHECK(s.top(false)->left_ms(2000) == -1);
  CHECK(!s.tick(100000));
  CHECK(!s.update("missing", nullptr, nullptr, -1, 0));
}

static void choosing() {
  PromptStack s;
  // A message closes on its answer.
  s.show(make("door", PromptStyle::URGENT, {"Unlock", "Talk", "Ignore"}), 0);
  CHECK(s.choose(s.top(false), 1));
  CHECK(s.empty());
  auto answers = s.take_answers();
  CHECK(answers.size() == 1 && answers[0].choice == "Talk" && answers[0].index == 1 &&
        answers[0].reason == Reason::CHOSEN);

  // A choice stays, locked, with the answer selected.
  s.show(make("q", PromptStyle::GAME, {"A", "B", "C", "D", "50:50"}, PromptLayout::CHOICE, 20000), 0);
  s.on_screen(s.top(false), 0);
  CHECK(s.choose(s.top(false), 2));
  Prompt *q = s.top(false);
  CHECK(q != nullptr && q->answered && q->mark(2) == Mark::SELECTED);
  CHECK(!s.choose(q, 3));  // Locked.
  CHECK(!s.tick(100000));  // Its timeout stopped.
  // HA marks it, then replaces it: no second answer for the old one.
  std::vector<Mark> marks = {Mark::NONE, Mark::NONE, Mark::WRONG, Mark::CORRECT};
  CHECK(s.update("q", nullptr, &marks, -1, 0));
  CHECK(q->mark(3) == Mark::CORRECT && q->mark(4) == Mark::NONE);
  s.show(make("q", PromptStyle::GAME, {"A", "B", "C", "D"}, PromptLayout::CHOICE), 0);
  answers = s.take_answers();
  CHECK(answers.size() == 1 && answers[0].index == 2);
  // Hidden answers can't be chosen.
  marks = {Mark::HIDDEN};
  s.update("q", nullptr, &marks, -1, 0);
  CHECK(!s.choose(s.top(false), 0));
  CHECK(!s.choose(s.top(false), 9));
}

static void dismissing() {
  PromptStack s;
  Prompt locked = make("door", PromptStyle::URGENT);
  locked.dismissable = false;
  s.show(locked, 0);
  CHECK(!s.dismiss(s.top(false)));
  CHECK(top_id(s) == "door");
  s.show(make("news", PromptStyle::URGENT), 0);
  CHECK(s.dismiss(s.top(false)));
  auto answers = s.take_answers();
  CHECK(answers.size() == 1 && answers[0].id == "news" && answers[0].reason == Reason::DISMISSED);
}

static void asks() {
  PromptStack s;
  // A hard deadline from the ask, even while waiting off screen.
  s.show(make("door", PromptStyle::URGENT), 0);
  s.show(make("q", PromptStyle::INFO, {"A", "B"}, PromptLayout::MESSAGE, 0, 7), 1000);
  CHECK(!s.tick(1000 + PromptStack::ASK_LIMIT_MS - 1));
  CHECK(s.tick(1000 + PromptStack::ASK_LIMIT_MS));
  auto answers = s.take_answers();
  CHECK(answers.size() == 1 && answers[0].ask == 7 && answers[0].reason == Reason::TIMEOUT);

  // Closed by HA: no answer for a plain prompt, CLOSED for an ask.
  s.show(make("q", PromptStyle::GAME, {"A", "B"}, PromptLayout::MESSAGE, 0, 8), 0);
  CHECK(s.close(""));
  answers = s.take_answers();
  CHECK(answers.size() == 1 && answers[0].ask == 8 && answers[0].reason == Reason::CLOSED);
  CHECK(!s.close("door"));

  // Replaced by a new ask with the same id: the old ask ends as REPLACED.
  s.show(make("q", PromptStyle::GAME, {"A", "B"}, PromptLayout::MESSAGE, 0, 9), 0);
  s.show(make("q", PromptStyle::GAME, {"A", "B"}, PromptLayout::MESSAGE, 0, 10), 0);
  answers = s.take_answers();
  CHECK(answers.size() == 1 && answers[0].ask == 9 && answers[0].reason == Reason::REPLACED);

  // The caller gave up.
  CHECK(s.expire_ask(10));
  CHECK(!s.expire_ask(10));
  answers = s.take_answers();
  CHECK(answers.size() == 1 && answers[0].ask == 10 && answers[0].reason == Reason::TIMEOUT);
}

static void capped() {
  PromptStack s;
  for (int i = 0; i < 10; i++)
    s.show(make("p" + std::to_string(i), i == 0 ? PromptStyle::URGENT : PromptStyle::INFO), i);
  CHECK(s.size() == PromptStack::MAX_PROMPTS);
  CHECK(s.find("p0") != nullptr);                             // The urgent one stays.
  CHECK(s.find("p1") == nullptr && s.find("p2") == nullptr);  // The oldest info ones went.
  auto answers = s.take_answers();
  CHECK(answers.size() == 2 && answers[0].reason == Reason::REPLACED);
}

// Needs no answer: an info message with at most one button.
static void quiet_prompts() {
  CHECK(make("a", PromptStyle::INFO, {}).quiet());
  CHECK(make("a", PromptStyle::INFO, {"OK"}).quiet());
  CHECK(!make("a", PromptStyle::INFO, {"Yes", "No"}).quiet());
  CHECK(!make("a", PromptStyle::URGENT, {}).quiet());
  CHECK(!make("a", PromptStyle::INFO, {"A", "B"}, PromptLayout::CHOICE).quiet());
  CHECK(!make("a", PromptStyle::INFO, {"A"}, PromptLayout::LIST).quiet());
}

static void parsing() {
  PromptLayout l;
  PromptStyle st;
  Mark m;
  CHECK(parse_layout("", &l) && l == PromptLayout::MESSAGE);
  CHECK(parse_layout("choice", &l) && l == PromptLayout::CHOICE);
  CHECK(!parse_layout("grid", &l));
  CHECK(parse_style("", &st) && st == PromptStyle::INFO);
  CHECK(parse_style("urgent", &st) && st == PromptStyle::URGENT);
  CHECK(!parse_style("loud", &st));
  CHECK(parse_mark("", &m) && m == Mark::NONE);
  CHECK(parse_mark("hidden", &m) && m == Mark::HIDDEN);
  CHECK(!parse_mark("right", &m));
}

static void default_timeouts() {
  CHECK(timeout_ms(0, false) == 60000);  // 0: the default.
  CHECK(timeout_ms(-1, false) == 0);     // -1: none.
  CHECK(timeout_ms(30, false) == 30000);
  // An ask ends within 25 s, so its countdown does too.
  CHECK(timeout_ms(0, true) == 25000);
  CHECK(timeout_ms(-1, true) == 25000);
  CHECK(timeout_ms(10, true) == 10000);
  CHECK(timeout_ms(90, true) == 25000);
}

static bool inside(const Rect &outer, const Rect &inner) {
  return inner.x >= outer.x && inner.y >= outer.y && inner.right() <= outer.right() && inner.bottom() <= outer.bottom();
}

static void geometry_fits() {
  const PromptMetrics m{27, 23};
  const int sizes[][2] = {{320, 240}, {480, 272}, {240, 240}};
  for (const auto &size : sizes) {
    const Layout l = Layout::compute(size[0], size[1]);
    // A short message keeps the base card, with room around it to tap.
    const PromptGeometry small = prompt_layout::message(l, m, 1, 1, false, true, true);
    CHECK(small.card == l.content.inset(l.px(8)));
    // The quiz's worst case: a title, a 3-line question, four answers, an
    // extra button and a countdown. It grows but stays on screen.
    for (bool urgent : {false, true}) {
      const PromptGeometry g = prompt_layout::choice(l, m, 5, 3, urgent, true, true);
      CHECK(inside(l.screen, g.card));
      CHECK(g.card.h > small.card.h);
      CHECK(g.body.h >= m.text_line);
      CHECK(g.options.size() == 5);
      for (const Rect &r : g.options)
        CHECK(inside(g.card, r) && !r.intersected(g.body).w && !r.intersected(g.bar).w);
      CHECK(inside(g.card, g.bar) && inside(g.card, g.title));
    }
    const PromptGeometry list = prompt_layout::list(l, m, 12, 9, 0, 2, false, true, true);
    CHECK(inside(l.screen, list.card) && list.scroll.w > 0);
    CHECK(list.first + (int) list.options.size() > 9);  // The focused row is in view.
  }
}

static void taps() {
  const Layout l = Layout::compute(320, 240);
  const PromptMetrics m{27, 23};
  Prompt quiz = make("q", PromptStyle::GAME, {"A", "B", "C", "D"}, PromptLayout::CHOICE);
  const PromptGeometry g = prompt_layout::choice(l, m, 4, 1, false, true, true);
  const Rect b = g.options[1];
  Tap t = tap_result(quiz, g, b.cx(), b.cy());
  CHECK(t.action == TapAction::CHOOSE && t.index == 1);
  t = tap_result(quiz, g, g.body.cx(), g.body.cy());  // On the card, not a button.
  CHECK(t.action == TapAction::NOTHING);
  t = tap_result(quiz, g, 2, 2);  // Outside the card.
  CHECK(t.action == TapAction::DISMISS);
  quiz.marks = {Mark::NONE, Mark::HIDDEN, Mark::NONE, Mark::NONE};
  CHECK(tap_result(quiz, g, b.cx(), b.cy()).action == TapAction::NOTHING);  // Hidden.
  quiz.dismissable = false;
  CHECK(tap_result(quiz, g, 2, 2).action == TapAction::NOTHING);
  // Answered, it waits for HA: it may go even when not dismissable, and
  // its answers no longer count.
  quiz.answered = true;
  CHECK(tap_result(quiz, g, 2, 2).action == TapAction::DISMISS);
  CHECK(tap_result(quiz, g, g.options[0].cx(), g.options[0].cy()).action == TapAction::NOTHING);

  // An info message with one button goes with any tap, the button included.
  Prompt note = make("n", PromptStyle::INFO, {"OK"});
  const PromptGeometry ng = prompt_layout::message(l, m, 1, 2, false, true, true);
  CHECK(tap_result(note, ng, ng.options[0].cx(), ng.options[0].cy()).action == TapAction::DISMISS);
  CHECK(tap_result(note, ng, ng.body.cx(), ng.body.cy()).action == TapAction::DISMISS);
  note.dismissable = false;  // Then only its button counts.
  t = tap_result(note, ng, ng.options[0].cx(), ng.options[0].cy());
  CHECK(t.action == TapAction::CHOOSE && t.index == 0);
  CHECK(tap_result(note, ng, 2, 2).action == TapAction::NOTHING);

  // An urgent message with buttons: outside dismisses, the card does not.
  Prompt bell = make("d", PromptStyle::URGENT, {"Unlock", "Talk", "Ignore"});
  const PromptGeometry bg = prompt_layout::message(l, m, 3, 0, true, true, true);
  CHECK(tap_result(bell, bg, bg.body.cx(), bg.body.cy()).action == TapAction::NOTHING);
  CHECK(tap_result(bell, bg, l.width - 2, l.height / 2).action == TapAction::DISMISS);
}

// A touch as the screen reports it: down at `from`, samples every 16 ms
// along the way, lift-off at `to`.
static Gesture drag(TouchTracker &tr, uint32_t at, int x, int y0, int y1, uint32_t ms) {
  tr.start(at, x, y0);
  const int steps = std::max<int>(1, ms / 16);
  for (int i = 1; i <= steps; i++)
    tr.move(x, y0 + (y1 - y0) * i / steps);
  return tr.end(at + ms);
}

// The bug on the device: in a 10-option list, the owner swiped up to page
// and then flicked again. The screen saw the second flick come down and lift
// off with no sample in between (the loop was busy drawing the new page), so
// it looked like a tap and chose the option under it.
static void list_scrolling_never_chooses() {
  const Layout l = Layout::compute(320, 240);
  const PromptMetrics m{27, 23};
  std::vector<std::string> snacks = {"Apples", "Bagels", "Chips",   "Dates",  "Eclairs",
                                     "Fudge",  "Grapes", "Popcorn", "Quiche", "Raisins"};
  Prompt p = make("snack", PromptStyle::INFO, snacks, PromptLayout::LIST);
  PromptGeometry g = prompt_layout::list(l, m, 10, -1, 0, 0, false, true, false);
  CHECK(g.scroll.w > 0 && g.first == 0);
  const int x = g.options[0].cx();
  ListScroll scroll;
  TouchTracker tr;

  // Swipe up: it pages to the second half.
  CHECK(drag(tr, 1000, x, 190, 90, 200) == Gesture::SWIPE_UP);
  scroll = ListScroll{true, 1200};
  g = prompt_layout::list(l, m, 10, -1, g.first + (int) g.options.size(), 0, false, true, false);
  CHECK(g.first == 5);
  const Rect popcorn = g.options[7 - g.first];

  // The next flick, seen only at touch-down and lift-off: no choice.
  tr.start(1350, x, popcorn.cy());
  CHECK(tr.end(1420) == Gesture::NONE && !tr.moved());
  CHECK(tap_result(p, g, tr.track(), scroll).action == TapAction::NOTHING);

  // A short drag inside the hub's slop, well after the page: no choice.
  CHECK(drag(tr, 5000, x, popcorn.cy() - 6, popcorn.cy() + 9, 150) == Gesture::NONE && !tr.moved());
  CHECK(tap_result(p, g, tr.track(), scroll).action == TapAction::NOTHING);

  // Lifted in the next row: no choice.
  tr.start(8000, x, popcorn.bottom() - 2);
  tr.move(x, popcorn.bottom() + 6);
  tr.end(8080);
  CHECK(tap_result(p, g, tr.track(), scroll).action == TapAction::NOTHING);

  // The list paged while the finger was down: no choice.
  tr.start(9000, x, popcorn.cy());
  tr.end(9080);
  CHECK(tap_result(p, g, tr.track(), ListScroll{true, 9040}).action == TapAction::NOTHING);

  // A tap that came down soon after any drag (a swipe that did not page):
  // no choice.
  CHECK(drag(tr, 11000, x, 60, 100, 300) == Gesture::NONE && tr.moved());  // Short, slow: no swipe.
  tr.start(11400, x, popcorn.cy());
  tr.end(11480);
  CHECK(tap_result(p, g, tr.track(), scroll).action == TapAction::NOTHING);

  // A still tap, a moment after the scroll and the last drag: Popcorn.
  tr.start(13000, x, popcorn.cy());
  tr.move(x + 2, popcorn.cy() + 2);  // The screen's jitter.
  tr.end(13080);
  Tap t = tap_result(p, g, tr.track(), scroll);
  CHECK(t.action == TapAction::CHOOSE && t.index == 7);
  // A tap outside the card still dismisses.
  tr.start(15000, 2, 2);
  tr.end(15080);
  CHECK(tap_result(p, g, tr.track(), scroll).action == TapAction::DISMISS);
}

// A list that fits and the other layouts keep plain taps, even right after
// a drag and with a little movement inside the hub's slop.
static void short_lists_and_cards_tap_as_before() {
  const Layout l = Layout::compute(320, 240);
  const PromptMetrics m{27, 23};
  TouchTracker tr;
  const ListScroll none;
  CHECK(drag(tr, 0, 160, 60, 160, 200) == Gesture::SWIPE_DOWN);

  Prompt menu = make("m", PromptStyle::INFO, {"Tea", "Coffee", "Water"}, PromptLayout::LIST);
  const PromptGeometry lg = prompt_layout::list(l, m, 3, -1, 0, 0, false, true, false);
  CHECK(lg.scroll.w == 0);
  const Rect r = lg.options[1];
  CHECK(drag(tr, 250, r.cx(), r.cy() - 7, r.cy() + 7, 100) == Gesture::NONE && !tr.moved());
  Tap t = tap_result(menu, lg, tr.track(), none);
  CHECK(t.action == TapAction::CHOOSE && t.index == 1);

  Prompt quiz = make("q", PromptStyle::GAME, {"A", "B", "C", "D"}, PromptLayout::CHOICE);
  const PromptGeometry cg = prompt_layout::choice(l, m, 4, 1, false, true, true);
  const Rect b = cg.options[2];
  CHECK(drag(tr, 500, b.cx(), b.cy() - 5, b.cy() + 5, 100) == Gesture::NONE);
  t = tap_result(quiz, cg, tr.track(), none);
  CHECK(t.action == TapAction::CHOOSE && t.index == 2);

  Prompt bell = make("d", PromptStyle::URGENT, {"Unlock", "Talk", "Ignore"});
  const PromptGeometry bg = prompt_layout::message(l, m, 3, 0, true, true, true);
  tr.start(700, bg.options[0].cx(), bg.options[0].cy());
  tr.end(780);
  t = tap_result(bell, bg, tr.track(), none);
  CHECK(t.action == TapAction::CHOOSE && t.index == 0);
}

int main() {
  higher_style_wins_and_lower_comes_back();
  focus_holds_back_info_only();
  same_id_replaces();
  timeout_starts_on_screen();
  countdown_update();
  choosing();
  dismissing();
  asks();
  capped();
  quiet_prompts();
  parsing();
  default_timeouts();
  geometry_fits();
  taps();
  list_scrolling_never_chooses();
  short_lists_and_cards_tap_as_before();
  if (failures == 0)
    std::printf("All prompt stack tests passed\n");
  return failures == 0 ? 0 : 1;
}
