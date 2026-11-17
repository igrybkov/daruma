# Prompts

> Incomplete. Moved from the old ARCHITECTURE.md. Add what you learn
> when a task needs more, and keep it under 300 lines.

How Home Assistant shows a card on the device and gets the answer. Usage for people: [prompts.md](../prompts.md).

These are "prompts": a full-screen card that HA shows, updates and closes. The
user's answer goes back to HA. One set of primitives serves a quiz game, a
doorbell and a confirmation.

## Calls from HA to the device (API actions)

| Action                          | Fields                                                               |
|---------------------------------|----------------------------------------------------------------------|
| `esphome.<device>_prompt_show`  | `id`, `layout`, `title`, `body`, `options: string[]`, `marks: string[]`, `style`, `timeout`, `state`, `sound`, `dismissable` |
| `esphome.<device>_prompt_update`| `id`, `body`, `marks: string[]` (selected, correct, wrong, hidden), `countdown` |
| `esphome.<device>_prompt_close` | `id` (`""` closes all)                                               |
| `esphome.<device>_ask`          | Same fields as show. Waits for the answer and returns it as the action's response. |

## Answers from the device to HA

The device fires the HA event `esphome.daruma_prompt` with
`{device_id, id, choice, index, reason}`. The reason is `chosen`,
`dismissed`, `timeout` or `replaced`.

## Layouts

- `message`: title, body, and 1 to 3 buttons in a row. Used for the
  doorbell: "Someone is at the door", with Unlock, Talk and Ignore.
- `choice`: a question and a 2x2 grid of answers. It has an optional
  countdown bar and an optional row of small extra buttons. This is the quiz
  layout: lifelines, then marks for the chosen, correct and wrong answers.
- `list`: a scrolling list of options, for longer menus HA wants to show.

## Priority

Prompts have a `style` of `info`, `game` or `urgent`. The order on screen is:
urgent, then game, then an open app or the menu, then info, then idle.

- A lower prompt waits behind a higher one.
- A focus session holds back `info` prompts until the break.
- The red circle dismisses a prompt unless the prompt sets
  `dismissable: false`.
- The prompt's `state` plays on the persona (default `attention`), so the
  corgi looks up when the doorbell rings.

## Details

Component `daruma_prompts`, package `prompts.yaml`. Usage and HA examples:
[docs/prompts.md](../prompts.md).

- **Every field is required.** HA registers each ESPHome action argument as
  required ([HA's esphome `manager.py`](https://github.com/home-assistant/core/blob/dev/homeassistant/components/esphome/manager.py)), and ESPHome has
  no optional arguments. So "optional" means an empty value: `""`, `[]`,
  `0` for the default timeout (60 s; 25 s for `ask`), `-1` for "keep" in
  `prompt_update`. A `timeout` of `-1` means none.
- **Validation.** `prompt_show` and `prompt_update` answer with
  `api.respond`. A bad value fails the HA action with a message that names
  the field.
- **`ask` lasts at most 25 s.** aioesphomeapi waits 30 s for an action
  response (`DEFAULT_EXECUTE_SERVICE_TIMEOUT`; HA passes no other value).
  The API server drops the call at 30 s as well
  (`USE_API_ACTION_CALL_TIMEOUT_MS`). The prompt ends itself at 25 s with
  reason `timeout`; a `wait_until` of 28 s is only a backstop. Its
  countdown is capped at 25 s, so the bar runs out with the prompt. Long
  prompts use `prompt_show` and `wait_for_trigger` on the event; both
  blueprints do, with 60 s by default. Concurrent asks work: each
  `wait_until` entry checks its own `call_id`.
- **ESPHome arrays.** A synchronous action gets `const FixedVector<T>&` and
  `StringRef` arguments. `api.respond` copies all arguments into a tuple,
  and a `FixedVector` can't be copied. So `prompt_show` and `prompt_update`
  hold a `delay: 0ms`, which switches the arguments to the owning
  `std::vector` and `std::string`.
- **The event.** `id`, `choice` and `reason` go in `data:` and stay strings.
  `index` goes through `data_template`, so HA makes it a number. A device
  may fire `esphome.*` events without the "perform actions" permission
  (`async_on_service_call` checks it only for actions). Every answer fires
  the event, `ask` answers too. `prompt_close` fires none; a waiting `ask`
  returns reason `closed`.
- **`marks` on show and ask too.** The quiz re-asks after 50:50 with two
  answers hidden.
- **Dismissing by touch.** A tap outside the card, or the red circle,
  dismisses at once. A tap on the card that misses the buttons does
  nothing. An info message with at most one button goes with any tap.
  `dismissable: false` ignores all of these. The rules are a plain
  function, `tap_result()` in `prompt_layout.h`, host-tested. Don't add a
  "Dismiss?" confirmation: one tap is enough.
- **Sounds.** A prompt plays `notify` (info, game) or `urgent` (urgent)
  when it first shows, unless it names a `sound`; `none` is silent. An
  urgent prompt repeats its sound every 15 s while it is on top and
  unanswered, 3 plays in all. The controller plays them through
  `Device::play_sound()`, which is core's `play_sound` script: the Sounds
  switch, a ringing timer, the assistant and HA announcements all stop it.
  HA's `show_message` action chimes `notify` for a new message too; the
  bubble's own uses (reactions' words, pomodoro) do not.
- **A choice stays after its answer.** It shows the answer as `selected`
  and waits, locked, for HA to mark, replace or close it. A message or a
  list closes on its answer.
- **Timeouts** start when the prompt first comes on screen, so an info
  prompt held back by focus does not expire unseen. A hidden ask still has
  its 25 s.
- **Screens and input.** Urgent and game prompts are a screen over the menu
  (priority 200 against 100) with an input handler over it (80 against 50).
  Info prompts sit under the menu (10 and 40), so an open menu covers them.
  `Input::DISMISS` (wake word, timer, app switched off) leaves prompts
  alone.
- **Core hooks:** `Device::set_prompt_open()`, so the menu closing under a
  prompt does not clear its input routing (`ui_open()` covers both), and
  `Device::holds_activity()` for the focus check (focus held anywhere in the
  stack, since the prompt's own activity goes on top).
- **Geometry** lives in `prompt_layout.h`, plain C++ on the hub's Layout.
  The card is `layout.content.inset(px(8))`. When its text and buttons need
  more height, it grows evenly, at most to `px(6)` from the screen's top
  and bottom; a full quiz card on 320x240 does. The controller wraps the
  body at the card's inner width first, so the card knows its lines.
  Choice answers are `grid.cell(i, 2, rows, gap)`. Host previews draw from
  the same rectangles (`tests/prompt_preview.py`, 320x240 and 480x272).
- **Focus and pace.** On boards with NEXT and PREV (`uses_focus()`), a
  `FocusRing` moves over the options, skipping hidden ones, and is drawn in
  `theme.on(panel, theme.focus_color())`. Touch boards draw no ring. On a
  slow profile the countdown redraws once a minute. All redraws go
  through `request_redraw()`.
- A stack holds at most 8 prompts; over that, the lowest and oldest goes
  with reason `replaced`.
- Not checked yet on the device: the event without the permission, and
  touch sizes.

## Example flows

- **Quiz** (`blueprints/script/quiz.yaml`). An HA script loops over
  questions. For each one, it calls `ask` with the question, four answers
  and 50:50. It then calls `prompt_update` to mark the answer right or
  wrong, waits, and moves on. After 50:50 it asks again with two wrong
  answers and the button hidden by `marks`.
- **Doorbell** (`blueprints/automation/doorbell_prompt.yaml`). An
  automation on the doorbell calls `prompt_show` with `style: urgent`. A
  second trigger on `esphome.daruma_prompt` unlocks the door or starts
  the talk-back.
