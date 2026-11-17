# Working in Daruma

A guide for coding agents that work in this repository. People are
welcome to read it too.

Daruma is an ESPHome framework for an animated desk companion on the
ESP32-S3-BOX-3, driven by Home Assistant.

## Playbooks

- Install Daruma on a person's device: [docs/agents/install.md](docs/agents/install.md).
- Make a new persona: [docs/agents/new-persona.md](docs/agents/new-persona.md).
- Contribute a change back: [CONTRIBUTING.md](CONTRIBUTING.md).

## Words

- **Daruma**: the framework, and the device that runs it. In prose, call
  the device "the device".
- **Persona**: one look of the device (the daruma doll, the pixel corgi,
  the eyes). A device has several; the "Persona" select picks one.
- **State**: what the core or a module asks a persona to show: a mood, an
  activity or a reaction. See [customize.md](docs/customize.md#states-what-the-device-can-show).
- **Module**: a package that adds states, actions, apps, menus or theme
  keys.

## Architecture in brief

Four layers, bottom up. [ARCHITECTURE.md](docs/ARCHITECTURE.md) has the
detail.

- **Board** (`packages/board_*.yaml`): the hardware, and names for its
  inputs.
- **Core** (`packages/core.yaml`, `components/daruma`): the hub owns the
  state, picks what is on screen, routes input and plays sounds. It never
  knows which personas or modules exist.
- **Personas** (`packages/persona_*.yaml`): each answers to states with
  its own animations. A missing state falls back along a chain the
  registry checks at build time.
- **Modules** (pomodoro, apps, prompts, menus): a package, plus a
  component when it needs C++. Including the package turns it on.

The build is strict. `components/daruma/registry.py` checks every state,
action, binding and theme key against every other, so a typo fails at
compile time.

### How the pieces connect

- **States.** `components/daruma/registry.py` declares every state once,
  with a kind (mood, activity, reaction) and a fallback. At build time it
  becomes the X-macro `DARUMA_STATE_LIST` in `defines.h`. `states.h` turns
  that into `enum class StateId`. Strings stay only in logs and HA selects.
- **Precedence.** A reaction wins, then the top activity, then the mood.
- **Modules add states** with their own fallbacks. Tasks adds `task_done`,
  which falls back to `celebrate`.
- **Showcase test.** `test_showcase_covers_every_state` in
  `demos/test_daruma.py` asks the running build for its states. Every state
  must appear in `demos/scenarios/emotions.yaml` or `activities.yaml`.
- **Screen tests give the same frames on every run.** `demos/fakeclock.c`
  fakes the clock and seeds the random numbers. The runner plays Home
  Assistant with made-up data from `demos/demo_data.py`. Golden pictures
  live in `tests/golden/<persona>/<scenario or test>/`. A failure writes
  the actual picture, a diff and a GIF.
- **Test API.** Screen tests find parts by text or role, like browser
  tests: `device.get_by_role("button", name="Unlock").tap()`. Pick a
  persona with `@pytest.mark.persona("Pixel corgi")`. The default is Eyes.

## Where things live

| Path | What |
|---|---|
| `packages/` | ESPHome packages: boards, `core.yaml`, `persona_*.yaml`, apps, `menu.yaml`, `pomodoro.yaml`, `prompts.yaml` |
| `components/` | ESPHome components in C++ and Python; `daruma/registry.py` holds the states and the build checks |
| `pixel/daruma_pixel/` | the pixel-art library: engines (`pet.py`, `desk_boss.py`), scenes, breeds, `personas.py` |
| `art/` | picture sets for `daruma_images` |
| `sounds/` | `preview.cpp`: writes the built-in sounds as WAV files to listen to |
| `examples/` | `box3.yaml` (a device), `desktop.yaml` (a window on a computer), build variants |
| `demos/` | the desktop test harness, scenarios, the GIF recorder |
| `tests/` | host tests (Python and C++) and golden pictures |
| `docs/` | install, customization, testing, prompts, private packages, architecture, agent playbooks |
| `blueprints/` | Home Assistant blueprints |

## Commands

Run them from the repository root. [docs/testing.md](docs/testing.md)
explains each. `make` lists every goal; `make -n <goal>` prints its
commands.

```sh
# Host tests: no ESPHome build needed
make test                 # test-py and test-cpp

# Screen tests on the desktop build (same pictures on macOS and Linux)
make screens              # golden, then test-screens
make docker-test          # both, in Ubuntu 24.04 as CI runs them

# Record GIFs, accept new golden pictures
make gifs PERSONA="<Name>" SCENARIO=highlight,emotions,activities
make update-golden CONFIRM=1 PERSONA="<Name>" SCENARIO=tour

# Preview a pixel persona: every frame in sheet.png
uv run python -m daruma_pixel.personas /tmp/p <name>

# Lint, and compile the example device (commit first)
make lint tidy
make compile

# Everything CI blocks on
make check
```

### Run one test

```sh
# One Python host test (tests/)
make test-py PYTEST_ARGS="-k test_registry"   # make always passes tests/
uv run pytest tests/test_registry.py::<name>   # or call pytest directly
DARUMA_SKIP_PERSONAS=1 make test-py           # skip the slow persona builds

# One screen test on the desktop build (demos/)
make test-screens PYTEST_ARGS="-k corgi -n 0"

# Golden check for one persona and scenario
make golden PERSONA=Eyes SCENARIO=emotions

# Run the device in a window
make desktop
```

The C++ host tests have no single-test switch. `tests/run_cpp.sh` builds
each `tests/test_*.cpp` against a scratch include folder. Copy its `c++`
line to build one by hand. `test_frames.cpp` runs through
`tests/test_frames.py`.

## Rules

- Run the checks above before you call a change done. All of them must
  pass.
- Look at every picture you change. Open the frames and the golden
  pictures up close: limbs attached, nothing floating, props in place.
  A passing test does not prove a picture looks right.
- A new state needs a fallback, and a step in a showcase scenario
  (`demos/scenarios/emotions.yaml` or `activities.yaml`). A test fails
  until it has one.
- Keep tunables in YAML options with defaults. Don't hardcode entity ids,
  colors or times in C++.
- Code comments explain the code on their own. They don't cite plans,
  tickets or conversations.
- Docs: short sentences, plain verbs, one idea per sentence. No em dashes.
- Commit messages and pull request titles are Conventional Commits
  (`feat(pixel): ...`); gitlint and CI check them.
- Before you commit, run `ruff check --fix`, `ruff format` and
  clang-format, or let the pre-commit hooks do it. Keep new functions
  under complexity 15 (complexipy, lizard); split them, don't add
  exclusions.
- Demo data is made up. Never put a real person's name, calendar or tasks
  into demos, tests or pictures.

## Pitfalls

- **ESPHome version.** The builds and docs use ESPHome 2026.10.2, from
  `.venv-esphome` (`make setup`). Outside make, pin it with
  `uvx --from esphome==2026.10.2`; another version may not compile.
- **Never flash a scratch build.** A build made with placeholder secrets
  loses its Wi-Fi on the device. Compile to check; flash only with the
  person's real secrets.
- **Busy folders.** Every device listens on a free API port, but the
  recorder and pytest share a temp folder. When another run may use it,
  pass `DARUMA_WORK=/tmp/mine` to make.
- **Paths in packages** are relative to the package file
  (`../components`, `../pixel/...`, `../art/...`). The components resolve
  them at validation time.
- **Ids.** An ESPHome id may not equal an integration name. That is why
  the doll persona's id is `daruma_doll`.
- **Slow tests.** The host tests build every persona and take minutes.
  `DARUMA_SKIP_PERSONAS=1` skips those while you iterate; run them all
  before you finish.
- **Pixel scripts** run with their own folder and `pixel/` on `sys.path`.
  Import the library as `daruma_pixel.X`.
