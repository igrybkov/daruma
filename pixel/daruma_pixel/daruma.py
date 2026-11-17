"""A red daruma doll on a cushion in a tatami room. Pixel art.

It is drawn the way daruma are painted: one round, bottom-heavy red body
with no neck or arms; a wide, nearly square white face set high, in gold
trim; crane-wing brows and a turtle-shell beard (curled moustache, cheek
swirls, a curly chin) in black brush strokes; 福 in gold on the belly and
gold cloud swirls on its sides.

A daruma is sold with blank eyes. You paint one in when you set a goal and
the other when you reach it. `Pose.painted` (0, 1 or 2) says how many are
painted; the first is the one on the viewer's left. Every pose works in all
three states, so expressions come from the brows, the mouth, a tilt of the
whole doll, and props, not from the pupils.

The doll is weighted, so it moves like one: it rolls on its round bottom.
`tilt` turns it around the centre of the bottom curve and rolls it sideways
by the same arc, then it is set back down on the cushion.

Smooth shapes (body, face, trim) are polygons, so they turn cleanly. The
features (eyes, brows, moustache, cheeks, beard, mouth, 福, swirls) are
hand-drawn pixel stamps.
Up to a small tilt a stamp only moves with its anchor. Past that it turns:
a quarter turn turns the art itself, exactly; other angles sample 4x4
points per pixel, and ink shows where it covers enough of a pixel, so thin
strokes do not break up. Upright, the doll is mirrored to be exactly
symmetric.

Layers for personas.Spec, as corgi_persona.py has for the corgi: background() (the
room with a hole for the glass), foreground(pose) (the doll and its props),
scene(pose), WINDOW (the tall window's glass; background() leaves it
open), plant() with PLANT_STAGES and DEFAULT_STAGE (the bonsai in the
alcove, bonsai.py), and RUG_COLORS with RUG_BY_WEEKDAY (here
the cushion changes color with the day). Animations are in daruma_moods.py.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from PIL import Image, ImageDraw

from .bonsai import DEFAULT_STAGE, plant  # noqa: F401  (layers API)
from .bonsai import STAGES as PLANT_STAGES  # noqa: F401  (layers API)
from .pixelkit import Canvas, Ramp, mask

W, H = 106, 80
CX = 53  # Doll centre, x.
CONTACT_Y = 72  # The row the doll rests on, on the cushion.
RX, RY = 24, 24  # Body half-width and half-height.
EGG = 0.08  # How much wider the bottom is than the top.
ROLL_R = 20  # Radius of the bottom curve: what the doll rolls on.

OUTLINE = (66, 20, 24)
INK = (34, 24, 30)
RED = Ramp(base=(206, 46, 42), shadow=(158, 30, 34), light=(232, 92, 72))
GLOSS = (255, 196, 170)
FACE = Ramp(base=(250, 242, 226), shadow=(226, 210, 188))
EYE_WHITE = (255, 253, 247)
EYE_SHADE = (228, 220, 208)
GOLD = (236, 188, 70)
GOLD_DARK = (184, 128, 38)
GOLD_LIGHT = (255, 228, 140)
NOSE = (214, 150, 132)
MOUTH = (150, 40, 50)
TONGUE = (236, 120, 128)

HEART = (226, 52, 72)
HEART_SHINE = (255, 160, 170)
TEARDROP = (120, 190, 255)
ZZZ = (120, 128, 190)
DOTS = (98, 70, 60)
SPARK = (255, 220, 110)
SMOKE = (200, 196, 204)
SMOKE_FAINT = (220, 216, 220)
BRUSH_HANDLE = Ramp(base=(210, 172, 104), shadow=(160, 122, 66))
BRUSH_BAND = (120, 40, 40)
BOWL = Ramp(base=(120, 92, 70), shadow=(84, 62, 48), light=(156, 124, 96))
EMBER = (255, 120, 60)
STICK = (120, 72, 48)


@dataclass(frozen=True)
class Pose:
    painted: int = 0  # Painted eyes: 0, 1 (viewer's left) or 2.
    eyes: str = "open"  # open, blink, happy, half, wide, wink, shut
    look: tuple[int, int] = (0, 0)  # Where painted pupils look, -1..1 each way.
    brows: str = "calm"  # calm, up, worried, down, one_up, low
    mouth: str = "smile"  # smile, grin, frown, o, flat, talk
    tilt: float = 0.0  # Degrees, positive leans the top to the right.
    extras: tuple[str, ...] = ()  # hearts, hearts2, zzz, zzz2, sweat, tear, tear2, dots, sparkle
    prop: str = ""  # "incense"
    smoke: int = 0  # Incense smoke shape, 0..2.
    brush: tuple[int, int, int] | None = None  # Brush tip x, y and which side it comes from (-1, 1).
    wet: int = 0  # Paint going into eye number `painted`: 1 a dab, 2 most of it. 0 when done.


def with_(pose: Pose, **changes) -> Pose:
    return replace(pose, **changes)


# --- Stamps -----------------------------------------------------------------
# Hand-drawn features. Letters pick colors (see _COLORS); "." is see-through.
# Drawn for the viewer's left side; the right side is mirrored.

_COLORS = {
    "O": INK,
    "W": EYE_WHITE,
    "S": EYE_SHADE,
    "I": INK,
    "h": (255, 255, 255),
    "B": INK,
    "G": GOLD,
    "g": GOLD_DARK,
    "L": GOLD_LIGHT,
    "R": RED.base,
    "r": RED.shadow,
    "M": MOUTH,
    "T": TONGUE,
    "N": NOSE,
    "F": FACE.base,
    "f": FACE.shadow,
}

EYE = [
    "..OOOOO..",
    ".OWWWWWO.",
    "OWWWWWWWO",
    "OWWWWWWWO",
    "OWWWWWWWO",
    "OWWWWWWSO",
    "OWWWWWWSO",
    ".OSWWWSO.",
    "..OOOOO..",
]
PUPIL = [
    ".III.",
    "IIIII",
    "IIIII",
    "IIIII",
    ".III.",
]
PUPIL_SMALL = [
    "III",
    "III",
    "III",
]
# Paint going in: a dab, then most of the pupil.
PUPIL_WET = {
    1: [".....", "..II.", ".III.", ".II..", "....."],
    2: ["..II.", ".IIII", "IIIII", "IIII.", ".II.."],
}

# Brush-stroke brows shaped like a crane's spread wings: a heavy stroke,
# blunt at the inner end (right side here), that sweeps out and tapers to
# a feathered tip. (art, rows its bottom row sits above BROW_Y).
BROWS = {
    "calm": (
        [
            "....BBBBB..",
            "..BBBBBBBBB",
            ".BBBBBBBBBB",
            "BB.B.....BB",
            "B..........",
        ],
        0,
    ),
    "up": (
        [
            "...BBBBB...",
            ".BBBBBBBBB.",
            "BBBBBBBBBBB",
            "BB.B...BBBB",
            "B.......BBB",
        ],
        2,
    ),
    "worried": (
        [
            ".......BBBB",
            "....BBBBBBB",
            "..BBBBBBBB.",
            "BBBBBBB....",
            "BB.B.......",
            "B..........",
        ],
        1,
    ),
    "down": (
        [
            "B..........",
            "BBB........",
            "BBBBBB.....",
            ".BBBBBBBB..",
            "...BBBBBBBB",
            "......BBBBB",
        ],
        0,
    ),
    "low": (
        [
            "..BBBBBBB..",
            "BBBBBBBBBBB",
            "BB.B...BBBB",
        ],
        -1,
    ),
}

# The turtle: a moustache that curls up at both ends, a swirl on each
# cheek and a curly beard on the chin, all in black brush strokes.
MOUSTACHE = [
    "..BBB.....BBB..",
    ".BBBBB...BBBBB.",
    "BB...BB.BB...BB",
    "B.............B",
]
CHEEK = [  # The viewer's left cheek; the right one is mirrored.
    ".BBB.",
    "B...B",
    "B.B.B",
    "B..B.",
    ".BB..",
]
BEARD = [
    "BB.......BB",
    ".BB.BBB.BB.",
    "...BB.BB...",
]
MOUTHS = {
    "smile": ["B...B", ".BBB."],
    "grin": ["BBBBB", "BMMMB", ".BTB."],
    "frown": [".BBB.", "B...B"],
    "o": [".BBB.", "BMMMB", ".BBB."],
    "flat": ["BBB"],
    "talk": ["BBB", "BMB", ".B."],
}

# The kanji 福 ("good fortune"), as gold on the belly of many daruma.
# Drawn by hand at 13x13 against the Hiragino glyph: the 礻 radical on the
# left (dot, a stroke that bends down-left, the stem, a short tick), then
# 一, 口 and 田 stacked on the right.
FUKU = [
    "..G...GGGGGGG",
    "..G..........",
    "GGGG...GGGGG.",
    "...G...G...G.",
    "..G....GGGGG.",
    ".GG..........",
    "G.GG..GGGGGGG",
    "..G.G.G..G..G",
    "..G...G..G..G",
    "..G...GGGGGGG",
    "..G...G..G..G",
    "..G...G..G..G",
    "..G...GGGGGGG",
]
EYE_CLOSED = ["O.....O", ".OOOOO."]
EYE_HAPPY = ["..OOO..", ".O...O.", "O.....O"]
EYE_SHUT = ["OO.....", ".OOO...", "...OOOO", ".OOO...", "OO....."]  # ">" for the left eye.


# --- Geometry ---------------------------------------------------------------


class Frame:
    """Maps doll-local points (origin at the body centre, upright) to the canvas."""

    def __init__(self, tilt: float, dy: float = 0.0) -> None:
        self.tilt = tilt
        a = math.radians(tilt)
        self.c, self.s = math.cos(a), math.sin(a)
        self.pivot_local = (0.0, RY - ROLL_R)
        # It rolls sideways as it tips: the full arc for small tilts, less
        # far once it is on its way over, so it stays on the cushion.
        self.pivot = (CX + round(ROLL_R * 0.7 * math.sin(a) + 0.3 * ROLL_R * a * math.cos(a)), CONTACT_Y - ROLL_R + dy)

    def pt(self, x: float, y: float) -> tuple[float, float]:
        px, py = self.pivot_local
        x, y = x - px, y - py
        return (self.pivot[0] + x * self.c - y * self.s, self.pivot[1] + x * self.s + y * self.c)

    def inv(self, X: float, Y: float) -> tuple[float, float]:
        px, py = self.pivot_local
        X, Y = X - self.pivot[0], Y - self.pivot[1]
        return (X * self.c + Y * self.s + px, -X * self.s + Y * self.c + py)


class Frame0:
    """A turned Frame that draws stamps without turning them (the art is pre-turned)."""

    def __init__(self, f: Frame) -> None:
        self.f = f
        self.tilt = 0.0

    def pt(self, x: float, y: float) -> tuple[float, float]:
        return self.f.pt(x, y)


class Frame0Light(Frame):
    """The same placement as `f`, flagged as not upright so the shape is not mirrored."""

    def __init__(self, f: Frame) -> None:
        self.__dict__.update(f.__dict__)
        self.tilt = f.tilt or 1e-9


def egg(rx: float, ry: float, ox: float = 0, oy: float = 0, e: float = EGG, n: int = 72) -> list[tuple[float, float]]:
    """Points of an egg shape, wider at the bottom."""
    out = []
    for i in range(n):
        t = 2 * math.pi * i / n
        s = math.sin(t)
        out.append((ox + rx * math.cos(t) * (1 + e * s), oy + ry * s))
    return out


def squircle(rx: float, ry: float, ox: float = 0, oy: float = 0, n: int = 96) -> list[tuple[float, float]]:
    """Points of a rounded square (power FACE_SQUARE), its top a little narrower."""
    out = []
    k = 2 / FACE_SQUARE
    for i in range(n):
        t = 2 * math.pi * i / n
        c, s = math.cos(t), math.sin(t)
        x = rx * math.copysign(abs(c) ** k, c)
        y = ry * math.copysign(abs(s) ** k, s)
        out.append((ox + x * (1 + 0.1 * y / ry), oy + y))
    return out


def body_outline() -> list[tuple[float, float]]:
    """The doll's body: the egg with its lowest pixel row cut flat, the
    weighted base it sits on (about 15 px wide upright)."""
    return [(x, min(y, RY - 1)) for x, y in egg(RX, RY)]


def _settle(tilt: float) -> float:
    """Vertical nudge so the lowest body row sits on the contact row."""
    if tilt not in _settled:
        m = _poly_mask(Frame(tilt), body_outline()).load()
        low = max(y for y in range(H) for x in range(W) if m[x, y])
        _settled[tilt] = CONTACT_Y - low
    return _settled[tilt]


_settled: dict[float, int] = {}


# Stamps turn with the doll only past this tilt; below it they just move.
STAMP_TURN = 14
INK_COVER = 0.375  # Share of a pixel ink must cover to show when a stamp turns.


def stamp(
    c: Canvas, f: Frame, art: list[str], ax: float, ay: float, mirror: bool = False, colors: dict | None = None
) -> None:
    """Draw `art` with its centre at doll-local (ax, ay)."""
    colors = colors or _COLORS
    h, w = len(art), len(art[0])
    ox, oy = (w - 1) / 2, (h - 1) / 2

    turns = round(f.tilt / 90)
    if turns and abs(f.tilt - 90 * turns) < 1e-6:  # Quarter turns are exact: turn the art itself.
        if mirror:
            art, mirror = [row[::-1] for row in art], False
        for _ in range(turns % 4):
            art = ["".join(art[len(art) - 1 - r][col] for r in range(len(art))) for col in range(len(art[0]))]
        stamp(c, Frame0(f), art, ax, ay, colors=colors)
        return

    def pick(col: int, row: int):
        if not (0 <= row < h and 0 <= col < w):
            return None
        ch = art[row][w - 1 - col if mirror else col]
        return colors.get(ch) if ch != "." else None

    if abs(f.tilt) < STAMP_TURN:
        X, Y = f.pt(ax, ay)
        X0, Y0 = round(X - ox), round(Y - oy)
        for row in range(h):
            for col in range(w):
                color = pick(col, row)
                if color:
                    c.dot(X0 + col, Y0 + row, color)
        return
    # Turned: look at 4x4 points inside each canvas pixel near the anchor.
    # Ink wins from a quarter of the pixel, so thin strokes stay unbroken;
    # other colors need most of it.
    X, Y = f.pt(ax, ay)
    r = int(max(w, h)) + 1
    n = 4
    for Yp in range(round(Y) - r, round(Y) + r + 1):
        for Xp in range(round(X) - r, round(X) + r + 1):
            counts: dict = {}
            for sy in range(n):
                for sx in range(n):
                    lx, ly = f.inv(Xp - 0.5 + (sx + 0.5) / n, Yp - 0.5 + (sy + 0.5) / n)
                    color = pick(round(lx - ax + ox), round(ly - ay + oy))
                    if color:
                        counts[color] = counts.get(color, 0) + 1
            if not counts:
                continue
            if counts.get(INK, 0) >= INK_COVER * n * n:
                c.dot(Xp, Yp, INK)
                continue
            color, k = max(counts.items(), key=lambda kv: kv[1])
            if sum(counts.values()) >= n * n // 2:
                c.dot(Xp, Yp, color)


SUPER = 8  # Smooth shapes are drawn this much finer, then kept where they cover half a pixel.


def _poly_mask(f: Frame, pts: list[tuple[float, float]]) -> Image.Image:
    """A smooth shape on the pixel grid. Pixel centres sit on whole canvas coordinates."""
    big = Image.new("L", (W * SUPER, H * SUPER), 0)
    ImageDraw.Draw(big).polygon(
        [((X + 0.5) * SUPER, (Y + 0.5) * SUPER) for X, Y in (f.pt(x, y) for x, y in pts)], fill=255
    )
    m = _smooth(big.resize((W, H), Image.BOX).point(lambda v: 255 if v >= 128 else 0).convert("1"))
    return _mirror(m) if f.tilt == 0 else m


def _smooth(m: Image.Image) -> Image.Image:
    """Clean a curve's edge: drop lone tips (one side neighbour), fill notches (three)."""
    out = m.copy()
    src, dst = m.load(), out.load()
    for y in range(H):
        for x in range(W):
            n = sum(
                1
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                if 0 <= x + dx < W and 0 <= y + dy < H and src[x + dx, y + dy]
            )
            if src[x, y] and n <= 1:
                dst[x, y] = 0
            elif not src[x, y] and n >= 3:
                dst[x, y] = 255
    return _trim_caps(out)


def _trim_caps(m: Image.Image) -> Image.Image:
    """Drop a short top or bottom row sitting on a much longer one: the nub a curve leaves."""
    px = m.load()
    rows = [y for y in range(H) if any(px[x, y] for x in range(W))]
    if len(rows) < 3:
        return m

    def run(y: int) -> int:
        return sum(1 for x in range(W) if px[x, y])

    for y, nxt in ((rows[0], rows[1]), (rows[-1], rows[-2])):
        if run(y) <= 4 and run(nxt) >= 3 * run(y):
            for x in range(W):
                px[x, y] = 0
    return m


def _mirror(m: Image.Image) -> Image.Image:
    """Upright, the doll is exactly symmetric: copy the left half onto the right."""
    out = m.copy()
    px = out.load()
    for y in range(H):
        for x in range(CX + 1, min(W, 2 * CX + 1)):
            px[x, y] = px[2 * CX - x, y]
    return out


def _crescent(m: Image.Image, dx: int, dy: int) -> Image.Image:
    """Pixels of m that are not in m shifted by (dx, dy): a rim on the far side."""
    out = Image.new("1", m.size, 0)
    src, dst = m.load(), out.load()
    w, h = m.size
    for y in range(h):
        for x in range(w):
            if src[x, y]:
                sx, sy = x + dx, y + dy
                if not (0 <= sx < w and 0 <= sy < h and src[sx, sy]):
                    dst[x, y] = 1
    return out


def _fill(c: Canvas, m: Image.Image, color) -> None:
    px, mp, bp = c.img.load(), m.load(), c.body.load()
    for y in range(H):
        for x in range(W):
            if mp[x, y]:
                px[x, y] = (*color, 255)
                bp[x, y] = 1


def _only(m: Image.Image, keep: Image.Image) -> Image.Image:
    out = Image.new("1", m.size, 0)
    a, b, o = m.load(), keep.load(), out.load()
    for y in range(H):
        for x in range(W):
            if a[x, y] and b[x, y]:
                o[x, y] = 1
    return out


# --- The doll ---------------------------------------------------------------

FACE_C = (0, -7)  # Face centre, doll-local: set high on the body.
FACE_R = (15, 12.5)  # Half width and height of the face panel.
FACE_SQUARE = 3.2  # Squircle power: 2 is an ellipse, higher is squarer.
EYE_X, EYE_Y = 6, -9  # Eye centres at (+-EYE_X, EYE_Y).
BROW_Y = -14  # Row under the calm brows.
NOSE_Y = -4
MOUSTACHE_Y = -1
MOUTH_Y = 1
CHEEK_X, CHEEK_Y = 12, -2
BEARD_Y = 4


def render(p: Pose) -> Image.Image:
    c = Canvas(W, H)
    f = Frame(p.tilt, _settle(p.tilt))

    # Body, shaded with light from the top left. The shading is worked out
    # on the canvas, so it stays put while the doll turns.
    body = _poly_mask(f, body_outline())
    _fill(c, body, RED.base)
    _fill(c, _crescent(body, 3, 3), RED.shadow)
    hi = _only(_poly_mask(Frame0Light(f), egg(6, 3, -10, -18, e=0)), body)
    _fill(c, hi, RED.light)
    gx, gy = f.pt(-10, -19)  # A glint of lacquer on the hood.
    c.dot(round(gx), round(gy), GLOSS)
    c.dot(round(gx) + 1, round(gy), GLOSS)

    # Gold trim, then the white face panel inside it: wide and nearly square,
    # a little narrower at the top where the body curves in.
    fx, fy = FACE_C
    rim = _poly_mask(f, squircle(FACE_R[0] + 1, FACE_R[1] + 1, fx, fy))
    _fill(c, rim, GOLD)
    face = _poly_mask(f, squircle(FACE_R[0], FACE_R[1], fx, fy))
    _fill(c, face, FACE.base)
    _fill(c, _crescent(face, 2, 2), FACE.shadow)

    # Belly: 福 in gold, and gold cloud swirls on both lower sides.
    stamp(c, f, FUKU, 0, 14)
    _side_swirls(c, f)

    _features(c, f, p)
    _props_under(c, p)
    c.outline(OUTLINE)
    _props_over(c, p)
    _extras(c, f, p)
    return c.img


# A gold cloud swirl for the lower left of the belly; the right one is mirrored.
SWIRL = [
    "..GGGG.",
    ".G....G",
    "G..GG.G",
    "G.G..G.",
    "G..GG..",
    ".G.....",
    "..GGG..",
]


def _side_swirls(c: Canvas, f: Frame) -> None:
    """Gold cloud swirls low on both sides of the belly."""
    for side in (-1, 1):
        stamp(c, f, SWIRL, side * 15, 11, mirror=side == 1)


def _features(c: Canvas, f: Frame, p: Pose) -> None:
    for side in (-1, 1):
        mirror = side == 1
        ex = side * EYE_X
        index = 0 if side == -1 else 1  # Painting order: viewer's left first.
        kind = p.eyes
        if kind == "wink":
            kind = "blink" if side == 1 else "open"
        _eye(c, f, kind, ex, index, p, mirror)

        brow = p.brows
        if brow == "one_up":
            brow = "up" if side == 1 else "calm"
        art, up = BROWS[brow]
        stamp(c, f, art, side * 7, BROW_Y - up - (len(art) - 1) / 2, mirror=mirror)
        stamp(c, f, CHEEK, side * CHEEK_X, CHEEK_Y, mirror=mirror)

    nx, ny = f.pt(0, NOSE_Y)
    c.dot(round(nx), round(ny), NOSE)
    stamp(c, f, MOUSTACHE, 0, MOUSTACHE_Y)
    stamp(c, f, BEARD, 0, BEARD_Y)
    stamp(c, f, MOUTHS[p.mouth], 0, MOUTH_Y + len(MOUTHS[p.mouth]) // 2)


def _eye(c: Canvas, f: Frame, kind: str, ex: int, index: int, p: Pose, mirror: bool) -> None:
    if kind == "blink":
        stamp(c, f, EYE_CLOSED, ex, EYE_Y + 1)
        return
    if kind == "happy":
        stamp(c, f, EYE_HAPPY, ex, EYE_Y)
        return
    if kind == "shut":
        stamp(c, f, EYE_SHUT, ex, EYE_Y, mirror=mirror)
        return
    stamp(c, f, EYE, ex, EYE_Y, mirror=mirror)
    lx, ly = p.look
    if kind == "half":
        ly = 1
    painted = index < p.painted
    wet = p.wet if index == p.painted else 0
    if painted:
        pupil = PUPIL_SMALL if kind == "wide" else PUPIL
        stamp(c, f, pupil, ex + lx, EYE_Y + ly)
        if kind != "wide":
            stamp(c, f, ["h"], ex + lx - 1, EYE_Y + ly - 1)
    elif wet:
        stamp(c, f, PUPIL_WET[wet], ex, EYE_Y)
    if kind == "half":  # Upper lid down to the middle.
        lid = [".FFFFFFF.", "FFFFFFFFF", "FFFFFFFFF", "FFFFFFFFF", "OOOOOOOOO"]
        stamp(c, f, lid, ex, EYE_Y - 2)


def _props_under(c: Canvas, p: Pose) -> None:
    """Props that get the outline, like the doll."""
    if p.prop == "incense":
        bx, by = INCENSE
        bowl, d = mask((W, H))
        d.rectangle((bx - 3, by - 2, bx + 3, by), fill=1)
        d.rectangle((bx - 2, by + 1, bx + 2, by + 1), fill=1)
        c.paint(bowl, BOWL)
        for x in range(bx - 2, bx + 3):  # Ash in the bowl.
            c.dot(x, by - 2, BOWL.shadow)
    if p.brush:
        _brush(c, *p.brush)


def _props_over(c: Canvas, p: Pose) -> None:
    """Thin things drawn over the outline: an outline would swallow them."""
    if p.prop == "incense":
        _smoke(c, p.smoke)


# Bowl centre: on the floor right of the cushion, toward the back, so the
# bowl, stick and smoke stay left of the temperature badge (from x 90, rows
# 56 to 70 on the 320x240 screen) and the fallen-over doll (Scared) misses it.
INCENSE = (84, 67)
# Where the props of an activity stand, for tests/test_props.py: activity
# state -> boxes (x0, y0, x1, y1, end exclusive). The incense bowl and stick
# (the smoke changes shape, so it is left out).
PROPS = {"focus": [(INCENSE[0] - 4, INCENSE[1] - 11, INCENSE[0] + 5, INCENSE[1] + 3)]}


def _smoke(c: Canvas, smoke: int) -> None:
    """The incense stick, its glowing tip, and a wisp of smoke in one of three shapes."""
    bx, by = INCENSE
    for y in range(by - 10, by - 3):
        c.dot(bx, y, STICK)
    c.dot(bx, by - 11, EMBER)
    wisps = [
        [(0, -12), (1, -13), (1, -14), (0, -15), (-1, -16), (-1, -17), (0, -18), (1, -19)],
        [(0, -12), (0, -13), (1, -14), (1, -15), (0, -16), (-1, -17), (-1, -18), (0, -19)],
        [(0, -12), (-1, -13), (-1, -14), (0, -15), (1, -16), (1, -17), (0, -18), (-1, -19)],
    ][smoke % 3]
    for i, (dx, dy) in enumerate(wisps):
        c.dot(bx + dx, by + dy, SMOKE if i < 5 else SMOKE_FAINT)


def _brush(c: Canvas, tx: int, ty: int, side: int) -> None:
    """A calligraphy brush, tip at (tx, ty), the handle going up and out to `side`.

    Two pixels wide along the diagonal: an ink-black tip, a red ferrule,
    a bamboo handle with a node. Drawn before the outline, which frames it.
    """
    for k in range(11):
        x, y = tx + side * k, ty - k
        if k <= 3:
            color = INK
        elif k == 4:
            color = BRUSH_BAND
        elif k == 8:
            color = BRUSH_HANDLE.shadow  # Bamboo node.
        else:
            color = BRUSH_HANDLE.base
        c.dot(x, y, color)
        if k >= 1:
            # Second pixel, on the side away from the light.
            c.dot(x - side, y, color if k <= 4 or k == 8 else BRUSH_HANDLE.shadow)


def _extras(c: Canvas, f: Frame, p: Pose) -> None:
    top = CONTACT_Y - 2 * RY  # Head top when upright.
    for e in p.extras:
        if e in ("hearts", "hearts2"):
            # The left one on the plaster between the window and the doll.
            if e == "hearts":
                spots = ((CX - 28, top + 8), (CX + 26, top + 12))
            else:
                spots = ((CX - 27, top + 4), (CX + 27, top + 8))
            for hx, hy in spots:
                for row, line in enumerate([".X.X.", "XXXXX", ".XXX.", "..X.."]):
                    for col, ch in enumerate(line):
                        if ch == "X":
                            c.dot(hx + col, hy + row, HEART)
                c.dot(hx + 1, hy + 1, HEART_SHINE)
        elif e in ("zzz", "zzz2"):
            # Two letters drifting up from the head over the shoji paper,
            # where they read on any sky, clear of the bonsai on the right.
            zs = (
                ((CX + 12, top - 1, 4), (CX + 18, top - 9, 5))
                if e == "zzz"
                else ((CX + 13, top - 4, 4), (CX + 19, top - 12, 5))
            )
            for zx, zy, s in zs:
                for k in range(s):
                    c.dot(zx + k, zy, ZZZ)
                    c.dot(zx + s - 1 - k, zy + k, ZZZ)
                    c.dot(zx + k, zy + s - 1, ZZZ)
        elif e == "sweat":
            sx, sy = (round(v) for v in f.pt(17, -20))
            for dx, dy in ((0, 0), (-1, 1), (0, 1), (-1, 2), (0, 2), (1, 2), (0, 3)):
                c.dot(sx + dx, sy + dy, TEARDROP)
        elif e in ("tear", "tear2"):
            tx, ty = (round(v) for v in f.pt(-EYE_X - 3, EYE_Y + 5))
            drop = 0 if e == "tear" else 2
            for dy in range(2):
                c.dot(tx, ty + drop + dy, TEARDROP)
        elif e == "dots":
            # Rising up and to the left, where it looks, over the shoji paper.
            # Two pixels square, between the lattice bars, so they stand out.
            for x, y in ((CX - 10, top - 2), (CX - 15, top - 6), (CX - 18, top - 10)):
                for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1)):
                    c.dot(x + dx, y + dy, DOTS)
        elif e == "sparkle":
            for sx, sy in ((CX - 26, top + 9), (CX + 29, top + 11)):
                for dx, dy in ((0, -2), (0, -1), (0, 0), (0, 1), (0, 2), (-2, 0), (-1, 0), (1, 0), (2, 0)):
                    c.dot(sx + dx, sy + dy, SPARK)
                c.dot(sx, sy, (255, 255, 240))


# --- The room ---------------------------------------------------------------
# A small tatami room, left to right: a plaster wall with a tall window
# (its paper panels slid open), two shoji screens behind the doll, and a tokonoma alcove with
# a hanging scroll and a low table for the bonsai (bonsai.py draws the tree
# and its pot as the plant layer).

BEAM = (92, 60, 44)
BEAM_DARK = (70, 44, 32)
WALL = (226, 210, 178)
WALL_SHADE = (214, 196, 162)
FRAME = (86, 56, 40)  # The window's wooden frame.
FRAME_LIGHT = (140, 100, 66)
SKY = [(122, 190, 236), (150, 206, 240), (184, 224, 246)]
POST = (98, 64, 46)
POST_SHADE = (74, 48, 34)
PILLAR = (168, 126, 84)  # The alcove's natural wood post.
PILLAR_LIGHT = (196, 156, 110)
PILLAR_SHADE = (132, 94, 62)
PAPER = (246, 240, 224)
KUMIKO = (184, 150, 108)  # The shoji's thin lattice.
SHOJI_FRAME = (128, 90, 62)
KOSHI = (150, 108, 72)  # Wooden panel at the foot of a shoji.
KOSHI_SHADE = (124, 86, 56)
ALCOVE = (212, 194, 160)
ALCOVE_SHADE = (194, 174, 138)
SCROLL_MOUNT = (112, 124, 98)
SCROLL_PAPER = (240, 232, 210)
SCROLL_ROD = (58, 40, 30)
TOKO_TOP = (176, 130, 86)  # The alcove's raised floor.
TOKO_TOP_LIGHT = (200, 156, 108)
TOKO_FRONT = (50, 38, 36)  # Its lacquered front edge.
TOKO_FRONT_LIGHT = (92, 70, 62)
TABLE_TOP = (156, 104, 66)
TABLE = (114, 74, 48)
TABLE_DARK = (80, 52, 36)
BASEBOARD = (110, 72, 50)
TATAMI = (198, 186, 118)
TATAMI_LINE = (178, 166, 98)
TATAMI_EDGE = (62, 74, 56)  # The cloth border (heri) of the mats.

# The cushion; the device swaps these three for the day's colors.
CUSHION_EDGE = (204, 158, 98)
CUSHION = (64, 76, 136)
CUSHION_SHADOW = (46, 56, 106)

FLOOR_Y = 60  # First row of the floor.
# A tall window in the plaster wall, its paper panels slid open to the left.
# Glass: x, y, width, height. The device paints the sky over this rectangle;
# the room around it is solid, so the sky shows only here.
WINDOW = (10, 10, 12, 42)
WINDOW_FRAME = (2, 8, 23, 53)  # Outer edge of the wooden frame: x0, y0, x1, y1.
WINDOW_PANEL = (4, 9)  # First and last column of the paper panels, slid open.

SHOJI = (34, 81)  # First and last column of the two shoji screens.
PILLAR_X = 82  # The alcove's post: two columns.
ALCOVE_X = (84, 102)  # The alcove, between its post and the right wall post.
LINTEL_Y = 6  # Last row of the beam over the alcove.
TOKO_Y = 50  # Top row of the alcove's raised floor.
TABLE_Y = 45  # Top row of the bonsai table; the pot stands on it.
TABLE_X = (87, 101)


def glass() -> set[tuple[int, int]]:
    """Room pixels that show the sky."""
    x0, y0, w, h = WINDOW
    return {(x, y) for y in range(y0, y0 + h) for x in range(x0, x0 + w)}


def room() -> Image.Image:
    img = Image.new("RGBA", (W, H), (*WALL, 255))
    d = ImageDraw.Draw(img)
    for y in range(3, FLOOR_Y):  # Plaster a little darker toward the corner.
        d.point((0, y), fill=WALL_SHADE)
        d.point((1, y), fill=WALL_SHADE)
    d.rectangle((0, 0, W, 2), fill=BEAM)
    d.line((0, 3, W, 3), fill=BEAM_DARK)

    _window(d)
    _shoji(d)
    _alcove(d)

    # Floor: a skirting board, then tatami with its weave and cloth borders.
    d.rectangle((0, FLOOR_Y - 2, PILLAR_X - 1, FLOOR_Y - 1), fill=BASEBOARD)
    d.rectangle((0, FLOOR_Y, W, H), fill=TATAMI)
    for y in range(FLOOR_Y + 2, H, 2):
        d.line((0, y, W, y), fill=TATAMI_LINE)
    d.line((0, FLOOR_Y, W, FLOOR_Y), fill=TATAMI_EDGE)
    # Two seams between mats, leaning out as they come forward.
    for top_x, side in ((14, -1), (92, 1)):
        for y in range(FLOOR_Y + 1, H):
            d.point((top_x + side * ((y - FLOOR_Y) // 3), y), fill=TATAMI_EDGE)

    _cushion(d)
    return img


def _window(d: ImageDraw.ImageDraw) -> None:
    """A tall window: a wooden frame and sill, the paper panels slid open to
    the left, the sky to the right of them."""
    fx0, fy0, fx1, fy1 = WINDOW_FRAME
    gx, gy, gw, gh = WINDOW
    # The frame: dark wood, lit on its top and left edges.
    d.rectangle((fx0, fy0, fx1, fy1), fill=FRAME)
    d.line((fx0, fy0, fx1, fy0), fill=FRAME_LIGHT)
    d.line((fx0, fy0, fx0, fy1), fill=FRAME_LIGHT)
    # A shadow on the plaster under the lower right of the frame.
    d.line((fx1 + 1, fy0 + 2, fx1 + 1, fy1 + 1), fill=WALL_SHADE)
    # The sill: a board a little wider than the frame, with a dark edge.
    d.rectangle((fx0 - 1, fy1 - 1, fx1 + 1, fy1), fill=FRAME_LIGHT)
    d.line((fx0 - 1, fy1 + 1, fx1 + 1, fy1 + 1), fill=BEAM_DARK)

    # The paper panels, stacked where they slid: paper between two stiles,
    # a light lattice across it, a wooden panel at the foot.
    p0, p1 = WINDOW_PANEL
    d.rectangle((p0, gy, p1, gy + gh - 1), fill=PAPER)
    for y in range(gy + 5, gy + gh - 8, 6):
        d.line((p0 + 1, y, p1 - 1, y), fill=KUMIKO)
    d.line((p0 + 3, gy + 1, p0 + 3, gy + gh - 7), fill=KUMIKO)
    d.rectangle((p0, gy + gh - 6, p1, gy + gh - 1), fill=KOSHI)
    d.line((p0, gy + gh - 1, p1, gy + gh - 1), fill=KOSHI_SHADE)
    d.line((p0, gy, p0, gy + gh - 1), fill=SHOJI_FRAME)
    d.line((p1, gy, p1, gy + gh - 1), fill=SHOJI_FRAME)
    d.line((p0, gy, p1, gy), fill=SHOJI_FRAME)

    # The sky as the device paints a clear day (daruma_sprites/window.cpp).
    for x, y, color in clear_sky():
        d.point((gx + x, gy + y), fill=color)


def clear_sky() -> list[tuple[int, int, tuple[int, int, int]]]:
    """The clear sky the device paints into the glass, as (x, y, color) in it."""
    _, _, w, h = WINDOW
    span = h - 1
    out = [(x, y, SKY[2 if y >= 2 * span // 3 else 1 if y >= span // 3 else 0]) for y in range(h) for x in range(w)]
    white = (255, 255, 255)
    clouds = [(4, 4)] + ([(5, 22)] if h > TALL_PANE else [])
    for cx, cy in clouds:
        out += [(cx + x - 4, cy, white) for x in range(6, 10)]
        out += [(cx + x - 4, cy + dy, white) for dy in (1, 2, 3) for x in range(4, 11)]
    return [(x, y, c) for x, y, c in out if 0 <= x < w and 0 <= y < h]


# A pane taller than this gets more sky in window.cpp (another cloud, more
# stars, more cloud lanes); the same number is there.
TALL_PANE = 30


def _shoji(d: ImageDraw.ImageDraw) -> None:
    """Two shoji screens: paper on a light lattice, a wooden panel at the foot."""
    left, right = SHOJI
    d.rectangle((left - 2, 4, left - 1, FLOOR_Y - 3), fill=POST)  # Post between wall and screens.
    d.line((left - 1, 4, left - 1, FLOOR_Y - 3), fill=POST_SHADE)
    d.rectangle((left, 4, right, 5), fill=POST)  # Top track.
    d.rectangle((left, 6, right, FLOOR_Y - 3), fill=PAPER)
    mid = (left + right) // 2
    for x0, x1 in ((left, mid), (mid + 1, right)):
        for x in range(x0 + 6, x1 - 2, 6):
            d.line((x, 7, x, 48), fill=KUMIKO)
        for y in range(13, 48, 7):
            d.line((x0 + 1, y, x1 - 1, y), fill=KUMIKO)
        d.rectangle((x0 + 1, 50, x1 - 1, 56), fill=KOSHI)
        d.line((x0 + 1, 56, x1 - 1, 56), fill=KOSHI_SHADE)
        d.line((x0, 6, x1, 6), fill=SHOJI_FRAME)
        d.line((x0, 49, x1, 49), fill=SHOJI_FRAME)
        d.line((x0, 6, x0, FLOOR_Y - 3), fill=SHOJI_FRAME)
        d.line((x1, 6, x1, FLOOR_Y - 3), fill=SHOJI_FRAME)


def _alcove(d: ImageDraw.ImageDraw) -> None:
    """The tokonoma: a natural wood post, a scroll, a raised floor, a low table."""
    a0, a1 = ALCOVE_X
    d.rectangle((a0, 4, a1, LINTEL_Y), fill=POST)
    d.line((a0, LINTEL_Y, a1, LINTEL_Y), fill=POST_SHADE)
    d.rectangle((a0, LINTEL_Y + 1, a1, TOKO_Y - 1), fill=ALCOVE)
    d.line((a0, LINTEL_Y + 1, a1, LINTEL_Y + 1), fill=ALCOVE_SHADE)
    d.line((a0, LINTEL_Y + 1, a0, TOKO_Y - 1), fill=ALCOVE_SHADE)
    d.rectangle((a1 + 1, 4, W - 1, FLOOR_Y - 1), fill=POST)  # Wall post on the right.
    d.line((a1 + 1, 4, a1 + 1, FLOOR_Y - 1), fill=POST_SHADE)
    # The natural wood post, lit from the left.
    d.line((PILLAR_X, 4, PILLAR_X, FLOOR_Y - 1), fill=PILLAR_LIGHT)
    d.line((PILLAR_X + 1, 4, PILLAR_X + 1, FLOOR_Y - 1), fill=PILLAR_SHADE)
    for y in (17, 38):  # Knots in the wood.
        d.point((PILLAR_X, y), fill=PILLAR)

    _scroll(d, (a0 + a1) // 2)

    # The raised floor: a polished top, a lacquered front edge.
    d.line((a0, TOKO_Y, a1, TOKO_Y), fill=TOKO_TOP_LIGHT)
    d.line((a0, TOKO_Y + 1, a1, TOKO_Y + 1), fill=TOKO_TOP)
    d.rectangle((a0, TOKO_Y + 2, a1, FLOOR_Y - 1), fill=TOKO_FRONT)
    d.line((a0, TOKO_Y + 2, a1, TOKO_Y + 2), fill=TOKO_FRONT_LIGHT)

    # A low table on it: a thick top, an apron, two legs with feet that curl out.
    t0, t1 = TABLE_X
    d.line((t0, TABLE_Y, t1, TABLE_Y), fill=TABLE_TOP)
    d.line((t0, TABLE_Y + 1, t1, TABLE_Y + 1), fill=TABLE)
    d.line((t0 + 1, TABLE_Y + 2, t1 - 1, TABLE_Y + 2), fill=TABLE_DARK)
    for lx, out in ((t0 + 1, -1), (t1 - 2, 1)):
        d.rectangle((lx, TABLE_Y + 3, lx + 1, TOKO_Y - 1), fill=TABLE)
        d.point((lx + (1 if out > 0 else 0), TABLE_Y + 3), fill=TABLE_DARK)
        d.point((lx + (2 if out > 0 else -1), TOKO_Y - 1), fill=TABLE)


def _scroll(d: ImageDraw.ImageDraw, cx: int) -> None:
    """A hanging scroll with an enso, the circle painted in one brush stroke."""
    top, bottom = 10, 37
    d.line((cx, LINTEL_Y + 1, cx, top - 1), fill=SCROLL_ROD)  # Hanging cord.
    d.line((cx - 6, top, cx + 6, top), fill=SCROLL_ROD)
    d.rectangle((cx - 5, top + 1, cx + 5, bottom - 1), fill=SCROLL_MOUNT)
    d.rectangle((cx - 4, top + 3, cx + 4, bottom - 3), fill=SCROLL_PAPER)
    d.line((cx - 6, bottom, cx + 6, bottom), fill=SCROLL_ROD)
    d.point((cx - 7, bottom), fill=SCROLL_ROD)
    d.point((cx + 7, bottom), fill=SCROLL_ROD)
    # The enso: thick on the left where the brush came down, open at the top right.
    oy = top + 4
    for row, line in enumerate(
        [
            "..XX...",
            ".X.....",
            "XX....X",
            "XX....X",
            "XX....X",
            ".XX..X.",
            "..XXX..",
        ]
    ):
        for col, ch in enumerate(line):
            if ch == "X":
                d.point((cx - 3 + col, oy + row), fill=INK)


def _cushion(d: ImageDraw.ImageDraw) -> None:
    """A square zabuton seen from the front: a top in perspective, a front face."""
    top, front, bottom = 67, 74, 77
    back_half, front_half = 24, 28
    for y in range(top, front + 1):
        t = (y - top) / (front - top)
        half = round(back_half + (front_half - back_half) * t)
        d.line((CX - half, y, CX + half, y), fill=CUSHION)
        d.point((CX - half, y), fill=CUSHION_EDGE)
        d.point((CX + half, y), fill=CUSHION_EDGE)
    d.line((CX - back_half, top, CX + back_half, top), fill=CUSHION_EDGE)
    d.rectangle((CX - front_half, front + 1, CX + front_half, bottom), fill=CUSHION_SHADOW)
    d.line((CX - front_half, front, CX + front_half, front), fill=CUSHION_EDGE)
    # Tufted centre and the soft dip under the doll.
    d.ellipse((CX - 17, CONTACT_Y - 2, CX + 17, CONTACT_Y + 2), fill=CUSHION_SHADOW)
    for x in (CX - front_half - 1, CX + front_half + 1):  # Corner tassels.
        d.point((x, front), fill=CUSHION_EDGE)
        d.point((x, front + 1), fill=CUSHION_EDGE)


RUG_COLORS = (CUSHION_EDGE, CUSHION, CUSHION_SHADOW)
# Edge, main, shadow per day, Sunday first: the same day colors as the corgi's rug.
RUG_BY_WEEKDAY = (
    ((184, 150, 104), (236, 228, 210), (204, 192, 170)),  # Sunday: white
    ((204, 170, 112), (58, 92, 160), (44, 70, 126)),  # Monday: blue
    ((236, 214, 160), (222, 182, 48), (180, 144, 32)),  # Tuesday: yellow
    ((206, 172, 100), (62, 128, 76), (46, 98, 58)),  # Wednesday: green
    ((206, 164, 110), (100, 62, 40), (78, 46, 30)),  # Thursday: brown
    ((228, 190, 144), (214, 104, 146), (172, 78, 114)),  # Friday: pink
    ((206, 166, 108), (112, 70, 150), (86, 52, 118)),  # Saturday: purple
)
BACKGROUND = 0x5C3C2C  # Outside the canvas: the beam's wood.


def background() -> Image.Image:
    """The room with a see-through hole where the window shows the sky."""
    img = room()
    px = img.load()
    for x, y in glass():
        px[x, y] = (0, 0, 0, 0)
    return img


def foreground(pose: Pose) -> Image.Image:
    return render(pose)


def scene(pose: Pose, plant_stage: int = DEFAULT_STAGE, wilted: bool = False) -> Image.Image:
    img = room()
    img.alpha_composite(plant(plant_stage, wilted))
    img.alpha_composite(render(pose))
    return img
