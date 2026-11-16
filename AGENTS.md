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
explains each.

```sh
# Host tests: no ESPHome build needed
uv run --no-project --with pillow --with pyyaml python -m unittest discover -s tests
tests/run_cpp.sh

# Screen tests on the desktop build
uv run demos/record.py --test
uv run --with pytest --with aioesphomeapi==46.30.0 --with pillow --with pyyaml pytest demos

# Record GIFs, accept new golden pictures
uv run demos/record.py --personas "<Name>" --scenario highlight,emotions,activities
uv run demos/record.py --update-golden --personas "<Name>" --scenario tour

# Preview a pixel persona: every frame in sheet.png
cd pixel && uv run --with pillow python -m daruma_pixel.personas /tmp/p <name>

# Compile the example device
uvx --from esphome==2026.10.2 esphome compile examples/box3.yaml
```

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
- Demo data is made up. Never put a real person's name, calendar or tasks
  into demos, tests or pictures.

## Pitfalls

- **ESPHome version.** The builds and docs use ESPHome 2026.10.2. Pin it
  with `uvx --from esphome==2026.10.2`; another version may not compile.
- **Never flash a scratch build.** A build made with placeholder secrets
  loses its Wi-Fi on the device. Compile to check; flash only with the
  person's real secrets.
- **Busy ports and folders.** The recorder uses port 6053 and a temp
  folder. When another run may hold them, pass `--port` and `--out` to
  record.py, or set `DARUMA_PORT` and `DARUMA_WORK` for pytest.
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
