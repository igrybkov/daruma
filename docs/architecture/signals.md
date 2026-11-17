# Looks that follow the world

> Incomplete. Moved from the old ARCHITECTURE.md. Add what you learn
> when a task needs more, and keep it under 300 lines.

How data from modules and Home Assistant reaches a persona's look: shared signals, persona params and looks per goal stage.

## Shared signals

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

The corgi draws `progress` as the plant growing.
The Boss could draw it as a pile of finished paperwork, and the eyes persona as
a small bar. A module or HA sets a signal through the device. A persona only
reads it.

Several sources can feed `progress`. Each source has a name and a weight in
the device yaml. HA can also take the signal over (`override`).

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

## Persona params

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

As built (`src/esphome/components/daruma/persona.py`):

- The prefix is the persona's id: `pixel_corgi.rug`, `eyes.color`.
- Each persona component declares its own params in Python. The types are
  `choice` and `bool`. In C++ they are ints.
- In yaml: `params: {rug: plain}`, or `rug: {value: weekday, expose: true}`.
- An exposed choice becomes a select, "Pixel corgi rug". An exposed bool
  becomes a switch.

## Looks per goal stage and one-shot animations

In `daruma_sprites`.

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
