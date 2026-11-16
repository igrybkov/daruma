# Contributing to Daruma

Thank you for helping. This guide is written for coding agents first and
for people second. Both follow the same steps. An agent should read
[AGENTS.md](AGENTS.md) too: it has the architecture, the commands and the
pitfalls in short form.

This repository is a starting point. Diverge from it as far as you like.
Send back what others could use: a persona, a room, an app, a module, a
board, a fix.

## Setup

You need git, [uv](https://docs.astral.sh/uv/), a C++17 compiler, SDL2
and ffmpeg. On macOS:

```sh
brew install uv sdl2 ffmpeg
```

You don't install ESPHome. The scripts run ESPHome 2026.10.2 through uv.

Fork the repository, clone your fork, and make a branch for your change:

```sh
git clone https://github.com/<you>/daruma && cd daruma
git switch -c my-change
```

To try your change on a real device, point the device file at your fork
and branch. Commit first: ESPHome fetches by ref.

```yaml
substitutions:
  daruma_url: https://github.com/<you>/daruma
  daruma_ref: my-change
```

## Repository layout

| Path | What |
|---|---|
| `packages/` | ESPHome packages: boards, `core.yaml`, `persona_*.yaml`, apps, `menu.yaml`, `pomodoro.yaml`, `prompts.yaml` |
| `components/` | ESPHome components. `daruma/` is the hub; `daruma/registry.py` holds the states and the build checks. `daruma_*` are personas and modules. |
| `pixel/daruma_pixel/` | the pixel-art library, run at build time: engines, scenes, breeds, `personas.py` |
| `art/` | picture sets for `daruma_images` |
| `examples/` | `box3.yaml` (a device), `desktop.yaml` (a window on a computer), build variants |
| `demos/` | the desktop test harness, scenarios, the GIF recorder, pytest tests |
| `tests/` | host tests in Python and C++, and golden pictures |
| `docs/` | manuals: install, customize, testing, prompts, architecture; `docs/agents/` holds agent playbooks |
| `blueprints/` | Home Assistant blueprints |

How the parts fit: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Add a persona

Follow [docs/agents/new-persona.md](docs/agents/new-persona.md). It works
for people too. To contribute the persona, also:

1. Add an entry to `PERSONAS` in `pixel/daruma_pixel/personas.py` (pixel
   art only).
2. Add `packages/persona_<name>.yaml`. Copy the header comment style of
   the others.
3. Add the package to `examples/box3.yaml` and `examples/desktop.yaml`.
4. Record its GIFs: `highlight`, `emotions`, `activities`, `tour`, `apps`
   and `prompts`.
5. Add its `highlight` GIF to the README grid, and a section to
   [docs/gallery.md](docs/gallery.md).
6. Add its golden pictures for the `tour` scenario.
7. Compile `examples/box3.yaml` and put the flash size before and after
   in the pull request.

## Add an app

An app is a C++ class with its own screen, registered by a module.
[components/daruma_weather](components/daruma_weather/) and
[packages/app_weather.yaml](packages/app_weather.yaml) are a compact
model: one component, one package, one theme. Read
[customize.md, Apps](docs/customize.md#apps) first.

1. Add the component and the package.
2. Give every setting an option with a default. Don't hardcode entity
   ids, times or colors.
3. Use the theme keys, so the app fits every persona's theme.
4. Add a step for it to a scenario, and a pytest test in
   `demos/test_daruma.py` that taps through it.
5. Add it to `examples/box3.yaml` and the app table in
   [docs/customize.md](docs/customize.md#apps).

## Add a module

A module adds states, actions, buttons, bindings or a progress source.
Many need only YAML. See
[customize.md, Your own module](docs/customize.md#your-own-module) and
[ARCHITECTURE.md, Modules and apps](docs/ARCHITECTURE.md#modules-and-apps).

- A new state needs a `fallback:`, so every persona can show it.
- A new state needs a step in a showcase scenario
  (`demos/scenarios/emotions.yaml` or `activities.yaml`).
  `test_showcase_covers_every_state` fails until it has one.
- Document new keys in [docs/customize.md](docs/customize.md).

## Tests

Run all four before you open a pull request. Run them from the
repository root. [docs/testing.md](docs/testing.md) explains each.

```sh
# 1. Host tests in Python: registry, build checks, pixel art, layout (minutes)
uv run --no-project --with pillow --with pyyaml python -m unittest discover -s tests

# 2. Host tests in C++: gestures, layout, prompts, pomodoro rules, agenda, weather
tests/run_cpp.sh

# 3. Golden pictures on the desktop build
uv run demos/record.py --test

# 4. Screen tests in Python on the desktop build
uv run --with pytest --with aioesphomeapi==46.30.0 --with pillow --with pyyaml pytest demos
```

- `DARUMA_SKIP_PERSONAS=1` skips the slow persona tests in step 1 while
  you work. Run the full set before you finish.
- If another run holds the default port or folder, pass
  `--port 6062 --out /tmp/mine` to record.py, or set
  `DARUMA_PORT=6062 DARUMA_WORK=/tmp/mine` for pytest.
- A new C++ test file goes into the list in `tests/run_cpp.sh`.

## Golden pictures and frames

Golden pictures live in `tests/golden/<persona>/<scenario or test>/`.
When a check fails, it writes the actual picture, a diff and a GIF of the
run.

If the change is on purpose, accept the new pictures:

```sh
uv run demos/record.py --update-golden --personas "<Name>" --scenario tour
```

Then look at every new picture. A passing test only says the picture
is the same as before. It can't say the picture looks right.

- Open each changed golden picture up close.
- For a recorded GIF, open the frames in `<out>/runs/<persona>-<scenario>/`.
  Look at some from each caption.
- Check: limbs attached, nothing floating, the outline closed, props in
  place, text inside its box, eyes readable at 1x.
- For pixel art, also look at `sheet.png` from the preview:
  `cd pixel && uv run --with pillow python -m daruma_pixel.personas /tmp/p <name>`.

Commit the GIFs and golden pictures with the change that made them.

## Privacy

This is a public repository. Demo data is made up.

- No real names of people or pets, no real calendars, tasks, addresses,
  IP addresses, host names, entity ids from your home, emails or tokens.
  This holds for code, docs, demos, tests, pictures and commit messages.
- Keep your own personas and settings in a repository of your own. See
  [docs/private-packages.md](docs/private-packages.md).
- Before you push, search your change:

  ```sh
  git diff main --stat
  git diff main | grep -nIE "@[A-Za-z0-9.-]+\.[a-z]{2,}|[0-9]{1,3}(\.[0-9]{1,3}){3}"
  ```

## Names

- **Persona**: one swappable look of the device. Use this word in code,
  YAML keys, docs and commits.
- **The device**: the hardware that runs Daruma. In prose, call it that.
- **Daruma**: the framework. The default persona is also a daruma doll;
  its id is `daruma_doll`.
- Don't invent other names for the device or for personas.
- "character" means text length only.

## Commits

- One logical change per commit. A commit builds and passes the tests.
- Subject in the
  [Conventional Commits](https://www.conventionalcommits.org/) style, in
  plain English: `feat(pixel): a parrot persona on a perch`,
  `fix(prompts): long titles wrap inside the card`. Common scopes:
  `core`, `pixel`, `apps`, `prompts`, `menu`, `pomodoro`, `demos`,
  `docs`.
- The body says why, and what a reader can't see in the diff.
- Sign your commits if you can (`git commit -S`).
- Code comments explain the code on their own. They don't cite tickets,
  plans or conversations.

## Docs style

Short sentences. Plain verbs. One idea per sentence. No em dashes. Write
for a reader who is tired and wants the next step.

## Pull request checklist

- [ ] The four test commands pass.
- [ ] I looked at every changed picture and frame up close.
- [ ] New states have a fallback and a showcase step.
- [ ] New options have defaults, and docs/customize.md lists them.
- [ ] A new persona is in both examples, the README grid and the gallery,
      with golden pictures and its flash size.
- [ ] No private data (see [Privacy](#privacy)).
- [ ] The description says what changed and why, with a GIF if it shows
      on screen.
