"""The Boss: a confident executive at her desk. A look for desk_boss.py.

Black hair pulled up into a bun with a center part, warm brown skin,
almond eyes with a lash flick, thin arched brows. A deep teal blazer over
a cream V-neck blouse and a thin gold necklace; small gold earrings.

Her room: a warm cream wall, a whiteboard with a rising bar chart, a
snake plant and a wall clock. On her walnut desk: a coral mug, a desk
sign with a check mark, an open laptop and a cup of pens.

Her idle: hands resting on the desk; now and then she checks her
wristwatch, or picks up the mug for a sip. She puts on thin gold glasses
to read.

This module is the persona: it has the names every persona module has
(see personas.Spec).
"""

from __future__ import annotations

from PIL import Image, ImageDraw

from .desk_boss import (
    HAPPY,
    READING,
    SAD,
    H,
    Look,
    Persona,
    Pose,
    Rig,
    W,
    animations,
    desk_hands,
    frames,
    raised_arm,
    shoulder,
    with_,
)
from .office import DeskColors
from .personas import Spec
from .pixelkit import Canvas, Ramp, ellipse, mask, poly, subtract
from .scene import Spot

OUTLINE = (34, 26, 30)
SKIN = Ramp(base=(186, 126, 90), shadow=(154, 100, 70), light=(206, 150, 112), line=(122, 76, 54))
HAIR = Ramp(base=(44, 32, 36), shadow=(30, 22, 26), light=(84, 66, 70), line=(22, 16, 20))
BROW = (42, 28, 30)
LASH = (30, 20, 24)
SUIT = Ramp(base=(30, 96, 100), shadow=(20, 70, 74), light=(48, 126, 128), line=(14, 52, 56))
BLOUSE = Ramp(base=(244, 238, 226), shadow=(214, 204, 186), line=(176, 164, 146))
GOLD = (226, 186, 92)
GOLD_DARK = (176, 136, 56)
WATCH = (222, 226, 232)
WHITE = (250, 250, 250)
IRIS = (92, 58, 40)
PUPIL = (34, 22, 20)
LIPS = (168, 82, 86)
LIP_LINE = (118, 50, 56)
MOUTH = (96, 34, 42)
TEETH = (250, 248, 242)
BLUSH = (210, 112, 104)
HEART = (226, 52, 72)
FRAMES = (70, 34, 52)  # Dark plum glasses.

# Office.
WALL = (222, 210, 190)
WALL_LOW = (208, 194, 172)
TRIM = (236, 228, 212)
CHAIR = Ramp(base=(62, 62, 70), shadow=(46, 46, 52), light=(86, 86, 96))
DESK = DeskColors(top=(118, 78, 56), edge=(148, 104, 76), front=(92, 60, 42), line=(66, 42, 30), handle=(196, 198, 204))
BOARD = (248, 249, 250)
BOARD_FRAME = (164, 168, 176)
LEAF = Ramp(base=(64, 132, 72), shadow=(42, 98, 54), light=(104, 168, 92))
MUG = Ramp(base=(232, 124, 92), shadow=(196, 96, 70), light=(246, 160, 128))
METAL = Ramp(base=(194, 198, 206), shadow=(156, 160, 170), light=(222, 226, 232))


# --- Office -----------------------------------------------------------------

DESK_AT = Spot(W // 2, 61)  # The middle of her desk's top edge; she sits behind it.


def office(img: Image.Image) -> None:
    d = ImageDraw.Draw(img)
    d.rectangle((0, 44, W, DESK_AT.y), fill=WALL_LOW)  # Two-tone wall with a trim line.
    d.line((0, 43, W, 43), fill=TRIM)

    # Wall clock, top right: no numbers, hands at ten past ten.
    d.ellipse((91, 1, 105, 15), fill=OUTLINE)
    d.ellipse((92, 2, 104, 14), fill=WHITE)
    for x, y in ((98, 3), (103, 8), (98, 13), (93, 8)):
        d.point((x, y), fill=(120, 120, 128))  # Quarter ticks.
    d.line((98, 8, 95, 6), fill=OUTLINE)
    d.line((98, 8, 101, 5), fill=OUTLINE)

    # Whiteboard, left, with a rising bar chart and a trend arrow.
    d.rectangle((3, 3, 38, 31), fill=BOARD_FRAME)
    d.rectangle((4, 4, 37, 29), fill=BOARD)
    d.line((4, 30, 37, 30), fill=(132, 136, 144))  # Marker tray.
    for x, color in ((24, (214, 64, 64)), (25, (214, 64, 64)), (28, (60, 110, 196)), (29, (60, 110, 196))):
        d.point((x, 29), fill=color)
    d.line((8, 7, 8, 26), fill=(90, 94, 102))  # Axes.
    d.line((8, 26, 34, 26), fill=(90, 94, 102))
    for i, height in enumerate((5, 9, 7, 14)):
        x = 11 + i * 6
        d.rectangle((x, 26 - height, x + 3, 25), fill=(70, 128, 204))
    d.line((11, 18, 17, 14, 23, 15, 31, 7), fill=(220, 84, 72))
    d.line((29, 7, 31, 7), fill=(220, 84, 72))  # Arrow head.
    d.line((31, 7, 31, 9), fill=(220, 84, 72))

    # Snake plant, right, its pot hidden behind the desk: tall leaves that
    # swell in the middle and end in a point, fanning out.
    c = Canvas(W, H)
    leaves = [(102, 36, 3), (90, 30, -3), (98, 22, 1), (93, 25, -1), (95, 40, 0)]
    for x, tip, lean in leaves:
        mid = (tip + DESK_AT.y) // 2
        leaf, ld = mask((W, H))
        poly(
            ld,
            [
                (x - 1, DESK_AT.y),
                (x + 1, DESK_AT.y),
                (x + 2 + lean // 2, mid),
                (x + lean, tip),
                (x - 2 + lean // 2, mid),
            ],
        )
        c.paint(leaf, LEAF)
        for y in range(tip + 5, DESK_AT.y - 2, 5):  # Darker bands across the leaf.
            t = (y - tip) / (DESK_AT.y - tip)
            lx = round(x + lean * (1 - t))
            c.dot(lx, y, LEAF.shadow)
    c.outline(OUTLINE)
    img.alpha_composite(c.img)


def desk_props(img: Image.Image, p: Pose) -> None:
    c = Canvas(W, H)
    if p.hand != "mug":  # She is holding it.
        _mug(c, 9, DESK_AT.y - 7)
    # Desk sign: a slanted plaque with a check mark.
    sign, d = mask((W, H))
    poly(d, [(20, DESK_AT.y - 1), (31, DESK_AT.y - 1), (30, DESK_AT.y - 6), (21, DESK_AT.y - 6)])
    c.paint(sign, Ramp(base=(58, 62, 72), shadow=(44, 46, 54)), shade=False)
    for x, y in ((23, -4), (24, -3), (25, -2), (26, -3), (27, -4), (28, -5)):
        c.dot(x, DESK_AT.y + y, (236, 240, 236))
    # Laptop, open toward her: a plain lid and the edge of its base.
    lid, d = mask((W, H))
    d.rectangle((75, DESK_AT.y - 13, 94, DESK_AT.y - 2), fill=1)
    c.paint(lid, METAL)
    c.line([(77, DESK_AT.y - 2), (92, DESK_AT.y - 2)], (92, 96, 106))  # Hinge.
    c.line([(74, DESK_AT.y - 1), (95, DESK_AT.y - 1)], METAL.shadow)  # Base.
    # Cup of pens, far left.
    cup, d = mask((W, H))
    d.rectangle((1, DESK_AT.y - 6, 5, DESK_AT.y - 1), fill=1)
    c.paint(cup, Ramp(base=(70, 74, 84), shadow=(52, 54, 62)), shade=False)
    for x, top, color in (
        (2, DESK_AT.y - 10, (60, 110, 196)),
        (4, DESK_AT.y - 9, (214, 64, 64)),
        (3, DESK_AT.y - 11, (40, 40, 44)),
    ):
        for y in range(top, DESK_AT.y - 6):
            c.dot(x, y, color)
    c.outline(OUTLINE)
    img.alpha_composite(c.img)


def _mug(c: Canvas, x: int, y: int, handle: int = 1) -> None:
    """Plain mug, 6x7, top left at (x, y). handle: 1 on the right, -1 on the left."""
    body, d = mask((W, H))
    d.rectangle((x, y, x + 5, y + 6), fill=1)
    c.paint(body, MUG)
    hx = x + 6 if handle == 1 else x - 2
    for dy in (1, 2, 3, 4):
        c.dot(hx + (1 if handle == 1 else 0), y + dy, MUG.shadow)
    c.dot(hx + (0 if handle == 1 else 1), y + 1, MUG.shadow)
    c.dot(hx + (0 if handle == 1 else 1), y + 4, MUG.shadow)
    for dx in range(1, 5):
        c.dot(x + dx, y, (110, 66, 44))  # Coffee at the rim.


# --- Clothes ------------------------------------------------------------------


def blouse(c: Canvas, r: Rig) -> None:
    """Cream V-neck blouse inside the blazer's lapels, a thin gold chain."""
    cx, top = r.cx, r.top
    v, d = mask((W, H))
    poly(d, [(cx - 7, top), (cx + 7, top), (cx, top + 16)])
    c.paint(v, BLOUSE)
    neck, d = mask((W, H))
    poly(d, [(cx - 4, top), (cx + 4, top), (cx, top + 6)])
    c.paint(neck, SKIN, shade=False)
    for dx, dy in ((-3, 1), (-2, 2), (-1, 3), (1, 3), (2, 2), (3, 1)):
        c.dot(cx + dx, top + dy, GOLD)
    c.dot(cx, top + 4, GOLD)  # Pendant.
    c.dot(cx, top + 5, GOLD_DARK)
    for side in (-1, 1):  # Lapel edges.
        c.line([(cx + side * 8, top + 1), (cx + side, top + 17)], SUIT.light if side == -1 else SUIT.line)


# --- Head and face ----------------------------------------------------------


def head(c: Canvas, r: Rig) -> None:
    """Small ears, an oval face that narrows to a soft chin."""
    hp, F = r.hp, r.look.head_scale
    ears, d = mask((W, H))
    for side in (-1, 1):
        ex, ey = hp(side * 8.2, -0.5)
        ellipse(d, ex, ey, 1.4, 2.4)
    c.paint(ears, SKIN, shade=False)
    face, d = mask((W, H))
    hx, hy = hp(0, -3)
    ellipse(d, hx, hy, 8 * F, 10.5 * F)
    poly(d, [hp(-8, -1), hp(8, -1), hp(7, 5), hp(4.5, 9.5), hp(1.5, 11.5), hp(-1.5, 11.5), hp(-4.5, 9.5), hp(-7, 5)])
    c.paint(face, SKIN)


def hair(c: Canvas, r: Rig) -> None:
    """Pulled back from a center part into a high bun; small gold earrings."""
    hp, F, hr = r.hp, r.look.head_scale, r.look.hair
    bun, d = mask((W, H))
    bx, by = hp(0, -15.4)
    ellipse(d, bx, by, 4.4 * F, 3.6 * F)
    c.paint(bun, hr)

    cap, d = mask((W, H))
    ox, oy = hp(0, -8.5)
    ellipse(d, ox, oy, 9.2 * F, 6.4 * F)
    for side in (-1, 1):  # Sides smoothed back over the tops of the ears.
        poly(d, [hp(side * 9.0, -8), hp(side * 6.0, -8), hp(side * 7.4, -2), hp(side * 8.8, -1)])
    face, d2 = mask((W, H))
    fx, fy = hp(0, -1.5)
    ellipse(d2, fx, fy, 7.4 * F, 9.6 * F)
    poly(
        d2,
        [
            hp(-7.4, -3),
            hp(-6.6, -7),
            hp(-4.5, -9),
            hp(-1.5, -9.8),
            hp(1.5, -9.8),
            hp(4.5, -9),
            hp(6.6, -7),
            hp(7.4, -3),
        ],
    )
    c.paint(subtract(cap, face), hr)
    c.line([r.hp(0, -10.4), r.hp(0, -14.2)], hr.light)  # Center part.
    for side in (-1, 1):  # Sheen sweeping back from the part.
        for x, y in ((2, -13), (4, -12), (6, -10.5)):
            c.dot(*r.at(side * x, y), hr.light)
    for x in (-2, -1, 0, 1, 2):  # Band around the bun.
        c.dot(*r.at(x, -13.6), SUIT.light)
    for side in (-1, 1):
        ex, ey = r.at(side * 8.4, 2.2)
        c.dot(ex, ey, GOLD)


def nose(c: Canvas, nx: int, ny: int) -> None:
    """Short nose: a shaded side, a lit tip, two nostrils."""
    c.dot(nx + 1, ny + 1, SKIN.shadow)
    c.dot(nx + 1, ny + 2, SKIN.shadow)
    c.dot(nx, ny + 2, SKIN.light)
    c.dot(nx - 1, ny + 3, SKIN.shadow)
    c.dot(nx + 1, ny + 3, SKIN.shadow)


def eye(c: Canvas, kind: str, x: int, y: int, look: int, side: int = 1) -> None:
    """Almond eyes, 3 wide: dark upper lash line with a flick at the outer corner."""
    out = x + side * 2  # Outer corner.
    if kind in ("open", "up"):
        for dx in (-1, 0, 1):
            c.dot(x + dx, y, LASH)
            c.dot(x + dx, y + 1, WHITE)
            c.dot(x + dx, y + 2, WHITE)
        c.dot(out, y - 1, LASH)
        c.dot(out, y, LASH)
        px = x + look
        c.dot(px, y + 1, PUPIL)
        if kind == "open":
            c.dot(px, y + 2, IRIS)  # Looking up leaves the lower row white.
    elif kind == "wide":
        for dx in (-1, 0, 1):
            for dy in (0, 1, 2):
                c.dot(x + dx, y + dy, WHITE)
            c.dot(x + dx, y - 1, LASH)
        c.dot(out, y - 2, LASH)
        c.dot(x, y + 1, PUPIL)
    elif kind == "blink":
        c.dot(x - 1, y + 1, LASH)
        c.dot(x, y + 2, LASH)
        c.dot(x + side, y + 2, LASH)
        c.dot(x + 1, y + 1, LASH)
        c.dot(out, y + 1, LASH)
    elif kind == "happy":
        c.dot(x - 1, y + 1, LASH)
        c.dot(x, y, LASH)
        c.dot(x + 1, y + 1, LASH)
        c.dot(out, y + 1, LASH)
    elif kind == "half":
        for dx in (-1, 0, 1):
            c.dot(x + dx, y, SKIN.line)
            c.dot(x + dx, y + 1, LASH)
            c.dot(x + dx, y + 2, WHITE)
        c.dot(out, y + 1, LASH)
        c.dot(x + look, y + 2, PUPIL)
    elif kind == "heart":
        for dx, dy in ((-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1), (0, 2)):
            c.dot(x + dx, y + dy, HEART)


def brow(c: Canvas, kind: str, x: int, eye_y: int, side: int) -> None:
    """Thin arched brows: the peak sits over the outer half of the eye."""
    y = eye_y - 3
    lift = -1 if kind == "up" or (kind == "one_up" and side == -1) else 0
    # u: inner (-) to outer (+); arch: rows above the base line.
    shape = {-2: 0, -1: -1, 0: -1, 1: -1, 2: 0}
    for u, dy in shape.items():
        if kind == "worried":
            dy -= {-2: 2, -1: 1}.get(u, 0)  # Inner ends lifted.
        elif kind == "down" and u <= -1:
            dy += 1  # Inner ends pulled down.
        c.dot(x + u * side, y + dy + lift, BROW)


def mouth(c: Canvas, kind: str, x: int, y: int) -> None:
    if kind == "flat":  # Closed, composed.
        for dx in range(-2, 3):
            c.dot(x + dx, y, LIP_LINE)
        for dx in (-1, 0, 1):
            c.dot(x + dx, y + 1, LIPS)
    elif kind == "smile":
        c.dot(x - 3, y - 1, LIP_LINE)
        c.dot(x + 3, y - 1, LIP_LINE)
        for dx in range(-2, 3):
            c.dot(x + dx, y, LIP_LINE)
        for dx in (-1, 0, 1):
            c.dot(x + dx, y + 1, LIPS)
    elif kind == "smirk":
        c.dot(x + 3, y - 1, LIP_LINE)
        for dx in range(-2, 3):
            c.dot(x + dx, y, LIP_LINE)
        for dx in (-1, 0, 1):
            c.dot(x + dx, y + 1, LIPS)
    elif kind == "grin":
        c.dot(x - 4, y - 1, LIP_LINE)
        c.dot(x + 4, y - 1, LIP_LINE)
        for dx in range(-3, 4):
            c.dot(x + dx, y, MOUTH)
        for dx in range(-2, 3):
            c.dot(x + dx, y, TEETH)
        for dx in range(-2, 3):
            c.dot(x + dx, y + 1, MOUTH)
        for dx in range(-1, 2):
            c.dot(x + dx, y + 2, LIPS)
    elif kind in ("open", "talk"):
        rows = 3 if kind == "open" else 2
        for dx in range(-1, 2):
            for dy in range(rows):
                c.dot(x + dx, y + dy, MOUTH)
            c.dot(x + dx, y, TEETH)
        for dy in range(rows):
            c.dot(x - 2, y + dy, LIPS)
            c.dot(x + 2, y + dy, LIPS)
        for dx in range(-1, 2):
            c.dot(x + dx, y + rows, LIPS)
    elif kind == "frown":
        c.dot(x - 3, y + 1, LIP_LINE)
        c.dot(x + 3, y + 1, LIP_LINE)
        for dx in range(-2, 3):
            c.dot(x + dx, y, LIP_LINE)
        for dx in (-1, 0, 1):
            c.dot(x + dx, y + 1, LIPS)
    elif kind == "o":
        for dx, dy in ((0, 0), (-1, 1), (1, 1), (0, 2)):
            c.dot(x + dx, y + dy, LIP_LINE)
        c.dot(x, y + 1, MOUTH)


# --- Her gestures -----------------------------------------------------------


def check_watch(c: Canvas, r: Rig) -> None:
    """Left forearm raised across the chest, the watch face turned toward her."""
    desk_hands(c, r, (-1,))
    wrist = raised_arm(c, r.look, shoulder(r, 1), (r.cx + 19, r.desk.y - 4), (r.cx - 1, r.top + 10), "fist")
    wx, wy = round(wrist[0]) + 1, round(wrist[1]) - 1
    for dx in (-1, 0, 1):  # Gold case around a white face.
        for dy in (-1, 0, 1):
            c.dot(wx + dx, wy + dy, GOLD_DARK if dx or dy else r.look.watch)
    c.dot(wx - 1, wy - 1, GOLD)  # Light on the case.


def sip(c: Canvas, r: Rig) -> None:
    """Right elbow on the desk, the mug lifted to her lips."""
    desk_hands(c, r, (1,))
    mx, my = r.at(*r.look.nose_at)
    my += r.look.mouth_drop - 1
    _mug(c, mx - 2, my, handle=-1)
    raised_arm(c, r.look, shoulder(r, -1), (r.cx - 13, r.desk.y - 1), (mx - 5, my + 4), "fist")


LOOK = Look(
    outline=OUTLINE,
    skin=SKIN,
    hair=HAIR,
    suit=SUIT,
    shirt=BLOUSE,
    tie=None,
    blush=BLUSH,
    watch=WATCH,
    wall=WALL,
    chair=CHAIR,
    desk=DESK,
    decor=office,
    desk_props=desk_props,
    neckline=blouse,
    head=head,
    hair_style=hair,
    eye=eye,
    brow=brow,
    nose=nose,
    mouth=mouth,
    glasses=frames(FRAMES),
    gestures={"watch": check_watch, "mug": sip},
    head_scale=1.15,
    neck_rise=22,
    eye_at=(3.8, -2),
    mouth_drop=7,
    tear_at=(-3.8, 0.5),
)

_boss = Persona(LOOK, desk=DESK_AT)
background, foreground, scene = _boss.background, _boss.foreground, _boss.scene
WINDOW = None

# --- Moods and animations ---------------------------------------------------

NEUTRAL = Pose(hand="desk")
WATCH_CHECK = with_(NEUTRAL, hand="watch", eyes="half", look=1, head_dy=1, tilt=4)
SIP = with_(NEUTRAL, hand="mug", eyes="happy", brows="up")

ANIMATIONS = animations(
    rest=NEUTRAL,
    # Sits composed; checks her watch; later, a sip of coffee and a small smile.
    neutral=[
        (NEUTRAL, 1800),
        (with_(NEUTRAL, breath=1), 1400),
        (NEUTRAL, 1200),
        (WATCH_CHECK, 1500),
        (NEUTRAL, 1400),
        (with_(NEUTRAL, breath=1), 1400),
        (SIP, 1600),
        (with_(NEUTRAL, mouth="smile"), 1400),
    ],
)

BLINKS: dict[str, Pose] = {
    "Neutral": with_(NEUTRAL, eyes="blink"),
    "Sad": with_(SAD, eyes="blink"),
    "Focus": with_(READING, eyes="blink"),
}
WINKS: dict[str, Pose] = {
    "Neutral": with_(NEUTRAL, eyes="wink", mouth="smile"),
    "Happy": with_(HAPPY, eyes="wink", mouth="smile"),
}

PERSONA = Spec("the_boss", background=0xDED2BE)
