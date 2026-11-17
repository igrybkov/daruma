# Run it on your computer

Daruma builds for your computer too. You can try a persona, record a demo
and test a screen without a device and without Home Assistant.

## What you need

uv, a C compiler, SDL2 and ffmpeg. On macOS: `brew install uv sdl2 ffmpeg`.
On Debian or Ubuntu: `sudo apt-get install build-essential libsdl2-dev ffmpeg`,
and uv.
The builds use ESPHome 2026.10.2 through uv; you don't install it.

The commands below are make goals. `make` lists them all.
`make -n <goal>` prints the commands a goal runs, for a machine
without make.

## The desktop build

[examples/desktop.yaml](../examples/desktop.yaml) runs Daruma in a window
(ESPHome's `host` platform and SDL), with the personas and apps of the
BOX-3 example:

```sh
make desktop
```

- The mouse is the finger: tap, hold, swipe, stroke.
- H is the red circle. T is the top button.
- It includes the packages from your checkout, so it shows your changes
  as they are, committed or not.

## Demo GIFs

One command records every persona in every scenario, into
[docs/demos](demos/):

```sh
make gifs                                    # everything
make gifs PERSONA=Eyes SCENARIO=emotions     # one persona, one scenario
make gifs VARIANT=wide SCENARIO=highlight    # the wide screen
```

The first run builds the firmware in a temp folder; later runs reuse it.
For an MP4 with the sounds too, run record.py itself:
`uv run demos/record.py --personas Eyes --scenario emotions --mp4`. GIFs are twice the screen
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

A caption holds the steps it explains. It shows under the screen while
those steps run:

```yaml
  - caption: "Focus: one tap starts 25 minutes"
    steps:
      - wait: 0.6
      - tap: {text: Focus}
      - wait: 3
```

The GIFs mark every touch: a ring where a finger lands, a trail for a
swipe, and a label for the board's buttons. The ring shows a moment before
the tap, so give it a short `wait` first. The marks are drawn on the GIF's
frames only (`with_touches` in [demos/media.py](../demos/media.py)); the
golden pictures never see them.

| Scenario | Shows |
|---|---|
| `highlight` | a short loop for the README's grid: idle, a pet, a celebration (`gif_scale: 1`) |
| `emotions` | every mood and reaction, with captions |
| `activities` | every activity: the voice assistant, the pomodoro's states, the menu and the Weather app in the persona's theme, a message, a doorbell card |
| `work` | the device at work, for the README: a focus block to the day's goal, Tasks, the Calendar's Agenda, Weather and a question from Home Assistant (Daruma only) |
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
    steps:
      - show: watered
      - wait: 2.5
```

`show:` works for any state: it forces a mood, holds an activity or plays
a reaction. `show: ""` goes back to normal.

## Screen tests

```sh
make golden                    # exit 1 on a difference
make update-golden CONFIRM=1   # accept the new pictures
make test-screens              # tests in Python
make screens                   # golden, then test-screens
```

`PERSONA=` and `SCENARIO=` narrow `golden` and `update-golden`.
`PYTEST_ARGS=` passes options to pytest, for example
`make test-screens PYTEST_ARGS="-k corgi"`.

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
- **The same pictures on macOS and Linux.** The runner reads the screen's
  RGB565 colors and widens them to 8 bits itself, as SDL builds differ
  there. The desktop build turns off fused multiply-add
  (`-ffp-contract=off`), so text blends to the same colors with any
  compiler. `--update-golden` keeps a picture whose pixels didn't change.
- **Linux in Docker.** `make docker-test` runs the screen tests in
  Ubuntu 24.04, as CI does. Its caches live in Docker volumes, so a
  second run starts warm. `make docker-test DOCKER_CMD=bash` opens a
  shell there.
- **Pick a persona** with `@pytest.mark.persona("Pixel corgi")` (default
  Eyes), and a wall clock with `@pytest.mark.clock(epoch=..., timezone=...)`.
- **Another port or folder.** The runner uses port 6053 and a temp folder.
  When another runner holds them, pass `--port 6062 --out /tmp/mine` to
  record.py, or set `DARUMA_PORT=6062 DARUMA_WORK=/tmp/mine` for pytest.
  With make, `DARUMA_WORK=/tmp/mine` sets the folder for both.

A persona kept out of this repository can still be recorded and tested:
`--private-persona path/to/persona.yaml --personas "<its name>"`. Its GIFs
and pictures stay in the temp folder.

## Host tests

These need no ESPHome build:

```sh
make test-py    # Python
make test-cpp   # C++
make test       # both
```

They cover the registry and the build checks, the pixel art (every
persona's layers add up, props stay put during reactions, frames round
trip through the patch encoder), gestures, layout, prompts, the
pomodoro's rules, the calendar's agenda and the weather words.
`DARUMA_SKIP_PERSONAS=1` skips the tests that build every persona.

## Coverage

CI measures which lines the tests run, in jobs beside the tests. The
"Coverage report" job puts a table per area in its summary, and the
`coverage` artifact holds `files.md` (per file) and `coverage.lcov`. On
a pull request it posts one comment, updated on every push: how many of
the changed lines the tests run, the changed lines no test runs, and
each total against main's newest run
([tests/coverage_comment.py](../tests/coverage_comment.py)). It never
fails the build. On Linux with gcc, the same steps run locally:

- C++ host tests: `CXXFLAGS=--coverage DARUMA_CPP_OUT=<folder>` keeps
  the programs and their data, in `tests/run_cpp.sh` and `test_frames.py`.
- Python host tests: `pytest tests --cov=components --cov=pixel`.
- Screen tests: `DARUMA_COVERAGE=<folder>` builds the desktop program
  with `--coverage`, in a build folder of its own, and runs ESPHome's code
  generation under coverage.py, which writes its data to that folder.
- [tests/coverage_report.py](../tests/coverage_report.py) reads the
  `.gcda` files with gcov and joins them with coverage.py's JSON.

## Preview pixel art

```sh
uv run python -m daruma_pixel.personas /tmp/personas jack_russell
```

This writes every layer and `sheet.png`: every frame of every animation,
as the screen shows it.
