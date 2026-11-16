# Run it on your computer

Daruma builds for your computer too. You can try a persona, record a demo
and test a screen without a device and without Home Assistant.

## What you need

uv, a C compiler, SDL2 and ffmpeg. On macOS: `brew install uv sdl2 ffmpeg`.
The builds use ESPHome 2026.10.2 through uv; you don't install it.

## The desktop build

[examples/desktop.yaml](../examples/desktop.yaml) runs Daruma in a window
(ESPHome's `host` platform and SDL), with the personas and apps of the
BOX-3 example:

```sh
cd examples && uvx --from esphome==2026.10.2 esphome run desktop.yaml
```

- The mouse is the finger: tap, hold, swipe, stroke.
- H is the red circle. T is the top button.
- It includes the packages from your checkout, so it shows your changes
  as they are, committed or not.

## Demo GIFs

One command records every persona in every scenario, into
[docs/demos](demos/):

```sh
uv run demos/record.py                                   # everything
uv run demos/record.py --personas Eyes --scenario emotions --mp4
```

The first run builds the firmware in a temp folder; later runs reuse it.
`--mp4` also writes an MP4 with the sounds. GIFs are twice the screen
size, or the scenario's `gif_scale`. They are kept under `--max-kb` by
lowering the frame rate, then the colors. The README shows the
`highlight` GIFs; [gallery.md](gallery.md) shows the rest.

## Scenarios

A scenario is a YAML list of steps in
[demos/scenarios/](../demos/scenarios/): wait, tap a point or a part by
its text, pet, press a button, set an entity, show a state, show a voice
screen, show a message or a prompt, add a caption, compare a snapshot,
expect a state or an event. [demos/scenario.py](../demos/scenario.py)
lists every step.

| Scenario | Shows |
|---|---|
| `highlight` | a short loop for the README's grid: idle, a pet, a celebration (`gif_scale: 1`) |
| `emotions` | every mood and reaction, with captions |
| `activities` | every activity: the voice assistant, the pomodoro's states, the menu and the Weather app in the persona's theme, a message, a doorbell card |
| `work` | the device at work, for the README: a focus block to the day's goal, Tasks, Calendar, Weather and a question from Home Assistant (Daruma only) |
| `tour` | a real day: idle, a pet, two focus blocks, the daily goal |
| `apps` | the menu, Tasks with a task checked off, Calendar |
| `prompts` | a doorbell card and a quiz |

`emotions` and `activities` are the showcase. They have
`showcase: true`, and together they must show every state the build
knows. `test_showcase_covers_every_state` in
[demos/test_daruma.py](../demos/test_daruma.py) asks the running build for
its states and fails when one is missing. So a new state, from the core or
from any module, needs a step in a showcase scenario:

```yaml
  - caption: Watered
  - show: watered
  - wait: 2.5
```

`show:` works for any state: it forces a mood, holds an activity or plays
a reaction. `show: ""` goes back to normal.

## Screen tests

```sh
uv run demos/record.py --test             # exit 1 on a difference
uv run demos/record.py --update-golden    # accept the new pictures
uv run --with pytest --with aioesphomeapi==46.30.0 --with pillow --with pyyaml \
    pytest demos                          # tests in Python
```

- **Time is fake.** A small library ([demos/fakeclock.c](../demos/fakeclock.c))
  gives the program a clock that only the runner moves, and a fixed random
  seed. The same scenario draws the same frames on every run, and a
  25-minute focus block takes a second.
- **The runner plays Home Assistant.** It talks to the build over the
  ESPHome API, sets entities, calls actions, and answers the calendar,
  to-do and weather requests with made-up data
  ([demos/demo_data.py](../demos/demo_data.py)).
- **Tests read like browser tests.** Find parts on screen by text or role
  and tap them:

  ```python
  def test_doorbell_unlock(device):
      device.show_prompt(id="door", title="Doorbell", options=["Unlock", "Ignore"], style="urgent")
      device.get_by_role("button", name="Unlock").tap()
      expect(device).to_fire_event("esphome.daruma_prompt", choice="Unlock")
  ```

  Parts of the persona that lead somewhere have role `target`:
  `device.get_by_role("target", "plaque").tap()`.
- **Golden pictures** live in `tests/golden/<persona>/<scenario or test>/`.
  A failed check writes the actual picture, a diff and a GIF of the run.
- **Pick a persona** with `@pytest.mark.persona("Pixel corgi")` (default
  Eyes), and a wall clock with `@pytest.mark.clock(epoch=..., timezone=...)`.
- **Another port or folder.** The runner uses port 6053 and a temp folder.
  When another runner holds them, pass `--port 6062 --out /tmp/mine` to
  record.py, or set `DARUMA_PORT=6062 DARUMA_WORK=/tmp/mine` for pytest.

A persona kept out of this repository can still be recorded and tested:
`--private-persona path/to/persona.yaml --personas "<its name>"`. Its GIFs
and pictures stay in the temp folder.

## Host tests

These need no ESPHome build:

```sh
uv run --no-project --with pillow --with pyyaml python -m unittest discover -s tests   # Python
tests/run_cpp.sh                                                                     # C++
```

They cover the registry and the build checks, the pixel art (every
persona's layers add up, props stay put during reactions, frames round
trip through the patch encoder), gestures, layout, prompts, the
pomodoro's rules, the calendar's agenda and the weather words.
`DARUMA_SKIP_PERSONAS=1` skips the tests that build every persona.

## Preview pixel art

```sh
cd pixel && uv run --with pillow python -m daruma_pixel.personas /tmp/personas jack_russell
```

This writes every layer and `sheet.png`: every frame of every animation,
as the screen shows it.
