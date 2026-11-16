"""Pixel personas for the BOX, built from the Python art in this package.

The device build calls build(name) while it compiles (daruma_sprites with
`pixel_art:`), so changing a persona or a room only needs a new compile.
Run it by hand to look at the result:

    uv run python -m daruma_pixel.personas OUT_DIR [corgi|the_boss|jack_russell|tabby_cat ...]

That writes, per persona, OUT_DIR/<name>/: every layer as a PNG and sheet.png,
every frame of every animation as the screen would show it.

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
import sys
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image


# name -> (background color, layers module, module with ANIMATIONS/BLINKS/WINKS)
# Modules may be given by name; they load when that persona is built, so a persona
# whose script is missing only fails when it is used. A name with a leading
# dot is a module of this package (".preview"); any other name is imported
# as is, so a persona kept outside the package names its own modules.
# The layers module has background(), foreground(pose), scene(pose), WINDOW
# (None without one), and optionally plant(stage, wilted) with PLANT_STAGES
# and the stage scene() shows by default, DEFAULT_STAGE (any prop that grows
# with the progress signal, healthy and wilted), and RUG_COLORS with
# RUG_BY_WEEKDAY (Sunday first) for colors that change daily, with RUG_BOX
# for where they may be (default: the bottom 13 rows).
PERSONAS = {
    "corgi": (0x4A2A1A, ".preview", ".moods"),
    "the_boss": (0xDED2BE, ".the_boss", ".the_boss"),
    "jack_russell": (0x76503A, ".jack_russell", ".jack_russell"),
    "tabby_cat": (0x281C16, ".tabby_cat", ".tabby_cat"),
}


def _persona(name: str):
    """(background, layers, source) for a persona, with its modules loaded."""
    import importlib

    background, layers, source = PERSONAS[name]
    load = lambda m: importlib.import_module(m, __package__) if isinstance(m, str) else m
    return background, load(layers), load(source)


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
    """Pixels at the screen's color depth; transparent ones as a marker no color can hit."""
    raw = img.convert("RGBA").tobytes()
    out = bytearray()
    for i in range(0, len(raw), 4):
        r, g, b, a = raw[i:i + 4]
        out += b"\xff\xff\xff" if a < 128 else bytes((r >> 3, g >> 2, b >> 3))
    return bytes(out)


def check_layers(layers, pose) -> None:
    """Stacked layers must equal the full scene. The hole shows the room's own glass."""
    full = layers.scene(pose)
    glass = Image.new("RGBA", full.size, (0, 0, 0, 0))
    if layers.WINDOW:
        x, y, w, h = layers.WINDOW
        glass.paste(full.crop((x, y, x + w, y + h)), (x, y))
    stacked = glass.copy()
    stacked.alpha_composite(layers.background())
    if hasattr(layers, "plant"):
        stacked.alpha_composite(layers.plant(layers.DEFAULT_STAGE, False))
    stacked.alpha_composite(layers.foreground(pose))
    # Glass pixels the persona covers come from the persona either way.
    if rgb565(stacked) != rgb565(full):
        raise ValueError("Layers do not add up to the scene; check background()/foreground()")


def check_rug(layers, bg: Image.Image) -> None:
    """The swapped rug colors must belong to the rug alone, at screen depth.

    The rug is where the layers' RUG_BOX (x0, y0, x1, y1) says, or else the
    bottom 13 rows; a scene may put its weekday colors anywhere it says.
    """
    box = getattr(layers, "RUG_BOX", (0, bg.height - 13, bg.width, bg.height))
    q = lambda c: (c[0] >> 3, c[1] >> 2, c[2] >> 3)
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


def build(name: str) -> Persona:
    background, layers, source = _persona(name)

    poses = []
    for frames in source.ANIMATIONS.values():
        poses += [pose for pose, _ in frames]
    poses += list(source.BLINKS.values()) + list(source.WINKS.values())
    for pose in poses:
        check_layers(layers, pose)
    # One crop box for every frame: the area the persona ever covers.
    box = union_box(layers.foreground(pose) for pose in poses)

    # Identical frames come back as the same picture, so they are stored once.
    by_hash: dict[str, Image.Image] = {}

    def frame(pose) -> Image.Image:
        img = layers.foreground(pose).crop(box)
        return by_hash.setdefault(hashlib.sha1(img.tobytes()).hexdigest(), img)

    animations = {}
    for key, frames in source.ANIMATIONS.items():
        animations[key] = Animation(
            frames=[(frame(pose), ms) for pose, ms in frames],
            blink=frame(source.BLINKS[key]) if key in source.BLINKS else None,
            wink=frame(source.WINKS[key]) if key in source.WINKS else None,
        )

    persona = Persona(background=background, backdrop=layers.background(), sprite_offset=box[:2],
                animations=animations, window=layers.WINDOW)

    if hasattr(layers, "plant"):
        stages = [layers.plant(s, False) for s in range(layers.PLANT_STAGES)]
        wilted = [layers.plant(s, True) for s in range(layers.PLANT_STAGES)]
        pbox = union_box(stages + wilted)
        persona.plant_offset = pbox[:2]
        persona.plant_stages = [img.crop(pbox) for img in stages]
        persona.plant_wilted = [img.crop(pbox) for img in wilted]

    if hasattr(layers, "RUG_COLORS"):
        check_rug(layers, persona.backdrop)
        hexc = lambda c: (c[0] << 16) | (c[1] << 8) | c[2]
        persona.recolor_from = [hexc(c) for c in layers.RUG_COLORS]
        persona.recolor_by_weekday = [[hexc(c) for c in day] for day in layers.RUG_BY_WEEKDAY]
    return persona


def previews(name: str, out: Path) -> None:
    _, layers, source = _persona(name)
    persona = build(name)
    out.mkdir(parents=True, exist_ok=True)
    persona.backdrop.save(out / "bg.png")
    for i, (healthy, wilted) in enumerate(zip(persona.plant_stages, persona.plant_wilted)):
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
    rows = [(key, [p for p, _ in frames] + [p for p in (source.BLINKS.get(key), source.WINKS.get(key)) if p])
            for key, frames in source.ANIMATIONS.items()]
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
    for persona_name in sys.argv[2:] or PERSONAS:
        previews(persona_name, Path(sys.argv[1]) / persona_name)
