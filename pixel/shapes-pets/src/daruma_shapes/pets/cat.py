"""Cats on the pet rig (rig.py): the parts only a cat has.

rig.py draws a sitting four-legged pet. A cat keeps its body, legs, head and
moods, and brings its own:

  nose and mouth  a small pink nose and a "w" mouth for every Pose.mouth
                  kind, plus "mew" (wide open, as in a meow or a yawn)
  ears            tall, wide-set triangles with pink insides and a pale
                  tuft; `ears` swings them out to the side ("airplane"
                  ears) or perks them up
  eyes            big round irises with a pupil and a dark rim (see Eyes)
  whiskers        two white lines a side, out past the cheeks
  tail            a long tail in rings, in one of several shapes (see Tail)
  stances         loaf, curled up asleep, the scared arch, the play bow,
                  kneading

A cat's look needs more per frame than Pose has, so CatPose adds the tail
shape, a hop and the laser dot it watches. render() draws one frame: the
tail behind, the rig's pet with the cat's hooks, then the eyes, whiskers
and anything in front (the tail around the paws, the dot). The eyes and
whiskers come after the rig's outline, so a whisker stays one pixel wide.

Eyes (CatPose.eyes): open, wide (dilated pupils), slit (narrow pupils),
left, right, down, up, half, blink, happy, heart, sad, wink. rig.py's eye
dots are not used: the rig gets an eye kind it does not draw.

Tail (CatPose.tail_shape), with `wag` (-1..1) moving the end:

  curl   around the front paws, along the floor; `wag` lifts the tip
  up     straight up behind, the tip hooked over; `wag` sways it
  low    down and out to the side along the floor
  puff   straight up and bushy, as when scared
  wrap   around a curled-up sleeping cat
  bow    up from a raised rump, in the play bow
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from PIL import Image

from daruma_pixel import effects
from daruma_pixel.effects import HEART, HEART_SHINE
from daruma_pixel.pixelkit import Canvas, Color, Point, Ramp, ellipse, intersect, mask, poly, rotate, subtract  # noqa: F401

from . import rig
from .rig import DARK, Breed, Coat, H, Pose, Rig, Stance, W  # noqa: F401

WHITE = (255, 255, 255)
LASER = (255, 60, 60)
LASER_GLOW = (255, 170, 160)


# --- Poses ----------------------------------------------------------------------


@dataclass(frozen=True)
class CatPose(Pose):
    tail_shape: str = "curl"  # curl, up, low, puff, wrap, bow (see the module doc).
    hop: int = 0  # Pixels the whole cat is off the ground.
    laser: int | None = None  # A laser dot on the drape, this many pixels right of the middle (clear of the paws: 20+).
    pupils: int = 0  # Pupils' sideways look, -1 left .. 1 right, for "open" eyes.


# --- Looks ----------------------------------------------------------------------


@dataclass(frozen=True)
class Look:
    """A cat's own colors, beyond the rig's Coat."""

    stripe: Color  # Tabby stripes, the M, the tail rings.
    iris: Ramp  # base, shadow (lower half), light (the glint side).
    pupil: Color
    rim: Color  # Around the eye, and closed lids.
    nose: Ramp
    mouth: Color  # The "w" line.
    inside: Color  # Open mouth.
    tongue: Color
    whisker: Color
    tail: Ramp  # The tail's fur.
    puff: Ramp | None = None  # A scared tail, if not `tail`.
    ring: Color | None = None  # The tail's rings, if not `stripe` (lighter keeps them apart from the outline).


# --- Nose and mouth -------------------------------------------------------------


def nose_fn(look: Look):
    def nose(c: Canvas, nx: int, ny: int) -> None:
        """A small pink nose: a flat top three wide, narrowing to a point."""
        for dx in (-1, 0, 1):
            c.dot(nx + dx, ny, look.nose.base)
        c.dot(nx - 1, ny, look.nose.light or look.nose.base)
        c.dot(nx, ny + 1, look.nose.shadow)

    return nose


def mouth_fn(look: Look):
    def mouth(c: Canvas, kind: str, x: int, y: int) -> None:
        """The mouth hangs off the nose: a line down, then the two halves of the "w"."""
        m = look.mouth
        if kind in ("smile", "flat", "frown"):
            c.dot(x, y, m)
            corner = {"smile": -1, "flat": 0, "frown": 1}[kind]
            for side in (-1, 1):
                c.dot(x + side, y + 1, m)
                c.dot(x + side * 2, y + 1 + (corner if corner > 0 else 0), m)
                if corner < 0:
                    c.dot(x + side * 3, y, m)
        elif kind in ("open", "talk", "mew"):
            rows = {"talk": 2, "open": 3, "mew": 4}[kind]
            c.dot(x, y, m)
            for dy in range(1, rows + 1):
                # Rounded: narrow at the top and bottom rows, wider between.
                half = 1 if kind == "talk" or dy in (1, rows) else 2
                for dx in range(-half, half + 1):
                    c.dot(x + dx, y + dy, look.inside)
            c.dot(x, y + rows, look.tongue)
            if rows > 2:
                c.dot(x - 1, y + rows - 1, look.tongue)
                c.dot(x + 1, y + rows - 1, look.tongue)
        elif kind == "o":
            c.dot(x, y, m)
            for dx, dy in ((0, 1), (-1, 2), (1, 2), (0, 3)):
                c.dot(x + dx, y + dy, look.inside)

    return mouth


# --- Ears -----------------------------------------------------------------------


def ears_fn(look: Look, base_in: Point = (3, -9), base_out: Point = (12, -4), tip: Point = (11, -19)):
    """Tall triangles at the top corners of the head, with pink insides and a
    pale tuft. They swing around the middle of their base: `ears` > 0 turns
    them out to the side, < 0 perks them up and in."""

    def ears(c: Canvas, r: Rig) -> None:
        coat, p, hp = r.breed.coat, r.pose, r.hp
        for side, twitch in ((-1, p.ear_left), (1, p.ear_right)):
            bi, bo, tp = (
                hp(side * base_in[0], base_in[1]),
                hp(side * base_out[0], base_out[1]),
                hp(side * tip[0], tip[1]),
            )
            pivot = ((bi[0] + bo[0]) / 2, (bi[1] + bo[1]) / 2)
            angle = side * (p.ears + twitch)
            ear, d = mask((W, H))
            poly(d, rotate([bi, bo, tp], pivot, angle))
            c.paint(ear, coat.fur)
            # The inside: a smaller triangle, pink at the base and fur-pale at the tip.
            k = 0.62
            mid = ((bi[0] + bo[0]) / 2, (bi[1] + bo[1]) / 2 + 1)
            inner = [(mid[0] + (q[0] - mid[0]) * k, mid[1] + (q[1] - mid[1]) * k) for q in (bi, bo, tp)]
            m, d = mask((W, H))
            poly(d, rotate(inner, pivot, angle))
            c.paint(m, coat.pink, shade=False)
            tx, ty = rotate([(mid[0] + (tp[0] - mid[0]) * 0.35, mid[1] + (tp[1] - mid[1]) * 0.35)], pivot, angle)[0]
            c.dot(round(tx), round(ty), coat.white.light or coat.white.base)

    return ears


# --- Eyes -----------------------------------------------------------------------

# A 5x5 round eye, top row first: "#" iris, "." empty.
_EYE = (".###.", "#####", "#####", "#####", ".###.")
_RIM = [
    (-1, -3),
    (0, -3),
    (1, -3),
    (-2, -3),
    (2, -3),
    (-3, -2),
    (3, -2),
    (-3, -1),
    (3, -1),
    (-3, 0),
    (3, 0),
    (-3, 1),
    (3, 1),
    (-2, 2),
    (2, 2),
    (-2, 3),
    (-1, 3),
    (0, 3),
    (1, 3),
    (2, 3),
]


def eye(c: Canvas, look: Look, kind: str, x: int, y: int, side: int, pupils: int = 0) -> None:
    """One eye centred at (x, y); side -1 is the cat's right (our left)."""
    rim, iris, pupil = look.rim, look.iris, look.pupil
    if kind in ("open", "wide", "slit", "left", "right", "down", "up", "sad", "heart"):
        top = -2
        if kind == "sad":
            top = -1  # The upper lid droops.
        if kind == "down":
            top = -1
        for row, line in enumerate(_EYE):
            dy = row - 2
            for col, ch in enumerate(line):
                dx = col - 2
                if ch != "#":
                    continue
                if dy < top:
                    c.dot(x + dx, y + dy, rim)
                else:
                    c.dot(x + dx, y + dy, iris.shadow if dy >= 1 else iris.base)
        # The rim: a dark line over the top and round the sides, a lighter one below.
        for dx, dy in ((-2, -3), (-1, -3), (0, -3), (1, -3), (2, -3), (-3, -2), (3, -2), (-3, -1), (3, -1)):
            c.dot(x + dx, y + dy, rim)
        c.dot(x + side * 3, y, rim)  # The outer corner, pulled out a little.
        if kind == "heart":
            for row, line in enumerate(("X.X", "XXX", ".X.")):
                for col, ch in enumerate(line):
                    if ch == "X":
                        c.dot(x - 1 + col, y - 1 + row, HEART)
            c.dot(x - 1, y - 1, HEART_SHINE)
            return
        px = {"left": -1, "right": 1}.get(kind, pupils)
        py = {"down": 1, "up": -1}.get(kind, 0)
        if kind == "wide":  # Dilated: scared, or in love.
            cells = [(dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)]
        elif kind == "slit":  # Narrowed to a line, locked on a target.
            cells = [(0, -1), (0, 0), (0, 1)]
        else:  # An upright oval.
            cells = [(0, -1), (0, 0), (0, 1)]
        for dx, dy in cells:
            ddy = dy + py
            if ddy < top or ddy > 2:
                continue
            c.dot(x + dx + px, y + ddy, pupil)
        gx, gy = x - 1 + px, y - 1 + py
        if kind == "wide":
            gx, gy = x - 1, y - 1
        if gy >= top:
            c.dot(gx, gy, WHITE)
    elif kind == "half":  # Sleepy: the lid down over the top half.
        for dx in range(-2, 3):
            c.dot(x + dx, y - 1, rim)
        for dx in range(-2, 3):
            c.dot(x + dx, y, look.iris.base if abs(dx) > 0 else pupil)
        for dx in range(-1, 2):
            c.dot(x + dx, y + 1, look.iris.shadow)
        c.dot(x + side * 3, y - 1, rim)
    elif kind == "blink":  # Closed, a soft curve with the outer corner up.
        for dx in range(-2, 3):
            c.dot(x + dx, y + 1, rim)
        c.dot(x + side * 3, y, rim)
    elif kind == "happy":  # Closed and smiling: an arch.
        for dx, dy in ((-2, 1), (-1, 0), (0, 0), (1, 0), (2, 1)):
            c.dot(x + dx, y + dy, rim)


# --- Whiskers -------------------------------------------------------------------


def whiskers(c: Canvas, look: Look, hp, droop: float = 0.0) -> None:
    """Two whiskers a side, from inside the cheek out past it.
    `droop` > 0 lets them hang, < 0 fans them forward and up."""
    for side in (-1, 1):
        for k, (y0, y1) in enumerate(((4, 2), (6, 7))):
            y1 = y1 + droop * (1 + k)
            a = hp(side * 11, y0)
            b = hp(side * 18, y1)
            n = max(abs(round(b[0]) - round(a[0])), abs(round(b[1]) - round(a[1])))
            for i in range(n + 1):
                t = i / max(1, n)
                x, y = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
                c.dot(round(x), round(y), look.whisker)


# --- Tail -----------------------------------------------------------------------


def tail_path(shape: str, cx: int, floor: int, hip_y: int, wag: float) -> list[Point]:
    """The tail's centre line, root first, one point per pixel of length."""
    w = max(-1.0, min(1.0, wag))
    pts: list[Point] = []

    def walk(x: float, y: float, headings: list[float]) -> None:
        pts.append((x, y))
        for a in headings:
            x, y = x + math.sin(math.radians(a)), y - math.cos(math.radians(a))
            pts.append((x, y))

    if shape == "curl":
        # Out from behind the right haunch, down to the floor, then along it
        # in front of the paws to the left, the tip curling up.
        n = 30
        heads = []
        for i in range(n):
            t = i / (n - 1)
            if t < 0.15:
                a = 180 + 90 * (t / 0.15)  # Down and round toward the front.
            elif t < 0.8:
                a = 270  # Along the floor, to the left.
            else:
                a = 270 + (50 + 40 * w) * ((t - 0.8) / 0.2)  # The tip lifts.
            heads.append(a)
        walk(cx + 18, floor - 5, heads)
    elif shape in ("up", "puff", "bow"):
        n = {"up": 44, "puff": 36, "bow": 30}[shape]
        lean = 8 * w
        heads = []
        for i in range(n):
            t = i / (n - 1)
            if t < 0.12:
                a = 50 - 45 * (t / 0.12)  # Out from behind the haunch ...
            elif t < 0.8 or shape == "puff":
                a = 5 + lean * t  # ... and straight up beside the body ...
            else:
                a = 5 + lean - 175 * ((t - 0.8) / 0.2)  # ... the tip hooked over.
            heads.append(a)
        base = (cx + 14, hip_y + 2) if shape != "bow" else (cx + 6, hip_y - 10)
        walk(*base, heads)
    elif shape == "low":
        # Down off the haunch and out along the floor to the right.
        n = 26
        heads = [140 + 40 * min(1.0, i / 6) - 90 * max(0.0, min(1.0, (i - 6) / 6)) - 10 * w * (i / n) for i in range(n)]
        walk(cx + 17, floor - 7, heads)
    elif shape == "wrap":
        # Round the front of the curled-up body, from the far side to under the chin.
        n = 42
        heads = []
        for i in range(n):
            t = i / (n - 1)
            if t < 0.1:
                a = 200 + 70 * (t / 0.1)
            elif t < 0.85:
                a = 270 + 8 * math.sin((t - 0.1) / 0.75 * math.pi)  # Rides over the paws.
            else:
                a = 270 + (40 + 20 * w) * ((t - 0.85) / 0.15)
            heads.append(a)
        walk(cx + 23, floor - 6, heads)
    return pts


def draw_tail(c: Canvas, look: Look, pts: list[Point], radius: tuple[float, float], ring: int = 4) -> None:
    """Discs along the path, thick at the root, in alternating fur and stripe
    rings; the last few pixels dark, as a tabby's tip is."""
    n = len(pts)
    fur = look.tail
    ring_color = look.ring or look.stripe
    dark = Ramp(base=ring_color, shadow=ring_color, line=ring_color)
    bands: list[tuple[Image.Image, Ramp]] = []
    cur, d, cur_dark = None, None, None
    for i, (x, y) in enumerate(pts):
        t = i / max(1, n - 1)
        is_dark = (i // ring) % 2 == 1 or i >= n - 3
        if cur is None or is_dark != cur_dark:
            cur, d = mask((W, H))
            cur_dark = is_dark
            bands.append((cur, dark if is_dark else fur))
        r = radius[0] + (radius[1] - radius[0]) * t
        ellipse(d, x, y, r, r)
    for m, ramp in bands:
        c.paint(m, ramp, shade=ramp is fur)


# --- Stances --------------------------------------------------------------------


def _legs(c: Canvas, r: Rig, ramp: Ramp, lift: tuple[int, int] = (0, 0), spread: int = 0, reach: int = 0) -> None:
    """Front legs from the chest to the floor. `lift` raises a paw (left,
    right) off the floor; `spread` sets them wider; `reach` puts the paws
    forward (lower, bigger) as in a stretch."""
    cx, floor = r.cx, r.floor
    top = r.chest_y + 1
    m, d = mask((W, H))
    for k, side in enumerate((-1, 1)):
        x0 = cx + side * (r.breed.leg_dx + spread)
        fy = floor - 2 - lift[k]
        poly(d, [(x0 - 2, top), (x0 + 2, top), (x0 + 2, fy), (x0 - 2, fy)])
        ellipse(d, x0, fy + reach * 0.3, 3 + reach * 0.3, 2.5)
    c.paint(m, ramp)
    for k, side in enumerate((-1, 1)):  # Toe lines.
        x0 = cx + side * (r.breed.leg_dx + spread)
        fy = floor - 2 - lift[k]
        c.dot(x0 - 1, fy + 1, ramp.shadow)
        c.dot(x0 + 1, fy + 1, ramp.shadow)
        if lift[k]:  # A raised paw: a dark edge under it, the gap to the floor in shadow.
            for dx in range(-2, 3):
                c.dot(x0 + dx, fy + 3, r.breed.coat.outline)
                for y in range(fy + 4, floor):
                    c.dot(x0 + dx, y, r.breed.coat.deep.shadow)


def _tucked(c: Canvas, r: Rig) -> None:
    """A loaf: the front paws folded under, two pale bumps at the front."""
    ramp = r.breed.coat.white
    m, d = mask((W, H))
    for side in (-1, 1):
        ellipse(d, r.cx + side * 4, r.floor - 2, 3, 2)
    c.paint(m, ramp)


def stance_hooks() -> dict[str, Stance]:
    """The cat's stances, by Pose.stance name."""

    def legs(c: Canvas, r: Rig, lift=(0, 0), spread=0, reach=0) -> None:
        _legs(c, r, r.breed.coat.white, lift, spread, reach)

    return {
        "knead_l": Stance(rise=0, front=lambda c, r: legs(c, r, lift=(3, 0))),
        "knead_r": Stance(rise=0, front=lambda c, r: legs(c, r, lift=(0, 3))),
        "stiff": Stance(rise=0, front=lambda c, r: legs(c, r, spread=2)),
        "loaf": Stance(rise=-6, front=_tucked),
        "curl": Stance(rise=-9, front=lambda c, r: None),
        "bow": Stance(rise=-9, front=lambda c, r: legs(c, r, spread=3, reach=2)),
    }


# --- Drawing --------------------------------------------------------------------


@dataclass(frozen=True, eq=False)
class Cat:
    """A cat: its Breed on the rig, its Look, and per-stance body changes."""

    breed: Breed
    look: Look
    shapes: dict[str, dict]  # stance -> Breed field changes (a loaf is wider and lower).

    def breed_for(self, p: Pose) -> Breed:
        changes = self.shapes.get(p.stance)
        return replace(self.breed, **changes) if changes else self.breed

    def render(self, p: CatPose, cx: int = W // 2, floor: int = H - 5) -> Image.Image:
        b = self.breed_for(p)
        floor -= p.hop
        stance = b.stances.get(p.stance) if p.stance != "sit" else None
        lift = b.leg + (stance.rise if stance else 0)
        hip_y = floor - 18
        neck = (cx + p.head_dx, floor - 32 + p.head_dy - lift)
        head_c = (neck[0], neck[1] - 10)

        def hp(x: float, y: float) -> tuple[float, float]:
            return rotate([(head_c[0] + x, head_c[1] + y)], neck, p.tilt)[0]

        out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        # The tail, behind or in front.
        front_tail = p.tail_shape in ("curl", "wrap")
        tail = Canvas(W, H)
        pts = tail_path(p.tail_shape, cx, floor, hip_y, p.wag)
        if p.tail_shape == "puff":
            look = replace(self.look, tail=self.look.puff or self.look.tail)
            draw_tail(tail, look, pts, (3.4, 2.4), ring=5)
        else:
            draw_tail(tail, self.look, pts, (2.0, 1.2))
        tail.outline(b.coat.outline)
        if not front_tail:
            out.alpha_composite(tail.img)

        body = rig.render(b, replace(p, eyes="-", blush=False, wag=0.0, extras=()), cx, floor)
        c = Canvas(W, H)
        c.img = body
        for side in (-1, 1):
            ex, ey = (round(v) for v in hp(side * b.eye_at[0], b.eye_at[1]))
            kind = p.eyes
            if kind == "wink":
                kind = "blink" if side == 1 else "open"
            eye(c, self.look, kind, ex, ey, side, p.pupils)
            if p.blush:
                c.dot(ex + side * 2, ey + 3, rig.BLUSH)
                c.dot(ex + side * 3, ey + 3, rig.BLUSH)
        whiskers(c, self.look, hp, droop=1.0 if p.eyes in ("sad",) else 0.0)
        out.alpha_composite(c.img)
        if front_tail:
            out.alpha_composite(tail.img)
        top = Canvas(W, H)
        top.img = out
        if p.laser is not None:
            lx, ly = cx + p.laser, H - 10  # On the drape, above the screen's bottom info line.
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                top.dot(lx + dx, ly + dy, LASER_GLOW)
            top.dot(lx, ly, LASER)
        lx_, ly_ = (round(v) for v in hp(-b.eye_at[0], b.eye_at[1]))
        effects.extras(top, p.extras, cx, floor + p.hop, tear=(lx_ - 1, ly_ + 3))
        return top.img
