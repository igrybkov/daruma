"""A bonsai on a low table, in 7 growth stages, healthy or wilted.

plant(stage, wilted, at) returns a 106x80 RGBA layer with only the tree and
its pot on it, the pot's feet on the spot `at` (scene.py, a table top), so
the device can draw it between the room and the actor. BONSAI is the
Grower a persona places:

  0  a seedling in a shallow pot
  1  a sapling with a first tuft
  2  a young trunk, two pads of foliage
  3  an S-curved trunk, three pads
  4  four pads, a thicker trunk
  5  five pads, roots gripping the soil
  6  a full shaped tree: a crown and four branches of cloud-like pads

It is one tree growing: every stage is the full tree's shape, shrunk
toward the pot, with the branches that have grown in by then.

Wilted: the same tree with brown, thinned foliage that sags and hangs in
strands, and a few dead needles on the table.
"""

from __future__ import annotations

from .scene import Grower, PropLayer, Spot

# The tree's own frame: the pot centers on CX, its feet are on ANCHOR.
CX = 94
TABLE_TOP = 45  # The row under the pot's feet.
ANCHOR = (CX, TABLE_TOP)
SOIL_Y = 39

POT = (82, 96, 128)  # A blue glazed pot.
POT_LIGHT = (116, 134, 168)
POT_SHADE = (58, 68, 96)
POT_FOOT = (44, 50, 70)
SOIL = (70, 50, 38)
MOSS = (96, 128, 64)

BARK = (104, 74, 54)
BARK_LIGHT = (140, 104, 74)
BARK_DARK = (70, 48, 36)

# Foliage tones: dark, mid, light, highlight.
LEAF = {
    False: ((38, 84, 52), (60, 120, 62), (98, 160, 80), (150, 198, 104)),
    True: ((104, 74, 40), (150, 108, 50), (186, 144, 70), (210, 176, 98)),
}

# The full tree, as points up the trunk from the soil (x, y).
TRUNK = [(94, 38), (93, 36), (92, 34), (92, 32), (93, 30), (95, 28), (96, 26), (95, 24), (94, 23)]
# Pads of the full tree: centre, half width, half height, the trunk point
# their branch leaves from, and the first stage that has them.
PADS = [
    ((89.5, 33.0), 3.5, 1.5, (92, 33), 2),  # Low left.
    ((98.5, 30.0), 3.5, 1.5, (93, 30), 3),  # Right.
    ((90.5, 27.0), 3.0, 1.5, (95, 27), 4),  # Upper left.
    ((99.0, 25.5), 2.5, 1.2, (96, 25), 5),  # Upper right.
]
APEX = ((94.5, 22.5), 3.5, 1.8)
# How far the tree has grown at each stage: 0 is the soil, 1 the full tree.
GROWTH = [0.12, 0.3, 0.45, 0.6, 0.75, 0.88, 1.0]


def _grown(pt: tuple[float, float], k: float) -> tuple[float, float]:
    """A point of the full tree, shrunk toward the trunk's base by k."""
    bx, by = TRUNK[0]
    return bx + (pt[0] - bx) * k, by + (pt[1] - by) * k


def _pot(L: PropLayer) -> None:
    """A shallow rectangular pot with a lip and two feet, on the table."""
    rim, base = SOIL_Y + 1, TABLE_TOP - 2
    for x in range(CX - 6, CX + 7):
        L.dot(x, rim, POT_LIGHT)
    for y in range(rim + 1, base + 1):
        for x in range(CX - 5, CX + 6):
            c = POT
            if x == CX + 5 or y == base:
                c = POT_SHADE
            elif x == CX - 5:
                c = POT_LIGHT
            L.dot(x, y, c)
    for fx in (CX - 4, CX - 3, CX + 3, CX + 4):
        L.dot(fx, TABLE_TOP - 1, POT_FOOT)
    for x in range(CX - 4, CX + 5):
        L.dot(x, SOIL_Y, SOIL)


def _trunk(L: PropLayer, k: float, stage: int) -> list[tuple[float, float]]:
    """The trunk up to this stage's height, thick at the base. Returns its points."""
    pts = [_grown(p, k) for p in TRUNK]
    base_w = 1 if stage <= 2 else 2 if stage <= 4 else 3
    # Walk the polyline in small steps so the line has no gaps.
    path = []
    for (x0, y0), (x1, y1) in zip(pts, pts[1:], strict=False):
        n = max(1, round(max(abs(x1 - x0), abs(y1 - y0)) * 2))
        for i in range(n):
            t = i / n
            path.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t))
    path.append(pts[-1])
    total = len(path)
    for i, (x, y) in enumerate(path):
        width = max(1, round(base_w * (1 - i / total) + 0.4))
        xs = [round(x) + dx for dx in range(-(width // 2), width - width // 2)]
        for j, xx in enumerate(xs):
            c = BARK_LIGHT if j == 0 and width > 1 else BARK_DARK if j == len(xs) - 1 and width > 2 else BARK
            L.dot(xx, round(y), c)
    if stage >= 5:  # Surface roots spreading over the soil.
        for dx, c in ((-3, BARK_DARK), (-2, BARK), (2, BARK), (3, BARK_DARK)):
            L.dot(CX + dx, SOIL_Y, c)
    return pts


def _branch(L: PropLayer, a: tuple[float, float], b: tuple[float, float]) -> None:
    n = max(1, round(max(abs(b[0] - a[0]), abs(b[1] - a[1]))))
    for i in range(n + 1):
        t = i / n
        L.dot(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, BARK)


def _pad(L: PropLayer, cx: float, cy: float, rx: float, ry: float, wilted: bool) -> None:
    """A cloud of foliage: lit on top, dark underneath. Wilted, it thins and hangs."""
    dark, mid, light, high = LEAF[wilted]
    if wilted:
        cy += 1  # The whole pad sags.
    cells = []
    for y in range(round(cy - ry - 1), round(cy + ry + 2)):
        for x in range(round(cx - rx - 1), round(cx + rx + 2)):
            if ((x - cx) / (rx + 0.5)) ** 2 + ((y - cy) / (ry + 0.5)) ** 2 <= 1:
                cells.append((x, y))
    if not cells:
        cells = [(round(cx), round(cy))]
    top = min(y for _, y in cells)
    bottom = max(y for _, y in cells)
    if not wilted:
        for x, y in cells:
            c = light if y == top else dark if y == bottom else mid
            if y == top and (x - round(cx - rx)) % 3 == 1:
                c = high  # Sunlit tufts along the top.
            L.dot(x, y, c)
        return
    # Wilted: the pad bends down toward its ends like a closed umbrella,
    # loses needles, and its tips hang in strands.
    lows: dict[int, int] = {}
    for x, y in cells:
        reach = abs(x - cx) / max(rx, 1)
        y2 = y + round(reach * reach * 1.6)
        if y == top and x % 3 == 0:
            continue  # A gap where needles have dropped.
        c = light if y == top else dark if y == bottom else mid
        L.dot(x, y2, c)
        lows[x] = max(lows.get(x, y2), y2)
    for x, y in lows.items():
        if abs(x - cx) >= rx - 1:  # The outer tips hang lowest.
            L.dot(x, y + 1, dark)
            if abs(x - cx) >= rx:
                L.dot(x, y + 2, dark)


def _seedling(L: PropLayer, wilted: bool) -> None:
    dark, mid, light, _ = LEAF[wilted]
    stem = LEAF[wilted][0]
    for y in (SOIL_Y - 1, SOIL_Y - 2):
        L.dot(CX, y, stem)
    if wilted:  # Two leaves hanging down from a bent tip.
        L.dot(CX + 1, SOIL_Y - 3, stem)
        L.dot(CX - 1, SOIL_Y - 2, mid)
        L.dot(CX - 1, SOIL_Y - 1, dark)
        L.dot(CX + 2, SOIL_Y - 2, mid)
        L.dot(CX + 2, SOIL_Y - 1, dark)
    else:  # Two leaves held up in a V.
        L.dot(CX - 1, SOIL_Y - 3, mid)
        L.dot(CX - 2, SOIL_Y - 4, light)
        L.dot(CX + 1, SOIL_Y - 3, mid)
        L.dot(CX + 2, SOIL_Y - 4, light)


def _fallen(L: PropLayer, stage: int) -> None:
    """A few dead needles on the table, more on a bigger tree."""
    spots = [(CX - 7, TABLE_TOP - 1), (CX + 7, TABLE_TOP - 1), (CX - 6, TABLE_TOP - 1), (CX + 6, TABLE_TOP - 1)]
    for x, y in spots[: 1 + stage // 2]:
        L.dot(x, y, LEAF[True][1])


def plant(stage: int, wilted: bool, at: Spot):
    """The bonsai at `stage`, its pot's feet on `at`."""
    stage = max(0, min(STAGES - 1, stage))
    L = PropLayer(ANCHOR, at)
    if stage == 0:
        _seedling(L, wilted)
        _pot(L)
        if wilted:
            _fallen(L, stage)
        return L.img
    k = GROWTH[stage]
    pts = _trunk(L, k, stage)
    pads = [(c, rx, ry, root) for c, rx, ry, root, first in PADS if stage >= first]
    size = 0.55 + 0.45 * k  # Pads grow fuller as the tree grows.
    for c, _rx, _ry, root in pads:
        _branch(L, _grown(root, k), _grown(c, k))
    for c, rx, ry, _root in pads:
        x, y = _grown(c, k)
        _pad(L, x, y, rx * size, ry * (0.7 + 0.3 * k), wilted)
    (ax, ay), arx, ary = APEX
    top = pts[-1]
    _pad(L, top[0] + (ax - TRUNK[-1][0]) * k, top[1] - 1, arx * size, ary * (0.6 + 0.4 * k), wilted)
    _pot(L)
    if wilted:
        _fallen(L, stage)
    return L.img


STAGES = 7
DEFAULT_STAGE = 3  # What previews and the flat scene show.
BONSAI = Grower(plant, STAGES, DEFAULT_STAGE)
