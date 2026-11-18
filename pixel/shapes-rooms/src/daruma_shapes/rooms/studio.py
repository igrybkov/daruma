"""The portrait studio: a Scene (scene.py) in the style of an 80s pet portrait.

A mottled brown backdrop hangs from a roll bar and sweeps down to the floor,
lit by a soft spotlight behind the sitter and falling off to near black at
the edges, as old studio portraits do. A chrome stand holds the roll at its
left end, and the cloth's edge turns back there and casts a soft shadow on
the wall. The wall is flat sage paint, lit from the window, so the backdrop
reads as a thing hung in front of it. In the wall, the studio's window (the
device draws the sky in its glass) with a wide sill. The sitter poses on a
velvet drape whose color follows the weekday (scene.py's weekday colors).

Spots: "floor" (the middle of the drape, where the sitter sits) and "sill"
(the middle of the window sill's top, where a pot like cat_grass.py's can
stand).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from PIL import Image, ImageDraw

from daruma_pixel.pixelkit import Color, cached_picture
from daruma_pixel.scene import WEEKDAY_COLORS, Spot

W, H = 106, 80
WINDOW = (4, 8, 22, 20)  # Glass: x, y, width, height. The cross bars stay in the scene.
SPOTS = {
    "floor": Spot(W // 2, H - 5),
    "sill": Spot(WINDOW[0] + WINDOW[2] // 2, WINDOW[1] + WINDOW[3] + 2),  # The sill's top row.
}
FLOOR_Y = H - 14
DRAPE_BOX = (0, H - 13, W, H)  # Where the weekday colors may be.
BACKDROP_X = 30  # The backdrop's left edge; the studio wall is left of it.
POLE_X = BACKDROP_X - 2  # The stand's upright, 2 pixels wide, just left of the cloth.

# Backdrop browns, darkest first: the spotlight picks among them.
BROWNS = ((40, 28, 22), (56, 38, 28), (74, 50, 34), (94, 64, 42), (116, 80, 52), (138, 96, 62), (158, 112, 72))
_BAYER = ((0, 8, 2, 10), (12, 4, 14, 6), (3, 11, 1, 9), (15, 7, 13, 5))


def _mottle(x: int, y: int) -> float:
    """Soft blotches, the same every build: a few slow waves added up."""
    return (
        math.sin(x * 0.31 + y * 0.17) + math.sin(x * 0.13 - y * 0.29 + 1.7) + 0.6 * math.sin(x * 0.57 + y * 0.43 + 0.4)
    ) / 2.6


@dataclass(frozen=True)
class Studio:
    """The studio, with its colors: sage, cream and a maroon drape by default."""

    # The studio wall round the window: flat sage paint, lightest by the window.
    wall: tuple[Color, ...] = ((104, 120, 108), (90, 104, 94), (76, 88, 80), (62, 72, 66))
    frame: Color = (196, 180, 150)  # Window frame and sill: old cream paint.
    frame_shade: Color = (150, 134, 108)
    bar: Color = (30, 28, 30)  # The roll the backdrop hangs from, and its stand.
    bar_light: Color = (86, 84, 88)
    curl: Color = (150, 124, 92)  # The cloth's paler back, where its edge turns over.
    floor: Color = (58, 40, 30)  # Dark boards left of the sweep.
    floor_line: Color = (42, 30, 24)
    drape_edge: Color = (156, 70, 92)  # Velvet: maroon, like an 80s sweater's collar.
    drape: Color = (122, 40, 62)
    drape_shadow: Color = (94, 28, 48)
    light_at: tuple[int, int] = (55, 34)  # The spotlight's centre: behind the sitter's head.

    window = WINDOW
    spots = SPOTS

    def image(self) -> Image.Image:
        return studio(self)

    def background(self) -> Image.Image:
        img = studio(self)
        px = img.load()
        x0, y0, w, h = WINDOW
        for y in range(y0, y0 + h):
            for x in range(x0, x0 + w):
                if not _is_bar(x, y):
                    px[x, y] = (0, 0, 0, 0)
        return img

    def layers(self) -> dict:
        return {
            "RUG_COLORS": (self.drape_edge, self.drape, self.drape_shadow),
            "RUG_BY_WEEKDAY": WEEKDAY_COLORS,
            "RUG_BOX": DRAPE_BOX,
        }


def _is_bar(x: int, y: int) -> bool:
    """The window's cross bars, inside the glass."""
    x0, y0, w, h = WINDOW
    return x == x0 + w // 2 or y == y0 + h // 2


def _wall_tone(x: int, y: int, tones: int) -> int:
    """Which wall paint, lightest first: light from the window falls off toward
    the floor and the backdrop. A thin checker where two tones meet."""
    t = math.hypot(x - 13, (y - 18) * 0.8) / 14 + max(0, y - 46) / 10 + max(0, x - 22) / 8
    k = int(t) + (1 if t % 1 > (0.42 if (x + y) % 2 else 0.58) else 0)
    return max(0, min(tones - 1, k))


@cached_picture
def studio(s: Studio) -> Image.Image:
    img = Image.new("RGBA", (W, H), (*s.wall[0], 255))
    d = ImageDraw.Draw(img)
    px = img.load()
    # The painted wall, then the cloth's shadow on it: a tone darker, softening
    # into a checker 3 pixels out.
    for y in range(FLOOR_Y + 1):
        for x in range(BACKDROP_X):
            k = _wall_tone(x, y, len(s.wall))
            out = BACKDROP_X - x
            if y > 4 and (out <= 3 or (out == 4 and (x + y) % 2 == 0)):
                k = min(len(s.wall) - 1, k + 1)
            px[x, y] = (*s.wall[k], 255)
    # The window, its sky as the device paints a clear day.
    x0, y0, w, h = WINDOW
    d.rectangle((x0 - 2, y0 - 2, x0 + w + 1, y0 + h + 1), fill=s.frame)
    d.line((x0 + w + 1, y0 - 1, x0 + w + 1, y0 + h + 1), fill=s.frame_shade)
    sky = ((122, 190, 236), (150, 206, 240), (184, 224, 246))
    span = h - 1
    for y in range(h):
        band = 2 if y >= 2 * span // 3 else 1 if y >= span // 3 else 0
        d.line((x0, y0 + y, x0 + w - 1, y0 + y), fill=sky[band])
    for xa, xb, yy in ((6, 9, 4), (4, 10, 5), (4, 10, 6), (4, 10, 7)):
        d.line((x0 + xa, y0 + yy, x0 + xb, y0 + yy), fill=(255, 255, 255))
    for y in range(y0, y0 + h):
        for x in range(x0, x0 + w):
            if _is_bar(x, y):
                px[x, y] = (*s.frame, 255)
    # The sill, wider than the frame.
    d.rectangle((x0 - 4, y0 + h + 2, x0 + w + 3, y0 + h + 3), fill=s.frame)
    d.line((x0 - 4, y0 + h + 4, x0 + w + 3, y0 + h + 4), fill=s.frame_shade)
    # The backdrop: mottled browns, bright in the spotlight, dark at the edges,
    # with soft folds where it is gathered under the roll.
    lx, ly = s.light_at
    for y in range(4, H):
        for x in range(BACKDROP_X, W):
            dist = math.hypot((x - lx) / 1.25, y - ly) / 44
            v = (1 - min(1.0, dist)) ** 1.3 * (len(BROWNS) - 1.6) + 0.9 * _mottle(x, y)
            if y < 16:
                v += 0.8 * math.sin(x * 0.8) * (16 - y) / 12
            v += (_BAYER[y % 4][x % 4] / 16 - 0.5) * 0.9
            k = max(0, min(len(BROWNS) - 1, round(v)))
            px[x, y] = (*BROWNS[k], 255)
    # Its left edge turns over: the paler back of the cloth, then a dark fold.
    d.line((BACKDROP_X, 4, BACKDROP_X, FLOOR_Y + 1), fill=s.curl)
    d.line((BACKDROP_X + 1, 4, BACKDROP_X + 1, FLOOR_Y + 1), fill=BROWNS[0])
    # The floor left of the sweep.
    d.rectangle((0, FLOOR_Y + 1, BACKDROP_X - 1, H), fill=s.floor)
    for y in range(FLOOR_Y + 4, H, 4):
        d.line((0, y, BACKDROP_X - 1, y), fill=s.floor_line)
    d.line((0, FLOOR_Y, BACKDROP_X - 1, FLOOR_Y), fill=s.floor_line)
    # The roll bar, its end resting in a clamp on the stand.
    d.rectangle((BACKDROP_X - 3, 1, W, 3), fill=s.bar)
    d.line((BACKDROP_X - 3, 1, W, 1), fill=s.bar_light)
    # The stand: a chrome upright from the clamp down to a foot on the floor.
    d.rectangle((POLE_X, 0, POLE_X + 1, FLOOR_Y + 2), fill=s.bar)
    d.line((POLE_X, 4, POLE_X, FLOOR_Y + 2), fill=s.bar_light)
    d.rectangle((POLE_X - 1, 0, POLE_X + 2, 4), fill=s.bar)
    d.line((POLE_X - 1, 0, POLE_X + 2, 0), fill=s.bar_light)
    d.line((POLE_X - 3, FLOOR_Y + 3, POLE_X + 4, FLOOR_Y + 3), fill=s.bar)
    d.line((POLE_X - 4, FLOOR_Y + 4, POLE_X + 5, FLOOR_Y + 4), fill=s.bar)
    # The velvet drape the sitter poses on, a fold of shadow in the middle.
    cx = W // 2
    d.ellipse((cx - 36, H - 12, cx + 36, H + 2), fill=s.drape_edge)
    d.ellipse((cx - 34, H - 11, cx + 34, H + 1), fill=s.drape)
    d.ellipse((cx - 24, H - 9, cx + 24, H - 2), fill=s.drape_shadow)
    return img
