# Working in Daruma

A guide for coding agents that work in this repository. People are
welcome to read it too.

Daruma is an ESPHome framework for an animated desk companion on the
ESP32-S3-BOX-3, driven by Home Assistant.

## Playbooks

- Change the code: find your kind of work in
  [docs/architecture/README.md](docs/architecture/README.md) and read that
  topic first.
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

Four layers, bottom up. The topics in
[docs/architecture/](docs/architecture/README.md) have the detail.

- **Board** (`packages/board_*.yaml`): the hardware, and names for its
  inputs.
- **Core** (`packages/core.yaml`, `src/esphome/components/daruma`): the hub owns the
  state, picks what is on screen, routes input and plays sounds. It never
  knows which personas or modules exist.
- **Personas** (`packages/persona_*.yaml`): each answers to states with
  its own animations. A missing state falls back along a chain the
  registry checks at build time.
- **Modules** (pomodoro, apps, prompts, menus): a package, plus a
  component when it needs C++. Including the package turns it on.

The build is strict. `src/esphome/components/daruma/registry.py` checks every state,
action, binding and theme key against every other, so a typo fails at
compile time.

## Where things live

| Path | What |
|---|---|
| [`packages/`](packages/README.md) | ESPHome packages: boards, `core.yaml`, `persona_*.yaml`, apps, `menu.yaml`, `pomodoro.yaml`, `prompts.yaml` |
| `src/esphome/components/` | ESPHome components in C++ and Python; `daruma/registry.py` holds the states and the build checks |
| `pixel/daruma-pixel/` | the drawing layer, `daruma_pixel`: pixelkit, scenes and spots, effects, the persona framework (`personas.py`) |
| `pixel/shapes-*/` | shapes, `daruma_shapes.<family>`: pets (the pet rig, dogs, cats), rooms, plants, office |
| `pixel/persona-*/` | one package per pixel persona, `daruma_personas.<name>`: its looks, colors and animations |
| `art/` | picture sets for `daruma_images` |
| `sounds/` | `preview.cpp`: writes the built-in sounds as WAV files to listen to |
| [`examples/`](examples/README.md) | `box3.yaml` (a device), `desktop.yaml` (a window on a computer), build variants |
| `demos/` | the desktop test harness, scenarios, the GIF recorder |
| `tests/` | host tests (Python and C++) and golden pictures |
| `docs/` | install, customization, testing, prompts, private packages, architecture, agent playbooks |
| [`blueprints/`](blueprints/README.md) | Home Assistant blueprints |

## Commands

Run them from the repository root. [docs/testing.md](docs/testing.md)
explains each. `make` lists every goal; `make -n <goal>` prints its
commands.

Don't run the full suites locally by default. Push and open a draft
pull request instead, and mark it ready when the work is done. CI is
tuned for speed and runs every check in under two minutes, which is
usually faster than a local build. Locally, run only what you need
while you iterate, such as one test file, a persona preview or a lint.

```sh
# Host tests: no ESPHome build needed
make test                 # test-py and test-cpp

# Mutation tests: would a test catch a bug in this code?
make mutate-diff          # lines changed since origin/main; CI runs it
make mutate               # everything, as a report

# Screen tests on the desktop build (same pictures on macOS and Linux)
make screens              # golden and test-screens, in one pytest run
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

## Rules

- A change is done when every CI check on its pull request passes.
  Read the results with `gh pr checks`, and fix what fails.
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
  `.venv` (`make setup`). Outside the project, pin it with
  `uvx --from esphome==2026.10.2`; another version may not compile.
- **Never flash a scratch build.** A build made with placeholder secrets
  loses its Wi-Fi on the device. Compile to check; flash only with the
  person's real secrets.
- **Busy folders.** Every device listens on a free API port, but the
  recorder and pytest share a temp folder. When another run may use it,
  pass `DARUMA_WORK=/tmp/mine` to make.
- **Paths in packages** are relative to the package file
  (`../src/esphome/components`, `../pixel/...`, `../art/...`). The components resolve
  them at validation time.
- **Ids.** An ESPHome id may not equal an integration name. That is why
  the doll persona's id is `daruma_doll`.
- **Persona tests.** Some host tests build every persona. They are the
  slowest host tests, a few seconds of the ten or so that `make test`
  takes. `DARUMA_SKIP_PERSONAS=1` skips them while you iterate. CI runs
  them all.
- **Pixel packages** are uv workspace members (`pixel/*/`), installed
  editable by `uv sync`. A device build installs nothing: it puts every
  `pixel/*/src` on `sys.path`. `daruma_shapes` and `daruma_personas` are
  namespace packages, so they have no `__init__.py` at the top.
- **Pixel layers.** A persona imports shapes and the drawing layer, never
  another persona. A shape never imports a persona. The drawing layer
  imports neither. `tests/test_pixel_layers.py` checks it.
