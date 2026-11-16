"""The cozy room: a Scene (pet.py) for pets indoors.

Plank walls, a window with the sky, a shelf with the plant (plant.py, the
progress prop), floor boards, and a rug that changes color by weekday.
Colors and a few details (a painted lower wall, a striped rug) vary per
persona, so two pets need not share one room. The defaults are the
corgi's room.
"""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image, ImageDraw

from . import plant as _plant
from .pixelkit import Color

W, H = 106, 80
WINDOW = (8, 8, 24, 21)  # Glass: x, y, width, height. The cross bars stay in the room.
RUG_BOX = (0, H - 13, W, H)  # Where the weekday colors may be: the rug, on the floor.

@dataclass(frozen=True)
class Room:
    """A cozy room: plank wall, a window, a shelf for the plant, floor boards
    and a rug. The defaults are the corgi's room."""

    wall: tuple[Color, ...] = ((116, 74, 48), (128, 84, 54), (122, 79, 51))  # Planks, repeating.
    wall_line: Color = (92, 56, 36)
    floor: Color = (164, 112, 70)
    floor_line: Color = (138, 90, 56)
    rug_edge: Color = (196, 150, 90)
    rug: Color = (150, 58, 58)
    rug_shadow: Color = (120, 44, 44)  # Darker middle, under the pet.
    rug_stripes: bool = False  # A woven stripe across the rug, in the shadow color.
    sky: tuple[Color, ...] = ((122, 190, 236), (150, 206, 240), (184, 224, 246))
    frame: Color = (86, 52, 34)  # Window frame and shelf.
    wainscot: Color | None = None  # A lower wall panel below a rail, if any.
    rail: Color | None = None

    # The Scene protocol (pet.py).
    window = WINDOW  # Not a field: every room has its window in the same place.

    def image(self) -> Image.Image:
        return room(self)

    def background(self) -> Image.Image:
        img = room(self)
        px = img.load()
        x0, y0, w, h = WINDOW
        for y in range(y0, y0 + h):
            for x in range(x0, x0 + w):
                if px[x, y][:3] != self.frame:
                    px[x, y] = (0, 0, 0, 0)
        return img

    def layers(self) -> dict:
        return {"plant": _plant.plant, "PLANT_STAGES": _plant.STAGES, "DEFAULT_STAGE": _plant.DEFAULT_STAGE,
                "RUG_COLORS": (self.rug_edge, self.rug, self.rug_shadow), "RUG_BY_WEEKDAY": RUG_BY_WEEKDAY,
                "RUG_BOX": RUG_BOX}



# The rug changes color with the day of the week, in the colors people most
# often "see" the days in (weekday-color synesthesia, and the meme that
# Thursday is brown): white Sunday, blue Monday, yellow Tuesday, green
# Wednesday, brown Thursday, pink Friday, purple Saturday. The device swaps
# the room's three rug colors for the day's (edge, main, shadow), Sunday first.
RUG_BY_WEEKDAY = (
    ((184, 150, 104), (236, 228, 210), (204, 192, 170)),  # Sunday: white
    ((204, 170, 112), (58, 92, 160), (44, 70, 126)),      # Monday: blue
    ((236, 214, 160), (222, 182, 48), (180, 144, 32)),    # Tuesday: yellow
    ((206, 172, 100), (62, 128, 76), (46, 98, 58)),       # Wednesday: green
    ((206, 164, 110), (100, 62, 40), (78, 46, 30)),       # Thursday: brown, obviously
    ((228, 190, 144), (214, 104, 146), (172, 78, 114)),   # Friday: pink
    ((206, 166, 108), (112, 70, 150), (86, 52, 118)),     # Saturday: purple
)


def room(r: Room) -> Image.Image:
    img = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    d = ImageDraw.Draw(img)
    floor_y = H - 14
    for x in range(0, W, 7):  # Vertical wall planks.
        d.rectangle((x, 0, x + 6, floor_y), fill=r.wall[(x // 7) % len(r.wall)])
        d.line((x, 0, x, floor_y), fill=r.wall_line)
    if r.wainscot:  # A painted lower panel under a rail.
        d.rectangle((0, 44, W, floor_y), fill=r.wainscot)
        for x in range(3, W, 9):
            d.line((x, 47, x, floor_y - 2), fill=r.wall_line)
        d.rectangle((0, 42, W, 43), fill=r.rail)
    # Window with sky bands and a cloud.
    wx, wy, ww, wh = 8, 8, 24, 20
    d.rectangle((wx - 2, wy - 2, wx + ww + 1, wy + wh + 1), fill=r.frame)
    for i, col in enumerate(r.sky):
        d.rectangle((wx, wy + i * wh // 3, wx + ww - 1, wy + (i + 1) * wh // 3), fill=col)
    d.rectangle((wx + 4, wy + 5, wx + 10, wy + 7), fill=(255, 255, 255))
    d.rectangle((wx + 6, wy + 4, wx + 9, wy + 4), fill=(255, 255, 255))
    d.line((wx + ww // 2, wy, wx + ww // 2, wy + wh), fill=r.frame)
    d.line((wx, wy + wh // 2, wx + ww, wy + wh // 2), fill=r.frame)
    # Shelf; the plant on it is its own layer (plant.py).
    d.rectangle((W - 30, 22, W - 8, 23), fill=r.frame)
    # Floor boards.
    d.rectangle((0, floor_y, W, H), fill=r.floor)
    for y in range(floor_y + 3, H, 4):
        d.line((0, y, W, y), fill=r.floor_line)
    d.line((0, floor_y, W, floor_y), fill=r.wall_line)
    # Rug and a soft shadow under the pet.
    d.ellipse((W // 2 - 34, H - 12, W // 2 + 34, H - 1), fill=r.rug_edge)
    d.ellipse((W // 2 - 32, H - 11, W // 2 + 32, H - 2), fill=r.rug)
    if r.rug_stripes:  # Two woven bands near each end, in the edge color.
        px = img.load()
        for dx in (-28, -27, -24, -23, 23, 24, 27, 28):
            for y in range(H - 11, H - 1):
                if px[W // 2 + dx, y][:3] == r.rug:
                    px[W // 2 + dx, y] = (*r.rug_edge, 255)
    d.ellipse((W // 2 - 24, H - 9, W // 2 + 24, H - 4), fill=r.rug_shadow)
    return img


