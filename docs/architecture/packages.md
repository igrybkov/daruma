# Packages

> Incomplete. Moved from the old ARCHITECTURE.md. Add what you learn
> when a task needs more, and keep it under 300 lines.

How the framework ships as one git checkout, and how a device pulls it. Private repositories: [private-packages.md](../private-packages.md).

The framework lives in its own git repository, versioned with tags:

```
src/esphome/components/
              daruma (core), daruma_menu, daruma_sounds, daruma_prompts,
              daruma_sprites, daruma_eyes, daruma_images, daruma_calendar,
              daruma_tasks, daruma_weather, daruma_desktop
packages/     boards (board_box3.yaml, board_box3_buttons.yaml,
              board_desktop.yaml), core.yaml, menu.yaml, pomodoro.yaml,
              prompts.yaml, app_tasks.yaml, app_calendar.yaml, persona_*.yaml
pixel/        pixel-art sources (Python), drawn at build time
art/          picture sets for persona_images.yaml
examples/     box3.yaml, desktop.yaml and build checks
blueprints/   HA blueprints: prompt demos, doorbell prompt, quiz, task list
```

A device is a short file. Its packages come from git at a ref (a branch,
a tag or a full commit hash):

```yaml
substitutions:
  name: office-device
  friendly_name: Office Device
packages:
  daruma:
    url: https://github.com/igrybkov/daruma
    ref: main
    files:
      - packages/board_box3.yaml
      - packages/core.yaml
      - packages/persona_daruma.yaml
      - path: packages/app_calendar.yaml
        vars: { calendars: calendar.home }
```

**One checkout for everything.** Each package declares the components it
needs as a local source, `path: ../src/esphome/components`, relative to the package
file. ESPHome looks for a relative path in the config folder first, then
next to the YAML file that names it (`cv.directory`). For a package from
git, that is the package's own checkout in ESPHome's cache. So a device
needs no `external_components:` entry, and components, packages and pixel
art always come from the same commit. Adding a second source for the same
components (`external_components: github://...`) is not needed and makes
the result depend on order.

**Why `src/esphome/components`.** ESPHome imports a component as
`esphome.components.<name>`. The folders spell out that name, so host
code imports the components the same way:

- The host tests import `tests/esphome_components.py` first. It adds the
  component folders to ESPHome's `esphome.components` package.
- `uv sync` also installs `src/pyproject.toml` (`daruma-components`) as
  an editable package, for scripts and the REPL. It is never built: a
  wheel would write the files into the installed ESPHome.
- C++ host tests compile with `-I src`, so the headers include each other
  as in a build (`esphome/components/<name>/...`).

**Files named by packages.** The same rule covers the files the personas
read. `pixel_art: {script: ../pixel/my_persona.py}` and
`art: ../art/flat_corgi` resolve next to the package, and the component
stores the absolute path (`resolve_file()` and `resolve_dir()` in
`src/esphome/components/daruma/sprite.py`). It resolves them while the config is
validated, while each value still knows its YAML file. The rest of the
build reads only absolute paths.

**The pixel library.** The pixel art is the Python package
`daruma_pixel` (`pixel/daruma_pixel/`, installable with pip through
`pyproject.toml`). Firmware builds do not install it. `daruma_sprites` puts
`pixel/` of its own checkout on the import path. `pixel_art: module:`
names a persona module by dotted name (`daruma_pixel.corgi_persona`), and
`pixel_art: script:` names a file. A script kept elsewhere (a persona in a
device's config folder or in another package's repository) runs with its
own folder and the library on the path. It imports the engines as
`from daruma_pixel import personas, pet` and declares its persona with
`PERSONA = personas.Spec(...)`; the component builds it with
`personas.build()`. A module with a `build(name)` of its own builds
itself. Library modules live in their own namespace, so
a script's own module names cannot replace them. The drawn-persona cache
hashes every file the script can import.

**Bundles.** `esphome bundle` packs the config folder for a remote build.
Pictures and scripts the config does not name as paths are added with
`bundle_file()`. Files in ESPHome's git cache are left out: the build
server fetches packages again.

**Developing.** `examples/desktop.yaml` includes the packages from the
checkout (`!include ../packages/...`), so it shows uncommitted changes. A
device yaml that names `url` and `ref` as substitutions builds from a
local clone with `-s daruma_url file:///path/to/daruma -s daruma_ref main`
(committed changes only).

Adding a state with a fallback is a minor version. Adding one without a
fallback, or changing an API action, is a major version.
