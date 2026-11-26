# Make it yours

Daruma is a starting point. Take what you like, change the rest, and send
back what others could use. This page shows what you can change and where.
It is written for people and for coding agents. For how it works inside,
see [architecture/](architecture/README.md).

- [Where changes go](#where-changes-go)
- [States: what the device can show](#states-what-the-device-can-show)
- [Personas](#personas)
- [Pixel art: pets, rooms and props](#pixel-art-pets-rooms-and-props)
- [Reactions during an activity: `during:`](#reactions-during-an-activity-during)
- [Sounds](#sounds)
- [Random events: quirks now and then](#random-events-quirks-now-and-then)
- [Themes and words](#themes-and-words)
- [Apps](#apps)
- [Menus](#menus)
- [Buttons and gestures: bindings](#buttons-and-gestures-bindings)
- [Parts of the screen that lead somewhere: targets](#parts-of-the-screen-that-lead-somewhere-targets)
- [Signals: progress, wellbeing, sky, goal](#signals-progress-wellbeing-sky-goal)
- [Your own module](#your-own-module)
- [Prompts from Home Assistant](#prompts-from-home-assistant)
- [Other screens and boards](#other-screens-and-boards)
- [Keep your own parts in your own repository](#keep-your-own-parts-in-your-own-repository)
- [Check your change](#check-your-change)

## Where changes go

There are three places:

1. **Your device file.** Which parts are in, the device-wide theme, menus,
   bindings, targets and progress weights. Most changes go here.
2. **Your own packages.** A persona, a module or an app of your own. Keep
   them next to your device file, or in a repository of your own (see
   [private-packages.md](private-packages.md)).
3. **A fork of this repository.** Changes to the framework itself. Send
   them back as a pull request when others could use them.

Daruma checks the whole config at build time. A typo in a state, an
action, a theme key or a menu item fails the build with a message that
names the choices. Mistakes show up on your computer, not on your desk.

## States: what the device can show

The core and the modules tell the persona what is going on. The persona
decides how to show it. Every state has one of three kinds:

| Kind | Lasts | States |
|---|---|---|
| mood | minutes | neutral, happy, sad, loved, scared, sleepy, sleeping |
| activity | while it runs | listening, thinking, talking, alarm, offline, error, waking, attention; pomodoro adds focus and break |
| reaction | one animation | petted, startled, celebrate, paint; pomodoro adds focus_done, goal, paused, focus_stopped, break_over; tasks adds task_done and tasks_done |

The persona shows the reaction if one plays, else the top activity, else
the mood. Every state but `neutral` has a fallback. A persona that has no
look for a state shows its fallback, and so on down the chain. So a new
persona needs only `Neutral` to work, and gets better with every
animation you add. The build log lists each fallback it took:
`pixel_corgi: focus -> neutral`.

The list lives in `src/esphome/components/daruma/registry.py` (the core) and in each
module's declaration. A module adds states of its own; see
[Your own module](#your-own-module).

The showcase demos show every state on every persona. A test fails when a
new state is not in them (see [testing.md](testing.md)).

## Personas

A persona is one entry in one of three components. Each entry adds an
option to the "Persona" select in Home Assistant. Swipe left or right on
the screen to change it on the device.

| Component | What it draws | Start from |
|---|---|---|
| `daruma_sprites` | pixel art drawn by a Python script at build time | [persona_jack_russell.yaml](../packages/persona_jack_russell.yaml) |
| `daruma_images` | PNG pictures, one per state | [persona_images.yaml](../packages/persona_images.yaml) |
| `daruma_eyes` | eyes drawn from shapes | [persona_eyes.yaml](../packages/persona_eyes.yaml) |

Every persona entry takes the same shared options:

```yaml
daruma_sprites:
  - id: my_fox                  # also the prefix of its params: my_fox.rug
    name: Fox                   # the option in the Persona select
    pixel_art: { script: ../pixel/fox.py, persona: fox }
    behaviors:                  # optional: per state, when the name alone is not enough
      celebrate: { animation: Happy, sound: goal }
      petted: { animation: Loved, sound: pet, say: "Yip!" }
    during:                     # optional: reaction looks while an activity runs
      focus: { Loved: LovedFocus }
    params:                     # the persona's own options
      rug: { value: weekday, expose: true }
    theme: { style: paper, frame: "C46A2A" }   # menu and app colors for this persona
    sounds: { pet: [ { note: A5, to: E6, seconds: 0.08 } ] }
```

- **Behaviors.** A state finds the animation named like it, in any case:
  `focus` finds `Focus`. Name a behavior only to pick another animation,
  a sound, or words (`say:` shows a bubble).
- **Params.** Options only this persona has, such as a rug that follows
  the weekday. With `expose: true` each is a setting on the device's page
  in Home Assistant ("Jack Russell throw").
- **Looks per goal stage.** A pixel persona may name a look per stage of
  today's goal: `pixel_art: goal: {started: ..., done: ...}`. The daruma
  uses this to paint its eyes. See
  [persona_daruma.yaml](../packages/persona_daruma.yaml).
- **One-shot animations.** `play_once: [Paint]` plays an animation once
  and holds its last frame.

### Pictures

`daruma_images` shows a PNG per state, up to the screen size, centered.
Name the files after the states: `neutral.png`, `happy.png`, `sad.png`,
`loved.png`, `scared.png`, `sleepy.png`, `sleeping.png`, `listening.png`,
`thinking.png`, `talking.png`, plus optional `neutral_blink.png`,
`neutral_wink.png` and so on. Only `neutral.png` is required. Copy
[persona_images.yaml](../packages/persona_images.yaml) next to your device
file, point `art:` at your folder, and drop the frames you don't have.

Pictures are stored as runs of flat color. A set of simple flat-color art
takes 50 to 100 KB. Photos and gradients do not compress well.

### Eyes

`daruma_eyes` draws two eyes that blink, glance, wink and change shape
with the mood. Its `color` param sets the color. It needs no art at all.

## Pixel art: pets, rooms and props

The pixel personas are Python. While the firmware compiles, a script draws
every frame of every animation. The device stores the frames as
keyframes and small patches, so the animation frames of a pixel persona
take 11 to 17 KB of flash (see the table in
[Rendering](architecture/rendering.md)).

The pixel art comes in three layers. Each is a set of Python packages
under [pixel/](../pixel/):

- **Drawing**: `daruma_pixel`
  ([pixel/daruma-pixel/](../pixel/daruma-pixel/)): pixelkit, scenes and
  spots, effects, and the persona framework.
- **Shapes**: `daruma_shapes.<family>`, generic parts any persona can use.
  `pets` ([pixel/shapes-pets/](../pixel/shapes-pets/)) is the pet rig: a
  front-facing pet sitting in a scene. A **breed** is a short module of
  colors and shapes: coat, ears, head, muzzle, tail, markings. The dogs
  share `dog.py` (nose, tongue, button ears, sitting pretty), the cats
  share `cat.py`. `office` ([pixel/shapes-office/](../pixel/shapes-office/))
  is a person behind a desk. A **look** sets skin, hair, clothes and desk
  props; the desk and chair are props in `furniture.py`. `rooms` and
  `plants` follow below.
- **Personas**: `daruma_personas.<name>`, one package each. A persona
  picks shapes, sets their colors, and writes its animations. See
  [persona-jack-russell](../pixel/persona-jack-russell/),
  [persona-tabby-cat](../pixel/persona-tabby-cat/) and
  [persona-the-boss](../pixel/persona-the-boss/).

The daruma draws its own actor
([persona-daruma](../pixel/persona-daruma/)): a persona can also draw
everything itself, as long as it offers the names below. A cat is generic
and fits any room. A tabby's colors and its studio are the tabby
persona's own.

### Rooms

The scene behind a pet is swappable. Three come with Daruma, in
`daruma_shapes.rooms`:

- `cozy_room.Room`: a cozy room with plank walls, a window, a shelf and a
  weekday rug. Its colors are fields, so each pet can have its own.
- `living_room.LivingRoom`: a couch (`couch.py`), an arched window and a
  ceiling hook.
- `studio.Studio`: an 80s portrait studio with a backdrop, a window sill
  and a velvet drape.

A scene has a window (the device draws the sky in its glass, from the
"Window" select), spots, and colors that change by weekday
(`RUG_COLORS`, `RUG_BY_WEEKDAY`). A spot is a named place in the scene
(`daruma_pixel.scene.Spot`): `Room` has "floor" and "shelf", `LivingRoom`
has "seat" and "hook", `Studio` has "floor" and "sill".

The persona puts things on the spots. The pet sits on one. A prop that
grows with the `progress` signal and wilts when you fall behind
(`daruma_pixel.scene.Grower`, in `daruma_shapes.plants`:
`pothos.POTHOS`, `spider_plant.SPIDER_PLANT`, `cat_grass.CAT_GRASS`,
`bonsai.BONSAI`) stands on another:

```python
_pet = Pet(CORGI, Room(), seat="floor", plant=POTHOS, plant_spot="shelf")
```

Props and actors know no scene, so any prop fits any scene with a spot
for it.

### Poses, animations and props

A `Pose` says where the parts go and which features show: eyes, mouth,
ears, tail, extras like hearts or zzz, and a `prop` such as a book or a
ball. An animation is a list of `(pose, milliseconds)`. A persona module
offers:

| Name | What |
|---|---|
| `background()`, `foreground(pose)`, `scene(pose)`, `WINDOW` | the layers; a pet takes them from its `Pet` and its scene (see `daruma_personas.corgi`) |
| `ANIMATIONS` | animation name -> list of (pose, ms); `Neutral` is required |
| `BLINKS`, `WINKS` | animation name -> the single frame the hub flashes for a blink or a wink |
| `PROPS` | optional: activity -> boxes where its props stand, for the props tests |
| `PERSONA` | `Spec(name, background=...)`: says the module is a persona |

`PERSONA` is what makes the module a persona. Nothing else lists it:
`discover()` in
[personas.py](../pixel/daruma-pixel/src/daruma_pixel/personas.py) finds
every persona in the `daruma_personas` namespace, and a `pixel_art:` entry
names yours.

```python
from daruma_pixel.personas import Spec

# Layers and animations default to this module; name others with
# Spec(..., layers=..., animations=...).
PERSONA = Spec("fox", background=0x3A2A20)
```

Preview it without a device. This writes every layer and a sheet of every
frame:

```sh
uv run python -m daruma_pixel.personas /tmp/personas fox
```

[agents/new-persona.md](agents/new-persona.md) walks through a new persona end to end.

## Reactions during an activity: `during:`

A reaction plays over the activity under it, and the activity stays on.
Petting the corgi while it reads would drop its book for two seconds.
`during:` names other animations for that case:

```yaml
    during:
      focus: { Petted: PettedFocus, Scared: ScaredFocus, Celebrate: CelebrateFocus }
```

While focus runs, any reaction that would play `Petted` plays
`PettedFocus`. Draw those with the prop in place. The tests
`tests/test_props.py` and `tests/test_pet_props.py` check that the props
stay put in every frame, for every persona whose art declares `PROPS`.

## Sounds

Each persona can replace any built-in sound with its own: `start`,
`pause`, `stop`, `focus_done`, `goal`, `break_over`, `pet`, `timer`,
`notify` and `urgent`. A sound is a short list of synth steps:

```yaml
    sounds:
      pet:
        - { note: A5, to: E6, seconds: 0.06, duty: 0.25, attack: 0.002, release: 0.02 }
        - { rest: 0.06 }
        - { arp: [E5, G5, C6], step: 0.07, duty: 0.25, last: 0.2 }
```

`to` glides, `duty` sets the tone (0.5 is a full square wave), `vibrato`
wobbles, `arp` runs through notes. A sound lasts 2 seconds at most. The
options are documented in
[src/esphome/components/daruma/sounds.py](../src/esphome/components/daruma/sounds.py). A
behavior can also pick any sound by name for any state.

## Random events: quirks now and then

A persona can play quirks on its own, now and then: a paw lick, a
sneeze, a line in a bubble, a trip away from the desk. Sprite and
images personas take `random_events:`. The eyes take none.

```yaml
daruma_sprites:
  - id: pixel_corgi
    random_events:
      lick_paw: { animation: LickPaw, frequency: 9 }
      sneeze: { animation: Sneeze, sound: sneeze, frequency: 8 }
      snore: { say: ["Zzz", "zzz... squirrel..."], frequency: 9, when: { moods: [sleeping] } }
      walk_q:
        say: ["Walk time?", "Is it 5 yet?", "Leash? Leash!"]
        frequency: 8
        when: { between: "16:00-18:00", weekdays: [mon-fri] }
      bathroom: { enter: WalkOff, animation: Away, exit: WalkBack, for: 3min, frequency: 7 }
```

Event names use lowercase letters, digits and `_`. A persona has 32
events at most. The animations are the persona's own; they need no
state. The pixel corgi's are in
[quirks.py](../pixel/persona-corgi/src/daruma_personas/corgi/quirks.py).

| Key | What |
|---|---|
| `animation` | a one-shot plays it once; a spell loops it |
| `enter`, `exit` | a spell only: plays once before and after the loop |
| `for` | makes the event a spell, and sets how long it loops: 5 s to 2 h |
| `say` | 1 to 8 lines; one, picked at random, shows in a bubble for 4 s |
| `sound` | a built-in sound or one of the persona's `sounds:`; skipped while muted |
| `frequency` | 1 to 10, default 8 (see the table below) |
| `cooldown` | the shortest time between two plays: 1 min to 366 days; kept across a reboot |
| `when` | conditions (see below) |

A **one-shot** has an `animation`, a `say`, a `sound`, or any of them. A
**spell** has `for:` and an `animation`; `enter` and `exit` are
optional. Any gesture ends an event at once, and the gesture goes on as
usual. A tap during the corgi's trip brings it back with no walk back,
and opens the menu. A reaction, a menu, a prompt or a quiet activity
ends it too. `exit:` plays only when the spell runs its full time.

### How often

At random waits of 2 to 20 minutes, the device rolls. Each event that
could play rolls on its own. Its chance grows with the time it could
have played since it last rolled. Over time, it plays about once per
mean interval:

| Frequency | Mean interval |
|---|---|
| 10 | 10 min |
| 9 | 30 min |
| 8 | 2 h |
| 7 | 6 h |
| 6 | 1 day |
| 5 | 3 days |
| 4 | 7 days |
| 3 | 14 days |
| 2 | 30 days |
| 1 | 90 days |

The real rates fall below the table:

- One roll plays at most one event. With the 2 to 20 minute waits, a
  frequency 9 event reaches about 0.83 of its table rate, and frequency
  10 less.
- After each event, the device waits the min gap (15 min by default).
  Time counts only after the gap. So frequency 10 can't beat the gap.
- Time counts only while the event could play: its `when:` holds, the
  screen is free and its cooldown is over.

These always hold:

- No event plays while a menu, an app, a prompt, a voice phase or a
  reaction is up, or while HA is gone. A quiet activity, such as focus,
  blocks them too.
- While asleep, only events that list `sleeping` in `moods:` play.
- The same event never plays twice in a row. The one exception: it is
  the only event that could play, and twice its mean interval has
  passed.
- A screen that doesn't animate (`animate: false`) plays only events
  with no animation.

### Conditions: `when:`

The keys combine with AND. A list inside a key combines with OR.

| Key | Takes | Example |
|---|---|---|
| `dates` | `MM-DD` or `MM-DD..MM-DD`; a range may wrap the year | `dates: ["12-24..12-26", "04-01"]` |
| `weekdays` | `sun` to `sat`, or a range | `weekdays: [mon-fri]` |
| `between` | `HH:MM-HH:MM`, end not included; may wrap midnight; the end may be `24:00` | `between: "16:00-18:00"` |
| `at` | one `HH:MM` or a list (see below) | `at: ["09:00", "15:14"]` |
| `moods` | a list of moods | `moods: [sleeping]` |

Quote every time: YAML reads an unquoted `16:00` as a number, and the
build says so. Dates, weekdays, times, `at:` and cooldowns need the time
from HA. Until it comes, those events wait.

A short `between:` window rarely fires. A roll must land inside it, and
a one minute window gets a roll about one day in eleven. For "at this
time", use `at:`.

### At a set time: `at:`

An event with `at:` never joins the random rolls. In each minute it
names, the device rolls once for it, with this chance:

| Frequency | 10 | 9 | 8 | 7 | 6 | 5 | 4 | 3 | 2 | 1 |
|---|---|---|---|---|---|---|---|---|---|---|
| Chance | 100% | 95% | 85% | 70% | 55% | 40% | 25% | 15% | 5% | 1% |

```yaml
      pi_time:
        say: ["3.14159..."]
        frequency: 10
        when: { at: "15:14", dates: "03-14" }
```

`at:` combines with `dates`, `weekdays` and `moods`. With `between:` it
fails the build. A scheduled roll skips the min gap and the no-repeat
rule. If the screen is busy for the whole minute, the event waits for
its next minute.

### Pictures: say-only events

The images persona draws no animation, so its events only say, sound,
or both. `animation`, `enter`, `exit` and `for` fail the build there.
Pass them as the `random_events` var of
[persona_images.yaml](../packages/persona_images.yaml), as
[box3.yaml](../examples/box3.yaml) does for the Flat corgi:

```yaml
      - path: packages/persona_images.yaml
        vars:
          persona_id: flat_corgi
          persona_name: "Flat corgi"
          art: flat_corgi
          random_events:
            walk_q:
              say: ["Walk?", "Walkies?", "Is it walk time?"]
              frequency: 8
            snore:
              say: ["Zzz...", "Zzzz... biscuit..."]
              frequency: 9
              when: { moods: [sleeping] }
```

### On the device

The device file tunes the engine under `daruma: random_events:`. Every
key is optional:

```yaml
daruma:
  random_events:
    enabled: true                    # first value of the "Random events" switch
    tick: { min: 2min, max: 20min }  # the wait between random rolls: 30 s to 24 h
    min_gap: 15min                   # first value of "Min gap": up to 240 min
    liveliness: 100                  # first value of "Liveliness": 0 to 200 %
    time_id: daruma_time             # the clock
    event_id: daruma_event           # the event entity that fires random_event
    personas:                        # changes per persona, by its id
      pixel_corgi:
        sneeze: false                # drop an event
        lick_paw: { frequency: 6 }   # change one
        snack_q: { say: ["Snack?"] } # add one
```

- `false` drops an event. Naming one the persona lacks fails the build.
- A map changes only the keys it names. A new `when:` replaces the old
  one as a whole.
- A new name adds an event, with frequency 8. It needs an animation, a
  `say` or a `sound`.
- Any sprite or images persona can take new events this way, also one
  that declares none.

The build makes the engine only when a persona has events or
`personas:` has some. Else the device has no engine and no entities. To
leave it out on purpose:

```yaml
daruma:
  random_events: false
```

The engine needs `api:`. The persona's own events are still checked with
the engine off, so a typo always fails the build.

### In Home Assistant

Three settings, under the device's "Configuration". Each keeps its value
across a reboot. The device file sets the first value.

| Entity | What |
|---|---|
| Random events (switch) | off: no roll plays an event |
| Liveliness (number, 0 to 200 %) | scales every chance; 200 % plays about twice as often, 0 % never |
| Min gap (number, 0 to 240 min) | the shortest time between two events |

Each play fires `daruma_event` with type `random_event`, and the HA
event `esphome.daruma_random_event`:

```yaml
event_type: esphome.daruma_random_event
data:
  name: bathroom
  persona: pixel_corgi
  manual: "false"      # "true" when an action played it
```

The action `esphome.<node>_play_random_event` plays one now. `<node>` is
the ESPHome node name with `-` changed to `_`:

```yaml
- action: esphome.daruma_play_random_event
  data:
    name: sneeze       # "" picks one
```

Both kinds ignore the switch and Liveliness:

| | `name: sneeze` | `name: ""` |
|---|---|---|
| Picks | that event of the active persona | one event, weighted by frequency; never an `at:` event |
| Odds, `when:`, cooldown | skipped | hold |
| Min gap, no repeat | skipped | skipped |
| A busy screen, or an event playing | refused, with a warning in the log | refused, with a warning in the log |

A name the active persona lacks logs a warning too.

## Themes and words

Every persona sets how the menu and apps look while it shows:

```yaml
    theme:
      style: paper          # wood, paper or outline
      frame: "C48A52"       # the board around the cards
      edge: "6E4426"
      panel: "FBF7EE"       # the cards
      ink: "3A2A20"
      muted: "7A6656"
      title: "FBF7EE"
      accent: "5E7A58"
      dot: "8A5A32"
      dock: "FBF7EE"        # the dock buttons
      dock_ink: "3A2A20"
      dock_muted: "7A6656"
      icon_color: "00DCF0"  # optional: one color for every app icon
      apps:                 # optional: an app under another name or icon
        tasks: { name: Chores }
      colors: { pomodoro.plaque: "000000" }   # a module's colors
      words: { calendar.today: "Heute" }      # a module's words
```

Modules declare their color and word keys with defaults, such as
`pomodoro.focus` or `calendar.today`. Set the words to translate the menu
and the apps. A few status lines on the persona's screen ("No Home
Assistant", "Waking up...") are still fixed in `packages/core.yaml`. The device file can set them too, for every persona or
for one:

```yaml
daruma:
  theme:
    words: { pomodoro.ready: "Bereit" }
  themes:
    eyes:
      colors: { pomodoro.plaque: "000000" }
```

Lowest first: the module's default, the persona's `theme:`, the device's
`theme:`, the device's `themes: <persona id>`. An unknown key fails the
build.

## Apps

Built in:

| App | Package | What |
|---|---|---|
| Pomodoro page | [pomodoro.yaml](../packages/pomodoro.yaml) | the timer, today against the goal, this week, the streak |
| Tasks | [app_tasks.yaml](../packages/app_tasks.yaml) | today's tasks from a to-do list or a script; tap to check one off |
| Calendar | [app_calendar.yaml](../packages/app_calendar.yaml) | the Agenda of your coming events, and a day view |
| Weather | [app_weather.yaml](../packages/app_weather.yaml) | now, today's high and low, rain, wind, the next hours |
| Controls | [app_controls.yaml](../packages/app_controls.yaml) | a few HA entities with their live state; a tap toggles or runs one |

- **Order.** `daruma: apps: [tasks, calendar, weather, stats]` sets the
  order on the app board.
- **On and off.** Each app gets an "App: Name" switch in Home Assistant.
  An app that is off leaves the board and stops fetching.
- **Controls.** List the tiles in the package's `tiles` var. A tile is an
  entity, a label and an optional icon:

  ```yaml
      - path: packages/app_controls.yaml
        vars:
          tiles:
            - { entity: light.desk, label: Desk }
            - { entity: scene.movie, label: Movie, icon: "mdi:movie" }
            - { entity: media_player.office, label: Music }
            - { entity: sensor.office_co2, label: CO2 }
  ```

  The header of [app_controls.yaml](../packages/app_controls.yaml) lists
  what a tap does for each kind of entity.
- **Copies.** Include `app_tasks.yaml`, `app_calendar.yaml` or
  `app_controls.yaml` again with another `app_id` for a second list,
  calendar set or page of controls:

  ```yaml
      - path: packages/app_calendar.yaml
        vars: { app_id: calendar_work, app_name: Work, calendars: calendar.work }
  ```

  [examples/variant_apps.yaml](../examples/variant_apps.yaml) builds two of
  each.
- **Your own app.** An app is a C++ class with its own screen, registered
  in a module's setup. [src/esphome/components/daruma_weather](../src/esphome/components/daruma_weather/)
  is a compact model to copy: one component, one package, one theme.

## Menus

A menu is a named list of dock buttons. A tap on the persona opens `main`.

```yaml
daruma:
  menus:
    main: [pomodoro, tasks, calendar]
    quick: [pomodoro.skip, pomodoro.stop, stats, more,
            { label: Lights, icon: "\U000F0335", event: desk_lights }]
```

An item is an app id, a module (its buttons for the moment, such as Focus
or Pause), an action, another menu, `more` (the app board), or a button
that fires the Home Assistant event `esphome.daruma_menu` with your
`event`. Automations in Home Assistant can do anything with that event.

## Buttons and gestures: bindings

The board names its inputs. On the BOX-3: `home` (the red circle), `top`
(the top-left button) and `screen` (touch). Bind any gesture to any
action a module offers:

```yaml
daruma:
  bindings:
    home.press: { action: pomodoro.toggle, when: idle }
    top.double: { action: menu.open, menu: quick }
    top.press: voice.start
    screen.stroke: daruma.pet
  expose_bindings: true    # each binding is also a select in Home Assistant
```

Gestures: `press`, `double`, `hold` for buttons; `tap`, `double`, `hold`,
`long_hold`, `swipe_left`, `swipe_right`, `swipe_up`, `swipe_down` and
`stroke` for touch. `when: idle` runs it only on the persona's own screen.
A press fires at once unless a double or a hold is bound to the same
input, so nothing waits that need not.

Actions in the box3 build include `daruma.pet`, `daruma.next_persona`,
`daruma.previous_persona`, `daruma.close_message`, `voice.start`,
`menu.open`, `menu.app:<id>`, `pomodoro.toggle`, `pomodoro.start`,
`pomodoro.stop`, `pomodoro.skip`, `pomodoro.break`,
`pomodoro.long_break` and `pomodoro.custom`. A binding to an action that no
included module offers fails the build.

## Parts of the screen that lead somewhere: targets

Some parts of the persona's screen are tap areas: the pomodoro `plaque`,
the temperature `badge` and the calendar's `next_event` line. Send a tap
on one wherever you like:

```yaml
daruma:
  targets:
    plaque: { menu: pomodoro }     # or { app: stats }, { action: pomodoro.toggle }
    badge: none                    # a tap there is a tap on the persona
```

## Signals: progress, wellbeing, sky, goal

Personas show a few shared signals, each in their own way:

| Signal | From | Shown as |
|---|---|---|
| `progress` (0 to 10, and "behind") | modules or Home Assistant | the plant, the bonsai or the cat grass grows; it wilts when behind |
| `wellbeing` (0 to 10) | Home Assistant, `set_wellbeing` | the plant wilts at 2 or less |
| `sky` | the "Window" select | clear, cloudy, rain, snow or night in the window |
| `goal` | pomodoro | the daruma's eyes |
| weekday, hour | the clock | the rug color, the light |

`progress` takes any source. Weigh them in the device file:

```yaml
daruma:
  progress: { pomodoro: 1, plants: 1 }
```

Or let Home Assistant drive it: set "Progress source" to Custom, then
"Progress" and "Progress behind" from an automation. A watered plant, a
habit tracker, steps walked: anything Home Assistant knows can grow the
plant.

## Your own module

A module is a package that declares what it adds. A module in YAML can
add states, actions, button looks, default bindings and a progress source.
This one adds a reaction for a watered plant and an action Home Assistant
or a button can run:

```yaml
# plants.yaml, next to your device file
daruma:
  modules:
    - name: plants
      states:
        watered: { kind: reaction, fallback: loved, sound: pet, duration: 2s }
      actions:
        plants.watered:
          - lambda: |-
              id(daruma_hub).react(Daruma::StateId::WATERED);
              id(daruma_hub).set_progress("plants", 10);
      progress: [plants]
      buttons:
        plants.watered: { label: Watered, icon: "\U000F058C", color: "2E9E44" }

api:
  actions:
    - action: plants_watered
      then:
        - lambda: id(daruma_hub).run_action("plants.watered");
```

Every persona now has a `watered` state. Those without a `Watered`
animation show `loved`. Add `plants.watered` to a menu, or bind it.

An activity that wants no quirks on screen sets `quiet: true`. While
the module holds it, no random event plays, and one that plays ends.
Pomodoro's focus does this:

```yaml
      states:
        focus: { kind: activity, fallback: neutral, sound: start, quiet: true }
```

Only an activity can be quiet. A break is not quiet, so quirks may play
during one.

A module in C++ adds screens, layers and apps. The model to follow is
the pomodoro ([pomodoro.yaml](../packages/pomodoro.yaml)): its states,
actions, buttons, menus, tap areas and theme keys are all in its
`daruma: modules:` entry. [Modules](architecture/modules.md)
lists everything a module may contribute.

## Prompts from Home Assistant

Home Assistant can put a card on the screen and get the answer back: a
doorbell with Unlock and Talk, a quiz with a countdown, a yes/no question.
See [prompts.md](prompts.md) and the [blueprints](../blueprints/).

## Quiet hours and Do not disturb

Include [quiet.yaml](../packages/quiet.yaml) and the device can stay on a
bedside table. It adds these entities to Home Assistant:

| Entity | What it does |
|---|---|
| Do not disturb (switch) | Info prompts and messages from HA wait. Sounds goes off. A mark shows on the info line. |
| Quiet start, Quiet end (times) | Quiet hours. Overnight is fine. The same time twice turns them off. |
| Dim after (number, minutes) | The screen dims when nothing happened for that long: no input, prompt, message or voice. 0 never dims. |
| Quiet (binary sensor) | On inside quiet hours, for automations. |

In quiet hours, Do not disturb is on, the persona sleeps and the screen
goes dark. A tap or a button wakes the screen for 30 s. That first input
does nothing else. The wake word also wakes the screen, and it stays on
until 30 s after the reply. Quiet hours need the clock from Home Assistant.

Do not disturb is about cards. Urgent prompts still show, with their
sound. When Do not disturb ends, Sounds comes back as it was, and the
cards that waited show one by one, oldest first.

```yaml
daruma_quiet:
  quiet_hours: { start: "22:00", end: "07:00" }  # first values; HA changes them
  quiet_brightness: 0%     # the screen in quiet hours; 0% is off
  wake_for: 30s
  idle_brightness: 30%     # after "Dim after"
  dnd_during: [focus]      # messages also wait during these activities
  dnd_keep: 12h            # a card that waited longer drops
  dnd_release: 5           # at most this many wait
```

The screen never goes brighter than the "Screen" light is set. Bind
`quiet.dnd` to a gesture to toggle Do not disturb on the device.

## Other screens and boards

The layout follows the display size. Build checks cover:

- [variant_wide.yaml](../examples/variant_wide.yaml): 480x272;
- [variant_square.yaml](../examples/variant_square.yaml): 240x240;
- [variant_mono.yaml](../examples/variant_mono.yaml): black and white,
  buttons only, a slow screen like e-ink;
- [desktop.yaml](../examples/desktop.yaml): a window on your computer.

A new board is a package that names its display, its display profile
(colors, animation, frame rate) and its inputs, like
[board_box3.yaml](../packages/board_box3.yaml). Boards without touch need
buttons or a knob for back, next, previous and select.

## Keep your own parts in your own repository

Your personas, art, modules and apps can live in a git repository of
your own, private or public. The device file pulls Daruma and yours. See
[private-packages.md](private-packages.md).

## Check your change

Run it on your computer first. [testing.md](testing.md) shows the desktop
build, the demo recorder, the golden pictures and the pytest harness.
