"""Pixel personas for the BOX, built from the Python art in this package.

The device build calls build(name) while it compiles (daruma_sprites with
`pixel_art:`), so changing a persona or a room only needs a new compile.
Run it by hand to look at the result:

    uv run python -m daruma_pixel.personas OUT_DIR [corgi|the_boss|jack_russell|tabby_cat ...]
    uv run python -m daruma_pixel.personas OUT_DIR my_module:my_persona

A name with a colon is MODULE:PERSONA: the persona from that module (a
dotted name on the import path), for a persona outside this package.

That writes, per persona, OUT_DIR/<name>/: every layer as a PNG and sheet.png,
every frame of every animation as the screen would show it.

A persona module says what it is with a Spec: `PERSONA = Spec(...)`, or
`PERSONAS = (Spec(...), ...)` for a module with several (the daruma's eye
states). The framework keeps no list of them: discover() finds every module
of a package that has one, and build(name, module) builds one from a module
you name.

Each persona is drawn on the device in layers, back to front:

  1. the window glass (sky and weather), drawn by the device, if any;
  2. the room, 106x80, with a hole where the glass is;
  3. the plant, one sprite per growth stage, healthy and wilted, if any;
  4. the persona frames, cropped to the area they ever cover and placed
     at a fixed offset.

build() checks that the layers stacked back up give exactly the full scene
for every frame, at the screen's color depth, and stops the build if not.
"""

from __future__ import annotations

import hashlib
import importlib
import pkgutil
import sys
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path
from types import ModuleType
from typing import Any

from PIL import Image

PACKAGE = "daruma_personas"  # Where discover() looks by default: every persona package.


@dataclass(frozen=True)
class Spec:
    """One persona: what build() needs to draw it.

    `layers` has background(), foreground(pose), scene(pose), WINDOW (None
    without one), and optionally plant(stage, wilted) with PLANT_STAGES and
    the stage scene() shows by default, DEFAULT_STAGE (any prop that grows
    with the progress signal, healthy and wilted), and RUG_COLORS with
    RUG_BY_WEEKDAY (Sunday first) for colors that change daily, with RUG_BOX
    for where they may be (default: the bottom 13 rows). `animations` has
    ANIMATIONS, BLINKS and WINKS. Either one left out is the module that
    holds the Spec. `check`, if set, runs on the built persona and raises
    when it is wrong.
    """

    name: str
    background: int  # 0xRRGGBB, for any margin round the room.
    layers: Any = None
    animations: Any = None
    check: Callable[[Persona], None] | None = None


def specs(module: ModuleType) -> dict[str, Spec]:
    """name -> Spec for every persona a module declares, with its defaults filled in."""
    found = getattr(module, "PERSONAS", None) or ((module.PERSONA,) if hasattr(module, "PERSONA") else ())
    return {
        s.name: replace(
            s,
            layers=module if s.layers is None else s.layers,
            animations=module if s.animations is None else s.animations,
        )
        for s in found
    }


def discover(package: str = PACKAGE) -> dict[str, Spec]:
    """name -> Spec for every persona in the modules of `package`."""
    root = importlib.import_module(package)
    found: dict[str, Spec] = {}
    for info in pkgutil.iter_modules(root.__path__, f"{package}."):
        for name, spec in specs(importlib.import_module(info.name)).items():
            if name in found:
                raise ValueError(f"Two personas are named {name!r} (in {info.name})")
            found[name] = spec
    return found


def spec(name: str, module: ModuleType | str | None = None) -> Spec:
    """The Spec of persona `name`: from `module` (a module or its dotted name), or found by discover()."""
    if isinstance(module, str):
        module = importlib.import_module(module)
    known = specs(module) if module is not None else discover()
    if name not in known:
        raise ValueError(f"No persona {name!r}; there are {sorted(known)}")
    return known[name]


@dataclass
class Animation:
    frames: list[tuple[Image.Image, int]]  # (picture, milliseconds)
    blink: Image.Image | None = None
    wink: Image.Image | None = None


@dataclass
class Persona:
    """Everything the device needs for one persona. Colors are 0xRRGGBB."""

    background: int
    backdrop: Image.Image
    sprite_offset: tuple[int, int]
    animations: dict[str, Animation]
    window: tuple[int, int, int, int] | None = None  # x, y, width, height
    plant_offset: tuple[int, int] = (0, 0)
    plant_stages: list[Image.Image] = field(default_factory=list)
    plant_wilted: list[Image.Image] = field(default_factory=list)
    recolor_from: list[int] = field(default_factory=list)
    recolor_by_weekday: list[list[int]] = field(default_factory=list)  # Sunday first


def rgb565(img: Image.Image) -> bytes:
    """Pixels at the screen's color depth; transparent ones as a marker no color can hit.

    Three bytes a pixel: red >> 3, green >> 2, blue >> 3, or ff ff ff where
    alpha is under 128 (no shifted value reaches ff).
    """
    r, g, b, a = img.convert("RGBA").split()
    out = Image.merge("RGB", (r.point(_SHIFT3), g.point(_SHIFT2), b.point(_SHIFT3)))
    out.paste((255, 255, 255), mask=a.point(_SEE_THROUGH))
    return out.tobytes()


_SHIFT3 = [v >> 3 for v in range(256)]
_SHIFT2 = [v >> 2 for v in range(256)]
_SEE_THROUGH = [255 if v < 128 else 0 for v in range(256)]


@dataclass(frozen=True)
class Under:
    """The layers under the persona, drawn once per build: room and plant."""

    background: Image.Image
    plant: Image.Image | None


def under(layers) -> Under:
    plant = layers.plant(layers.DEFAULT_STAGE, False) if hasattr(layers, "plant") else None
    return Under(layers.background(), plant)


def check_layers(layers, pose, below: Under | None = None, fg: Image.Image | None = None) -> None:
    """Stacked layers must equal the full scene. The hole shows the room's own glass.

    `below` and `fg` are the layers already drawn, if the caller has them.
    """
    below = below or under(layers)
    fg = layers.foreground(pose) if fg is None else fg
    full = layers.scene(pose)
    glass = Image.new("RGBA", full.size, (0, 0, 0, 0))
    if layers.WINDOW:
        x, y, w, h = layers.WINDOW
        glass.paste(full.crop((x, y, x + w, y + h)), (x, y))
    stacked = glass.copy()
    stacked.alpha_composite(below.background)
    if below.plant is not None:
        stacked.alpha_composite(below.plant)
    stacked.alpha_composite(fg)
    # Glass pixels the persona covers come from the persona either way.
    if rgb565(stacked) != rgb565(full):
        raise ValueError("Layers do not add up to the scene; check background()/foreground()")


def check_rug(layers, bg: Image.Image) -> None:
    """The swapped rug colors must belong to the rug alone, at screen depth.

    The rug is where the layers' RUG_BOX (x0, y0, x1, y1) says, or else the
    bottom 13 rows; a scene may put its weekday colors anywhere it says.
    """
    box = getattr(layers, "RUG_BOX", (0, bg.height - 13, bg.width, bg.height))

    def q(c):
        return (c[0] >> 3, c[1] >> 2, c[2] >> 3)

    keys = {q(c) for c in layers.RUG_COLORS}
    if len(keys) != len(layers.RUG_COLORS):
        raise ValueError("rug colors collide at RGB565")
    for i, px in enumerate(bg.convert("RGBA").getdata()):
        x, y = i % bg.width, i // bg.width
        x0, y0, x1, y1 = box
        if px[3] and q(px) in keys and not (x0 <= x < x1 and y0 <= y < y1):
            raise ValueError(f"rug color at ({x},{y}) outside the rug")


def union_box(images) -> tuple[int, int, int, int]:
    box = None
    for img in images:
        b = img.getbbox()
        if b:
            box = b if box is None else (min(box[0], b[0]), min(box[1], b[1]), max(box[2], b[2]), max(box[3], b[3]))
    return box or (0, 0, 1, 1)


def build(name: str, module: ModuleType | str | None = None) -> Persona:
    """Every picture the device needs for persona `name` (see spec())."""
    return build_spec(spec(name, module))


def build_spec(s: Spec) -> Persona:
    background, layers, source = s.background, s.layers, s.animations

    poses = []
    for frames in source.ANIMATIONS.values():
        poses += [pose for pose, _ in frames]
    poses += list(source.BLINKS.values()) + list(source.WINKS.values())
    # Each pose is drawn once, however many animations show it.
    drawn = {pose: layers.foreground(pose) for pose in dict.fromkeys(poses)}
    below = under(layers)
    for pose, fg in drawn.items():
        check_layers(layers, pose, below, fg)
    # One crop box for every frame: the area the persona ever covers.
    box = union_box(drawn.values())

    # Identical frames come back as the same picture, so they are stored once.
    by_hash: dict[str, Image.Image] = {}

    def frame(pose) -> Image.Image:
        img = drawn[pose].crop(box)
        return by_hash.setdefault(hashlib.sha1(img.tobytes()).hexdigest(), img)

    animations = {}
    for key, frames in source.ANIMATIONS.items():
        animations[key] = Animation(
            frames=[(frame(pose), ms) for pose, ms in frames],
            blink=frame(source.BLINKS[key]) if key in source.BLINKS else None,
            wink=frame(source.WINKS[key]) if key in source.WINKS else None,
        )

    persona = Persona(
        background=background,
        backdrop=below.background.copy(),
        sprite_offset=box[:2],
        animations=animations,
        window=layers.WINDOW,
    )

    if hasattr(layers, "plant"):
        stages = [layers.plant(s, False) for s in range(layers.PLANT_STAGES)]
        wilted = [layers.plant(s, True) for s in range(layers.PLANT_STAGES)]
        pbox = union_box(stages + wilted)
        persona.plant_offset = pbox[:2]
        persona.plant_stages = [img.crop(pbox) for img in stages]
        persona.plant_wilted = [img.crop(pbox) for img in wilted]

    if hasattr(layers, "RUG_COLORS"):
        check_rug(layers, persona.backdrop)

        def hexc(c):
            return (c[0] << 16) | (c[1] << 8) | c[2]

        persona.recolor_from = [hexc(c) for c in layers.RUG_COLORS]
        persona.recolor_by_weekday = [[hexc(c) for c in day] for day in layers.RUG_BY_WEEKDAY]
    if s.check is not None:
        s.check(persona)
    return persona


def previews(name: str, out: Path, module: ModuleType | str | None = None) -> None:
    s = spec(name, module)
    layers, source = s.layers, s.animations
    persona = build_spec(s)
    out.mkdir(parents=True, exist_ok=True)
    persona.backdrop.save(out / "bg.png")
    for i, (healthy, wilted) in enumerate(zip(persona.plant_stages, persona.plant_wilted, strict=False)):
        healthy.save(out / f"plant_s{i}.png")
        wilted.save(out / f"plant_w{i}.png")
    unique: dict[int, Image.Image] = {}
    for anim in persona.animations.values():
        for img in [f for f, _ in anim.frames] + [anim.blink, anim.wink]:
            if img is not None:
                unique.setdefault(id(img), img)
    for i, img in enumerate(unique.values()):
        img.save(out / f"f{i:02d}.png")

    # One row per animation: each frame as the full scene, at 2x.
    rows = [
        (key, [p for p, _ in frames] + [p for p in (source.BLINKS.get(key), source.WINKS.get(key)) if p])
        for key, frames in source.ANIMATIONS.items()
    ]
    w, h = persona.backdrop.size
    cols = max(len(poses) for _, poses in rows)
    sheet = Image.new("RGB", (cols * w * 2, len(rows) * h * 2), (40, 40, 40))
    for r, (_, poses) in enumerate(rows):
        for c, pose in enumerate(poses):
            tile = layers.scene(pose).convert("RGB").resize((w * 2, h * 2), Image.NEAREST)
            sheet.paste(tile, (c * w * 2, r * h * 2))
    sheet.save(out / "sheet.png")
    print(f"{name}: {len(unique)} frames of {persona.animations['Neutral'].frames[0][0].size} -> {out}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    for arg in sys.argv[2:] or discover():
        where, _, persona_name = arg.rpartition(":")
        previews(persona_name, Path(sys.argv[1]) / persona_name, where or None)
