"""Preview the daruma: contact sheets, GIFs, a hero still, and its size in flash.

    uv run python -m daruma_pixel.daruma_preview OUT_DIR

Writes to OUT_DIR:
  daruma_sheet_eyes{0,1,2}.png  every frame of every animation, one row each, 2x
  daruma_<name>.gif             main loops with their real timings, 3x (one eye)
  daruma_paint{1,2}.gif         the Paint one-shot for the first and second eye
  daruma_hero.png               Neutral with one eye painted, 3x
  daruma_hero_1x.png            the same at 1x

and prints the encoded size of the frames: all three eye states as whole
faces, and the blank face plus eye overlays. Sizes come from the encoder
the firmware build uses (components/daruma/sprite_codec.py).
"""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent

from . import daruma
from . import daruma_persona
from . import daruma_moods
from .pixelkit import upscale

GIFS = ["Neutral", "Happy", "Loved", "Sad", "Scared", "Sleepy", "Sleeping", "talking", "Focus"]


def contact_sheet(n: int) -> Image.Image:
    src = daruma_moods.eyes(n)
    rows = []
    for key, frames in src.ANIMATIONS.items():
        tiles = [(f"{key} {i}: {ms} ms", pose) for i, (pose, ms) in enumerate(frames)]
        if key in src.BLINKS:
            tiles.append((f"{key} blink", src.BLINKS[key]))
        if key in src.WINKS:
            tiles.append((f"{key} wink", src.WINKS[key]))
        rows.append(tiles)
    w, h = daruma.W * 2, daruma.H * 2
    cols = max(len(r) for r in rows)
    sheet = Image.new("RGB", (cols * (w + 2), len(rows) * (h + 2)), (30, 30, 30))
    font = ImageFont.load_default()
    for r, tiles in enumerate(rows):
        for c, (label, pose) in enumerate(tiles):
            tile = upscale(daruma.scene(pose), 2).convert("RGB")
            d = ImageDraw.Draw(tile)
            d.rectangle((0, 0, len(label) * 6 + 4, 11), fill=(0, 0, 0))
            d.text((2, 0), label, font=font, fill=(255, 255, 255))
            sheet.paste(tile, (c * (w + 2), r * (h + 2)))
    return sheet


def gif(frames, path: Path) -> None:
    pics = [upscale(daruma.scene(p), 3).convert("RGB") for p, _ in frames]
    pics[0].save(path, save_all=True, append_images=pics[1:], duration=[ms for _, ms in frames], loop=0)


# --- Size, with the firmware's encoder ---------------------------------------


def _encoder():
    """components/daruma/sprite_codec.py: the encoder the firmware build uses.

    It is plain Python with no ESPHome imports, so it loads on its own.
    """
    path = HERE.parents[1] / "components/daruma/sprite_codec.py"
    spec = importlib.util.spec_from_file_location("daruma_sprite_codec", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses look the module up by name.
    spec.loader.exec_module(module)
    return module


def encoded_bytes(img: Image.Image, enc) -> int:
    """Flash bytes of one sprite: run data, RGB565 palette, and the Sprite object."""
    _, _, _, _, palette, data = enc.encode_image(img, "daruma")
    return len(data) + 2 * len(palette) + 16


def _key(img: Image.Image) -> str:
    return hashlib.sha1(repr(img.size).encode() + img.convert("RGBA").tobytes()).hexdigest()


def frames_of(face) -> list[Image.Image]:
    out = []
    for anim in face.animations.values():
        out += [f for f, _ in anim.frames] + [i for i in (anim.blink, anim.wink) if i is not None]
    return out


def report_size() -> None:
    enc = _encoder()
    faces = {n: daruma_persona.build(n) for n in daruma_persona.EYE_STATES}
    unique: dict[str, Image.Image] = {}
    naive = 0
    for n, face in faces.items():
        mine = {_key(i): i for i in frames_of(face)}
        size = sum(encoded_bytes(i, enc) for i in mine.values())
        naive += size
        unique.update(mine)
        w, h = face.animations["Neutral"].frames[0][0].size
        print(f"eyes {n}: {len(mine)} frames of {w}x{h} at {face.sprite_offset}, {size} B")
    shared = sum(encoded_bytes(i, enc) for i in unique.values())
    print(f"all three eye states: {naive} B separately, {shared} B with shared frames ({len(unique)} frames)")
    backdrop = encoded_bytes(faces[0].backdrop, enc)
    plant = sum(encoded_bytes(i, enc) for i in faces[0].plant_stages + faces[0].plant_wilted)
    print(f"room {backdrop} B, plant {plant} B (once for all three)")

    # Overlay option: blank face + eye patches + Paint stored whole.
    base = {_key(i): i for i in frames_of(faces[0])}
    patches = {}
    for entry in daruma_persona.eye_overlays().values():
        for row in entry.frames + [r for r in (entry.blink, entry.wink) if r]:
            for patch in row:
                if patch:
                    patches[_key(patch.image)] = patch.image
    paint = {}
    for n in (1, 2):
        paint.update({_key(f): f for f, _ in faces[n].animations["Paint"].frames})
    paint = {k: v for k, v in paint.items() if k not in base}
    b = sum(encoded_bytes(i, enc) for i in base.values())
    p = sum(encoded_bytes(i, enc) for i in patches.values())
    q = sum(encoded_bytes(i, enc) for i in paint.values())
    print(f"overlay option: blank face {b} B + {len(patches)} eye patches {p} B + Paint {q} B = {b + p + q} B")


def main(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for n in daruma_persona.EYE_STATES:
        contact_sheet(n).save(out / f"daruma_sheet_eyes{n}.png")
    one = daruma_moods.eyes(1).ANIMATIONS
    for key in GIFS:
        gif(one[key], out / f"daruma_{key.lower()}.gif")
    for n in (1, 2):
        paint = daruma_moods.eyes(n).ANIMATIONS["Paint"]
        # Hold the blank eye a moment first, then paint, then rest.
        gif([(daruma.Pose(painted=n - 1), 800), *paint, (daruma.Pose(painted=n), 1200)], out / f"daruma_paint{n}.gif")
    hero = daruma.scene(daruma.Pose(painted=1))
    hero.save(out / "daruma_hero_1x.png")
    upscale(hero, 3).save(out / "daruma_hero.png")
    report_size()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    main(Path(sys.argv[1]))
