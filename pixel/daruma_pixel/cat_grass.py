"""A pot of cat grass on the studio's window sill, in 7 growth stages,
healthy or wilted: the progress prop of the tabby's studio (studio.py).

grass(stage, wilted) returns a 106x80 RGBA layer with only the pot on it:

  0  fresh soil, two green points just showing
  1  a short row of shoots
  2  a small tuft
  3  a tuft as tall as the pot
  4  a full tuft, a few blades bending out
  5  tall and thick
  6  lush, with seed heads on the tallest blades

Wilted: the same blades yellowed, shorter, flopped over the rim.
"""

from __future__ import annotations

from PIL import Image

W, H = 106, 80

CX = 15  # Pot centre, on the sill (sill top is y=31).
RIM_Y = 25
BASE_Y = 30

POT = (226, 220, 206)  # A plain white ceramic pot.
POT_SHADE = (190, 182, 166)
POT_LIGHT = (246, 242, 232)
POT_LINE = (112, 100, 88)
POT_BAND = (122, 46, 64)  # A maroon band, like the posing drape.
SOIL = (70, 46, 32)

GREEN = {False: ((52, 116, 52), (84, 156, 68), (140, 200, 96)),  # dark, mid, light
         True: ((132, 116, 52), (176, 156, 72), (208, 190, 110))}
SEED = (214, 196, 136)

# Blades per stage: (dx at the root, height, lean in px at the top).
_ALL = [(-3, 9, -2), (0, 13, 0), (2, 11, 1), (-1, 12, -1), (3, 8, 3), (-4, 7, -4), (1, 14, 1), (4, 10, 4),
        (-2, 10, -2), (0, 9, 2)]
BLADES = [
    [(-1, 1, 0), (2, 1, 0)],
    [(-3, 3, -1), (-1, 3, 0), (1, 4, 0), (3, 3, 1)],
    [(b[0], max(2, b[1] * 2 // 5), b[2] // 2) for b in _ALL[:6]],
    [(b[0], max(3, b[1] * 3 // 5), b[2] // 2) for b in _ALL[:8]],
    [(b[0], b[1] * 4 // 5, b[2]) for b in _ALL[:9]],
    [(b[0], b[1], b[2]) for b in _ALL],
    [(b[0], b[1] + 2, b[2]) for b in _ALL],
]


class Layer:
    def __init__(self) -> None:
        self.img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        self.px = self.img.load()

    def dot(self, x: float, y: float, c) -> None:
        x, y = round(x), round(y)
        if 0 <= x < W and 0 <= y < H:
            self.px[x, y] = (*c, 255)


def _pot(L: Layer) -> None:
    for y in range(RIM_Y, BASE_Y + 1):
        half = 5 if y == RIM_Y else (4 if y < BASE_Y - 1 else 3)
        for x in range(CX - half, CX + half + 1):
            c = POT_LIGHT if y == RIM_Y else POT
            if x >= CX + half - 1 and y > RIM_Y:
                c = POT_SHADE
            if y == RIM_Y + 3:
                c = POT_BAND
            L.dot(x, y, c)
        L.dot(CX - half - 1, y, POT_LINE)
        L.dot(CX + half + 1, y, POT_LINE)
    for x in range(CX - 4, CX + 5):
        L.dot(x, RIM_Y - 1, POT_LINE)
        L.dot(x, RIM_Y, SOIL if abs(x - CX) < 4 else POT_LIGHT)
    L.dot(CX - 5, RIM_Y - 1, POT_LINE)
    L.dot(CX + 5, RIM_Y - 1, POT_LINE)


def _blades(L: Layer, stage: int, wilted: bool) -> None:
    dark, mid, light = GREEN[wilted]
    root_y = RIM_Y - 1
    for i, (dx, h, lean) in enumerate(BLADES[stage]):
        if wilted:
            h = max(1, h * 3 // 5)
            lean = max(-6, min(6, (lean or (1 if i % 2 else -1)) * 2))  # Flopped over the rim.
        color = (dark, mid, light)[i % 3]
        # Small steps along the blade, so a bent one stays one connected line.
        steps = 4 * h
        for k in range(1, steps + 1):
            t = k / steps
            x = CX + dx + lean * t * t
            y = root_y - h * t + (abs(lean) * t * t * 0.9 if wilted else 0)
            L.dot(x, y, color)
        if stage == 6 and not wilted and h >= 14:
            L.dot(CX + dx + lean, root_y - h - 1, SEED)


def grass(stage: int, wilted: bool = False) -> Image.Image:
    stage = max(0, min(6, stage))
    L = Layer()
    _pot(L)
    _blades(L, stage, wilted)
    return L.img


STAGES = 7
DEFAULT_STAGE = 3  # What previews and the flat scene show.
