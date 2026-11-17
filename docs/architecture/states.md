# States and reactions

> Incomplete. Moved from the old ARCHITECTURE.md. Add what you learn
> when a task needs more, and keep it under 300 lines.

What the core and the modules ask a persona to show, and how a persona answers.

## The model

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
  celebrate and paint (see the `goal` signal in [signals.md](signals.md)). Pomodoro adds focus, break, focus_done, goal, paused,
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
