"""A spider plant in a hanging pot, for the living room, in 7 growth stages, healthy or wilted.

plant(stage, wilted) returns a 106x80 RGBA layer with only the plant on it
(and its hanger). The device draws one of them between the room and the pet.

  0  a few short leaves over the rim
  1  a small tuft
  2  arching leaves
  3  a full fountain of leaves
  4  the first runner, with a baby plant
  5  two runners
  6  three long runners with babies, and a little white flower

Its leaves are long and striped: green edges, a cream stripe down the
middle. Wilted: the leaves turn yellow-brown, droop flat and hang down,
the tips brown; runners are shorter and limp.
"""

from __future__ import annotations

import math

from .scene import Grower, PropLayer, Spot

# The plant's own frame: the rope hangs from HOOK, the anchor.
CX = 20  # Pot centre.
RIM_Y = 15  # The pot's rim.
HOOK = (CX, 0)

POT = (214, 204, 186)  # A pale ceramic pot.
POT_SHADE = (176, 164, 146)
POT_LIGHT = (240, 234, 222)
POT_LINE = (120, 106, 90)
ROPE = (178, 150, 110)
ROPE_KNOT = (140, 114, 80)

# Edge, stripe, dark (the underside, as a leaf arches over).
LEAF = {False: ((70, 146, 70), (226, 232, 178), (46, 104, 52)), True: ((160, 142, 64), (206, 190, 120), (120, 102, 48))}
TIP = {False: (96, 170, 84), True: (126, 84, 46)}
RUNNER = {False: (196, 200, 120), True: (150, 130, 70)}
FLOWER = (252, 252, 244)
FLOWER_EYE = (240, 210, 110)

# Leaves per stage: (angle from straight up in degrees, length). Mirrored pairs read as a fountain.
LEAVES = [
    [(-30, 3), (25, 3)],
    [(-50, 5), (-15, 4), (20, 4), (55, 5)],
    [(-70, 7), (-35, 6), (0, 5), (35, 6), (72, 7)],
    [(-85, 9), (-55, 8), (-25, 6), (10, 6), (40, 8), (80, 9)],
    [(-95, 10), (-62, 9), (-30, 7), (5, 6), (35, 8), (66, 9), (98, 10)],
    [(-100, 11), (-70, 10), (-40, 8), (-10, 7), (22, 7), (50, 9), (78, 10), (104, 11)],
    [(-105, 12), (-78, 11), (-48, 9), (-18, 8), (12, 7), (40, 9), (68, 10), (92, 11), (110, 12)],
]
# Runners per stage: (side, length down from the rim).
RUNNERS = [[], [], [], [], [(1, 14)], [(1, 20), (-1, 14)], [(1, 27), (-1, 21), (1, 12)]]


def _hanger(L: PropLayer) -> None:
    """Three ropes from a ring at the ceiling down to the pot, knotted above it."""
    hx, hy = HOOK
    for y in range(hy, hy + 2):
        L.dot(hx, y, ROPE_KNOT)
    knot_y = 7
    for y in range(hy + 2, knot_y):
        L.dot(hx, y, ROPE)
    L.dot(hx, knot_y, ROPE_KNOT)
    for dx in (-5, 0, 5):  # Splitting out to the pot's rim.
        for y in range(knot_y + 1, RIM_Y):
            t = (y - knot_y) / (RIM_Y - knot_y)
            L.dot(hx + dx * t, y, ROPE)


def _pot(L: PropLayer) -> None:
    for y in range(RIM_Y, RIM_Y + 7):
        half = 6 if y == RIM_Y else (5 if y < RIM_Y + 4 else 4 - (y - RIM_Y - 4))
        for x in range(CX - half, CX + half + 1):
            c = POT_LIGHT if y == RIM_Y else POT
            if x >= CX + half - 1 and y > RIM_Y:
                c = POT_SHADE
            if y == RIM_Y + 1:
                c = POT_SHADE  # Under the rim.
            L.dot(x, y, c)
        L.dot(CX - half - 1, y, POT_LINE)
        L.dot(CX + half + 1, y, POT_LINE)
    for x in range(CX - 3, CX + 4):
        L.dot(x, RIM_Y + 7, POT_LINE)
    for x in range(CX - 7, CX + 8):
        L.dot(x, RIM_Y - 1, POT_LINE)  # The rim's top edge.
    for dx in (-5, 0, 5):  # The ropes cross the pot's front.
        for y in range(RIM_Y + 1, RIM_Y + 6):
            L.dot(CX + dx * (1 - (y - RIM_Y) / 12), y, ROPE)


def _leaf(L: PropLayer, angle: float, length: int, wilted: bool) -> None:
    """A long leaf from the middle of the rim: up and out, then arching over
    and down. Each pixel along it: edge color, with the stripe every other one."""
    edge, stripe, dark = LEAF[wilted]
    a = math.radians(angle)
    x, y = CX + math.sin(a) * 1.5, RIM_Y - 1.0
    # Wilted leaves droop: they bend down sooner and hang flatter.
    bend = 0.32 if wilted else 0.18
    heading = a
    for i in range(length):
        side = 1 if angle >= 0 else -1
        heading += side * bend * (0.3 + i / length)
        x += math.sin(heading)
        y -= math.cos(heading)
        c = edge if i % 2 or i < 2 else stripe
        if i >= length - 1:
            c = TIP[wilted]
        L.dot(x, y, c)
        if i < length - 2 and abs(math.sin(heading)) > 0.6:
            L.dot(x, y + 1, dark)  # The underside shows as the leaf arches over.


def _runner(L: PropLayer, side: int, length: int, wilted: bool) -> None:
    """A thin runner arching out of the pot and hanging down, a baby plant at its end."""
    x0 = CX + side * 6
    x = x0
    for i in range(length):
        y = RIM_Y + 1 + i
        x = x0 + side * (2 * math.sin(min(1.0, i / 6) * math.pi / 2)) + side * (0 if wilted else round(i / 14))
        L.dot(x, y, RUNNER[wilted])
    by = RIM_Y + 1 + length
    edge, stripe, _ = LEAF[wilted]
    # The baby: a little star of short leaves.
    spread = (
        ((-2, -1), (-1, -2), (1, -2), (2, -1), (-2, 1), (2, 1)) if not wilted else ((-2, 1), (2, 1), (-1, 2), (1, 2))
    )
    for dx, dy in spread:
        L.dot(x + dx, by + dy, edge)
    L.dot(x, by, stripe)
    L.dot(x, by - 1 if not wilted else by + 1, edge)


def plant(stage: int, wilted: bool, at: Spot):
    """The spider plant at `stage`, hanging from the spot `at`."""
    stage = max(0, min(STAGES - 1, stage))
    L = PropLayer(HOOK, at)
    _hanger(L)
    for side, length in RUNNERS[stage]:
        _runner(L, side, length * 3 // 4 if wilted else length, wilted)
    _pot(L)
    # Leaves from the back out: the outer ones first, so the middle ones lie on top.
    for angle, length in sorted(LEAVES[stage], key=lambda leaf: -abs(leaf[0])):
        _leaf(L, angle, length - (1 if wilted else 0), wilted)
    if stage == 6 and not wilted:
        fx, fy = CX + 9, RIM_Y + 7  # On the long right runner.
        for ox, oy in ((0, -1), (-1, 0), (1, 0), (0, 1)):
            L.dot(fx + ox, fy + oy, FLOWER)
        L.dot(fx, fy, FLOWER_EYE)
    return L.img


STAGES = 7
DEFAULT_STAGE = 3  # What previews and the flat scene show.
SPIDER_PLANT = Grower(plant, STAGES, DEFAULT_STAGE)
