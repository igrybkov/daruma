# Prompts

A prompt is a card that Home Assistant puts on the device's screen. HA can
change it and close it. When someone taps an answer, the answer goes back to
HA. One set of actions covers a doorbell, a quiz and a yes/no question.

Include `packages/prompts.yaml` in the device yaml. It works with or
without the menu.

## Try it first

Import the [prompt demos blueprint](../blueprints/script/prompt_demos.yaml),
make a script from it, and run it. It shows each kind of card: a yes/no
question with `ask`, an urgent alert, a card that stays, a list that
scrolls, and two urgent alerts stacked. After each answer the device shows
what it sent to Home Assistant, and the script's trace has every answer
event in full. The rest of this page explains what you just saw.

| Blueprint | What it does | Import |
|---|---|---|
| [Prompt demos](../blueprints/script/prompt_demos.yaml) (script) | Try every kind of card in two minutes: a yes/no question, an urgent alert, a card that stays, a scrolling list, two stacked alerts. The device shows the answer it sent back. | <a href="https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fraw.githubusercontent.com%2Figrybkov%2Fdaruma%2Fmain%2Fblueprints%2Fscript%2Fprompt_demos.yaml"><img src="https://my.home-assistant.io/badges/blueprint_import.svg" alt="Import blueprint" width="296"></a> |
| [Doorbell prompt](../blueprints/automation/doorbell_prompt.yaml) (automation) | When the doorbell rings, an urgent card offers Unlock, Talk and Ignore. | <a href="https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fraw.githubusercontent.com%2Figrybkov%2Fdaruma%2Fmain%2Fblueprints%2Fautomation%2Fdoorbell_prompt.yaml"><img src="https://my.home-assistant.io/badges/blueprint_import.svg" alt="Import blueprint" width="296"></a> |
| [Quiz](../blueprints/script/quiz.yaml) (script) | A quiz from your list of questions, with a score and a 50:50 button. | <a href="https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fraw.githubusercontent.com%2Figrybkov%2Fdaruma%2Fmain%2Fblueprints%2Fscript%2Fquiz.yaml"><img src="https://my.home-assistant.io/badges/blueprint_import.svg" alt="Import blueprint" width="296"></a> |
| [Task list from a sensor](../blueprints/script/task_list.yaml) (script) | Turns a list of tasks in a sensor attribute into a source for the Tasks app. | <a href="https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fraw.githubusercontent.com%2Figrybkov%2Fdaruma%2Fmain%2Fblueprints%2Fscript%2Ftask_list.yaml"><img src="https://my.home-assistant.io/badges/blueprint_import.svg" alt="Import blueprint" width="296"></a> |
| [Focus scores a Habitica habit](../blueprints/automation/habitica_focus_habit.yaml) (automation) | Each finished focus block scores a Habitica habit. Setup: [habitica.md](habitica.md). | <a href="https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fraw.githubusercontent.com%2Figrybkov%2Fdaruma%2Fmain%2Fblueprints%2Fautomation%2Fhabitica_focus_habit.yaml"><img src="https://my.home-assistant.io/badges/blueprint_import.svg" alt="Import blueprint" width="296"></a> |

Each blueprint asks for the device's node name (default `daruma`, as in
examples/box3.yaml), since the action names come from it.

## Actions

Each action is `esphome.<node>_<action>`, where `<node>` is the ESPHome node
name with `-` changed to `_`, such as `esphome.daruma_prompt_show`.

HA makes every field of an ESPHome action required. So every call passes
every field. An empty value means "use the default".

| Field         | Type     | Values                                    | Empty means      |
|---------------|----------|-------------------------------------------|------------------|
| `id`          | string   | your name for the prompt, 1-64 characters | (required)       |
| `layout`      | string   | `message`, `choice`, `list`               | `message`        |
| `title`       | string   | one line                                  | no title         |
| `body`        | string   | wrapped text                              | no body          |
| `options`     | string[] | message 0-3, choice 2-7, list 1-20        | no buttons       |
| `marks`       | string[] | one per option: `""`, `selected`, `correct`, `wrong`, `hidden` | no marks |
| `style`       | string   | `info`, `game`, `urgent`                  | `info`           |
| `timeout`     | int      | seconds, or `-1` for none                 | `0`: 60 s (`ask`: 25 s) |
| `state`       | string   | an activity the persona plays, such as `attention` | `attention` |
| `sound`       | string   | a sound name, or `none`                   | `notify`; `urgent` for urgent prompts |
| `dismissable` | bool     | can a tap outside or the red circle dismiss it? | (required) |

- `prompt_show`: all the fields above. Shows the prompt, or replaces the one
  with the same `id`.
- `prompt_update`: `id`, `body` (`""` keeps it), `marks` (`[]` keeps them)
  and `countdown` (seconds left; `0` stops it, `-1` keeps it). Note the
  difference: in `prompt_show`, `0` is the default and `-1` is none; in
  `prompt_update`, `0` stops the countdown and `-1` leaves it.
- `prompt_close`: `id`. `""` closes every prompt. This sends no event.
- `ask`: the same fields as `prompt_show`. It waits for the answer and
  returns `{id, choice, index, reason}`.

A wrong value makes the HA action fail with a message that names the field.
For example: `marks[2]: 'right' is not one of '', selected, correct, wrong,
hidden`.

### `ask` or show and wait

HA stops waiting for an ESPHome action's response after 30 s
(aioesphomeapi's `DEFAULT_EXECUTE_SERVICE_TIMEOUT`). The device's API server
drops the call at 30 s too. So `ask` always answers within 25 s. When nobody
answers in that time, it closes the prompt and returns reason `timeout`. Its
countdown is 25 s by default, and a longer `timeout` is cut to 25 s.

- Use `ask` for quick questions, answered in under about 25 s.
- For anything longer, call `prompt_show`, then `wait_for_trigger` on the
  `esphome.daruma_prompt` event with your prompt's `id`. Give the wait
  a few seconds more than the prompt's `timeout`, so the device's own
  `timeout` answer arrives first. Both blueprints work this way, with 60 s
  by default:

```yaml
- action: esphome.daruma_prompt_show
  data:
    id: lights_off
    layout: message
    title: Lights still on downstairs
    body: Turn them off?
    options: ["Yes", "No"]
    marks: []
    style: info
    timeout: 60
    state: ""
    sound: ""
    dismissable: true
- wait_for_trigger:
    - trigger: event
      event_type: esphome.daruma_prompt
      event_data:
        id: lights_off
  timeout: 65
  continue_on_timeout: true
- if: "{{ wait.trigger and wait.trigger.event.data.reason == 'chosen' and wait.trigger.event.data.index == 0 }}"
  then:
    - action: light.turn_off
      target:
        area_id: living_room
```

Reasons that `ask` can return:

- `chosen`, `dismissed`, `timeout` or `replaced`;
- `closed`: HA closed the prompt with `prompt_close`.

## The answer event

Every answer also fires the HA event `esphome.daruma_prompt`, `ask`
answers included:

```yaml
event_type: esphome.daruma_prompt
data:
  device_id: 4f1c...   # added by HA
  id: doorbell
  choice: Unlock       # the option text; "" when nothing was chosen
  index: 0             # from 0; -1 when nothing was chosen
  reason: chosen       # chosen, dismissed, timeout or replaced
```

A device may fire `esphome.*` events without "Allow the device to perform
Home Assistant actions".

## What shows when

- **Priority:** urgent, then game, then an open menu or app, then info.
  A lower prompt waits behind a higher one and comes back when it closes.
  Among prompts of the same style, the newest is on top.
- **Focus:** info prompts wait while a focus session runs. This is the
  `hold_back_during` option, `[focus]` by default.
- **Do not disturb:** info prompts wait while it is on (see
  [customize.md: Quiet hours](customize.md#quiet-hours-and-do-not-disturb)).
  Urgent and game prompts still show.
- **After a wait:** when focus or Do not disturb ends, the info prompts
  that waited show one by one, oldest first. At most 5 stay, the newest;
  the older ones end with reason `replaced`. One that waited over 12 hours
  ends with reason `timeout`. The quiet module's `dnd_release` and
  `dnd_keep` change these.
- **Same id:** the new prompt replaces the old one. If the old one still
  waited for an answer, it ends with reason `replaced`.
- **Timeout:** 60 s unless the call gives another, `-1` for none. It starts
  when the prompt first comes on screen. The countdown bar shows the time
  left; on a slow screen (e-ink) it moves once a minute.
- **Answers:** a `message` or `list` closes when an option is chosen. A
  `choice` stays on screen with the answer marked `selected`. It waits for
  HA to mark it, replace it or close it, and the red circle can still close
  it.
- **Dismiss by touch.** All of these end the prompt at once with reason
  `dismissed`. There is no "are you sure" step.
  - A tap outside the card dismisses it.
  - The red circle dismisses it.
  - A tap on the card that misses every button does nothing.
  - An `info` `message` with no button or one OK-style button needs no
    answer: any tap anywhere dismisses it, the button included.
  - With `dismissable: false`, none of these work. Only the buttons do.
  - The action `prompts.dismiss` dismisses at once, for a binding.
  - The card grows to fit long text. On a 320x240 screen a full quiz card
    leaves only thin strips at the sides; the red circle always works.
- **The persona:** while a prompt is on top, the persona plays its
  `state` (activity owner `prompts`). An urgent prompt also turns on the
  screen light.
- **Sound:** the first time a prompt comes on screen, it plays its `sound`.
  By default that is `notify`, a soft two-note chime, for info and game
  prompts, and `urgent`, a bright repeated pair, for urgent ones. An urgent
  prompt plays it again every 15 s while nobody answers, 3 times in all.
  `sound: none` is silent. The Sounds switch (and the call-mute automation
  that turns it off) silences all of them. When Do not disturb turned
  Sounds off, urgent prompts still sound. A persona can replace
  `notify` and `urgent` through its `sounds:`.
- **Voice:** prompts draw only while the device is idle. A voice reply, an
  announcement or a ringing timer covers them. The wake word does not
  dismiss them.
- **Without touch:** NEXT and PREV move a focus ring over the options, and
  SELECT chooses. The ring shows only on boards that navigate by buttons.
- **Text:** Ukrainian works. Glyphs the font lacks, such as emoji, are
  dropped.

The look follows the current persona's theme. A persona can set these
theme colors: `prompts.urgent`, `prompts.game`, `prompts.countdown`,
`prompts.selected`, `prompts.correct` and `prompts.wrong`.

## Layouts

- `message`: a title, the body, and 1-3 buttons in a row.
- `choice`: the title as a small header line, the body as the question, and
  up to 4 answers in a 2x2 grid with A-D badges. Options 5 to 7 become small
  buttons under the grid, for lifelines such as 50:50.
- `list`: a title, up to two lines of body, and options that scroll. Swipe
  up or down to page. For about a third of a second after a swipe or a
  page change, a tap does not count, so scrolling never picks an option.

## Examples

A quick yes/no question in one step:

```yaml
- action: esphome.daruma_ask
  data:
    id: lights_off
    layout: message
    title: Lights still on downstairs
    body: Turn them off?
    options: ["Yes", "No"]
    marks: []
    style: info
    timeout: 20
    state: ""
    sound: ""
    dismissable: true
  response_variable: answer
- if: "{{ answer.reason == 'chosen' and answer.index == 0 }}"
  then:
    - action: light.turn_off
      target:
        area_id: living_room
```

A prompt that stays, with an automation for the answer:

```yaml
# Show it
- action: esphome.daruma_prompt_show
  data:
    id: laundry
    layout: message
    title: Laundry is done
    body: Hang the shirts before they wrinkle.
    options: [OK, Remind me later]
    marks: []
    style: info
    timeout: -1
    state: ""
    sound: ""
    dismissable: true

# React to it, in another automation
triggers:
  - trigger: event
    event_type: esphome.daruma_prompt
    event_data:
      id: laundry
      reason: chosen
      index: 1
actions:
  - delay: "00:30:00"
  - action: script.laundry_reminder
```

Marking a quiz answer:

```yaml
- action: esphome.daruma_prompt_update
  data:
    id: quiz
    body: "Right!"
    marks: [correct, "", wrong, ""]
    countdown: -1
```

## Blueprints

The blueprints are listed with import buttons under
[Try it first](#try-it-first).

- `blueprints/script/prompt_demos.yaml`: every kind of card, one after
  another or one at a time, with the answer shown back on the device.
  The yes/no demo uses `ask`; the others use `prompt_show` and wait for
  the answer event, 10 minutes by default.
- `blueprints/automation/doorbell_prompt.yaml`: when the doorbell
  rings, an urgent card offers Unlock, Talk and Ignore. Unlock opens the
  lock; Talk runs an action you choose. The card waits 60 s by default.
- `blueprints/script/quiz.yaml`: a quiz from a list of questions,
  with a score and a 50:50 button. Each question waits 60 s by default.
- `blueprints/script/task_list.yaml`: not a prompt. It turns a task list
  in a sensor attribute into a source for the Tasks app.

The doorbell and the quiz show the card with `prompt_show` and wait for
the answer event, so the wait can be longer than `ask` allows.

All of them ask for the node name (default `daruma`, as in
examples/box3.yaml), since the action names come from it, not from the
device's name in HA.
