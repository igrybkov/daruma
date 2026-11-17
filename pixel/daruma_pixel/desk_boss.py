"""A boss behind a desk: the drawing engine for desk-boss personas.

A Look says who sits at the desk: skin, hair, face parts, clothes, glasses,
the room behind them and the props on the desk, plus any gestures of
their own. The engine draws everything they share: body, arms and hands,
chair, desk, the moods, and the layers the device needs.

A look module builds a Persona from its Look and exposes the same names
every persona module has (see personas.py):

    _boss = Persona(LOOK)
    background, foreground, scene = _boss.background, _boss.foreground, _boss.scene
    WINDOW = None
    ANIMATIONS = animations(rest=NEUTRAL, neutral=[...])
    BLINKS, WINKS = {...}, {...}

Everything is drawn on the 106x80 canvas, with the light from the top left.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Callable

from PIL import Image, ImageDraw

from .pet import extras as _extras
from .pixelkit import Canvas, Color, Point, Ramp, ellipse, mask, poly, rotate

W, H = 106, 80
CX = W // 2
DESK_Y = 61  # Top edge of the desk.

PAPER = Ramp(base=(248, 248, 242), shadow=(214, 216, 210))
PRINT = (150, 154, 160)


@dataclass(frozen=True)
class Pose:
    eyes: str = "open"  # open, blink, happy, half, wide, heart, wink, up
    look: int = 0  # Where the pupils point: -1 left, 0 at you, 1 right.
    brows: str = "flat"  # flat, up, worried, one_up, down
    mouth: str = "flat"  # smile, grin, open, talk, frown, o, flat, smirk
    blush: bool = False
    head_dx: int = 0
    head_dy: int = 0
    tilt: float = 0.0
    breath: int = 0
    hand: str = "desk"  # A gesture name: desk, thumbs, chin, ear, paper, or one the Look adds.
    glasses: bool = False  # Glasses on, for reading.
    extras: tuple[str, ...] = ()  # hearts, zzz, sweat, dots, sparkle, tear


def with_(pose: Pose, **changes) -> Pose:
    return replace(pose, **changes)


@dataclass(frozen=True)
class Rig:
    """Where the parts of one frame sit. Hooks in a Look get this."""

    pose: Pose
    look: "Look"
    cx: int
    top: int  # Shoulder line.
    neck: tuple[int, int]
    head_c: tuple[int, int]

    def hp(self, x: float, y: float) -> Point:
        """A point in head space (scaled, tilted with the head) on the canvas."""
        F = self.look.head_scale
        return rotate([(self.head_c[0] + x * F, self.head_c[1] + y * F)], self.neck, self.pose.tilt)[0]

    def at(self, x: float, y: float) -> tuple[int, int]:
        """hp() snapped to the pixel grid."""
        px, py = self.hp(x, y)
        return round(px), round(py)


@dataclass(frozen=True)
class DeskColors:
    top: Color
    edge: Color  # The lit front edge of the top.
    front: Color
    line: Color  # Drawer outlines and the seam under the top.
    handle: Color


Hook = Callable[[Canvas, Rig], None]
EyeFn = Callable[[Canvas, str, int, int, int, int], None]  # c, kind, x, y, look, side
BrowFn = Callable[[Canvas, str, int, int, int], None]  # c, kind, eye x, eye y, side
MouthFn = Callable[[Canvas, str, int, int], None]  # c, kind, x, y
NoseFn = Callable[[Canvas, int, int], None]  # c, x, y
GlassesFn = Callable[[Canvas, list[tuple[int, int]]], None]  # c, eye centers
RoomFn = Callable[[Image.Image], None]
PropsFn = Callable[[Image.Image, Pose], None]


def _nothing(*_args) -> None:
    pass


@dataclass(frozen=True, eq=False)
class Look:
    """Who sits at the desk. Colors are ramps or RGB tuples; parts are drawing hooks.

    Hooks run in this order for the body: neckline, head, hair, marks, then
    for each eye (left, right) eye and brow, then nose and mouth, glasses.
    """

    # Materials.
    outline: Color
    skin: Ramp  # base, shadow, light and line (the line draws fingers and lids).
    hair: Ramp
    suit: Ramp
    shirt: Ramp
    tie: Ramp | None  # None: no tie.
    blush: Color
    watch: Color  # The watch face on a wrist.
    # Office.
    wall: Color  # Also the face's background color on the device.
    chair: Ramp
    desk: DeskColors
    decor: RoomFn  # Wall decor; draws on the bare wall.
    desk_props: PropsFn  # Things on the desk; gets the pose, so a prop can leave with a hand.
    # Body and face parts.
    neckline: Hook  # Shirt, tie, collar or jewelry inside the jacket's V.
    head: Hook  # Ears, face shape, beard.
    hair_style: Hook
    eye: EyeFn
    brow: BrowFn
    nose: NoseFn
    mouth: MouthFn
    glasses: GlassesFn | None = None
    shirt_stripe: Color | None = None  # Pinstripes, for shirt_and_tie.
    tie_stripe: Color | None = None  # Diagonal stripes, for shirt_and_tie.
    marks: Hook = _nothing  # Lines, freckles or a dimple, drawn before the eyes.
    gestures: dict[str, Hook] = field(default_factory=dict)  # Extra or replaced hand poses.
    # Proportions, in head space.
    head_scale: float = 1.25
    neck_y: int = 37  # Top of the neck at rest.
    eye_at: Point = (4, -2)  # Right eye; the left one is mirrored.
    nose_at: Point = (0, -0.5)
    mouth_drop: int = 9  # Pixels from the nose point down to the mouth.
    tear_at: Point = (-4, 0)


# --- Clothes ------------------------------------------------------------------


def shirt_and_tie(c: Canvas, r: Rig) -> None:
    """A shirt V with collar points and a tie; stripes when the look gives them."""
    look, cx, top = r.look, r.cx, r.top
    shirt, d = mask((W, H))
    poly(d, [(cx - 7, top), (cx + 7, top), (cx, top + 17)])
    c.paint(shirt, look.shirt)
    if look.shirt_stripe:
        for x in range(cx - 6, cx + 7, 2):
            for y in range(top + 1, top + 17):
                if abs(x - cx) * 17 < (top + 17 - y) * 7 - 3:
                    c.dot(x, y, look.shirt_stripe)
    for side in (-1, 1):  # Collar points.
        for i in range(3):
            c.dot(cx + side * (3 + i), top + 1 + i, look.shirt.shadow)
    if look.tie is None:
        return
    tie, d = mask((W, H))
    d.rectangle((cx - 2, top, cx + 1, top + 2), fill=1)
    poly(d, [(cx - 2, top + 3), (cx + 1, top + 3), (cx + 3, top + 17), (cx, top + 20), (cx - 3, top + 17)])
    c.paint(tie, look.tie)
    if look.tie_stripe:
        for y in range(top + 4, top + 19, 3):  # Diagonal stripes.
            c.dot(cx - 1, y + 1, look.tie_stripe)
            c.dot(cx, y, look.tie_stripe)
            c.dot(cx + 1, y - 1, look.tie_stripe)


# --- Glasses ------------------------------------------------------------------


def readers(color: Color) -> GlassesFn:
    """Half-frame reading glasses, low on the nose: the wearer can look over them."""

    def draw(c: Canvas, eyes: list[tuple[int, int]]) -> None:
        (lx, ly), (rx, _) = eyes
        for ex, ey in eyes:
            for dx in range(-2, 3):
                c.dot(ex + dx, ey + 3, color)  # Top bar.
            c.dot(ex - 2, ey + 4, color)
            c.dot(ex + 2, ey + 4, color)
            for dx in range(-1, 2):
                c.dot(ex + dx, ey + 5, color)  # Rounded lower rim.
        for x in range(lx + 3, rx - 2):  # Bridge, a step up over the nose.
            c.dot(x, ly + 2, color)

    return draw


def frames(color: Color, temple: int = 2) -> GlassesFn:
    """Full rectangular frames around eyes 3 pixels wide, rows y to y+2; short temples."""

    def draw(c: Canvas, eyes: list[tuple[int, int]]) -> None:
        (lx, ly), (rx, _) = eyes
        for ex, ey in eyes:
            for dx in range(-2, 3):
                c.dot(ex + dx, ey - 1, color)
                c.dot(ex + dx, ey + 3, color)
            for dy in (0, 1, 2):
                c.dot(ex - 2, ey + dy, color)
                c.dot(ex + 2, ey + dy, color)
        for x in range(lx + 3, rx - 2):  # Bridge.
            c.dot(x, ly + 1, color)
        for k in range(1, temple + 1):
            c.dot(lx - 2 - k, ly + 1, color)
            c.dot(rx + 2 + k, ly + 1, color)

    return draw


# --- Arms and hands -------------------------------------------------------------


def limb(d: ImageDraw.ImageDraw, a: Point, b: Point, wa: float, wb: float) -> None:
    """A tapered segment from a to b, half-widths wa and wb. Always a convex quad."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    n = (dx * dx + dy * dy) ** 0.5 or 1.0
    nx, ny = -dy / n, dx / n
    poly(
        d,
        [
            (a[0] + nx * wa, a[1] + ny * wa),
            (b[0] + nx * wb, b[1] + ny * wb),
            (b[0] - nx * wb, b[1] - ny * wb),
            (a[0] - nx * wa, a[1] - ny * wa),
        ],
    )


def raised_arm(c: Canvas, look: Look, shoulder: Point, elbow: Point, hand: Point, kind: str) -> Point:
    """Whole arm: shoulder to elbow, a rounded elbow, forearm to the hand.

    kind is fist, rest (flat on the desk), cup (at the ear) or thumb (up).
    Returns the wrist, where a watch or a held thing can go.
    """
    hx, hy = round(hand[0]), round(hand[1])
    ex, ey = elbow
    dx, dy = hx - ex, hy - ey
    n = (dx * dx + dy * dy) ** 0.5 or 1.0
    wrist = (hx - dx / n * 4, hy - dy / n * 4)
    k = 0.75 if kind == "rest" else 1.0  # Resting arms hang closer to the body.
    arm, d = mask((W, H))
    limb(d, shoulder, elbow, 5 * k, 4.5 * k)
    ellipse(d, ex, ey, 4.5 * k, 4.5 * k)
    limb(d, elbow, wrist, 4.5 * k, 3.5)
    c.paint(arm, look.suit)
    cuff, d = mask((W, H))
    limb(d, (wrist[0] - dx / n * 1.5, wrist[1] - dy / n * 1.5), wrist, 3.5, 3.5)
    c.paint(cuff, look.shirt, shade=False)
    palm, d = mask((W, H))
    if kind == "fist":
        ellipse(d, hx, hy, 3.5, 3)
    elif kind == "rest":
        ellipse(d, hx, hy, 4, 2.5)
    elif kind == "cup":
        ellipse(d, hx, hy, 2.5, 4.5)
    else:  # thumb
        d.rectangle((hx - 3, hy - 2, hx + 3, hy + 3), fill=1)
        d.rectangle((hx - 2, hy - 7, hx, hy - 2), fill=1)
    c.paint(palm, look.skin)
    line = look.skin.line
    if kind == "fist":
        for k in (-2, 0, 2):
            c.dot(hx + k, hy - 1, line)
    elif kind == "rest":
        for k in (-2, 1):
            c.dot(hx + k, hy - 1, line)
    elif kind == "cup":
        for k in (-2, 0, 2):
            c.dot(hx - 1, hy + k, line)
    else:
        for k in (0, 2):
            c.dot(hx + 2, hy + k, line)
    return wrist


def shoulder(r: Rig, side: int) -> Point:
    """Where a sleeve starts. side -1 is the arm on the left of the picture."""
    return (r.cx + side * 16, r.top + 6)


def desk_hands(c: Canvas, r: Rig, sides: tuple[int, ...] = (-1, 1)) -> None:
    """Arms down the sides, forearms on the desk, hands resting in the middle."""
    for side in sides:
        raised_arm(c, r.look, shoulder(r, side), (r.cx + side * 18, DESK_Y - 2), (r.cx + side * 5, DESK_Y), "rest")


def _desk(c: Canvas, r: Rig) -> None:
    desk_hands(c, r)


def _thumbs(c: Canvas, r: Rig) -> None:
    """Elbow out, forearm up, thumb up."""
    desk_hands(c, r, (-1,))
    raised_arm(c, r.look, shoulder(r, 1), (r.cx + 25, r.top + 13), (r.cx + 22, r.top - 9), "thumb")


def _chin(c: Canvas, r: Rig) -> None:
    """Elbow on the desk, fist under the chin."""
    desk_hands(c, r, (-1,))
    raised_arm(c, r.look, shoulder(r, 1), (r.cx + 12, DESK_Y - 1), r.hp(2, 13), "fist")


def _ear(c: Canvas, r: Rig) -> None:
    """Elbow out to the side, hand cupped at the ear."""
    desk_hands(c, r, (1,))
    raised_arm(c, r.look, shoulder(r, -1), (r.cx - 24, r.top + 15), r.hp(-14, 1), "cup")


def _paper(c: Canvas, r: Rig) -> None:
    """Elbows on the desk, a sheet held up in both hands at chest height."""
    cx, top = r.cx, r.top
    y0 = top + 4
    sheet, d = mask((W, H))
    d.rectangle((cx - 8, y0, cx + 8, y0 + 16), fill=1)  # Tall enough to hide a tie's tip.
    c.paint(sheet, PAPER, shade=False)
    c.line([(cx - 6, y0 + 2), (cx + 2, y0 + 2)], PRINT)  # Heading, then lines of print.
    for y in range(y0 + 5, y0 + 15, 2):
        for x in range(cx - 6, cx + 7 - (4 if y == y0 + 13 else 0)):
            if (x - cx + y) % 6 != 0:  # Gaps between words.
                c.dot(x, y, PRINT)
    for side in (-1, 1):
        raised_arm(c, r.look, shoulder(r, side), (cx + side * 19, DESK_Y - 1), (cx + side * 9, y0 + 8), "fist")


GESTURES: dict[str, Hook] = {"desk": _desk, "thumbs": _thumbs, "chin": _chin, "ear": _ear, "paper": _paper}


# --- The scene ------------------------------------------------------------------


class Persona:
    """A Look at its desk: the device layers and the full scene for any pose."""

    def __init__(self, look: Look) -> None:
        self.look = look
        self.gestures = {**GESTURES, **look.gestures}

    def chair(self, img: Image.Image) -> None:
        """High-back office chair, so the suit stands out from the wall."""
        ramp = self.look.chair
        c = Canvas(W, H)
        back, d = mask((W, H))
        d.rounded_rectangle((CX - 27, 30, CX + 27, DESK_Y + 4), radius=8, fill=1)
        c.paint(back, ramp)
        for x in (CX - 18, CX + 18):  # Stitched panels.
            c.line([(x, 36), (x, DESK_Y)], ramp.shadow)
        c.outline(self.look.outline)
        img.alpha_composite(c.img)

    def desk(self, img: Image.Image, p: Pose) -> None:
        dc = self.look.desk
        d = ImageDraw.Draw(img)
        d.rectangle((0, DESK_Y, W, DESK_Y + 4), fill=dc.top)
        d.line((0, DESK_Y, W, DESK_Y), fill=dc.edge)
        d.rectangle((0, DESK_Y + 5, W, H), fill=dc.front)
        d.line((0, DESK_Y + 5, W, DESK_Y + 5), fill=dc.line)
        for x in (12, W - 13):  # Drawer panels.
            d.rectangle((x - 9, DESK_Y + 8, x + 9, H - 2), outline=dc.line)
            d.rectangle((x - 2, DESK_Y + 12, x + 2, DESK_Y + 12), fill=dc.handle)
        self.look.desk_props(img, p)

    def body(self, p: Pose) -> tuple[Image.Image, Image.Image]:
        """Returns (body behind the desk, arms and hands in front of it)."""
        look = self.look
        c = Canvas(W, H)
        cx = CX
        neck = (cx + p.head_dx, look.neck_y + p.head_dy)
        top = 41 - p.breath
        r = Rig(pose=p, look=look, cx=cx, top=top, neck=neck, head_c=(neck[0], neck[1] - 15))

        torso, d = mask((W, H))
        ellipse(d, cx, top + 8, 21, 8)
        d.rectangle((cx - 21, top + 8, cx + 21, H), fill=1)
        c.paint(torso, look.suit)
        look.neckline(c, r)

        neck_m, d = mask((W, H))
        d.rectangle((neck[0] - 4, neck[1] - 4, neck[0] + 4, top + 1), fill=1)
        c.paint(neck_m, look.skin)
        look.head(c, r)
        look.hair_style(c, r)

        look.marks(c, r)
        eyes = []
        for side in (-1, 1):
            ex, ey = r.at(side * look.eye_at[0], look.eye_at[1])
            eyes.append((ex, ey))
            kind = p.eyes
            if kind == "wink":
                kind = "blink" if side == 1 else "open"
            look.eye(c, kind, ex, ey, p.look, side)
            look.brow(c, p.brows, ex, ey, side)
            if p.blush:
                for dx in (-1, 0, 1):
                    c.dot(ex + dx, ey + 3, look.blush)
        nx, ny = r.at(*look.nose_at)
        look.nose(c, nx, ny)
        look.mouth(c, p.mouth, nx, ny + look.mouth_drop)
        if p.glasses and look.glasses:
            look.glasses(c, eyes)

        c.outline(look.outline)
        _extras(c, tuple(e for e in p.extras if e != "tear"), cx, 76)
        if "tear" in p.extras:
            tx, ty = r.at(*look.tear_at)
            for dy in range(3):
                c.dot(tx, ty + dy, (120, 190, 255))

        front = Canvas(W, H)
        self.gestures[p.hand](front, r)
        front.outline(look.outline)
        # Sleeves grow out of the jacket: no dark line where an arm sits on the shoulder.
        fp, bp = front.img.load(), c.body.load()
        for y in range(max(0, top - 2), top + 10):
            for x in range(W):
                if abs(x - cx) >= 12 and bp[x, y] and fp[x, y][:3] == look.outline and fp[x, y][3]:
                    fp[x, y] = (0, 0, 0, 0)
        return c.img, front.img

    # Layers for the device. The room and chair never change. Body, desk
    # and arms make one layer, so the desk stays between body and hands.

    def background(self) -> Image.Image:
        img = Image.new("RGBA", (W, H), (*self.look.wall, 255))
        self.look.decor(img)
        self.chair(img)
        return img

    def foreground(self, p: Pose) -> Image.Image:
        body, front = self.body(p)
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        img.alpha_composite(body)
        self.desk(img, p)
        img.alpha_composite(front)
        return img

    def scene(self, p: Pose) -> Image.Image:
        img = self.background()
        img.alpha_composite(self.foreground(p))
        return img


# --- Moods and animations -------------------------------------------------------
# Shared by every look. A look picks its resting pose and may replace the
# Neutral and Focus loops with its own.

HAPPY = Pose(eyes="happy", brows="up", mouth="grin", hand="thumbs")
LOVED = Pose(eyes="heart", brows="up", mouth="grin", blush=True, hand="desk", extras=("hearts",))
SAD = Pose(eyes="open", brows="worried", mouth="frown", head_dy=2, hand="desk", extras=("tear",))
SCARED = Pose(eyes="wide", brows="up", mouth="o", hand="desk", extras=("sweat",))
SLEEPING = Pose(eyes="blink", mouth="o", head_dy=3, tilt=-10, hand="desk", extras=("zzz",))
LISTENING = Pose(brows="one_up", tilt=8, hand="ear")
THINKING = Pose(eyes="up", brows="worried", tilt=-5, hand="chin", extras=("dots",))
TALKING = Pose(brows="up", mouth="talk", hand="desk")
READING = Pose(eyes="half", hand="paper", glasses=True, head_dy=1)

Frames = list[tuple[Pose, int]]


def sleepy(rest: Pose) -> Pose:
    return with_(rest, eyes="half", head_dy=1)


def animations(rest: Pose, neutral: Frames | None = None, focus: Frames | None = None) -> dict[str, Frames]:
    """Every mood the device asks for. rest is the look's idle pose."""
    drowsy = sleepy(rest)
    return {
        # Sits at the desk, breathing.
        "Neutral": neutral or [(rest, 1800), (with_(rest, breath=1), 1400)],
        # Thumbs up with a little bounce, then a proud smile.
        "Happy": [
            (HAPPY, 450),
            (with_(HAPPY, head_dy=-1, breath=1), 450),
            (HAPPY, 450),
            (with_(HAPPY, head_dy=-1, breath=1), 450),
            (with_(HAPPY, hand=rest.hand, eyes="open", mouth="smile"), 2000),
        ],
        "Loved": [(LOVED, 600), (with_(LOVED, head_dy=-1, breath=1), 600)],
        "Sad": [(SAD, 1400), (with_(SAD, breath=1), 1400), (with_(SAD, look=1), 1400)],
        "Scared": [(SCARED, 120), (with_(SCARED, head_dx=1), 120), (SCARED, 120), (with_(SCARED, head_dx=-1), 120)],
        "Sleepy": [(drowsy, 1200), (with_(drowsy, eyes="blink", head_dy=2), 900), (drowsy, 1500)],
        "Sleeping": [(SLEEPING, 1400), (with_(SLEEPING, breath=1, mouth="flat"), 1400)],
        "listening": [(LISTENING, 1000)],
        "thinking": [(THINKING, 1000)],
        "talking": [(TALKING, 1000)],
        # Reads a sheet with glasses on, then looks up at you.
        "Focus": focus
        or [
            (READING, 2600),
            (with_(READING, breath=1), 2000),
            (READING, 1800),
            (with_(READING, eyes="open", brows="up"), 1400),
            (READING, 1600),
            (with_(READING, breath=1), 1400),
        ],
    }
