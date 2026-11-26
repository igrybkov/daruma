"""Preview: the Habitica persona (fixture art) on the screen, corners marked.

    uv run python tests/preview_habitica.py OUT_DIR

Writes OUT_DIR/<look>-<w>x<h>.png (the screen as the device draws it) and
<look>-<w>x<h>-corners.png (the same with the bottom corners marked), for
the fixture standing and riding, on the BOX-3's 320x240 and a wider
480x272. Then all.png, every corners picture side by side.

The view follows SpritePersona::view_ (sprite_persona.cpp): the largest
whole scale that fits, the room on the bottom, and edge strips
(daruma_sprites/extend.py) wherever a margin has room for a scene pixel.
The corners follow layout.h: the pomodoro plaque in the bottom left
(three tomatoes, and its tallest, 15), the badge in the bottom right.

Uses only the fixture: no Habitica art.
"""

from __future__ import annotations

import sys
from pathlib import Path

import esphome_components  # noqa: F401
from esphome.components.daruma_sprites import extend
from PIL import Image, ImageDraw

from daruma_personas import habitica
from daruma_personas.habitica import fixture, moods

SCREENS = ((320, 240), (480, 272))
PLAQUE_STEP, PLAQUE_PAD, BADGE = 22, 6, 42  # Design pixels (layout.h, plaque.h).


def view(size: tuple[int, int], w: int, h: int) -> tuple[int, int, int, int, int, int]:
    """scale, left, right and top strip cells, and where the view starts on screen."""
    sw, sh = size
    s = max(1, min(sw // w, sh // h))
    core_x, core_y = (sw - w * s) // 2, sh - h * s

    def cells(margin: int) -> int:
        return (margin + s - 1) // s if margin >= s else 0

    left, right, top = cells(core_x), cells(sw - (core_x + w * s)), cells(core_y)
    return s, left, right, top, core_x - left * s, core_y - top * s


def screen(scene: Image.Image, room: Image.Image, size: tuple[int, int]) -> Image.Image:
    """The scene with the room's edge strips round it, scaled onto a screen."""
    s, left, right, top, sx, sy = view(size, room.width, room.height)
    rows = [[room.getpixel((x, y)) for x in range(room.width)] for y in range(room.height)]
    ls, rs, ts = extend.left_strip(rows), extend.right_strip(rows), extend.top_strip(rows)
    out = Image.new("RGBA", (left + room.width + right, top + room.height))
    for y in range(out.height):
        by = y - top
        sy_ = by if by >= 0 else by % len(ts)
        for x in range(out.width):
            bx = x - left
            if by >= 0 and 0 <= bx < room.width:
                px = scene.getpixel((bx, by))
            elif bx < 0:
                px = ls[sy_][bx % len(ls[0])]
            elif bx >= room.width:
                px = rs[sy_][(bx - room.width) % len(rs[0])]
            else:
                px = ts[sy_][bx]
            out.putpixel((x, y), px)
    img = Image.new("RGB", size, (20, 20, 24))
    img.paste(out.resize((out.width * s, out.height * s), Image.NEAREST).convert("RGB"), (sx, sy))
    return img


def corners(img: Image.Image) -> Image.Image:
    """The plaque with 3 tomatoes (solid), its tallest (faint), the badge and the info line."""
    w, h = img.size
    unit = min(w, h) / 240

    def px(v: float) -> int:
        return round(v * unit)

    edge, bottom = px(6), h - px(6) - px(18) - px(4)
    out = img.convert("RGBA")
    over = Image.new("RGBA", out.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(over)
    pw = 3 * px(PLAQUE_STEP) + px(PLAQUE_PAD)
    for rows, alpha in ((1, 110), (5, 40)):
        ph = rows * px(PLAQUE_STEP) + px(PLAQUE_PAD)
        box = (edge, bottom - ph, edge + pw - 1, bottom - 1)
        d.rectangle(box, fill=(255, 80, 60, alpha), outline=(255, 80, 60, 255))
    b = px(BADGE)
    d.ellipse((w - edge - b, bottom - b, w - edge - 1, bottom - 1), fill=(52, 150, 74, 160))
    d.rectangle((edge, bottom + px(4), w - edge - 1, bottom + px(4) + px(18) - 1), outline=(255, 255, 0, 180))
    out.alpha_composite(over)
    return out.convert("RGB")


def main(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    riding = {**fixture.USER, "items": {**fixture.USER["items"], "currentMount": fixture.MOUNT}}
    looks = {"standing": habitica.FIXTURE_LAYERS, "riding": habitica.layers_of({"look": riding}, None)}
    marked = []
    for name, layers in looks.items():
        scene = layers.scene(moods.ANIMATIONS["Neutral"][0][0])
        for size in SCREENS:
            img = screen(scene, layers.background(), size)
            img.save(out / f"{name}-{size[0]}x{size[1]}.png")
            marked.append(corners(img))
            marked[-1].save(out / f"{name}-{size[0]}x{size[1]}-corners.png")
    gap = 8
    sheet = Image.new("RGB", (sum(i.width for i in marked[:2]) + gap, 2 * 272 + gap), (255, 255, 255))
    for i, img in enumerate(marked):
        sheet.paste(img, ((i % 2) * (320 + gap), (i // 2) * (272 + gap)))
    sheet.save(out / "all.png")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(Path(sys.argv[1]))
