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
make screens                   # golden and test-screens, in one run
```

All four run pytest. Each scenario file is a test per persona in its
`test_personas`, with the marker `scenario`: `make golden` runs those,
`make test-screens` the rest. `PERSONA=` and `SCENARIO=` narrow the
scenario tests. `PYTEST_ARGS=` passes options to pytest, for example
`make test-screens PYTEST_ARGS="-k corgi"`.

pytest itself takes the same options:

```sh
uv run pytest demos/scenarios/tour.yaml                     # one scenario, every persona
uv run pytest demos -m scenario --persona Eyes --scenario tour
uv run pytest "demos/scenarios/tour.yaml::tour[pixel-corgi]"
```

- **Time is fake.** A small library ([demos/fakeclock.c](../demos/fakeclock.c))
  gives the program a clock that only the runner moves, and a fixed random
  seed. The same scenario draws the same frames on every run, and a
  25-minute focus block takes a second.
- **The runner plays Home Assistant.** It talks to the build over the
  ESPHome API, sets entities, calls actions, and answers the calendar,
  to-do, weather and media player requests with made-up data
  ([demos/demo_data.py](../demos/demo_data.py)). Its three media players
  change when the device sends them a command, and it serves their album
  covers over HTTP itself. Every HA action the device calls is in
  `device.events` as `action:<domain.service>`;
  `expect(device).to_call_action("media_player.media_pause", entity_id=...)`
  checks one.
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
  A failed check writes the actual and expected pictures, a diff and a
  GIF of the run.
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

A persona kept out of this repository can still be recorded and tested.
Pass its package to either runner:

```sh
uv run demos/record.py --private-persona path/to/persona.yaml --personas "<its name>"
uv run pytest demos -m scenario --private-persona path/to/persona.yaml --persona "<its name>"
```

Its GIFs and golden pictures stay in the temp folder (or `$DARUMA_WORK`),
in `golden/`.

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
pomodoro's rules, the calendar's agenda, the weather words and the
media remote's rules.
`DARUMA_SKIP_PERSONAS=1` skips the tests that build every persona.

The C++ tests run through pytest too. `tests/conftest.py` collects each
`tests/test_*.cpp` as one test: pytest builds it and runs it. The
`cpp` marker picks them out. To run one test, name it:

```sh
uv run pytest tests/test_registry.py   # one Python file
uv run pytest tests/test_layout.cpp    # one C++ test
uv run pytest tests -m cpp             # every C++ test
```

### Persona frames

`tests/test_persona_frames.py` pins every picture each pixel persona
gives the device. It checks the room, every frame of every animation,
blinks and winks, and the plant in each stage, healthy and wilted. It
also checks the numbers in `persona.json`: offsets, the window, the
weekday colors and the frame times. It compares pixels, not file bytes.

The goldens live in `tests/golden/frames/<persona>/`, one PNG per
frame. A refactor of the pixel art must leave them all equal. A failed
check names each file that differs. It writes the actual and the
expected pictures to `$DARUMA_WORK/frames`, or to a temp folder.

```sh
make update-frames CONFIRM=1   # accept new persona frames
make update-golden CONFIRM=1   # persona frames and screens
```

The update keeps a golden whose pixels did not change. It removes the
goldens of frames a persona no longer draws. Open the changed pictures
before you commit them.

## Coverage

CI measures which lines the tests run, in jobs beside the tests. The
"Coverage report" job puts a table per area in its summary, and the
`coverage` artifact holds `files.md` (per file) and `coverage.lcov`.

Python has two numbers:

- **Tested**: the lines the Python host tests run.
- **Run in builds**: also the lines that run in any build. Every build
  runs the components' config checks and code generation, whether a test
  checks them or not. So this number is higher than what the tests check.

On a pull request, the job checks two rules
([tests/coverage_comment.py](../tests/coverage_comment.py)):

- **Changed lines**: at least 80% of the lines the pull request changes
  must run. Only lines that coverage measures count. A changed Python
  line counts only when a host test runs it. A pull request that changes
  no measured line passes.
- **No drop**: the C++ total and the Python tested total may each fall at
  most 0.5 percentage points below main's newest run. When main has no
  number to compare, the rule passes.

The job posts one comment, updated on every push. It shows each rule's
result with its numbers, the changed lines no test runs, the totals and a
table per area. Then the job fails if a rule failed. On a push to main
it only writes the report. On Linux with gcc, the same steps run locally:

- C++ host tests: `CXXFLAGS=--coverage DARUMA_CPP_OUT=<folder>` keeps
  the programs and their data, in `tests/conftest.py` and `test_frames.py`.
- Python host tests: `pytest tests --cov=components --cov=pixel`.
- Screen tests: `DARUMA_COVERAGE=<folder>` builds the desktop program
  with `--coverage`, in a build folder of its own, and runs ESPHome's code
  generation under coverage.py, which writes its data to that folder.
- [tests/coverage_report.py](../tests/coverage_report.py) reads the
  `.gcda` files with gcov and joins them with coverage.py's JSON. Give it
  the host tests' Python data alone with `--tested-python` for the tested
  number.

## Mutation tests

A passing test shows that code ran. A mutation test shows that a test
would notice a bug in it. The tool makes one small change at a time,
such as `<` to `<=` or `true` to `false`. Then it runs the host tests
that reach that code. When no test fails, the change "survived". That
is a gap in the tests.

```sh
make mutate                    # every mutant: a report
make mutate-diff               # only the lines changed since origin/main
make mutate-diff BASE=main     # or since another branch
```

`make mutate` takes about three minutes. It never fails on a survivor.
`make mutate-diff` takes seconds. It fails when a mutant on a changed
line survives. The changes count from the merge base, so commits that
land on main later are not yours. CI runs `make mutate-diff` on every
pull request. That check is not required.

- **Python**: [mutmut](https://github.com/boxed/mutmut) mutates the
  files in `[tool.mutmut]` in `pyproject.toml`. Only the files the host
  tests can load are there. The others import ESPHome.
- **C++**: `tests/mutate_cpp.py` mutates the component files that the
  C++ host tests include. It builds and runs every test that includes
  the file. A change that doesn't build doesn't count.

When a mutant survives, add a test that tells the change apart. Some
changes can't be told apart. For example, a bound that a later check
covers too. Mark those lines `# pragma: no mutate` in Python or
`// pragma: no mutate` in C++, and say why in a comment. In Python, a
comment line `# pragma: no mutate block, <why>` covers the statements
after it, to the end of their block. `make mutate-diff` starts from a
fresh `mutants/` folder, so it sees a new pragma. `make mutate` keeps
the folder between runs: delete `mutants/` after you add a pragma.

The Python runs skip lines that raise an error or add a build log line.
That text is for people, and tests match only a few words of it.

The host tests load each Python file under its path's name, such as
`components.daruma.registry` (`tests/component_loader.py`). mutmut needs
that name to find the tests for a mutant.

## Preview pixel art

```sh
uv run python -m daruma_pixel.personas /tmp/personas jack_russell
```

This writes every layer and `sheet.png`: every frame of every animation,
as the screen shows it.
