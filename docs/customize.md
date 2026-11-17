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

The library is the Python package `daruma_pixel`
([pixel/daruma_pixel/](../pixel/daruma_pixel/)). It has two engines:

- **`pet`**: a front-facing pet sitting in a scene. A **breed** is a short
  module of colors and shapes: coat, ears, head, muzzle, tail, markings.
  The dogs share `dog.py` (nose, tongue, button ears, sitting pretty), the
  cats share `cat.py`. See [jack_russell.py](../pixel/daruma_pixel/jack_russell.py)
  and [tabby_cat.py](../pixel/daruma_pixel/tabby_cat.py).
- **`desk_boss`**: a person behind a desk. A **look** sets skin, hair,
  clothes and desk props. The desk and chair are `office.py` props; the
  look module says where the desk stands. See
  [the_boss.py](../pixel/daruma_pixel/the_boss.py).

The daruma is its own module ([daruma.py](../pixel/daruma_pixel/daruma.py)):
a persona can also draw everything itself, as long as it offers the names
below.

### Rooms

The scene behind a pet is swappable. Three come with Daruma:

- `room.Room`: a cozy room with plank walls, a window, a shelf and a
  weekday rug. Its colors are fields, so each pet can have its own.
- `living_room.LivingRoom`: a couch (`couch.py`), an arched window and a
  ceiling hook.
- `studio.Studio`: an 80s portrait studio with a backdrop, a window sill
  and a velvet drape.

A scene has a window (the device draws the sky in its glass, from the
"Window" select), spots, and colors that change by weekday
(`RUG_COLORS`, `RUG_BY_WEEKDAY`). A spot is a named place in the scene
(`scene.Spot`): `Room` has "floor" and "shelf", `LivingRoom` has "seat"
and "hook", `Studio` has "floor" and "sill".

The persona puts things on the spots. The pet sits on one. A prop that
grows with the `progress` signal and wilts when you fall behind
(`scene.Grower`: `plant.POTHOS`, `spider_plant.SPIDER_PLANT`,
`cat_grass.CAT_GRASS`, `bonsai.BONSAI`) stands on another:

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
| `background()`, `foreground(pose)`, `scene(pose)`, `WINDOW` | the layers; a pet takes them from its `Pet` and its scene (see `corgi_persona.py`) |
| `ANIMATIONS` | animation name -> list of (pose, ms); `Neutral` is required |
| `BLINKS`, `WINKS` | animation name -> the single frame the hub flashes for a blink or a wink |
| `PROPS` | optional: activity -> boxes where its props stand, for the props tests |
| `PERSONA` | `Spec(name, background=...)`: says the module is a persona |

`PERSONA` is what makes the module a persona. Nothing else lists it:
[personas.py](../pixel/daruma_pixel/personas.py) finds every persona
module of the library, and a `pixel_art:` entry names yours.

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

- **Order.** `daruma: apps: [tasks, calendar, weather, stats]` sets the
  order on the app board.
- **On and off.** Each app gets an "App: Name" switch in Home Assistant.
  An app that is off leaves the board and stops fetching.
- **Copies.** Include `app_tasks.yaml` or `app_calendar.yaml` again with
  another `app_id` for a second list or calendar set:

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

A module in C++ adds screens, layers and apps. The model to follow is
the pomodoro ([pomodoro.yaml](../packages/pomodoro.yaml)): its states,
actions, buttons, menus, tap areas and theme keys are all in its
`daruma: modules:` entry. [Modules](architecture/modules.md)
lists everything a module may contribute.

## Prompts from Home Assistant

Home Assistant can put a card on the screen and get the answer back: a
doorbell with Unlock and Talk, a quiz with a countdown, a yes/no question.
See [prompts.md](prompts.md) and the [blueprints](../blueprints/).

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
