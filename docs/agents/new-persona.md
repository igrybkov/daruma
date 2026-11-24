# Agent playbook: make a new persona

You are a coding agent. A person named a character, an animal, a plant,
a bird or an imaginary friend. You make a Daruma persona of it that
reacts to every state, keeps its props, and passes the tests. People are
welcome to read this too.

The repository: <https://github.com/igrybkov/daruma>. Clone it if you
have no checkout: you need the files to read, preview and test. Read
[AGENTS.md](../../AGENTS.md) first for the words, the layout and the
rules.

## Pick the way to draw it

| It is | Use | Model to copy |
|---|---|---|
| a four-legged pet sitting up | a breed on the pet rig (`daruma_shapes.pets`) | `pixel/persona-jack-russell/` (dog), `pixel/persona-tabby-cat/` (cat) |
| a person at a desk | a look on the office (`daruma_shapes.office`) | `pixel/persona-the-boss/` |
| anything else in pixel art | an actor of your own | `pixel/persona-daruma/` (the doll, its moods, the persona) |
| existing pictures | `daruma_images` | `packages/persona_images.yaml`, `art/flat_corgi/` |
| something abstract | `daruma_eyes` with a color | `packages/persona_eyes.yaml` |

A pixel persona is the richest: a room, a window with the sky, a prop
that grows with progress, a rug that changes by weekday. Read the model
package fully before you write one.

The pixel art has three layers. `daruma_pixel` draws. The shapes
(`daruma_shapes.pets`, `.rooms`, `.plants`, `.office`) are generic: a cat
fits any room. A persona package picks shapes, colors and animations. If
your persona needs a shape another persona could use too, such as a new
room or plant, put it in a shapes package. Keep what only this persona
looks like in its own package. A persona never imports another persona.

## Where it lives

- **In a fork of this repository**, to contribute it: copy a persona
  package, for example `pixel/persona-jack-russell/` to
  `pixel/persona-<name>/`. Rename the package folder to
  `src/daruma_personas/<name>/` and the project name in its
  `pyproject.toml`. Add the member to the `pixel` group and to
  `[tool.uv.sources]` in the root `pyproject.toml`, then run `uv sync`.
  Its `__init__.py` holds the layers and `PERSONA = Spec(...)`. Add a
  package `packages/persona_<name>.yaml`, and a line in
  `examples/box3.yaml` and `examples/desktop.yaml`. Then follow
  [CONTRIBUTING.md](../../CONTRIBUTING.md).
- **In the person's own files**: the art module next to their device file
  or in a repository of their own. Follow
  [private-packages.md](../private-packages.md). The art module imports
  the pixel packages by name (`from daruma_shapes.pets import dog`) and
  declares itself with `PERSONA = Spec(...)`.

## Steps

1. **Design on paper first.** Colors (a few ramps: base, shadow, light,
   line), the silhouette, and how it shows each mood. Decide its scene and
   its focus prop: the corgi reads a book, the Jack Russell holds a ball,
   the daruma burns incense. Pick the scene's spots it uses: where the
   actor sits ("floor", "seat") and where its progress prop stands
   ("shelf", "sill", "hook"). Actors and props draw at the spot you pass
   in; they never assume a scene.
2. **Write the persona package.** Its `__init__.py` offers `background()`,
   `foreground(pose)`, `scene(pose)`, `WINDOW`, `ANIMATIONS`, `BLINKS`,
   `WINKS`, `PROPS` when an activity has props, and
   `PERSONA = Spec("<name>", background=0x...)`. `Neutral` is required.
   Animation names match states in any case (`focus` finds `Focus`).
   Cover at least: Neutral, Happy, Sad, Loved, Scared, Sleepy, Sleeping,
   listening, thinking, talking, Focus, Petted, Celebrate. Every other
   state falls back to one of these.
3. **Reactions during focus.** A reaction plays over the activity. If
   Focus has a prop, draw `PettedFocus`, `ScaredFocus`, `CelebrateFocus`
   (or the names your reactions use) with the prop in place, and name them
   in the package's `during:`. Declare `PROPS = {"focus": [boxes]}`.
4. **Preview and look.**
   `uv run python -m daruma_pixel.personas /tmp/p <name>`
   writes `sheet.png`, every frame of every animation. Open it and look at
   every frame up close: limbs attached, nothing floating, the outline
   closed, the prop where it belongs, eyes readable at 1x. Fix and repeat.
   Show the sheet to the person before you go on.
5. **Write the package.** Copy `packages/persona_jack_russell.yaml`: `id`,
   `name`, `pixel_art`, `during:`, `params:` (the rug), a `theme:` in the
   persona's colors, and a `pet` sound in its voice. Write the header
   comment the way the others do: what it looks like and what it does.
6. **Host tests.**
   `uv run pytest tests`. It runs the C++ tests too. The persona tests
   build every persona: layers, rug colors, props, patch frames.
7. **Build and record.** Record the showcase on the desktop build and
   look at the frames:

   ```sh
   uv run demos/record.py --personas "<Name>" --scenario highlight,emotions,activities,tour,apps,prompts --out /tmp/rec
   ```

   The run folders under `/tmp/rec/runs/` hold every frame as a picture.
   Open some from each caption. Add the persona to the README's grid
   (its `highlight` GIF) and to `docs/gallery.md`. Check the build log's
   fallback lines (`<id>: focus -> neutral`): each is a state you could
   still draw.
8. **Golden pictures.** The `tour`, `emotions` and `activities` scenarios
   are checked for every persona:
   `make update-golden CONFIRM=1 PERSONA="<Name>" SCENARIO=tour,emotions,activities`,
   then look at the new pictures in `tests/golden/<slug>/`.
9. **Full checks.** `uv run pytest demos`. It runs the scenario files
   and the Python screen tests.
10. **Size.** Compile `examples/box3.yaml` and compare the flash line with
    the build before. A pixel persona's frames take tens of KB, not
    hundreds.

## Optional: random events

A persona may play quirks now and then: a paw lick, a sneeze, a line in
a bubble. Ask the person which quirks fit the character. Skip this when
they want none.

1. **Draw the quirks.** Add each as an animation in `ANIMATIONS`, with a
   name no state uses (`LickPaw`, not `Petted`). A one-shot plays once
   and holds its last frame. Start and end it on the neutral pose. A
   spell needs a loop, and optionally an enter and an exit. Copy the
   corgi's `pixel/persona-corgi/src/daruma_personas/corgi/quirks.py`.
2. **Look at them** in `sheet.png`, as in step 4.
3. **Declare them** in the package's `random_events:`, as
   `packages/persona_pixel_corgi.yaml` does. Keep most at frequency 8
   or lower. The keys and the frequency table are in
   [customize.md](../customize.md#random-events-quirks-now-and-then).
4. **Test them.** Add a scenario to `demos/scenarios/random_events/`
   with `build: events`, a `random_event:` step per quirk and a snapshot
   mid-animation. Copy `one_shots.yaml` there. Then write its golden
   pictures and look at them:
   `make update-golden CONFIRM=1 PERSONA="<Name>" SCENARIO=<scenario>`.

A picture persona has say-only events: `say:` and `sound:`, no
animation. See
[customize.md](../customize.md#pictures-say-only-events).

## Picture personas

Draw PNGs up to 320x240 named after the states (`neutral.png`,
`happy.png`, ...). Only `neutral.png` is required. Flat colors compress
well; photos and gradients don't. Include `persona_images.yaml` with
`persona_id`, `persona_name` and `art`.
