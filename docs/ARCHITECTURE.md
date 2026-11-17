# Daruma: architecture

Daruma started as the firmware of one device, an ESP32-S3-BOX-3. This
document turned it into a small framework: several devices around a
house, on different screens, with different personas and apps. Each
section names what was there before and what changed.

## Layers

```
 device yaml        examples/box3.yaml: name, board, personas, apps, HA entities
 ───────────────────────────────────────────────────────────────────────────
 modules            pomodoro, calendar, tasks, weather, prompts, jokes, ...
 personas         daruma, pixel corgi, Jack Russell, tabby cat, The Boss, eyes, images
 core               state, behaviors, render loop, layout, input, sounds, themes
 board              ESP32-S3-BOX-3: display, touch, buttons, audio, mic
```

- **Board.** A package that brings the hardware and names its inputs
  (`board_box3.yaml`). It will also declare the display profile (size,
  colors, refresh speed).
- **Core.** It owns the device's state and decides what is on screen. It
  routes input and plays sounds. It never knows which modules or personas
  exist.
- **Personas.** A persona is a persona that answers to states. "Persona" stays
  as the name of the HA select.
- **Modules.** One package plus, when needed, one component per feature.
  Including the package turns it on.

## Typed states and behaviors

### Before

Moods and poses were strings: "Happy" and "listening". The display lambda
and the personas passed them around. A persona that lacked one fell back quietly,
and a typo compiled fine. Sounds were looked up by name the same way.

### The model

The core tells the persona what is going on. The persona decides how to
show it. There are three kinds of state:

| Kind     | Set by                     | Lasts            | Examples                                   |
|----------|----------------------------|------------------|--------------------------------------------|
| Mood     | happiness and reactions    | minutes          | neutral, happy, sad, sleepy, sleeping      |
| Activity | modules, as a stack        | while it runs    | focus, break, listening, thinking, talking, alarm, offline, attention |
| Reaction | one-shot calls             | one animation    | petted, startled, celebrate, task_done     |

The persona plays the reaction if there is one. Otherwise it plays the
top activity, and otherwise the mood.

Every state is declared once, in a registry
(`components/daruma/registry.py`):

```python
State("focus", ACTIVITY, fallback="neutral")
State("celebrate", REACTION, fallback="happy")
State("neutral", MOOD)  # no fallback: every persona must have it
```

At build time, the registry generates a C++ `enum class StateId`. Strings
remain only in logs and HA selects. A module can add states of its own, each
with a fallback. Tasks, for example, adds `task_done`, which falls back to
`celebrate`.

How it is built:

- The list reaches C++ as an X-macro, `DARUMA_STATE_LIST`, in `defines.h`
  (`cg.add_define`). `states.h` turns it into `StateId` and a table of
  name, kind, fallback, duration and "celebrates".
- Core states: the moods neutral, happy, sad, loved, scared, sleepy and
  sleeping; the activities listening, thinking, talking, alarm, offline,
  error, waking and attention; the reactions petted, startled,
  celebrate and paint (see the `goal` signal). Pomodoro adds focus, break, focus_done, goal, paused,
  focus_stopped and break_over. Tasks adds task_done and tasks_done.
- A reaction has a duration. A duration of 0 means sound only (`paused`).
  A reaction whose chain passes through `celebrate` ends with a double
  wink.
- Precedence: a reaction, then the top activity, then the mood. An
  activity also beats the mood select and the muted sleep. The voice
  phases (listening, thinking, talking, error, alarm, offline, waking) stay
  single still frames (`Device::draw_still`), so the screen does not compete
  with audio.
- Activities are a stack with owners. Each owner holds one:
  `set_activity("pomodoro", StateId::FOCUS)`, `clear_activity("pomodoro")`.

A **behavior** is what a persona does for a state: an animation, a sound,
and optional words. A persona declares its behaviors:

```yaml
daruma_sprites:
  - id: pixel_corgi
    behaviors:
      focus:     { animation: Focus }
      celebrate: { animation: Happy, sound: goal }
      petted:    { animation: Loved, sound: pet }
```

A state without a `behaviors:` entry uses the animation named like it, in
any case (`focus` finds the art's `Focus`). So sprite personas need no
yaml for it: their list comes from what the art's `build()` returns.

A reaction plays over the activity under it, which stays on. Props of the
activity (the daruma's incense) would vanish while the reaction plays, so a
persona can name, per activity, the animation to play instead:

```yaml
    during:
      focus: { Loved: LovedFocus, Scared: ScaredFocus }
```

While focus is on, any reaction that would play Loved plays LovedFocus.
`tests/test_props.py` checks this for every persona whose art declares
`PROPS` (activity -> boxes where its props stand).

The build checks every persona against the registry, in ESPHome's final
validation step, where the whole config is visible:

- An unknown state name is an error. Typos fail the build.
- A state the persona lacks, with a fallback chain that reaches one it
  has, works. The build log says so: `pixel_corgi: focus -> neutral`.
- A state the persona lacks, with no fallback, is an error.
- An animation or sound that doesn't exist is an error.

So a new state can never go unnoticed. It ships with a sensible default, or
the build fails.

Sounds join the same table. `play_sound("pet")` becomes
`device.react(StateId::PETTED)`. The persona's behavior picks the sound, and
the built-in synth sounds become defaults. Themes stay per persona as they
are now.

- A state's sound is its behavior's, else the registry's default for that
  state. A sound does not follow the fallback: `petted` shown as `loved`
  still plays `pet`.
- An activity plays its sound when it starts, unless the caller passes
  `sound = false`. A break right after a focus block is quiet, because
  `focus_done` just played.
- Core's `play_sound` script still plays every sound. It keeps the guards:
  the Sounds switch, a ringing timer, the voice assistant, announcements,
  and the shared I2S bus.
- The timer chime is the persona's sound for `alarm` (default `timer`).
- The eyes persona has a focus look: eyes down and narrowed, as if reading.

## The world: shared signals and persona params

### Before

The plant, the window's sky and the rug color by weekday all lived in one
`World` struct. The pomodoro package grew the plant. The plant meant
"progress" to the corgi, but The Boss has a desk and no plant. The eyes
persona has neither.

### Shared signals

Core keeps a small set of typed, standard signals. Any persona may show
them in its own way:

| Signal        | Type             | Source                                    |
|---------------|------------------|-------------------------------------------|
| `progress`    | 0..10            | modules: pomodoro goal, tasks done, ...   |
| `wellbeing`   | 0..10, or unset  | HA: a plant sensor, sleep score, ...      |
| `sky`         | clear, cloudy, rain, snow, night | HA weather                |
| `day_part`    | morning, day, evening, night | the clock                     |
| `weekday`     | 1..7             | the clock                                 |
| `goal`        | none, started, done | modules: pomodoro's daily goal         |

`progress` replaces the plant stage. The corgi draws it as the plant growing.
The Boss could draw it as a pile of finished paperwork, and the eyes persona as
a small bar. A module or HA sets a signal through the device. A persona only
reads it.

Several sources can feed `progress`. Each source has a name and a weight in
the device yaml. HA can also take the signal over (`override`), as the
custom plant stage did.

As built (`signals.h`):

- `progress` is the weighted average of the sources that reported. It also
  carries `behind`, which is true when any source is behind its pace. The
  corgi's plant takes the stage `ceil(progress x (stages - 1) / 10)`. It
  wilts while `behind`, or while `wellbeing` is 2 or less.
- Pomodoro feeds `pomodoro`: this week's pomodoros against the weekly goal,
  and `behind` from the hourly pace check.
- The device yaml sets the weights: `daruma: progress: {pomodoro: 1}`.
  Without that list, every offered source counts at weight 1. A weight for
  a source no module feeds fails the build.
- HA takes over with "Progress source" set to Custom, then "Progress"
  (0..10) and "Progress behind".
- `wellbeing` comes from the API action `set_wellbeing` (-1 = unset).
- `day_part` comes from the clock: morning 5-11, day 12-16, evening 17-21,
  night 22-4.
- `goal` is where today's goal stands: `none`, `started` or `done`
  (`Device::set_goal`). Pomodoro feeds it: started after the first
  pomodoro of the day, done at the daily goal, none again at midnight.
  `progress` can't carry it, since that is this week's pomodoros.
- When a module moves `goal` up with `announce`, the hub plays the core
  reaction `paint`, but only on a persona with a look of its own for it
  (`Behavior::own`). The daruma paints an eye. Other personas show the
  module's own reaction as before, so a corgi's first pomodoro stays
  Happy. Pomodoro announces right after its `focus_done` or `goal`
  reaction, so `paint` replaces it on screen and its sound still plays.
  `paint` has no sound of its own. Restoring at boot, the midnight reset
  and a new daily goal setting are quiet.
- With a daily goal of 1, the goal goes from none to done at once. The
  daruma then plays the second eye's Paint, which starts with the first
  eye already painted.

### Persona params

A persona can also declare its own params. They are for things only that
persona has, such as the corgi's rug color or The Boss's mug text. Each
param:

- is declared in the persona's schema with a type and a default;
- is named with the persona id as a prefix: `corgi.rug`, `the_boss.mug`.
  Names from two personas can't clash, and the build checks that no two
  declarations share a name;
- can be set from YAML. With `expose: true`, it is also set from HA as a
  device setting (below).

Shared signals cover what every persona should react to. Params cover the
rest. A param must never stand in for a shared signal, so a module can't
depend on a param of one persona.

As built (`components/daruma/persona.py`):

- The prefix is the persona's id: `pixel_corgi.rug`, `eyes.color`.
- Each persona component declares its own params in Python. The types are
  `choice` and `bool`. In C++ they are ints.
- In yaml: `params: {rug: plain}`, or `rug: {value: weekday, expose: true}`.
- An exposed choice becomes a select, "Pixel corgi rug". An exposed bool
  becomes a switch.

## Device settings in Home Assistant

Settings that may change after flashing appear in HA under the device's
"Configuration" section. They are ESPHome entities with
`entity_category: config`. They keep their values across reboots. The device
yaml sets their first value.

- Apps: one switch per app ("App: Calendar").
- App settings: for example "Calendars", a text entity holding a list of
  entity IDs, "Days ahead", and "Tasks source".
- Persona params with `expose: true`.
- Bindings, with `expose_bindings: true`.
- The home button action, the jokes switch and the theme options already
  work like this, or will.

Things that change the build stay in YAML: which modules, which personas,
fonts and the board.

## Interactive sessions driven by Home Assistant

These are "prompts": a full-screen card that HA shows, updates and closes. The
user's answer goes back to HA. One set of primitives serves a quiz game, a
doorbell and a confirmation.

### Calls from HA to the device (API actions)

| Action                          | Fields                                                               |
|---------------------------------|----------------------------------------------------------------------|
| `esphome.<device>_prompt_show`  | `id`, `layout`, `title`, `body`, `options: string[]`, `marks: string[]`, `style`, `timeout`, `state`, `sound`, `dismissable` |
| `esphome.<device>_prompt_update`| `id`, `body`, `marks: string[]` (selected, correct, wrong, hidden), `countdown` |
| `esphome.<device>_prompt_close` | `id` (`""` closes all)                                               |
| `esphome.<device>_ask`          | Same fields as show. Waits for the answer and returns it as the action's response. |

### Answers from the device to HA

The device fires the HA event `esphome.daruma_prompt` with
`{device_id, id, choice, index, reason}`. The reason is `chosen`,
`dismissed`, `timeout` or `replaced`.

### Layouts

- `message`: title, body, and 1 to 3 buttons in a row. Used for the
  doorbell: "Someone is at the door", with Unlock, Talk and Ignore. A camera
  snapshot (`image_url`) comes later.
- `choice`: a question and a 2x2 grid of answers. It has an optional
  countdown bar and an optional row of small extra buttons. This is the quiz
  layout: lifelines, then marks for the chosen, correct and wrong answers.
- `list`: a scrolling list of options, for longer menus HA wants to show.

### Priority

Prompts have a `style` of `info`, `game` or `urgent`. The order on screen is:
urgent, then game, then an open app or the menu, then info, then idle.

- A lower prompt waits behind a higher one.
- A focus session holds back `info` prompts until the break.
- The red circle dismisses a prompt unless the prompt sets
  `dismissable: false`.
- The prompt's `state` plays on the persona (default `attention`), so the
  corgi looks up when the doorbell rings.

### As built

Component `daruma_prompts`, package `prompts.yaml`. Usage and HA examples:
[docs/prompts.md](prompts.md).

- **Every field is required.** HA registers each ESPHome action argument as
  required (`homeassistant/components/esphome/manager.py`), and ESPHome has
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
  function, `tap_result()` in `prompt_layout.h`, host-tested. An earlier
  "Dismiss?" confirmation panel was dropped: one tap is enough.
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

### Example flows

- **Quiz** (`blueprints/script/quiz.yaml`). An HA script loops over
  questions. For each one, it calls `ask` with the question, four answers
  and 50:50. It then calls `prompt_update` to mark the answer right or
  wrong, waits, and moves on. After 50:50 it asks again with two wrong
  answers and the button hidden by `marks`.
- **Doorbell** (`blueprints/automation/doorbell_prompt.yaml`). An
  automation on the doorbell calls `prompt_show` with `style: urgent`. A
  second trigger on `esphome.daruma_prompt` unlocks the door or starts
  the talk-back.

## Modules and apps

Before, packages registered apps, menu items and layers in `on_boot`
lambdas, and the order of the lambdas mattered.

- A module is a C++ `Module` with one `setup(Device &)`. It registers apps,
  menu items, layers, input handlers, states and prompt layouts there. The
  package yaml only wires HA entities and options.
- Apps get `on_open` and `on_close`, so they fetch data only while shown.
  The Calendar and Tasks apps are built this way.
- **On and off.** An app is in the build when its package is included. At
  run time, core adds one switch per app ("App: Calendar"). A switched-off
  app leaves the board and stops fetching.
- The board order comes from one `apps:` list in the device yaml, so the
  order no longer depends on package order.

As built:

- A module is declared where the build can see it. A package adds a
  `daruma: modules:` entry with `name`, `states`, `actions` (each a
  list of ESPHome steps), `apps`, `progress`, `theme: {colors, words}`,
  `bindings` (defaults) and `setup:`, a lambda over `hub` (the Device). A
  C++ component can declare the same as `DARUMA_MODULE` in its Python file
  (the menu does). `Device::setup()` runs each module's `setup()` before
  the on_boot automations and the first draw. Final validation reads every
  declaration.
- Core's own actions belong to the module `daruma`: daruma.pet,
  daruma.next_persona, daruma.previous_persona and daruma.close_message. The module
  `voice` offers voice.start.
- An app missing from `apps:` goes last on the board, and the build log
  says so. Every app a `daruma: modules:` entry declares gets a
  switch. An app that only a C++ `DARUMA_MODULE` declares gets one only if
  it is in `apps:`. A name in `apps:` that no module offers fails the
  build.
- An open app gets every swipe, so Calendar pages days with left and
  right. Board paging lives one level up, on the board, so the two never
  meet.
- A switched-off app gets `on_enable(false)` and stops fetching. Calendar
  fetches only while open or for its status line. Tasks fetches for its
  tile.
- The text helpers that Calendar and Tasks shared (`fit_text`,
  `drawable_text`, `text_width`) now live in `daruma/text.h`.
- **Copies of an app.** `app_tasks.yaml` and `app_calendar.yaml` take
  `!include` vars (`app_id`, `app_name`, and `source`/`entity` or
  `calendars`), with defaults in the package's top-level `defaults:`
  block. Without vars they build the single app as before.
  - Every id, script, setting and the module name come from `app_id`. The
    module name is also the theme key prefix (`calendar_work.today`), and
    a theme renames or re-icons a copy by its app id.
  - A module's `apps:` entry may be `{id, name}`; the switch then reads
    "App: <name>" ("App: Family").
  - The components are `MULTI_CONF`, written as lists in the packages, so
    two includes add two entries instead of merging into one.
  - States shared by every copy (`task_done`, `tasks_done`) are declared
    once, by `daruma_tasks`'s `DARUMA_MODULE`.
  - The default copies keep their entity names: "Tasks source", "Tasks
    entity", "Calendars". A second calendar copy gets "Work calendars" and
    "Work days ahead".
  - Two copies with one `app_id` fail the build. ESPHome reports the
    clashing ids first; the registry also fails on two modules with one
    name or one app id.
  - `variants/variant_apps.yaml` builds two of each.
- **Back into an app.** `App::back` runs before the menu closes an open
  app (header arrow or the board's back input). Calendar uses it to leave
  its day view.
- **Tasks sources.** "To-do list" (`todo.get_items`, check-off with
  `todo.update_item`) and "Script": an HA script that returns
  `{open, total, tasks: [{id, title, done, flagged, overdue, due_today}]}`.
  The blueprint `blueprints/script/task_list.yaml` ("Daruma: task
  list from a sensor") makes one from a sensor attribute, with field names
  as inputs. It replaced a `recorder.get_statistics` call that only
  carried a response template. The select keeps its option indexes: the
  old "Task feed" (0) is now "Script". The entity text's `max_length`
  went from 100 to 120, so a stored `sensor.*` entity is dropped for the
  build's default.
- **Pomodoro page** (app id `stats`, named "Pomodoro"). It replaced the
  Stats app and keeps its id, so `apps:`, menus and the app's switch keep
  working. The timer big (the focus length while idle), the phase and
  "N of goal today", one dot per pomodoro of the goal, this week's bars
  with the goal line, the week's total and the streak, and a row of the
  buttons for now (see Menus). Custom swaps the row for the lengths; back
  leaves them. While open it redraws every second. NEXT, PREV and SELECT
  move a focus over the buttons. A tap on the plaque opens it.
- **Weather** (`app_weather.yaml`, component `daruma_weather`). Today's
  report from one HA weather entity, the setting "Weather entity"
  (`weather.home` by default):
  - now: the condition's icon, the temperature big, its name; today's
    high and low; the chance of rain and the wind; a strip of the next
    hours (five on 320x240, eight on wide screens);
  - two `weather.get_forecasts` calls, hourly then daily, through the
    hub's gate; now, the units and the wind come from the entity's state
    in the hourly template. Only while open: on open, then every 30
    minutes. A service without hourly forecasts still shows the rest;
  - units from HA: the temperature as "72°", the wind in its own unit;
  - "Can't reach Home Assistant" without HA, "Can't load the weather"
    when both calls fail; a tap tries again;
  - the conditions' icons and words are plain C++ (`weather.h`, tested in
    `tests/test_weather.cpp`); menu.yaml's icon font lists the glyphs;
  - a tap on the temperature badge opens it.
- **Calendar agenda.** The app opens on an agenda; a day opens the old
  day view.
  - One request covers today and "Days ahead" days (a number setting, 1
    to 31, 14 by default). HA sends at most `agenda_max` (25) events,
    sorted by start, titles cut to `title_chars`, no descriptions. All-day
    events carry HA's local midnights as epochs.
  - Grouping and headings are plain C++ in `daruma_calendar/agenda.h`,
    host-tested (`tests/test_agenda.cpp`). An event goes under the day it
    starts; one still running from before today goes under Today. All-day
    events are placed by their middle, so a clock a few hours off HA's
    still finds the right day.
  - The day view takes its day from the agenda when the agenda holds all
    of it: in range, and before the last event's start when HA trimmed
    the list. Otherwise it fetches that day alone (at most 12 events).
  - The tile reads today from the agenda. It refreshes on open (when over
    a minute old), every 15 minutes, at midnight, and when "Days ahead"
    changes.
  - Words are theme words under the app id, with defaults from the
    package's `text_*` values, weekday and month names included.
  - `tests/preview_agenda.py` draws the agenda in the wood and outline
    themes at 320x240 and 480x272.
- **Next event line.** A short line on the device's own screen, at the
  hub's info line: "14:00 Dentist", or "Now: Standup · until 10:30".
  - "Next event within" (hours, 0 = off, 3 by default) is a number
    setting per copy. The package var `next_event` picks the copies that
    show it: `auto` is the first copy only.
  - The pick is plain C++ (`daruma_calendar/next_event.h`, tested in
    `test_agenda.cpp`). A running event wins; of several, the one that
    started last. Else the earliest that starts within the hours and
    before midnight: the line is about today. All-day events never show.
    It works on the agenda as loaded, so the minutes after midnight need
    no fetch.
  - Several copies share one line (`next_line.cpp`): running first, then
    the soonest. The words come from the copy the event belongs to.
  - It looks again once a minute and when an agenda arrives. A new text
    redraws only its pill (`request_area`). The pill never gets narrower
    in such a redraw, so it covers the old one. The line going away is a
    full frame. Nothing logs a title.
  - Pill in the dock colors of the persona's theme, text in the menu's small
    font. Templates `line_next`, `line_now` and `line_now_open` are theme
    words with `{start}`, `{end}` and `{title}`; only the title is cut.
  - `tests/preview_line.py` draws it on every persona at 320x240, and the
    corgi at 480x272, 240x240 and mono: idle, a focus, a break and a
    pause, with the plaque and the badge. `--before` draws the old
    layout for comparison.

### Home Assistant calls with a reply

In ESPHome 2026.10.2, each `homeassistant.action` keeps its own call id
counter. So two actions hand out the same ids, and the API server runs
the first callback registered under an id. A call sent before HA
subscribes is dropped, but its callback stays. A later action can then
reach that id, and its reply goes to the stale callback. Seen: a to-do
check-off answered as an old fetch, never confirmed, so the row flipped
back.

The hub's gate (`ha_calls.h`, tested in `test_ha_calls.cpp`) fixes the
cases we can:

- Every action with `capture_response`, `on_success` or `on_error` goes
  through `hub.ha_calls().call(name, send)`. Its `on_success` and
  `on_error` call `done(token)`.
- Nothing goes until HA has been connected, with its subscription, for
  3 s. Calls asked for earlier wait and go then.
- One call is in flight at a time; the rest queue (16 at most). A call
  with no answer frees the gate after 8 s, under the apps' own 10 s.
- Calendar fetches, Tasks fetches and Tasks check-offs use it.
- A call cut off by a disconnect can still leave a stale callback. Drop
  the gate when ESPHome shares one counter and forgets dropped calls.

### What a module may contribute

Pomodoro is the model: it already has its own screens and settings, and they
look right on every persona. Every module, pomodoro included, may
contribute:

- **States**, each with a fallback: pomodoro adds the `focus` and `break`
  activities and the `focus_done` and `goal` reactions.
- **Signal sources**: pomodoro feeds `progress` from today's goal, and Tasks
  can feed it from tasks done.
- **Screens and layers**: the timer plaque, the dock buttons, the Pomodoro
  page.
- **Settings**: device settings in HA, such as the focus length and the
  daily goal.
- **Looks per persona**: theme keys under the module's name, such as
  `pomodoro.ring` or `pomodoro.done_word`. A persona may set them, and a
  default covers any it leaves out. The build checks the keys the same way
  as states.

Theme keys as built: a module declares `theme: colors:` and `words:` with
defaults. A persona's theme sets `colors: {pomodoro.focus: ...}` or
`words: {calendar.today: ...}`. C++ reads `theme.color("pomodoro.focus")`.

The device yaml, where the parts come together, may set module keys too:

```yaml
daruma:
  theme:                     # every persona
    colors: { pomodoro.done: "D62828" }
    words: { pomodoro.ready: "Bereit" }
  themes:                    # one persona, by its id
    eyes:
      colors: { pomodoro.plaque: "000000" }
```

- For a module key, lowest first: the module's default, the persona's own
  `theme:`, the device's `theme:`, the device's `themes: <persona id>`.
- A persona id is the persona's `id:` (`eyes`, `pixel_corgi`, `daruma`).
  The build stops on an unknown persona id and names the ones there are, and
  on a key no included module declares, as for a persona's theme.
- `theme.py` applies them when it builds each persona's theme, so a persona
  without a `theme:` of its own gets one. Gray and mono screens derive
  from the result at setup, as before.
- A module may keep old key names working: `theme: aliases: {old: new}`.
  The pomodoro's `tomato_unripe`, `tomato` and `tomato_bonus` are now
  `pending`, `done` and `extra`. They color both the tomatoes and the
  timer's dots.

Nothing in core or in the board package refers to pomodoro. Modules offer
named actions (`pomodoro.toggle`, `pomodoro.stop`, `voice.start`,
`menu.open`). The device yaml binds them to inputs:

```yaml
daruma:
  bindings:
    home.press: { action: pomodoro.toggle, when: idle }
    home.hold: { action: pomodoro.stop, when: idle }
  expose_bindings: true   # also a device setting in HA, starting from these
```

The build fails if a binding names an action that no included module
offers. With `expose_bindings: false`, the yaml choice is fixed.

With `expose_bindings: true`, each binding in the device yaml becomes a
select ("Home press") with "none", every action and `menu.open:<name>` for
every menu. It stores the chosen action by name, so builds with other
modules keep the choice. A stored choice wins over the yaml, so a binding
moved from the device yaml to a module default also drops its select.

Default bindings: a module may declare them. The device yaml wins over
every default, and any module's default wins over the core `daruma`
module's. Two other modules binding one trigger fails the build until the
device yaml picks one. Today's defaults:

- screen.tap and screen.swipe_up: menu.open, the `main` menu (menu);
- screen.hold and screen.long_hold: pomodoro.toggle and pomodoro.stop
  (pomodoro);
- home.press: the `pomodoro` menu (pomodoro). On the BOX-3, home is the
  red circle and also navigation `back`, so the default rests while a
  menu, app or prompt is open. A device that wants one press to start a
  focus binds `home.press: { action: pomodoro.toggle, when: idle }`;
- screen.stroke: daruma.pet;
- screen.swipe_left and screen.swipe_right: change the persona;
- screen.swipe_down: close the message.

A module default whose action belongs to a module the build lacks (the
pomodoro's menu without menu.yaml) is skipped, and the build log says so.

Filters see a gesture before any binding does. A ringing timer takes any
press, tap or hold and stops. A tap closes a message bubble.

### Tap areas: parts of the persona that lead somewhere

A part of the device's own screen can lead somewhere: the pomodoro plaque
opens the Pomodoro page, the temperature badge the Weather app, the next
event line the Calendar.

- **Areas.** The module that draws a part names it in `areas:` and tells
  the hub where it is now: `hub.add_tap_area("plaque", fn)`, where `fn`
  returns the rect, or an empty one while the part is hidden (under a
  message bubble, the badge switched off, no event on the line). Today:
  `badge` (core), `plaque` (pomodoro) and `next_event` (calendar).
- **Targets.** What a tap on an area does. A module offers defaults; the
  device yaml wins per area:

  ```yaml
  daruma:
    targets:
      plaque: { menu: pomodoro }        # or { app: stats }, { action: pomodoro.toggle }
      badge: none                       # a tap there is a tap on the persona again
  ```

  `app` opens one app on its own (the action `menu.app:<id>`; back closes
  it), `menu` opens a menu, `action` runs one.
- **The build checks:** an area no module draws, an app, menu or action
  that is not there, and apps or menus without menu.yaml. A module's
  default that can't work is skipped, and the build log says so, like
  default bindings. When two modules offer different defaults for one
  area, the first in the config wins and the log names both (copies of
  Calendar share `next_event` this way). `registry.resolve_targets`,
  tested in `test_registry.py`.
- **At run time.** A tap on the device's own screen (touch, nothing open)
  goes to the gesture filters first, then to the area under it, then to
  the bindings as before. So a tap elsewhere still opens the main menu.
  Boards without touch have no taps; their areas do nothing.
- **Tests.** The hub lists each visible area on every frame as a UiTree
  part with role `target` and the area's name, so a test taps it:
  `device.get_by_role("target", "plaque").tap()`.

### Menus

A menu is a named list of dock buttons. Modules offer default menus; the
device yaml's `menus:` replaces one by name or adds more:

```yaml
daruma:
  menus:
    main: [tasks, calendar]                    # a tap on the persona opens main
    quick: [pomodoro.skip, pomodoro.stop, stats, more]
  bindings:
    top.double: { action: menu.open, menu: quick }
```

An item is one of these. The build checks each and names the choices when
one is wrong:

| Item | Button |
|---|---|
| an app id (`tasks`, `tasks_family`) | opens the app; hidden while its switch is off |
| a module name (`pomodoro`) | the module's buttons for the moment: Focus, or Pause and Stop |
| an action (`pomodoro.break`) | runs it; label, icon and color from the module's `buttons:` |
| another menu's name | opens that menu; back returns |
| `more` | the app board |
| `{ label, icon, event }` | fires the HA event `esphome.daruma_menu` with `event` in its data |

- A name is looked up as an app id first, then a module, then a menu. So
  the menu `pomodoro` can list the module `pomodoro`.
- A module that adds buttons declares `menu: true` and calls
  `add_menu_provider()` in its setup. The hub tags each provider with the
  module whose setup added it.
- A module gives its actions a button look under `buttons:`, `{label,
  icon, color}`. The color is a module theme key (`pomodoro.break`) or
  hex. An action without a look can be bound but not listed.
- Two modules offering one menu name fail the build, unless the device
  yaml defines it.
- `main` ends with More unless it lists `more`, so the app board stays in
  reach. Without `main` in any yaml, it is every `menu: true` module that
  has no menu of its own, then Tasks and Calendar when the build has them.
  So pomodoro stays out of `main`: its buttons are in its own menu, one
  press away on the board's main button.
- The pomodoro offers `pomodoro: [pomodoro]` and opens it with home.press.
- **No buttons that contradict the moment.** A module may give an action's
  button a hook (`Device::set_action_button(name, fn)`). The hub calls it
  for that action in every menu that lists it. The hook can change the
  label or icon, give the button a submenu, or hide it (return false).
  Bindings are not affected. The pomodoro's rules are plain C++
  (`pomodoro_rules.h`, host-tested in `tests/test_pomodoro_rules.cpp`),
  and the module's own buttons, the listed actions and the Pomodoro page
  all ask them:

  | Now | Buttons |
  |---|---|
  | focus, running or paused | Pause or Resume, Stop, Skip |
  | break | Resume (when paused), Focus (ends the break), End |
  | idle, in the break window | Focus, Custom, Break, Long break |
  | idle otherwise | Focus, Custom |

  The break window: the last focus ended less than the break it earned
  ago (long after every Nth pomodoro, else short). A focus starts its
  break by itself, so the window shows after End or Stop on that break.
  The time is kept in `millis()`, cleared at midnight and lost on a
  reboot, which only hides the Break buttons.
- Focus (`pomodoro.start`) starts the "Pomodoro focus" length at once.
  Custom (`pomodoro.custom`) shows the lengths: in a menu as its submenu,
  bound to an input as the Pomodoro page's row. `pomodoro.long_break` is
  new.
- The dock lays out five buttons at most. A longer menu shows four and
  Next (`text_menu_next`), which pages to the rest. A label may use the
  room its neighbours' shorter labels leave, so "Calendar" fits between
  "Tasks" and "More" on five buttons.
- Back: an app opened from a dock button returns to that dock, and a
  nested menu to the one that opened it.
- The menu title is the pomodoro's "N of goal today" on every menu.
- `menu.open` with a menu runs as `menu.open:<name>`, an action with an
  argument (`Device::add_arg_action`). HA opens one with
  `esphome.<device>_menu_open(name)`.
- The build checks: unknown items, an item listed twice, a menu that lists
  itself, an event button without label, icon or event, `buttons:` for an
  action of another module, `menu:` on any action but menu.open, a
  binding to a menu that does not exist, and `menus:` without menu.yaml.

### Inputs are named by the board

Boards differ: two buttons and a touch screen, one knob, five buttons and
no touch. So the board package names its inputs. Each one points at a
binary sensor, a touch zone or an encoder, and lists the gestures it
supports:

```yaml
daruma:
  inputs:
    - name: home                 # bindings use this name
      button: home_button        # a binary_sensor id
      gestures: [press, double, hold]
      hold_time: 1.5s
    - name: top
      button: left_top_button
      gestures: [press, double, hold]
    - name: screen
      touch: s3_box_touch        # a touchscreen id
      gestures: [tap, double, hold, long_hold, swipe, stroke]
  # How the menu, apps and prompts are driven. Touch covers them on the BOX-3.
  navigation:
    back: home.press
    close: home.hold
```

A binding then names an input and a gesture, such as `top.double` or
`screen.swipe_up`. The `screen.*` bindings act only on the device's own
screen. In the menu, apps and prompts, gestures keep their usual meaning.

The build checks:

- A binding to an input or gesture the board doesn't have fails the build.
  This applies only to bindings in the device yaml. A module's default
  binding for a missing input is skipped, and the build log says so.
- **Navigation must be complete.** Every board needs `back`. A board without
  touch also needs `next`, `prev` and `select`, from buttons or a knob
  (`knob.turn` counts as next and prev). Without them, the menu could never
  be left, so the build fails.
- A gesture used by both navigation and a binding fails the build unless
  the binding sets `when: idle`, like the red circle. It goes back in the
  menu, and runs the binding on the device's screen. The check is per
  gesture: `home.double` may be bound while `home.press` navigates.

The source key names the kind: `button:` for a binary sensor and `touch:`
for a touch screen. A knob would get its own key later. Touch has a second
hold, `long_hold`, so the screen can keep two holds: 1-2.5 s toggles and
3 s stops. In an open menu or app, screen gestures go to it. Screen
bindings rest there, so a hold on the dock no longer reaches the pomodoro.

**No delay unless it is needed.** What counts is what is bound in the
current context: idle, or navigation (`when: idle` bindings rest while a
menu, app or prompt is open).

- A press fires at once, on press-down, when that input has neither a
  double nor a hold bound.
- Only a bound double adds the wait for a second press (`double_window`).
- Only a bound hold makes a press fire on release instead of press-down.
  With hold and long hold both bound, HOLD fires on a release between the
  two times, and LONG_HOLD fires the moment it is reached. With only one
  bound, it fires the moment its time is reached.
- Touch follows the same rule. A tap can't fire before lift-off, since a
  swipe starts the same way, but it fires at lift-off unless a double tap
  is bound. Swipes and strokes are unaffected.

Timings are per input, with board defaults. Each is an ESPHome time period
with a checked range: `double_window` (300 ms, 100 ms-1 s), `hold_time`
(1 s, 300 ms-5 s) and `long_hold_time` (3 s, 1-9 s, longer than
`hold_time`). A touch held past `hold_time` is never a tap, even with no
hold bound (an open app). The recognizer is
plain C++ (`gesture.h`). A host test covers the timing
(`tests/test_input.cpp`).

The board keeps safety inputs out of the list, so they can't be bound: the
hardware mute switch, and holding the top button for 10 s to factory reset.
The top button's press fires on press-down, as long as nothing holds it.
So the reset hold also runs the top press action first, which is
voice.start today.

## Packaging as a framework

The framework lives in its own git repository, versioned with tags:

```
components/   daruma (core), daruma_menu, daruma_sounds, daruma_prompts,
              daruma_sprites, daruma_eyes, daruma_images, daruma_calendar,
              daruma_tasks, daruma_desktop
packages/     boards (board_box3.yaml, board_box3_buttons.yaml,
              board_desktop.yaml), core.yaml, menu.yaml, pomodoro.yaml,
              prompts.yaml, app_tasks.yaml, app_calendar.yaml, persona_*.yaml
pixel/        pixel-art sources (Python), drawn at build time
art/          picture sets for persona_images.yaml
examples/     box3.yaml, desktop.yaml and build checks
blueprints/   HA blueprints: prompt demos, doorbell prompt, quiz, task list
```

A device is a short file. Its packages come from git at a ref (a branch,
a tag or a full commit hash):

```yaml
substitutions:
  name: office-device
  friendly_name: Office Device
packages:
  daruma:
    url: https://github.com/igrybkov/daruma
    ref: main
    files:
      - packages/board_box3.yaml
      - packages/core.yaml
      - packages/persona_daruma.yaml
      - path: packages/app_calendar.yaml
        vars: { calendars: calendar.home }
```

**One checkout for everything.** Each package declares the components it
needs as a local source, `path: ../components`, relative to the package
file. ESPHome looks for a relative path in the config folder first, then
next to the YAML file that names it (`cv.directory`). For a package from
git, that is the package's own checkout in ESPHome's cache. So a device
needs no `external_components:` entry, and components, packages and pixel
art always come from the same commit. Adding a second source for the same
components (`external_components: github://...`) is not needed and makes
the result depend on order.

**Files named by packages.** The same rule covers the files the personas
read. `pixel_art: {script: ../pixel/personas.py}` and
`art: ../art/flat_corgi` resolve next to the package, and the component
stores the absolute path (`resolve_file()` and `resolve_dir()` in
`components/daruma/sprite.py`). It resolves them while the config is
validated, while each value still knows its YAML file. The rest of the
build reads only absolute paths.

**The pixel library.** The pixel art is the Python package
`daruma_pixel` (`pixel/daruma_pixel/`, installable with pip through
`pyproject.toml`). Firmware builds do not install it. `daruma_sprites` puts
`pixel/` of its own checkout on the import path and imports a library
script by module name (`daruma_pixel.personas`). A script kept elsewhere (a
persona in a device's config folder or in another package's repository) runs
with its own folder and the library on the path. It imports the engines
as `from daruma_pixel import personas, pet`, adds its persona to `personas.PERSONAS`
and calls `personas.build()`. Library modules live in their own namespace, so
a script's own module names cannot replace them. The drawn-persona cache
hashes every file the script can import.

**Bundles.** `esphome bundle` packs the config folder for a remote build.
Pictures and scripts the config does not name as paths are added with
`bundle_file()`. Files in ESPHome's git cache are left out: the build
server fetches packages again.

**Developing.** `examples/desktop.yaml` includes the packages from the
checkout (`!include ../packages/...`), so it shows uncommitted changes. A
device yaml that names `url` and `ref` as substitutions builds from a
local clone with `-s daruma_url file:///path/to/daruma -s daruma_ref main`
(committed changes only).

### Blueprints

`blueprints/` holds examples of what Home Assistant can do with a device.
Each one started as a real automation and was made generic: every entity
is an input. Four are built: `prompt_demos`, `doorbell_prompt`, `quiz`
and `task_list`. The others in the table are ideas.

| Blueprint | Kind | What it does |
|---|---|---|
| `joke_after_focus` | automation | After a focus session or the daily goal, asks an AI task for a short joke and shows it on the device. |
| `window_weather` | automation | Sets the persona's window sky from a weather entity, and the temperature badge from a sensor. |
| `quiet_during_calls` | automation | While a call is on, mutes the device's sounds, speaker and mic, and restores them after. |
| `prompt_demos` | script | Shows every kind of card (yes/no with `ask`, an urgent alert, a card that stays, a list, two stacked alerts) and the answer it sent back. |
| `doorbell_prompt` | automation | Shows an urgent prompt when someone rings: Unlock, Talk or Ignore. |
| `quiz` | script | A multiple-choice quiz with scores and a 50:50 lifeline. |
| `task_list` | script | Returns a sensor attribute's task list, trimmed, for the Tasks app's "Script" source. |
| `goal_nudge` | automation | Late in the day, if the daily goal is still far off, the device looks sad and offers to start a focus session. |
| `calendar_heads_up` | automation | A few minutes before a meeting, shows an info prompt with the title and a "Start focus after" option. |

New blueprints land here when an automation in a real house proves
useful. Blueprints use only what the
framework offers (API actions, events, entities), so they keep working on any
board and persona.

A home's own things stay in its own config: entity IDs, automations and
any private personas. Everything the device sends to HA carries its
`device_id`, so one automation or blueprint can serve every device.

Adding a state with a fallback is a minor version. Adding one without a
fallback, or changing an API action, is a major version.

## Screen sizes

What assumes 320x240 today:

- The menu: `width_`/`height_` defaults, `DOCK_TOP = 128`, 61 px dock
  slots, `HEADER_H = 40`, and the 2x2 board.
- Pixel art: drawn at about 106x80 and scaled 3x.
- Font sizes, and the speech bubble and badge offsets.

The plan:

- Core computes a **Layout** once from the display size. It gives the size
  class (4:3, 16:9, square, tall), a unit (`min(w, h) / 240`) and named
  regions: stage, dock, header and content. Everything draws into regions.
  Fixed pixel numbers go away.
- Grids follow the width: 2x2 on 4:3 and square screens, 3x2 on 16:9.
- A persona draws into the stage. Pixel art takes the largest whole-number
  scale that fits. The scene fills the rest by extending its wall and floor,
  so a wide screen shows more room, without black bars. Art can add a wide
  variant later.
- Font sizes come from the board package.
- **Input without touch.** An alarm clock may have only buttons or a knob.
  The input set gets NEXT, PREV, SELECT and BACK. The menu, apps and prompts
  get a focus ring. This is the change that affects the architecture most,
  so it goes in early. Retrofitting it into every app later costs more.

### As built

**Layout** (`components/daruma/layout.h`). Plain C++, host-tested.

- The hub computes it in `setup()`, before any module, from the display
  the board names (`daruma: display: s3_box_lcd`). `render()` checks
  the size again on every frame.
- `device.layout()` gives:
  - `width`, `height`, `size_class` (standard, wide, square, tall);
  - `unit` = min(w, h) / 240, and `px(v)`, which turns a 320x240 design
    size into screen pixels;
  - regions as `Rect`: `stage`, `dock`, `header`, `back` (the back
    arrow's tap zone), `content` (the app area) and `board` (the tiles);
  - `grid_cols` x `grid_rows`, `gap`, `tile(i)`, `tile_at(x, y)` and
    `dots_y`.
- Size classes by aspect: wide from 1.6, standard from 1.2, square from
  0.84, tall below. The grid is 2x2, 3x2 on wide screens, 2x3 on tall
  ones.
- `Rect` has `inset`, `contains`, `cell(i, cols, rows, gap)` and
  `cell_at`. A prompt card starts as `layout.content.inset(px(8))`, and
  its 2x2 answers are cells of a grid in it (see Prompts, as built).
- Regions sit on the screen's edges and their sizes scale by `unit`. So
  320x240 gives back every old number: the dock at y 128, the header 40
  high, tiles of 140x82 at x 16/164 and y 48/138, the app area at
  (14, 42, 292, 184), and the badge, bubbles and captions where they were.
  `test_layout.cpp` checks that table.
- `AppView` carries `layout` and `px()`. Calendar, the Pomodoro page and the pomodoro
  layers scale their sizes with it. Tasks already sized itself from the
  app area.
- Font sizes are board substitutions: `font_size_text`, `font_size_small`,
  `font_size_badge`, `font_size_icon` and `font_size_timer`.
- The menu adapts to narrow screens:
  - tiles narrower than 130 design pixels put the icon above the name;
  - names and statuses are cut to fit (`fit_text`);
  - dock buttons shrink so they never touch.

**Personas in the stage.**

- **Pixel art** takes the largest whole-number scale that fits the stage.
  `scale:` now only caps it.
- A layered room fills the rest from **edge strips** that the build takes
  from the room itself (`components/daruma_sprites/extend.py`, plain
  Python, host-tested). The strips work like this:
  - For each edge, every line across it gets tested for a repeat period.
    The period most lines share wins: the corgi's planks repeat every
    21 px. Rows that repeat with a shorter period that divides it (floor
    rows) keep their own pattern.
  - Rows that don't repeat (the window frame, the shelf) borrow the nearest
    row that does and that starts with the same pixel. So the wall goes on
    plain, and no plank changes color.
  - The left and right strips are as tall as the room, and the top strip is
    as wide as it. The bottom gets no strip: the rug and the furniture
    stand there. The room sits on the bottom of the stage, centered, and
    extra height goes above it onto the wall.
- On the device, `SpritePersona::view_()` works out how many whole scene
  pixels each side needs. `compose_under_()` maps each pixel of that view
  to the room, a strip, or a top-strip row (also for the corners). The
  recolor, the window, the plant and the persona are shifted by the
  extension. `present_()` clips to the stage.
- A margin narrower than one scene pixel stays in the background color.
  That keeps 320x240 the same as before.
- The extension costs the strips in flash, under 1 KB per persona, and larger
  frame buffers in PSRAM: 160x91 on 480x272.
- **The eyes persona** centers on the stage and scales every size and offset
  by `unit`. Each mood renderer takes `setGeometry(cx, cy, unit)`.
  Blinks, glances, winks and moving moods repaint only the union of the
  old and new eye boxes (`draw_delta`), clipped, so the screen sends that
  box instead of the whole frame. Each mood has a box in design pixels.
  Loved draws hearts and always redraws in full.
- **Layers over a delta.** A persona whose `draw_delta()` repaints a box with
  its background reports it in `delta_area()`. The hub then draws the
  layers again, clipped to that box, so a timer or badge under it stays.
  Pixel-art personas report the box they sent too.
- **A layer's own area.** `request_area(rect)` says a layer changed only
  inside `rect` and paints all of it. The next idle frame draws the layers
  clipped to it and leaves the persona alone, on still screens too. A persona
  can't repaint just a part of itself without spoiling its next delta (it
  keeps what it last sent), so a layer that shrinks or goes away calls
  `request_redraw()` instead.
- **The bottom band.** One fixed layout, with or without the info line:
  - The info line (`layout.info`) is a strip 18 high, 6 up from the
    bottom, between 6 px side margins (`layout.edge`). 320x240:
    (6, 216, 308, 18).
  - The two bottom corners stand on one line 4 above it
    (`corner_bottom`, 212 on 320x240), each 6 from its side.
    `corner_left(w, h)` holds the tomato plaque, `badge()` (42 across, in
    `corner_right`) the temperature badge.
  - Nothing moves when an event comes or goes, or when the line is off.
  - `layout.upper` is the stage above that line. The eyes persona centers
    there, so its eyes stay clear of the corners at rest.
  - A persona's theme sets `info_line: bottom`, `top` (`info_top`, right of
    the voice timer) or `off`. A module that draws there calls
    `set_info_line_used(true)`, and `Device::info_line()` then gives the
    rect for the current persona.
- **The pomodoro plaque** (`plaque.h`, host-tested, bottom left):
  - Idle: today's tomatoes, three a row, 22 apart.
  - A focus or a break, running or paused: the timer. mm:ss in the phase
    color, each digit in a fixed cell so nothing shifts, the colon
    blinking. Under it one dot per pomodoro of the goal: filled when done,
    a ring when still to do. Paused: gray, a pause sign in the colon's
    place. Slow screens show "12m".
  - The timer plaque keeps one size for the session. Each tick repaints
    only its rect (`request_area`); a full frame only when its rect
    changed. No tick while the menu, a prompt or a bubble is up.
  - The old top-right timer and the bottom countdown bar are gone. The
    plaque gives the same time, and the bar's every step needed the persona
    repainted under it.
  - Gray and mono: colors go through `theme.on()` against the plaque;
    done and to-do differ by shape (filled or a ring).
- **Picture personas** are drawn 1:1, centered, on the art's top-left color,
  unless `background:` is set. A screen smaller than the art crops it.

**Animation frames as patches** (`sprite_codec.py`, `frame_chain.h`,
host-tested by `tests/test_frames.py`).

- Most animation frames differ from the one before by a few pixels. So a
  layered pixel persona stores its frames as one set: each frame is a
  keyframe (a whole picture), or a patch on an earlier frame. A patch is a
  small sprite of the box where the two differ. In it, one code means
  "keep the frame below", and the see-through index means the persona
  no longer covers that pixel.
- Each frame has its own palette, so a patch with three colors uses two
  bits per run code. Same palettes are stored once.
- The encoder picks each frame's base at build time:
  - an animation's first frame comes first, and stays at most 2 patches
    from a keyframe, since it is shown out of order;
  - any other frame prefers the frame before it, which is what the screen
    already shows; else the cheapest of the animation's first frame and
    the three closest frames;
  - no frame is more than 4 patches from its keyframe;
  - a frame whose best patch costs more than a whole picture is a keyframe.
  - Frames with the same pixels are one frame, across animations and the
    daruma's eye states.
- The art scripts are unchanged. They still draw whole frames, and the
  build checks that every patch chain gives back exactly that picture.
- On the device, `FrameCanvas` holds the persona's pixels and which
  frame they are. To show a frame, it applies the patches from the frame
  it holds, when that frame is on the chain. Otherwise it starts from the
  keyframe. It returns the box that changed.
- `SpritePersona` keeps the room behind the persona in a buffer
  (`under_`), composed again only when the window step, sky, plant stage,
  wilting or rug day changes. When only the persona moved,
  `draw_delta()` sends just the patch box: the canvas over the room,
  where it differs from the screen. A blink, a wink or a new animation
  rebuilds the canvas from its keyframe and sends what differs in it.
- Flat personas (no backdrop) and picture personas keep whole pictures.
- Sizes for the frames, at full color (gray4, mono):

  | Persona        | Frames | Whole pictures | Keyframes and patches |
  |-------------|--------|----------------|-----------------------|
  | Pixel corgi | 41     | 37.9 KB        | 13.0 KB (9.3, 7.8)    |
  | The Boss    | 31     | 37.4 KB        | 11.0 KB (7.8, 5.8)    |
  | Daruma, 3 eye states | 119 | 79.8 KB  | 16.9 KB (13.7, 11.1)  |

- The canvas and the room buffer cost RAM, both in PSRAM: 3 bytes per
  persona pixel, and one more view-sized frame buffer.

**Looks per goal stage and one-shot animations** (`daruma_sprites`).

- `pixel_art: goal: {started: ..., done: ...}` names the script's persona for
  each goal stage. The daruma has one per number of painted eyes. The
  personas must share the room, the window, the plant and the rug colors.
- Behaviors see each animation name once. The device keeps a map per
  stage from that name to the stage's animation. A stage without an
  animation uses the nearest stage that has it, so `Paint`, drawn only
  for one and two eyes, also covers `none`.
- `play_once: [Paint]` plays an animation once and holds its last frame.
  The `paint` reaction lasts 2.7 s; the daruma's Paint lasts 2.66 s and
  ends on the new eyes' Neutral frame.

**The Persona select** stores the chosen persona by its id (an FNV-1a hash). So a
new persona anywhere in the list, or a renamed one, keeps the choice. Its
options follow the config order: the first persona package in the device
yaml is the default.
`legacy_options` lists the options of an older build that stored a
position, so an update keeps that choice too.

**Focus ring** (`components/daruma/focus.h`, host-tested).

- `device.uses_focus()` is true when the board's navigation has both
  `next` and `prev`. The BOX-3 with touch has neither, so it looks and
  works as before.
- The menu keeps a `FocusRing` for the dock and one for the board:
  - NEXT and PREV move it, with wrap-around, and the board follows it from
    page to page;
  - SELECT opens the focused item;
  - the ring is drawn in `theme.focus_color()`: a ring around the dock
    button, and a rounded frame with a gap around the tile.
- An open app gets NEXT, PREV and SELECT through `App::input`, with x and
  y set to -1. When it returns false for NEXT or PREV, the menu sends
  SWIPE_UP or SWIPE_DOWN instead, so a scrolling app needs no extra code.
  `AppView::focus` tells the app to draw its focus.
- Tasks moves a focus over its rows, keeps it in view, and checks off the
  focused row with SELECT. SELECT retries after a failure.
- Calendar's agenda moves a focus over its rows with NEXT and PREV, and
  SELECT opens the focused row's day. In the day view, NEXT and PREV
  change the day; SELECT pages through the events, wraps to the top, or
  retries after a failure.
- A theme can set `focus:`. Without it, the accent is used.
- The build: a board without touch that includes the menu must bind
  `menu.open` to something. Otherwise the build fails, since the menu's
  own default is a tap.
- `board_box3_buttons.yaml` drives the BOX-3 by its two buttons:
  - next is `top.press` and prev is `top.double`;
  - select is `home.press`, back is `home.double` and close is
    `home.hold`.
- The BOX-3 hardware now lives in `board_box3_hardware.yaml`, which both
  board files include.

Prompts use the layout and the focus ring too (see Prompts, as built).

## E-ink and slow screens

The board declares a **display profile**:

```yaml
display_profile:
  colors: full        # full, gray4 or mono
  animate: true       # false: still frames only
  min_frame: 33ms     # e-ink: several seconds
  partial_refresh: true
  full_refresh_every: 20
```

- The render loop already redraws only when something changed
  (`needs_redraw`, `draw_delta`). It becomes fully invalidate-driven. A
  scheduler caps the frame rate and groups changes, and on e-ink it does a
  full refresh every N partial ones.
- Each behavior has a **still** frame: the animation's first frame, or one
  the art names. With `animate: false`, personas show only stills, and
  blinks, wags and idle drift stop.
- Themes get a mono variant. The Python art pipeline quantizes and dithers
  sprites for gray or mono screens at build time, the same way it compresses
  them now.
- Text that changes over time, such as clocks and countdowns, updates once a
  minute on slow screens.

### As built

The board declares the profile under `daruma:`:

```yaml
daruma:
  display: s3_box_lcd
  display_profile:
    colors: full           # full, gray4 or mono
    animate: true
    min_frame: 100ms       # 10 ms to 60 s
    partial_refresh: true
    full_refresh_every: 0  # 0 = never; needs partial_refresh
```

The build fails on `animate: true` with `min_frame` of 1 s or more. It also
fails on `full_refresh_every` without `partial_refresh`
(`registry.check_profile`).

**Frames** (`FrameScheduler` in `profile.h`, host-tested).

- `Device::loop()` draws when something asked for a frame, no sooner than
  `min_frame` after the last one. It replaces core's 100 ms polling
  interval. On the BOX-3, `min_frame` is 100 ms, so the pace is the same.
- `request_frame()` draws soon, even in a voice phase. The `draw_display`
  script calls it, so voice phases still get one still frame each.
- `request_redraw()` and the persona's own motion are drawn only while core's
  frame gate allows: no voice phase up, and not still booting.
- Requests inside one `min_frame` make a single frame.
- `full_frame()` is true for the first frame, for every frame without
  partial refresh, and for every `full_refresh_every`-th frame. On those,
  `draw_idle_delta()` gives way to a full draw.
- An e-ink driver with its own full-update setting
  (`full_update_every`) should get the same number.

**Still screens and slow screens.**

- `animate: false` changes the hub, not the personas:
  - `draw_idle()` and `draw_persona()` ask the persona for `draw_still()`;
  - `needs_redraw()` asks only whether the state changed;
  - `blink`, `wink` and `look_around` do nothing.
  So the sprite cycles, the window's rain, the eye moods and the
  celebrate winks all stop.
- `profile().slow()` is true when `min_frame` is 1 s or more. The pomodoro
  then shows "12m" and the voice timer "12 min". Both redraw only when a
  minute turns over.

**Gray and mono.**

- `Theme::for_mode()` derives the theme from luminance: mono is a
  threshold at 128, and gray4 rounds to 0, 85, 170 or 255. The hub swaps
  each persona's theme for it at setup.
- Readable pairs are kept apart: ink on the panel, titles on the frame,
  dock text on the dock, and the focus on the frame. Where both sides come
  out the same gray, the foreground flips to black or white.
- A theme's `mono:` colors override the derived ones.
- `theme.fit(c)` and `theme.on(bg, fg)` let the menu and the badge adapt
  their own colors.
- Module colors from `theme.color()` come out in grays too.
- At build time, `sprite.py` reduces every picture to the screen's grays
  by the same rule (`reduce_colors`). The edge strips are reduced as well.
  On the device, `SpritePersona` reduces the composed room the same way,
  which covers the painted sky. The persona's frames come reduced from
  the build, patches included.
- The weekday rug colors are left out in gray, so the rug keeps the room's
  own color.
- A dither was tried and dropped. A 4x4 ordered dither turned the corgi's
  mid-tone wall and fur into noise at 106x80. A plain threshold reads as
  a clear silhouette.

**Proof without hardware.**

- `examples/` holds three build checks. Each one compiles next to
  `box3.yaml`:
  - `variant_wide.yaml`: 480x272, with larger fonts;
  - `variant_square.yaml`: 240x240;
  - `variant_mono.yaml`: two buttons, mono, stills, a 5 s `min_frame`,
    and a full refresh every 20 frames.
  The wide and square checks are the BOX-3 with the display's
  `dimensions` overridden. They compile and pass the registry checks, but
  that panel can't show them.
- `tests/preview_screens.py` draws the idle corgi, the dock, the app
  board and Tasks at 320x240, 480x272, 240x240 and in mono. It takes its
  regions from `test_layout --json`, which runs `layout.h` itself.

## Order of work

1. **Now.** Calendar and Tasks apps, and a focus animation for the corgi.
   Flash the current build and check the menu, themes, sounds and fonts on
   the device.
2. **States and behaviors.** Done. The registry, the build checks, and
   porting the personas. Sounds become reactions. Pomodoro sets the `focus`
   and `break` activities, which shows the corgi's focus animation. Shared
   signals replace `World`, and persona params arrive.
3. **Modules.** Done. `Module`, app switches, device settings and the
   `apps:` order. Port pomodoro, stats, calendar and tasks. Named inputs,
   bindings and the board package.
4. **Prompts.** Done. show, update, close and ask, plus the answer event.
   A quiz script and a doorbell blueprint as the first two users.
5. **Layout and button input.** Done. Regions, size classes, the focus ring
   and edge-extended pixel art.
6. **Own repo.** Done. The framework is this repository. Devices pull
   its packages from git.
7. **Display profiles and e-ink.** Done in software: the profile, the frame
   scheduler, stills, and gray and mono themes and art. A real e-ink panel
   still needs a driver package and a device test.
