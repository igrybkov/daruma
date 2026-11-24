# Random events

Quirks a persona plays now and then on its own: a paw lick, a sneeze, a
line in a bubble, a trip away from the desk. Example tasks: give a
persona a quirk, make one rarer on one device, keep events out of a new
activity.

The options are in
[customize.md: Random events](../customize.md#random-events-quirks-now-and-then).
This topic says how the engine runs.

## How it works

Three files in `src/esphome/components/daruma/` share the work:

| File | What |
|---|---|
| `random_events.py` | the rules in plain Python: `when:`, the event shape, the device's overrides, the encoding |
| `random_events.h` | the engine in plain C++: rolls, eligible time, the gates, playback |
| `random_events_component.cpp` | the ESPHome side: the clock, the hub, the HA action and events |

`persona.py` holds the persona schema (`RANDOM_EVENTS_SCHEMA`, and
`SAY_ONLY_EVENTS_SCHEMA` for the images persona). `registry.py` checks
each event's animations, moods and sound
(`resolve_random_events`). The hub's `random_events:` config is in
`__init__.py`.

### The build

- `daruma_sprites` and `daruma_images` take `random_events:`.
  `daruma_eyes` takes none.
- The build makes the engine only when a persona declares events or the
  device has `personas:` overrides. Else it emits no code and no
  entities. `daruma: random_events: false` leaves it out on purpose.
- A persona's own events are checked also with the engine off. A typo
  always fails the build.
- The engine needs `api:`, for its action and its events.
- Each persona's pool becomes a constant `EventDef` table. Animations
  become indices into the persona's animation list.
- A module's activity state with `quiet: true` blocks events while it is
  held anywhere on the activity stack. Pomodoro's `focus` is quiet.

### At run time

Every 5 s the component builds a `Context` (the clock, the mood, the
gates) and calls the engine:

1. `sample()`: each event that could play now gains 5 s of eligible
   time.
2. `roll_at()`: in a minute an `at:` event names, one scheduled roll
   for the `at:` events due then.
3. `roll()`: when the random wait (2 to 20 minutes) is over, one random
   roll for the other events.

A random roll gives each eligible event the chance
`1 - e^(-liveliness * eligible time / mean interval)`. Every event that
hits joins a list, and one of them plays. Eligible time restarts at
zero for every event that rolled.

Only the active persona's pool samples and rolls. The others keep their
eligible time frozen.

### Gates

An event is eligible only when all of these hold:

| Gate | Where |
|---|---|
| The "Random events" switch is on | `set_enabled()` |
| No menu, app, prompt or screen is up | `hub.ui_open()`, `hub.screen_shown()` |
| No voice phase, and the device is not booting | `hub.motion_open()` |
| HA is connected | `hub.ha_linked()` |
| No reaction plays, no quiet activity is held | `state_info()`, `hub.holds_activity()` |
| No event plays now | the playback phase |
| The min gap has passed since the last event | `Engine::open_()` |
| Its `when:` holds, and its cooldown is over | `when_holds()`, `cooled_down()` |
| It is not the last event played | `Engine::eligible()` |
| The display animates, or the event has no animation | `Context::animate` |

The last event may play again only when it is the only one that could,
and twice its mean interval has passed.

Dates, weekdays, times, `at:` and cooldowns need the clock. Until HA
sends the time, events with any of them sit out.

### Playback

`Playback` steps through one event. A one-shot plays its animation once.
A spell plays `enter:` once, loops `animation:` for `for:`, then plays
`exit:` once. A missing animation takes no time, so a say-only event is
over at once.

At the start, the component:

- sets the interlude on the persona (`Persona::set_interlude`);
- plays `sound:`, unless the device is muted;
- shows one `say:` line, picked at random, for 4 s;
- fires the HA events (`announce_`);
- stamps the cooldown and restarts the gap.

The interlude replaces the state's animation, except during a reaction.
`Hub::state()` does not change, so HA and `expect: {state: ...}` still
see the mood or the activity.

### What ends an event

`Playback::stop()` ends it at once, in any phase. No `exit:` plays.

| Trigger | How |
|---|---|
| Any gesture | a gesture filter at priority 110 stops the event; the gesture goes on to the bindings |
| A menu, app, prompt or screen, a voice phase, HA gone, a quiet activity | the gate check in `loop()` |
| A reaction | the gate check; the reaction then plays |
| A persona switch | `follow_persona_()` |

The filter sits above the ringing timer's filter (100). So a press on a
ringing timer also ends the event.

When an event stops, its own bubble goes with it. A bubble shown since
then stays.

### Home Assistant

The engine fires two things per play:

- the `daruma_event` entity with type `random_event` (no name: ESPHome's
  event entity carries only a type);
- the bus event `esphome.daruma_random_event` with `name`, `persona` and
  `manual` (`"true"` or `"false"`).

The `play_random_event` action calls `play()`. It ignores the switch and
Liveliness. A named call skips everything but the screen gates. An empty
name calls `Engine::pick()`. The table in
[customize.md](../customize.md#in-home-assistant)
lists what each skips.

## Conventions

- Event animations are the persona's own. They are not registry states.
  The build log names an event animation that is also a state's look.
- The engine has its own generator. It never draws from
  `esphome::random_uint32()`, so the blinks stay the same with or
  without it.
- Tunables live in YAML with defaults. The HA numbers keep their value
  across a reboot.
- Personas never ask for an event. Only the engine plays them.

## Traps

- **The rates fall below the table.** One roll plays at most one event.
  With the 2 to 20 minute waits, a frequency 9 event reaches about 0.83
  of its table rate, and frequency 10 less. Eligible time counts only
  after the min gap, so a busy pool plays each event less often still.
- **Frequency 10 can't beat the min gap.** Its mean is 10 minutes. The
  default gap is 15. Lower "Min gap" to see the table rate.
- **A short `between:` window rarely fires.** A roll must land inside
  it. A one minute window gets a roll about one day in eleven. Use `at:`
  for "at this time".
- **A blocked `at:` minute is lost.** The engine tries at each 5 s step
  while the minute lasts. Then the event waits for its next minute.
- **A rename resets a cooldown.** The cooldown key is a hash of
  `random_events/<persona id>/<event name>`. A new persona id or event
  name starts with no stamp.
- **An event with no `moods:` never plays while asleep.** Only events
  that list `sleeping` do. The mood is sleeping also while the mic is
  muted.
- **A named call during an event is refused.** The playing event counts
  as a busy screen. The log says "the screen is busy".
- **The standard desktop build has no engine.** A quirk at a random
  moment would move the screen tests' pictures. Scenarios that play
  events set `build: events`. See
  [testing.md](../testing.md#scenarios).

## Example to copy

`packages/persona_pixel_corgi.yaml` has one-shots, a sound, a sleeping
line, a weekday window and a spell. Its animations are in
`pixel/persona-corgi/src/daruma_personas/corgi/quirks.py`. For say-only
events, see the Flat corgi in `examples/box3.yaml`.

## Check it

```sh
uv run pytest tests/test_random_events.py tests/test_random_events_build.py
uv run pytest tests/test_random_events.cpp
uv run pytest demos/scenarios/random_events/
```

The first two check the rules and the build. The C++ test drives the
engine with a fixed seed. The scenarios play each corgi quirk and the
say-only lines on the `events` build. Open their golden pictures in
`tests/golden/pixel-corgi/random_events/` and look at every frame.
