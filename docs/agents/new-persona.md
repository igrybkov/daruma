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
| a four-legged pet sitting up | a breed on `pet` | `pixel/daruma_pixel/jack_russell.py` (dog), `tabby_cat.py` (cat) |
| a person at a desk | a look on `desk_boss` | `pixel/daruma_pixel/the_boss.py` |
| anything else in pixel art | a module of your own | `pixel/daruma_pixel/daruma.py`, `daruma_moods.py`, `daruma_persona.py` |
| existing pictures | `daruma_images` | `packages/persona_images.yaml`, `art/flat_corgi/` |
| something abstract | `daruma_eyes` with a color | `packages/persona_eyes.yaml` |

A pixel persona is the richest: a room, a window with the sky, a prop
that grows with progress, a rug that changes by weekday. Read the model
module fully before you write one.

## Where it lives

- **In a fork of this repository**, to contribute it: the art in
  `pixel/daruma_pixel/<name>.py`, an entry in `PERSONAS` in
  `pixel/daruma_pixel/personas.py`, a package
  `packages/persona_<name>.yaml`, and a line in `examples/box3.yaml` and
  `examples/desktop.yaml`. Then follow [CONTRIBUTING.md](../../CONTRIBUTING.md).
- **In the person's own files**: the art and a small build script next to
  their device file or in a repository of their own. Follow
  [private-packages.md](../private-packages.md). The script imports
  the library (`from daruma_pixel import personas, pet`) and adds itself to
  `personas.PERSONAS`.

## Steps

1. **Design on paper first.** Colors (a few ramps: base, shadow, light,
   line), the silhouette, and how it shows each mood. Decide its scene and
   its focus prop: the corgi reads a book, the Jack Russell holds a ball,
   the daruma burns incense.
2. **Write the art module.** It offers `background()`,
   `foreground(pose)`, `scene(pose)`, `WINDOW`, `ANIMATIONS`, `BLINKS`,
   `WINKS`, and `PROPS` when an activity has props. `Neutral` is required.
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
   `uv run pytest tests`
   and `tests/run_cpp.sh`. The persona tests build every persona: layers,
   rug colors, props, patch frames.
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
   `uv run demos/record.py --update-golden --personas "<Name>" --scenario tour,emotions,activities`,
   then look at the new pictures in `tests/golden/<slug>/`.
9. **Full checks.** `uv run demos/record.py --test` and
   `uv run pytest demos`.
10. **Size.** Compile `examples/box3.yaml` and compare the flash line with
    the build before. A pixel persona's frames take tens of KB, not
    hundreds.

## Picture personas

Draw PNGs up to 320x240 named after the states (`neutral.png`,
`happy.png`, ...). Only `neutral.png` is required. Flat colors compress
well; photos and gradients don't. Include `persona_images.yaml` with
`persona_id`, `persona_name` and `art`.
