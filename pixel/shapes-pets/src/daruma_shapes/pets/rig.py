"""A front-facing sitting pet in a cozy room: the drawing engine for pet personas.

The rig is any small four-legged pet sitting up and facing you. A Breed
says what it looks like: its nose and mouth (the species' own), the ears
(drawn behind the head, like tall pointed ears, or over it, like folded
ones), head and muzzle, leg and body size, the tail, the coat colors and
where the patches go, and any stances beyond sitting. The engine draws
what every pet shares: body, chest, legs, haunches, head, eyes, the
glasses, book and ball, the tail and its wag, and the moods. The effects
(hearts, zzz, ...) are effects.py's. The scene behind the pet (room,
window, rug, plant) is separate and swappable: see scene.py.

Species parts live on top: dog.py has the dog's nose, mouth (tongue out),
button ears and "sitting pretty". A cat would add its own nose and mouth,
whiskers (Breed.head_marks), smaller pointed ears and a carried tail.

A Pose says where parts go (ears, head, tail) and which features to show
(eyes, mouth, extras). render() turns a Breed and a Pose into a crisp RGBA
sprite on the logical canvas. Moods and animations are lists of poses.

Two ways to wag (Breed.tail):

  "butt"     No tail, as on a Pembroke: the whole rear end is the signal.
             `wag` (-1..1) slides the hindquarters sideways, grows the
             haunch on the swing side and shrinks the other, bends the rear
             around the hip (row shear, so no blur), and flashes the white
             "pants" fluff on the outside. The chest counter-sways one
             pixel; the head stays level, as a real dog's does.
  "carried"  A tail that sticks up behind one haunch and swings from its
             base. `wag` swings it; `Pose.tail` sets how high it is
             carried (1 up and proud, 0 low and tucked). The body keeps
             still.

A persona module builds a Pet from its Breed, a Scene, the spot the pet
sits on and, if it has one, a progress prop and its spot. It exposes the
names every persona module has (see personas.Spec):

    ROOM = Room(...)
    _pet = Pet(BREED, ROOM, seat="floor", plant=POTHOS, plant_spot="shelf")
    background, foreground, scene = _pet.background, _pet.foreground, _pet.scene
    WINDOW = ROOM.window
    _extra = _pet.layers()
    plant, PLANT_STAGES, DEFAULT_STAGE = _extra["plant"], ...   # the progress prop
    RUG_COLORS, RUG_BY_WEEKDAY, RUG_BOX = _extra["RUG_COLORS"], ...   # weekday colors
    ANIMATIONS, BLINKS, WINKS = ...
    PERSONA = Spec("name", background=0x...)

Everything is drawn on the 106x80 canvas, with the light from the top left.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field, replace

from PIL import Image, ImageDraw

from daruma_pixel.effects import HEART, HEART_SHINE, extras
from daruma_pixel.pixelkit import (
    Canvas,
    Color,
    Point,
    Ramp,
    cached_picture,
    ellipse,
    mask,
    poly,
    rotate,
    shear_rows,
    shift,
)
from daruma_pixel.scene import Grower, Scene, Spot

W, H = 106, 80  # Logical canvas: 318x240 on screen at 3x.

# Colors every pet shares: eyes, effects and props.
DARK = (44, 28, 24)
BLUSH = (244, 150, 140)
BOOK = Ramp(base=(44, 116, 124), shadow=(30, 86, 96), light=(70, 150, 156), line=(24, 64, 72))
PAGE = Ramp(base=(240, 224, 184), shadow=(212, 192, 150), line=(150, 120, 84))
GOLD = (226, 186, 88)
GLASSES = (44, 28, 24)
LENS_GLINT = (236, 246, 255)
BALL = Ramp(base=(206, 224, 72), shadow=(160, 180, 46), light=(236, 246, 146), line=(104, 118, 30))  # A tennis ball.
BALL_SEAM = (250, 250, 236)


# --- Poses ----------------------------------------------------------------------


@dataclass(frozen=True)
class Pose:
    eyes: str = "open"  # open, blink, happy, heart, half, small, up, up_left, sad, wink, down
    mouth: str = "smile"  # smile, open, frown, o, flat, talk; a species may add more (the dog: blep, grin)
    blush: bool = False
    ears: float = 0.0  # Degrees each ear tips outward. Negative perks up and in.
    ear_left: float = 0.0  # Extra per-ear twitch.
    ear_right: float = 0.0
    head_dx: int = 0
    head_dy: int = 0
    tilt: float = 0.0  # Head tilt in degrees (positive = clockwise).
    wag: float = 0.0  # -1 (swing left) .. 1 (swing right): the butt or the tail.
    tail: float = 1.0  # A carried tail: 1 held up, 0 hanging low.
    breath: int = 0  # 0 or 1: chest rises a pixel.
    stance: str = "sit"  # sit, or a stance the breed adds (Breed.stances), such as the dog's "beg".
    extras: tuple[str, ...] = ()  # hearts, zzz, sweat, sparkle, dots, tear
    glasses: bool = False  # Round reading glasses.
    prop: str = ""  # "book": an open book held in the lap, paws over its top edge; "ball": a ball held in the mouth.
    page: int = 0  # Page turn on the book: 0 still, 1 a corner lifts, 2 it falls over.


def with_(pose: Pose, **changes) -> Pose:
    return replace(pose, **changes)


# --- Breeds ---------------------------------------------------------------------


@dataclass(frozen=True)
class Coat:
    """The colors of one pet."""

    outline: Color
    fur: Ramp  # Head and ears. Its line also draws sad brows and sleepy lids.
    body: Ramp  # Back and sides of the body.
    deep: Ramp  # Haunches, behind the body.
    white: Ramp  # Chest, legs, paws, blaze and muzzle.
    pink: Ramp  # Inside an erect ear.
    eye: Color = DARK
    bib: Ramp | None = None  # The chest, if not `white` (a white body's chest needs no contour).
    ear: Ramp | None = None  # Ears, if not `fur` (a folded ear reads as a flap in a deeper shade).


@dataclass(frozen=True)
class Rig:
    """Where the parts of one frame sit. Breed hooks get this."""

    pose: Pose
    breed: Breed
    cx: int
    floor: int
    hip_y: int
    neck: tuple[int, int]
    head_c: tuple[int, int]
    sway: int  # Chest sideways offset.
    chest_y: int  # Center of the body ellipse.

    def hp(self, x: float, y: float) -> Point:
        """A head-local point on the canvas, tilted with the head around the neck."""
        return rotate([(self.head_c[0] + x, self.head_c[1] + y)], self.neck, self.pose.tilt)[0]


Hook = Callable[[Canvas, Rig], None]
NoseFn = Callable[[Canvas, int, int], None]  # c, x, y: the top middle of the nose.
MouthFn = Callable[[Canvas, str, int, int], None]  # c, kind (Pose.mouth), x, y: just under the nose.


@dataclass(frozen=True)
class Stance:
    """A way of holding the body other than sitting on all fours."""

    rise: int  # Pixels the chest and head rise.
    front: Hook  # Draws the front legs, after the chest.
    # Adds shapes to the chest's mask before it is painted, so a leg grows
    # out of the chest with no seam: d, r.
    chest: Callable[[ImageDraw.ImageDraw, Rig], None] = lambda d, r: None


def pointed_ears(c: Canvas, r: Rig) -> None:
    """Tall pointed triangles with pink insides, rotating outward from their base:
    a corgi's, or a cat's with smaller numbers one day."""
    head_pt = r.hp
    coat, p = r.breed.coat, r.pose
    for side, twitch in ((-1, p.ear_left), (1, p.ear_right)):
        base_in = head_pt(side * 5, -10)
        base_out = head_pt(side * 16, -6)
        tip = head_pt(side * 18, -23)
        pivot = ((base_in[0] + base_out[0]) / 2, (base_in[1] + base_out[1]) / 2)
        angle = side * (p.ears + twitch)
        ear, d = mask((W, H))
        poly(d, rotate([base_in, base_out, tip], pivot, angle))
        c.paint(ear, coat.fur)
        inner, d = mask((W, H))
        inner_pts = [head_pt(side * 7, -9), head_pt(side * 13, -7), head_pt(side * 16, -19)]
        poly(d, rotate(inner_pts, pivot, angle))
        c.paint(inner, coat.pink, shade=False)


@dataclass(frozen=True, eq=False)
class Breed:
    """What the pet looks like. The number defaults are the corgi's."""

    coat: Coat
    nose: NoseFn  # The species' nose, and mouth for every Pose.mouth kind.
    mouth: MouthFn
    ears_behind: Hook | None = pointed_ears  # Ears drawn before the head (they stand above it) ...
    ears_front: Hook | None = None  # ... or after it (they fold over it).
    tail: str = "butt"  # butt: no tail, the rear wags; carried: a tail of its own (see the module doc).
    stances: dict[str, Stance] = field(default_factory=dict)  # Extra stances by Pose.stance name.
    leg: int = 0  # Extra front-leg length: the chest and head sit this much higher.
    body_r: tuple[float, float] = (15, 14)  # Body ellipse radii.
    bib_r: tuple[float, float] = (10, 12)  # White chest ellipse radii.
    leg_dx: int = 6  # Front legs, each side of the middle.
    haunch_dx: int = 11  # Haunch centers, each side of the middle.
    haunch_r: float = 8
    foot_dx: int = 15  # Hind feet, each side of the middle.
    # The front legs part below the chest, showing `deep` between them. False
    # keeps them together, parted by a short seam between the paws: on a
    # white body a pale gap there reads as something else.
    leg_gap: bool = True
    head_r: tuple[float, float] = (17, 13)
    cheek_at: Point = (13, 5)  # Right cheek fluff; the left one is mirrored.
    cheek_r: tuple[float, float] = (6, 5)
    blaze: tuple[Point, ...] = ((-2, -12), (2, -12), (5, 2), (-5, 2))  # White stripe up the face.
    muzzle_at: Point = (0, 6)
    muzzle_r: tuple[float, float] = (8, 6)
    nose_at: Point = (0, 2)
    eye_at: Point = (7, -1)  # Right eye; the left one is mirrored.
    # Breed hooks, drawn in this order; None draws nothing.
    rear_marks: Hook | None = None  # Patches on the haunches, after them.
    body_marks: Hook | None = None  # Patches on the body, after it and before the chest.
    head_marks: Hook | None = None  # Patches on the head, after the blaze and the ears.
    # A carried tail: its base (from the middle and the hip line), length and colors.
    tail_base: Point = (12, 4)
    tail_len: int = 15
    tail_colors: tuple[Ramp, ...] = ()  # Base to tip, one ramp per band.
    tail_band: tuple[int, ...] = ()  # Where each band after the first starts, in pixels from the base.


# --- Drawing --------------------------------------------------------------------


@cached_picture
def render(b: Breed, p: Pose, cx: int = W // 2, floor: int = H - 5) -> Image.Image:
    coat = b.coat
    c = Canvas(W, H)
    stance = b.stances.get(p.stance) if p.stance != "sit" else None
    lift = b.leg + (stance.rise if stance else 0)
    w = max(-1.0, min(1.0, p.wag))
    butt = b.tail == "butt"
    bw = w if butt else 0.0  # Only a tailless pet wags its rear.
    sway = -round(1.6 * bw)  # Chest counter-sways; the legs lean with it.
    # Free, the head stays level over the swaying chest, as a real dog's
    # does. Holding something (a prop, or its glasses on), the head and
    # glasses lean with the chest instead, so they move as one; a book stays
    # in the lap, the paws on it.
    carry = sway if (p.prop or p.glasses) else 0
    # Anchor points.
    hip_y = floor - 18
    neck = (cx + p.head_dx + carry, floor - 32 + p.head_dy - lift)
    head_c = (neck[0], neck[1] - 10)

    def head_pt(x: float, y: float) -> tuple[float, float]:
        """Head-local point -> canvas, applying tilt around the neck."""
        return rotate([(head_c[0] + x, head_c[1] + y)], neck, p.tilt)[0]

    # --- Hindquarters (behind everything) -------------------------------------
    chest_y = floor - 15 - p.breath - lift
    rig = Rig(p, b, cx, floor, hip_y, neck, head_c, sway, chest_y)
    if b.tail == "carried":
        _tail(c, rig)

    rear_dx = round(2 * bw)
    rear, d = mask((W, H))
    ellipse(
        d, cx - b.haunch_dx, hip_y + 9, b.haunch_r - 1.5 * bw, b.haunch_r
    )  # Left haunch shrinks as the butt swings right.
    ellipse(d, cx + b.haunch_dx, hip_y + 9, b.haunch_r + 1.5 * bw, b.haunch_r)
    rear = shift(shear_rows(rear, hip_y - 4, 0.22 * bw), rear_dx, 0)
    c.paint(rear, coat.deep)
    if b.rear_marks:
        b.rear_marks(c, rig)

    feet, d = mask((W, H))
    ellipse(d, cx - b.foot_dx + rear_dx, floor - 2, 4, 2.5)
    ellipse(d, cx + b.foot_dx + rear_dx, floor - 2, 4, 2.5)
    c.paint(feet, coat.white)

    if butt and abs(w) > 0.35:  # White "pants" fluff peeks out on the swing side.
        side = 1 if w > 0 else -1
        fluff, d = mask((W, H))
        ellipse(d, cx + side * 19 + rear_dx, hip_y + 7, 2.5, 3.5)
        c.paint(fluff, coat.white)

    # --- Body and chest -----------------------------------------------------
    body, d = mask((W, H))
    ellipse(d, cx + sway, chest_y, *b.body_r)
    c.paint(body, coat.body)
    if b.body_marks:
        b.body_marks(c, rig)

    bib, d = mask((W, H))
    ellipse(d, cx + sway, chest_y + 1, *b.bib_r)
    zig = [(cx - 9 + sway, chest_y - 9)]
    for i in range(7):  # Fluffy top edge of the white chest.
        zig.append((cx - 9 + sway + i * 3 + 1.5, chest_y - 13 - (i % 2) * 2))
    zig.append((cx + 9 + sway, chest_y - 9))
    poly(d, zig)
    bib_ramp = coat.bib or coat.white
    if stance:
        stance.chest(d, rig)
        c.paint(bib, bib_ramp)
        stance.front(c, rig)
    elif p.prop == "book":  # The legs hide behind the book; _book() draws the paws.
        c.paint(bib, bib_ramp)
        _book(c, coat.white, p.page, cx, floor)
    else:
        _front_legs(c, rig, d, bib, bib_ramp)

    # --- Ears and head --------------------------------------------------------
    if b.ears_behind:
        b.ears_behind(c, rig)

    head, d = mask((W, H))
    hx, hy = head_pt(0, 0)
    ellipse(d, hx, hy, *b.head_r)
    for side in (-1, 1):  # Cheek fluff.
        cxk, cyk = head_pt(side * b.cheek_at[0], b.cheek_at[1])
        ellipse(d, cxk, cyk, *b.cheek_r)
    c.paint(head, coat.fur)

    blaze, d = mask((W, H))
    poly(d, [head_pt(x, y) for x, y in b.blaze])
    mx, my = head_pt(*b.muzzle_at)
    ellipse(d, mx, my, *b.muzzle_r)
    c.paint(blaze, coat.white)

    if b.ears_front:
        b.ears_front(c, rig)
    if b.head_marks:
        b.head_marks(c, rig)

    # --- Face features ------------------------------------------------------
    nx, ny = (round(v) for v in head_pt(*b.nose_at))
    b.nose(c, nx, ny)
    if p.prop == "ball":  # The jaws close round the ball: no other mouth.
        _ball(c, nx, ny + 2)
    else:
        b.mouth(c, p.mouth, nx, ny + 2)
    eyes = []
    for side in (-1, 1):
        ex, ey = (round(v) for v in head_pt(side * b.eye_at[0], b.eye_at[1]))
        eyes.append((ex, ey))
        kind = p.eyes
        if kind == "wink":
            kind = "blink" if side == 1 else "open"
        _eye(c, coat, kind, ex, ey, side)
        if p.blush:
            c.dot(ex - 1 + side * 2, ey + 3, BLUSH)
            c.dot(ex + side * 2, ey + 3, BLUSH)
    if p.glasses:
        _glasses(c, eyes)

    c.outline(coat.outline)
    lx, ly = eyes[0]
    extras(c, p.extras, cx, floor, tear=(lx - 2, ly + 5))
    return c.img


def _front_legs(c: Canvas, r: Rig, d: ImageDraw.ImageDraw, bib: Image.Image, bib_ramp: Ramp) -> None:
    """Front legs grow out of the chest: one white shape, so no seam. Paws
    stay planted; the tops ride along with the chest's sway and breath, so
    the legs lean and stretch as the body moves."""
    cx, floor, sway, white = r.cx, r.floor, r.sway, r.breed.coat.white
    leg_top = r.chest_y + 1

    def lean(y: float) -> float:
        """Sideways offset at height y: full sway at the chest, none at the paws."""
        return sway * (floor - 2 - y) / (floor - 2 - leg_top)

    for side in (-1, 1):
        x0 = cx + side * r.breed.leg_dx
        poly(d, [(x0 - 3 + sway, leg_top), (x0 + 3 + sway, leg_top), (x0 + 3, floor - 2), (x0 - 3, floor - 2)])
        ellipse(d, x0, floor - 2, 4, 2.5)
    gap = r.breed.leg_gap
    d.rectangle(
        (cx - 3 + sway, leg_top, cx + 3 + sway, floor - (9 if gap else 2)), fill=1
    )  # Chest fills the top of the gap.
    c.paint(bib, bib_ramp)
    if gap:  # The legs part below the chest: a soft shadow between them.
        for y in range(floor - 9, floor - 1):
            gx = cx + round(lean(y))
            for x in range(gx - 2, gx + 3):
                c.dot(x, y, white.shadow if y < floor - 7 or abs(x - gx) == 2 else r.breed.coat.deep.base)
    else:  # Only the paws part: a short seam between them.
        for y in range(floor - 5, floor - 1):
            c.dot(cx + round(lean(y)), y, white.shadow)
    for side in (-1, 1):  # Toe lines.
        x0 = cx + side * r.breed.leg_dx
        c.dot(x0 - 1, floor - 2, white.shadow)
        c.dot(x0 + 1, floor - 2, white.shadow)


def _tail(c: Canvas, r: Rig) -> None:
    """A carried tail, behind a haunch. It rises from its base in a gentle
    curve, thick at the root and thin at the tip, in bands of color.

    The base sits inside the haunch, so the tail stays attached at every
    angle. Carriage `tail` 1 points it up and out, 0 hangs it low to the
    side; `wag` swings it around the base.
    """
    b, p = r.breed, r.pose
    bx, by = r.cx + b.tail_base[0], r.hip_y + b.tail_base[1]
    carry = 38 + (1 - p.tail) * 80  # Degrees from straight up, to the right.
    swing = max(-1.0, min(1.0, p.wag)) * 26 * (0.4 + 0.6 * p.tail)
    angle = math.radians(carry + swing)
    # A curve that bends back toward the middle near the tip, as a terrier's
    # tail curls slightly over the back.
    pts = []
    for i in range(b.tail_len + 1):
        t = i / b.tail_len
        a = angle - math.radians(26) * t * t
        if i == 0:
            x, y = float(bx), float(by)
        else:
            x, y = pts[-1][0] + math.sin(a), pts[-1][1] - math.cos(a)
        pts.append((x, y))
    bands = b.tail_colors
    starts = (0, *b.tail_band)
    for k, ramp in enumerate(bands):
        lo = starts[k]
        hi = starts[k + 1] if k + 1 < len(starts) else len(pts) - 1
        m, d = mask((W, H))
        for i in range(lo, hi + 1):
            x, y = pts[i]
            t = i / b.tail_len
            radius = 2.2 - 1.3 * t  # 4-5 px wide at the root, 2 at the tip.
            ellipse(d, x, y, radius, radius)
        c.paint(m, ramp)


# Eyes that look up, and the side the pupil leans to.
LOOK_UP = {"up": 1, "up_left": -1}


def _eye(c: Canvas, coat: Coat, kind: str, x: int, y: int, side: int) -> None:
    dark, line = coat.eye, coat.fur.line
    if kind == "open" or kind == "sad":
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                c.dot(x + dx, y + dy, dark)
        c.dot(x - 1, y - 1, (255, 255, 255))
        if kind == "sad":  # Brows lifted toward the middle.
            c.dot(x - side * 1, y - 4, line)
            c.dot(x - side * 0, y - 3, line)
            c.dot(x + side * 1, y - 3, line)
    elif kind == "blink":
        for dx in (-2, -1, 0, 1, 2):
            c.dot(x + dx, y + 1, DARK)
    elif kind == "happy":
        for dx, dy in ((-2, 1), (-1, 0), (0, -1), (1, 0), (2, 1)):
            c.dot(x + dx, y + dy, DARK)
    elif kind == "down":  # Looking down, as at a book in the lap.
        for dx in (-1, 0, 1):
            c.dot(x + dx, y, dark)
            c.dot(x + dx, y + 1, dark)
        c.dot(x - 1, y, (255, 255, 255))
    elif kind == "half":
        for dx in (-1, 0, 1):
            c.dot(x + dx, y + 1, dark)
            c.dot(x + dx, y, dark)
        for dx in (-2, -1, 0, 1, 2):
            c.dot(x + dx, y - 1, line)
    elif kind == "small":
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                c.dot(x + dx, y + dy, (255, 255, 255))
        c.dot(x, y, dark)
    elif kind in LOOK_UP:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                c.dot(x + dx, y + dy, (255, 255, 255))
        c.dot(x + LOOK_UP[kind], y - 1, dark)
        c.dot(x, y - 1, dark)
    elif kind == "heart":
        shape = ["X.X", "XXX", ".X."]
        for row, line_ in enumerate(shape):
            for col, ch in enumerate(line_):
                if ch == "X":
                    c.dot(x - 1 + col, y - 1 + row, HEART)
        c.dot(x - 1, y - 1, HEART_SHINE)


_RING = [
    (-1, -3),
    (0, -3),
    (1, -3),
    (-2, -2),
    (2, -2),
    (-3, -1),
    (3, -1),
    (-3, 0),
    (3, 0),
    (-3, 1),
    (3, 1),
    (-2, 2),
    (2, 2),
    (-1, 3),
    (0, 3),
    (1, 3),
]


def _glasses(c: Canvas, eyes: list[tuple[int, int]]) -> None:
    """Round frames around both eyes, a bridge over the blaze, short temples."""
    (lx, ly), (rx, ry) = eyes
    for ex, ey in eyes:
        for dx, dy in _RING:
            c.dot(ex + dx, ey + dy, GLASSES)
        c.dot(ex + 1, ey - 2, LENS_GLINT)
    for x in range(lx + 4, rx - 3):  # Bridge.
        c.dot(x, round(ly + (ry - ly) * (x - lx) / max(1, rx - lx)) - 1, GLASSES)
    for ex, ey, side in ((lx, ly, -1), (rx, ry, 1)):  # Temples, toward the ears.
        for k in range(4, 7):
            c.dot(ex + side * k, ey - 1, GLASSES)


def _book(c: Canvas, white: Ramp, page: int, cx: int, floor: int) -> None:
    """An open book in the lap, cover out, paws hooked over its top edge.

    The book opens away from us, so the spine is nearest and the top edge
    dips toward it. `page` > 0 shows a page standing up over the top edge,
    leaning first one way, then the other, as it turns.
    """
    top, bottom, half = floor - 18, floor - 1, 13

    def dip(x: int) -> int:  # Edges run down toward the spine in two even steps.
        d = abs(x - cx)
        return 2 if d <= 2 else 1 if d <= 8 else 0

    if page:  # The turning page stands up from the spine, behind the paws.
        sheet, d = mask((c.w, c.h))
        lean = -1 if page == 1 else 1
        rows = ((5, 3), (5, 2), (4, 1), (4, 1), (3, 0), (3, 0), (2, 0), (1, 0), (1, 0))
        for dy, (a, b) in zip(range(-6, 3), rows, strict=False):
            d.line((cx + lean * a, top + dy, cx + lean * b, top + dy), fill=1)
        c.paint(sheet, PAGE, shade=False)

    cover, d = mask((c.w, c.h))
    for x in range(cx - half, cx + half + 1):
        ct = top + 2 + dip(x)
        d.line((x, ct, x, bottom), fill=1)
        # The page block peeks over the cover: lit top row, shaded below.
        c.dot(x, ct - 3, BOOK.line)
        c.dot(x, ct - 2, PAGE.base)
        c.dot(x, ct - 1, PAGE.shadow)
    c.paint(cover, BOOK)
    for x in range(cx - half + 2, cx + half - 1):  # Gold bands near the top and bottom.
        if abs(x - cx) > 1:
            c.dot(x, top + 4 + dip(x), GOLD)
            c.dot(x, bottom - 3, GOLD)
    for y in range(top + 3, bottom + 1):  # Spine, nearest us: a lit ridge.
        c.dot(cx, y, BOOK.light)

    paws, d = mask((c.w, c.h))
    for side in (-1, 1):
        ellipse(d, cx + side * 6, top + 2, 3.5, 2.5)
    c.paint(paws, white)
    for side in (-1, 1):  # Toe lines.
        c.dot(cx + side * 6 - 1, top + 4, white.shadow)
        c.dot(cx + side * 6 + 1, top + 4, white.shadow)


_BALL = (
    "...XXX...",
    ".XXXXXXX.",
    ".XXXXXXX.",
    "XXXXXXXXX",
    "XXXXXXXXX",
    "XXXXXXXXX",
    ".XXXXXXX.",
    ".XXXXXXX.",
    "...XXX...",
)
# The seam: two arcs bowing toward each other, ")(", as a tennis ball shows it.
_BALL_SEAM = ((1, 2), (2, 3), (2, 4), (2, 5), (1, 6), (7, 2), (6, 3), (6, 4), (6, 5), (7, 6))


def _ball(c: Canvas, x: int, y: int) -> None:
    """A tennis ball held in the mouth: round, 9 px across, its top at (x, y)
    just under the nose. A dark rim keeps it apart from the white muzzle
    and chest, and the corners of the mouth run back from its sides."""
    x0 = x - 4
    inside = {(x0 + i, y + j) for j, row in enumerate(_BALL) for i, ch in enumerate(row) if ch == "X"}
    for px, py in inside:
        for nx, ny in ((px + 1, py), (px - 1, py), (px, py + 1), (px, py - 1)):
            if (nx, ny) not in inside and ny >= y + 1:  # The top tucks under the nose.
                c.dot(nx, ny, DARK)
    for side in (-1, 1):  # Corners of the mouth, pulled back round the ball.
        c.dot(x + side * 6, y + 2, DARK)
        c.dot(x + side * 7, y + 1, DARK)
    ball, d = mask((c.w, c.h))
    for px, py in inside:
        d.point((px, py), fill=1)
    c.paint(ball, BALL)
    for i, j in _BALL_SEAM:
        c.dot(x0 + i, y + j, BALL_SEAM)


# --- Layers for the device ------------------------------------------------------


@dataclass(frozen=True, eq=False)
class Pet:
    """A breed in a scene: the layers a persona module takes its names from.

    The pet sits on the scene's spot `seat`; the progress prop, if any,
    stands on the spot `plant_spot`. The device draws the window glass
    itself (sky, weather), then the scene with a hole where the glass is,
    then the progress prop, then the pet.
    """

    breed: Breed
    stage: Scene
    seat: str = "floor"
    plant: Grower | None = None
    plant_spot: str = ""

    @property
    def spot(self) -> Spot:
        """Where the pet sits."""
        return self.stage.spots[self.seat]

    def layers(self) -> dict:
        """The persona-module names for the progress prop and the weekday
        colors: plant, PLANT_STAGES, DEFAULT_STAGE, RUG_COLORS, RUG_BY_WEEKDAY
        and RUG_BOX, the ones this pet's scene and prop have."""
        found = dict(self.stage.layers())
        if self.plant is not None:
            found.update(self.plant.layers(self.stage.spots[self.plant_spot]))
        return found

    def render(self, pose: Pose) -> Image.Image:
        """The pet alone, on its spot."""
        return render(self.breed, pose, cx=self.spot.x, floor=self.spot.y)

    def scene(self, pose: Pose, plant_stage: int | None = None, wilted: bool = False) -> Image.Image:
        """The full picture, with the progress prop (if any) at plant_stage,
        by default its DEFAULT_STAGE."""
        img = self.stage.image()
        if self.plant is not None:
            stage = self.plant.default_stage if plant_stage is None else plant_stage
            img.alpha_composite(self.plant.draw(stage, wilted, self.stage.spots[self.plant_spot]))
        img.alpha_composite(self.render(pose))
        return img

    def background(self) -> Image.Image:
        return self.stage.background()

    def foreground(self, pose: Pose) -> Image.Image:
        return self.render(pose)


# --- Moods and animations -------------------------------------------------------

Frames = list[tuple[Pose, int]]


def wag_cycle(base: Pose, frames: int = 8, amplitude: float = 1.0, ms: int = 100) -> Frames:
    """One full side-to-side wag, of the butt or the tail."""
    out = []
    for i in range(frames):
        w = amplitude * math.sin(2 * math.pi * i / frames)
        out.append((with_(base, wag=round(w, 2), breath=1 if i < frames // 2 else 0), ms))
    return out


NEUTRAL = Pose()
HAPPY = Pose(eyes="happy", mouth="open", blush=True, ears=-4)
SAD = Pose(eyes="sad", mouth="frown", ears=38, head_dy=2, extras=("tear",))
LOVED = Pose(eyes="heart", mouth="open", blush=True, ears=-4, extras=("hearts",))
SCARED = Pose(eyes="small", mouth="o", ears=30, head_dy=1, extras=("sweat",))
SLEEPY = Pose(eyes="half", mouth="flat", ears=18, head_dy=2)
SLEEPING = Pose(eyes="blink", mouth="flat", ears=26, head_dy=3, tilt=-6, extras=("zzz",))
LISTENING = Pose(eyes="open", mouth="flat", ears=-10, ear_left=-6, tilt=10)
THINKING = Pose(eyes="up", mouth="flat", tilt=-8, extras=("dots",))
TALKING = Pose(eyes="happy", mouth="talk", blush=True)
READING = Pose(eyes="down", head_dy=2, glasses=True, prop="book")
