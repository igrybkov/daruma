"""Preview: the fixture Habitica avatar at three scales on a 320x240 screen.

    uv run python tests/preview_habitica_scale.py OUT_DIR

Writes, per candidate, OUT_DIR/<n>-<name>.png (the screen as the device
draws it) and <n>-<name>-corners.png (the same with the bottom corners
marked), then all.png, every candidate side by side.

1. scene: 106x80 at 3x, the avatar in our cozy room, like the other personas;
2. habitica: the avatar's own background, 47x48 (the top row cut) at 5x,
   the sides filled from its edge strips;
3. figure: a 40x30 room of our own at 8x, the figure first.

The view follows SpritePersona::view_ (sprite_persona.cpp): the largest
whole scale that fits, the room on the bottom, and edge strips
(daruma_sprites/extend.py) wherever a margin has room for a scene pixel.
The corners follow layout.h at 320x240: the pomodoro plaque in the bottom
left (three tomatoes, and its tallest, 15), the badge in the bottom right.

Uses only the fixture: no Habitica art.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, replace
from pathlib import Path

import esphome_components  # noqa: F401
from esphome.components.daruma_sprites import extend
from PIL import Image, ImageDraw

from daruma_personas.habitica import compose, fixture, look
from daruma_shapes.rooms.cozy_room import Room

SCREEN = (320, 240)
EDGE = 6
CORNER_BOTTOM = SCREEN[1] - 6 - 18 - 4  # layout.h: the info line, then 4 above it.
PLAQUE_STEP, PLAQUE_PAD = 22, 6
BADGE = 42


@dataclass
class View:
    scale: int
    left: int
    right: int
    top: int
    sx: int
    sy: int


def view(w: int, h: int, strips: bool) -> View:
    s = max(1, min(SCREEN[0] // w, SCREEN[1] // h))
    core_x = (SCREEN[0] - w * s) // 2
    core_y = SCREEN[1] - h * s

    def cells(margin: int) -> int:
        return (margin + s - 1) // s if margin >= s else 0

    left = cells(core_x) if strips else 0
    right = cells(SCREEN[0] - (core_x + w * s)) if strips else 0
    top = cells(core_y) if strips else 0
    return View(s, left, right, top, core_x - left * s, core_y - top * s)


def extended(room: Image.Image, v: View) -> Image.Image:
    """The room with its edge strips round it, at one pixel per scene pixel."""
    rows = [[room.getpixel((x, y)) for x in range(room.width)] for y in range(room.height)]
    ls, rs, ts = extend.left_strip(rows), extend.right_strip(rows), extend.top_strip(rows)
    pl, pr, pt = len(ls[0]), len(rs[0]), len(ts)
    bw, bh = room.size
    out = Image.new("RGBA", (v.left + bw + v.right, v.top + bh))
    for y in range(out.height):
        by = y - v.top
        sy = by if by >= 0 else by % pt
        for x in range(out.width):
            bx = x - v.left
            if by >= 0 and 0 <= bx < bw:
                px = rows[by][bx]
            elif bx < 0:
                px = ls[sy][bx % pl]
            elif bx >= bw:
                px = rs[sy][(bx - bw) % pr]
            else:
                px = ts[sy][bx]
            out.putpixel((x, y), px)
    return out


def screen(room: Image.Image, actors: list[tuple[Image.Image, tuple[int, int]]], background=(20, 20, 24)) -> tuple:
    """The screen: the extended room, then each actor at its place in room pixels."""
    v = view(room.width, room.height, strips=True)
    scene = extended(room.convert("RGBA"), v)
    for img, (x, y) in actors:
        # paste, not alpha_composite: an actor taller than the room starts above it.
        # Its alpha is 0 or 255 (downscale.py), so the mask is exact.
        scene.paste(img, (x + v.left, y + v.top), img)
    out = Image.new("RGB", SCREEN, background)
    big = scene.resize((scene.width * v.scale, scene.height * v.scale), Image.NEAREST)
    out.paste(big.convert("RGB"), (v.sx, v.sy))
    return out, v, scene.size


def corners(img: Image.Image) -> Image.Image:
    """The bottom corners marked: plaque with 3 tomatoes (solid), its tallest (dashed), and the badge."""
    out = img.copy().convert("RGBA")
    over = Image.new("RGBA", out.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(over)
    w = 3 * PLAQUE_STEP + PLAQUE_PAD
    for rows, alpha in ((1, 110), (5, 40)):
        h = rows * PLAQUE_STEP + PLAQUE_PAD
        d.rectangle((EDGE, CORNER_BOTTOM - h, EDGE + w - 1, CORNER_BOTTOM - 1), fill=(255, 80, 60, alpha))
        d.rectangle((EDGE, CORNER_BOTTOM - h, EDGE + w - 1, CORNER_BOTTOM - 1), outline=(255, 80, 60, 255))
    bx = SCREEN[0] - EDGE - BADGE
    d.ellipse((bx, CORNER_BOTTOM - BADGE, bx + BADGE - 1, CORNER_BOTTOM - 1), fill=(52, 150, 74, 160))
    d.rectangle((0, CORNER_BOTTOM, SCREEN[0] - 1, CORNER_BOTTOM + 3 + 18), outline=(255, 255, 0, 180))
    out.alpha_composite(over)
    return out.convert("RGB")


def trimmed(img: Image.Image) -> tuple[Image.Image, tuple[int, int]]:
    """`img` cut to what it shows, and where that was."""
    box = img.getbbox() or (0, 0, 1, 1)
    return img.crop(box), box[:2]


def standing(img: Image.Image, foot_x: int, floor: int) -> tuple[Image.Image, tuple[int, int]]:
    """`img` cut to what it shows, centered on foot_x with its bottom row on `floor`."""
    cut, _ = trimmed(img)
    return cut, (foot_x - cut.width // 2, floor - cut.height + 1)


def scene_3x(avatar: compose.Avatar) -> tuple:
    """1. The cozy room, 106x80. The rider stands on the rug, the pet beside."""
    room = Room().image()
    rider = avatar.flat(compose.MOUNT_BODY, compose.RIDER, compose.MOUNT_HEAD)
    return screen(room, [standing(rider, 53, 76), standing(avatar.groups[compose.PET], 32, 77)])


def habitica_5x(avatar: compose.Avatar) -> tuple:
    """2. Habitica's background, 47x49 cut to 47x48 (the top row: sky), the avatar as Habitica stacks it."""
    room = avatar.groups[compose.BACKGROUND].crop((0, 1, 47, 49))
    figure = avatar.flat(*(g for g in compose.GROUPS if g != compose.BACKGROUND)).crop((0, 1, 47, 49))
    return screen(room, [(figure, (0, 0))])


WALL, WALL_LINE, WAINSCOT, RAIL, FLOOR, FLOOR_LINE = (
    (98, 84, 120),
    (86, 72, 106),
    (72, 60, 90),
    (130, 110, 150),
    (150, 104, 68),
    (124, 84, 54),
)


def small_room() -> Image.Image:
    """A 40x30 room of our own: wall, a rail, wainscot, floor boards."""
    img = Image.new("RGBA", (40, 30), (*WALL, 255))
    d = ImageDraw.Draw(img)
    for x in range(0, 40, 5):
        d.line((x, 0, x, 15), fill=WALL_LINE)
    d.rectangle((0, 16, 39, 16), fill=RAIL)
    d.rectangle((0, 17, 39, 23), fill=WAINSCOT)
    d.rectangle((0, 24, 39, 29), fill=FLOOR)
    for y in (26, 28):
        d.line((0, y, 39, y), fill=FLOOR_LINE)
    return img


def figure_8x(avatar: compose.Avatar) -> tuple:
    """3. A 40x30 room at 8x. Rider and pet each stand on the floor."""
    rider = avatar.flat(compose.MOUNT_BODY, compose.RIDER, compose.MOUNT_HEAD)
    return screen(small_room(), [standing(rider, 22, 28), standing(avatar.groups[compose.PET], 7, 29)])


CANDIDATES = (("1-scene-3x", scene_3x), ("2-habitica-5x", habitica_5x), ("3-figure-8x", figure_8x))


def describe(name: str, v: View, size: tuple[int, int]) -> str:
    w, h = size
    # Three view-sized RGB565 buffers in PSRAM (SpritePersona::buffers_).
    return f"{name}: scale {v.scale}, view {w}x{h} (strips L{v.left} R{v.right} T{v.top}), buffers {3 * w * h * 2} B"


def main(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    plain = look.from_user(fixture.USER)
    looks = {"": plain, "-mount": replace(plain, mount=fixture.MOUNT)}
    row = []
    for suffix, the_look in looks.items():
        avatar = compose.compose(the_look, fixture.source())
        for name, render in CANDIDATES:
            img, v, size = render(avatar)
            img.save(out / f"{name}{suffix}.png")
            marked = corners(img)
            marked.save(out / f"{name}{suffix}-corners.png")
            row.append(marked)
            print(describe(name + suffix, v, size))
    gap = 8
    sheet = Image.new("RGB", (3 * SCREEN[0] + 2 * gap, 2 * SCREEN[1] + gap), (255, 255, 255))
    for i, img in enumerate(row):
        sheet.paste(img, ((i % 3) * (SCREEN[0] + gap), (i // 3) * (SCREEN[1] + gap)))
    sheet.save(out / "all.png")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(Path(sys.argv[1]))
