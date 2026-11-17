"""A potted pothos for the corgi's shelf, in 7 growth stages, healthy or wilted.

plant(stage, wilted) returns a 106x80 RGBA layer with only the plant on it.
The device draws one of them between the room and the corgi:

  0  a sprout in fresh soil
  1  two small leaves
  2  a little tuft
  3  a full tuft, the first vine over the shelf edge
  4  two vines trailing down the wall
  5  long vines, a taller tuft
  6  lush, three long vines and a small flower

Wilted: the same plant with yellowed leaves that hang down, the tips curled.
"""

from __future__ import annotations

import math

from PIL import Image

W, H = 106, 80

CX = 87  # Pot centre, on the shelf (shelf top is y=22).
RIM_Y = 15

POT = (178, 92, 60)
POT_SHADE = (140, 66, 44)
POT_LIGHT = (210, 128, 84)
POT_LINE = (96, 46, 30)
SOIL = (66, 42, 30)

LEAF = {
    False: ((48, 104, 50), (78, 148, 70), (132, 194, 98)),  # dark, mid, light
    True: ((112, 100, 46), (156, 140, 60), (192, 176, 92)),
}
STEM = {False: (44, 92, 44), True: (106, 92, 44)}
FLOWER = (248, 196, 214)
FLOWER_EYE = (250, 220, 120)

# Tuft stems per stage: (dx at the top, height). Grown from the soil.
TUFT = [
    [(0, 2)],
    [(-1, 3), (1, 3)],
    [(-2, 4), (0, 5), (2, 4)],
    [(-3, 5), (-1, 6), (1, 7), (3, 5)],
    [(-4, 5), (-1, 7), (1, 8), (4, 6)],
    [(-5, 6), (-2, 8), (0, 10), (2, 9), (5, 6)],
    [(-6, 6), (-3, 9), (-1, 11), (1, 12), (3, 9), (6, 7)],
]
# Vines per stage: (side, length in px down from the rim).
VINES = [
    [],
    [],
    [],
    [(1, 9)],
    [(1, 16), (-1, 12)],
    [(1, 26), (-1, 21)],
    [(1, 36), (-1, 31), (1, 18)],
]


class Layer:
    def __init__(self) -> None:
        self.img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        self.px = self.img.load()

    def dot(self, x: float, y: float, c) -> None:
        x, y = round(x), round(y)
        if 0 <= x < W and 0 <= y < H:
            self.px[x, y] = (*c, 255)

    def leaf(self, x: int, y: int, side: int, wilted: bool) -> None:
        """A 3-px heart leaf pointing to `side`; wilted ones hang their tip down."""
        dark, mid, light = LEAF[wilted]
        self.dot(x, y, mid)
        self.dot(x + side, y, light if not wilted else mid)
        self.dot(x, y + 1, dark)
        if wilted:
            self.dot(x + side, y + 1, dark)
            self.dot(x + side, y + 2, dark)  # Drooping tip.
        else:
            self.dot(x + side, y - 1, light)  # Perky tip.
            self.dot(x + 2 * side, y, mid)


def _pot(L: Layer) -> None:
    for y in range(RIM_Y, 22):
        half = 4 if y == RIM_Y else (3 if y < 20 else 2)
        for x in range(CX - half, CX + half + 1):
            c = POT_LIGHT if y == RIM_Y else POT
            if x == CX + half or (y > RIM_Y and x >= CX + half - 1 and y > 18):
                c = POT_SHADE
            if y == RIM_Y + 1:
                c = POT_SHADE  # Under the rim.
            L.dot(x, y, c)
        L.dot(CX - half - 1, y, POT_LINE)
        L.dot(CX + half + 1, y, POT_LINE)
    for x in range(CX - 3, CX + 4):
        L.dot(x, RIM_Y - 1, SOIL)
    L.dot(CX - 5, RIM_Y, POT_LINE)
    L.dot(CX + 5, RIM_Y, POT_LINE)


def _tuft(L: Layer, stage: int, wilted: bool) -> None:
    base_y = RIM_Y - 1
    for dx, h in TUFT[stage]:
        top_x = CX + dx
        if wilted:
            h = max(1, h * 2 // 3)  # Slumps.
            top_x = CX + dx + (1 if dx > 0 else -1 if dx < 0 else 0)
        for i in range(1, h + 1):
            t = i / h
            L.dot(CX + (top_x - CX) * t * t, base_y - i, STEM[wilted])
        side = 1 if dx > 0 else -1 if dx < 0 else (1 if stage % 2 else -1)
        tip_y = base_y - h - (0 if wilted else 1)
        if stage == 0:
            L.dot(top_x - 1, tip_y + 1, LEAF[wilted][2])
            L.dot(top_x + 1, tip_y + 1, LEAF[wilted][1])
            continue
        L.leaf(top_x, tip_y, side, wilted)
        if h >= 6:  # A second leaf halfway up the taller stems.
            mid_x = round(CX + (top_x - CX) * 0.3)
            L.leaf(mid_x, base_y - h // 2, -side, wilted)


def _vine(L: Layer, side: int, length: int, wilted: bool, phase: float) -> None:
    x0 = CX + side * 4
    for i in range(length):
        y = RIM_Y + i
        # Out over the rim, then down the wall in front of the shelf with a gentle wave.
        if i < 3:
            x = x0 + side * i
        else:
            x = x0 + side * 3 + round(math.sin((i + phase) / 3.2) * 1.2)
        L.dot(x, y, STEM[wilted])
        if i >= 3 and (i + int(phase)) % 4 == 1:
            leaf_side = side if (i // 4) % 2 else -side
            L.leaf(x + leaf_side, y, leaf_side, wilted)
    if length:
        tip = RIM_Y + length
        x = x0 + side * 3 + round(math.sin((length + phase) / 3.2) * 1.2)
        L.leaf(x, tip - 1, side, wilted)


def plant(stage: int, wilted: bool = False) -> Image.Image:
    stage = max(0, min(6, stage))
    L = Layer()
    # Vines first: the pot and its lip sit in front of where they start.
    for n, (side, length) in enumerate(VINES[stage]):
        if wilted:
            length = length * 3 // 4
        _vine(L, side, length, wilted, phase=n * 2.5)
    _pot(L)
    _tuft(L, stage, wilted)
    if stage == 6 and not wilted:
        fx, fy = CX + 1, RIM_Y - 14
        for ox, oy in ((0, -1), (-1, 0), (1, 0), (0, 1)):
            L.dot(fx + ox, fy + oy, FLOWER)
        L.dot(fx, fy, FLOWER_EYE)
    return L.img


STAGES = 7
DEFAULT_STAGE = 3  # What previews and the flat scene show.
