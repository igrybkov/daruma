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

The `screens` scenario has `stills: true`. It records no GIF. Each of
its snapshots becomes a PNG in [docs/demos/screens](demos/screens/), for
the README's table of screens. Run `make gifs SCENARIO=screens` after you
change how an app or a card looks. `tests/test_readme_screens.py` fails
when an app has no snapshot named after it (`calendar`, `calendar-day`),
or when a still is missing from the README.

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
  The time zone is an IANA name, New York by default. The device takes
  it from "HA", as on the BOX-3, so one build serves every zone. The
  tests run with the local zone set to Honolulu: a zone that does not
  reach the device shows as clocks hours off.
- **Another port or folder.** The runner uses port 6053 and a temp folder.
  When another runner holds them, pass `--port 6062 --out /tmp/mine` to
  record.py, or set `DARUMA_PORT=6062 DARUMA_WORK=/tmp/mine` for pytest.
  With make, `DARUMA_WORK=/tmp/mine` sets the folder for both.

A persona kept out of this repository can still be recorded and tested.
Name its repository in `DARUMA_PERSONA_PATH`, a list of folders joined
like `PATH`. Every tool reads it the same way (`demos/persona_path.py`):
the desktop build, the scenario tests, the recorder, the frame goldens and
the prop check.

```sh
export DARUMA_PERSONA_PATH=/path/to/my-daruma-private
uv run demos/record.py --personas "<its name>"
uv run pytest demos -m scenario --persona "<its name>"
uv run python tests/persona_frames.py check <its pixel_art persona>
```

The pictures go to that folder, never into this repository, laid out as
Daruma keeps its own: GIFs in `docs/demos/`, goldens in `tests/golden/`.
`DARUMA_PERSONA_GOLDEN` and `DARUMA_PERSONA_DEMOS` move them. See
[private-packages.md](private-packages.md#test-before-you-push).

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

The C++ tests run through pytest too. `tests/conftest.py` collects each
`tests/test_*.cpp` as one test: pytest builds it and runs it. The
`cpp` marker picks them out. The compiler is `c++`, or `$CXX` when set.
`CXX="ccache c++"` caches the objects, as CI does. To run one test, name
it:

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

### Pixel layers

`tests/test_pixel_layers.py` checks the imports between the pixel
packages with grimp. Imports only go down: a persona imports shapes and
`daruma_pixel`, a shape imports `daruma_pixel` and other shapes, and
`daruma_pixel` imports neither. A persona never imports another persona.
A failed check names the module, the line and the rule it breaks.

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
- Python host tests: `pytest tests --cov=src/esphome/components --cov=pixel`.
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
make mutate SHARD=2/3          # one of three parts of the run
```

`make mutate` mutates all the Python. It takes about 45 minutes on an
M-series Mac, and it never fails on a survivor. `make mutate-diff`
mutates only the functions a branch changed. It takes from seconds to
a few minutes. It fails when a mutant on a changed line survives, or
when no test reaches it. The changes count from the merge base, so
commits that land on main later are not yours. CI runs
`make mutate-diff MINUTES=8` on every pull request, in three parts on
three runners. That check is not required. `MINUTES` stops each part's
Python run in time: it then lists what it found and fails.

`SHARD=K/N` runs part K of N, for either goal. A part is a set of
whole functions, picked the same way on every run. The split weighs each
function by its lines and its package. Persona functions count the most,
then shapes, then the drawing layer, since their mutants run the
persona tests. So the slow mutants spread across the parts. Each part
reports and fails on its own mutants. The C++ mutants run in part 1.
A run stops when a mutant is in no part or in two. A test checks that
the three parts hold every mutant exactly once.

- **Python**: [mutmut](https://github.com/boxed/mutmut) mutates the
  folders and files in `[tool.mutmut]` in `pyproject.toml`: every
  component, every pixel package, and the demo modules that a test
  reaches without a device. `demos/harness.py`, `record.py` and
  `contact_sheet.py` are left out: only the screen tests reach them, and
  those build a device. The runs include the persona tests, even when
  `DARUMA_SKIP_PERSONAS` is set. Each mutant runs in a fresh process
  (`process_isolation = "forkserver"`). The fork server imports only
  outside modules first (`tests/mutmut_preload.txt`). So each mutant
  imports the repository's modules again, with the mutant on, and builds
  the persona tables and cached pictures again.
- **C++**: `tests/mutate_cpp.py` mutates the component files that the
  C++ host tests include. It builds and runs every test that includes
  the file. A change that doesn't build doesn't count.
  `test_frames.cpp` reads the frames of every persona from a fixture.
  The Python encoder writes it once, before the mutants run.

### Reading the report

`make mutate` lists two kinds of mutants, then a count per part of the
code:

- **Survived**: a test runs the code, but no test fails with the
  change. Add a test that tells the change apart, or mark the line.
- **No tests**: no test runs the code at all. That code is untested.
  The diff run fails on it too, so new untested code shows.

The counts give each part's mutants, then how many were killed, timed
out (a test noticed: the change made it loop), survived, or had no
tests. A mutant that breaks the test run itself, such as one that makes
a persona fail to import, counts as a timeout too. A mutant is named by
its module and function, such as
`daruma_pixel.pixelkit.xǁCanvasǁdot__mutmut_3`. `uv run python
tests/mutmut_run.py show <name>` prints its change.

When a mutant survives, add a test that tells the change apart. Some
changes can't be told apart. For example, a bound that a later check
covers too. Mark those lines `# pragma: no mutate` in Python or
`// pragma: no mutate` in C++, and say why in a comment. In Python, a
comment line `# pragma: no mutate block, <why>` covers the statements
after it, to the end of their block. `make mutate-diff` starts from a
fresh `mutants/` folder, so it sees a new pragma. `make mutate` keeps
the folder between runs: delete `mutants/` after you add a pragma.

The Python runs skip some lines (`do_not_mutate_patterns`):

- lines that raise an error or add a build log line: that text is for
  people, and tests match only a few words of it;
- a `mode="full"` default: any mode but gray4 and mono is full color;
- a new Pillow picture filled with zeros, `Image.new(..., 0)` or
  `(0, 0, 0, 0)`: the default fill is the same.

mutmut names a mutant by its file's path, less a leading `src.`. The
tests record which test reaches a function by the module's import name.
The two agree for the components (`src/esphome/components/daruma` is
`esphome.components.daruma`, through `tests/esphome_components.py`).
They don't for `pixel/<package>/src/<module>` and `demos/<module>`.
`tests/mutmut_run.py` runs mutmut with those mapped to their import
names. It also puts the mutated pixel folders ahead of the editable
installs on `sys.path`. Both scripts fail when mutmut has a name that
still starts with a path, or no mutants under a changed module's name.
Either would match no test and pass without running one.

mutmut runs a mutant only against the tests that reached its function
in a first, recorded run. Two things hide that reach. A call made while
a module is imported counts for the one test that imported it first. A
cache (`functools.cache`, `cached_picture`) skips the call in later
tests. `tests/mutmut_run.py` handles both in the recorded run. It
empties the repository's caches before each test. It also charges a
call made at import to every test that runs code of the same package,
such as `daruma_personas.corgi` or `daruma_shapes.pets`.

mutmut wraps every function of a mutated module in a trampoline. On
each call it reads which mutant is on, and calls that mutant or the
original. That made the drawing tests run about three times slower.
`tests/mutmut_fast.py` puts a cheaper wrapper in its place. It works the
target out once for each mutant, then calls it straight. Classmethods,
generators, async functions and the recorded run keep mutmut's own.
`tests/mutmut_run.py` installs it before mutmut starts.

These scripts change mutmut's internals, so `uv.lock` pins mutmut. An
upgrade can still move what they rely on. Then a test fails and names
it: `tests/test_mutmut_fast.py` checks each internal the wrapper uses,
and that it calls what mutmut's own would. A small real run in
`tests/test_mutate_py.py` checks that each mutant runs under the cheap
wrapper, and still kills and finds the planted mutants.

mutmut runs the tests from a copy of the checkout in `mutants/`. The
copy takes every top-level entry git tracks (`also_copy`). A test fails
when a new one is missing there.

## Preview pixel art

```sh
uv run python -m daruma_pixel.personas /tmp/personas jack_russell
```

This writes every layer and `sheet.png`: every frame of every animation,
as the screen shows it.
