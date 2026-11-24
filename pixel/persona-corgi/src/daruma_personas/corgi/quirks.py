"""The corgi's quirks: short surprises (a paw lick, a nose scratch, a
sneeze) and the "brb" trip (it puts up a sign, hops off and comes back).

Each animation is a list of (pose, milliseconds) frames, as in moods.py.
Nothing on the device plays them by itself: a persona picks them by name.

A trip frame is a Trip: the corgi (or nobody) moved along the rug, with
the sign, a dust puff or a sneeze spray around it. Walker draws it; for a
plain Pose it draws the pet as always. Every trip frame stays inside the
area the other frames cover, so the stored frames keep their size.
"""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image

from daruma_pixel.pixelkit import Canvas, Ramp, cached_picture, ellipse, mask
from daruma_pixel.scene import Spot
from daruma_shapes.pets.rig import NEUTRAL, Breed, H, Pet, Pose, W, render, wag_cycle, with_

BOARD = Ramp(base=(242, 230, 202), shadow=(216, 200, 166), light=(252, 246, 230), line=(150, 112, 80))
POST = Ramp(base=(124, 84, 52), shadow=(96, 62, 38), line=(80, 52, 32))
SIGN_EDGE = (70, 44, 30)
INK = (44, 28, 24)
DUST = Ramp(base=(232, 222, 204), shadow=(198, 184, 162), light=(250, 246, 236), line=(206, 190, 168))
DUST_EDGE = (150, 128, 108)
SPEED = (236, 228, 212)
SPRAY = (150, 204, 255)

# "BRB" in a 3x5 pixel font, one string per row.
BRB = ("XX..XX..XX.", "X.X.X.X.X.X", "XX..XX..XX.", "X.X.X.X.X.X", "XX..X.X.XX.")

SIGN_DX = -19  # The sign's post, from the middle of the seat: beside the corgi's left haunch.
OFF = 13  # How far the corgi hops before it dashes: as far as the stored frames reach.


@dataclass(frozen=True)
class Trip:
    """One frame of a trip: the corgi `pet` (None: gone) `dx` pixels along
    the rug and `hop` pixels up, with the sign, a dust puff (1 big, 2 small)
    where it stood, speed lines or a sneeze spray."""

    pet: Pose | None = None
    dx: int = 0
    hop: int = 0
    sign: bool = False
    puff: int = 0
    spray: bool = False


def _sign(c: Canvas, x: int, floor: int) -> None:
    """A little card on a post, standing on the rug: BRB."""
    post, d = mask((W, H))
    d.rectangle((x - 1, floor - 16, x, floor - 1), fill=1)
    c.paint(post, POST)
    board, d = mask((W, H))
    d.rectangle((x - 8, floor - 25, x + 8, floor - 16), fill=1)
    c.paint(board, BOARD)
    c.outline(SIGN_EDGE)
    for row, line in enumerate(BRB):
        for col, ch in enumerate(line):
            if ch == "X":
                c.dot(x - 5 + col, floor - 23 + row, INK)


# Dust cloud lobes, (dx, dy, radius) from where the corgi sat: back row first.
PUFF_BIG = ((-7, -11, 5), (1, -14, 6), (8, -11, 4), (-11, -5, 4), (-4, -6, 5), (4, -6, 5), (11, -5, 4))
PUFF_SMALL = ((-1, -7, 3), (-4, -4, 3), (3, -4, 3))
SPECKS = ((-12, -14), (12, -16), (-14, -4), (9, -11))


def _puff(c: Canvas, x: int, floor: int, size: int, lines: bool) -> None:
    """A dust cloud where the corgi stood (size 1 big, 2 small), and speed
    lines toward where it went."""
    for dx, dy, r in PUFF_BIG if size == 1 else PUFF_SMALL:
        lobe, d = mask((W, H))  # One lobe at a time, so each gets its own contour.
        ellipse(d, x + dx, floor + dy, r, r - 1)
        c.paint(lobe, DUST)
    c.outline(DUST_EDGE)
    if size != 1:
        for dx, dy in SPECKS:  # Loose specks drifting off.
            c.dot(x + dx, floor + dy, DUST.shadow)
    elif lines:
        for y, x0 in ((floor - 15, x + 9), (floor - 9, x + 16), (floor - 3, x + 16)):
            for k in range(x0, W - 16):
                c.dot(k, y, SPEED)


def _spray(c: Canvas, x: int, y: int) -> None:
    """Droplets flying out past both cheeks, two pixels each."""
    for dx, dy in ((20, -3), (22, 1), (20, 5), (24, -1), (23, 6)):
        for side in (-1, 1):
            c.dot(x + side * dx, y + dy, SPRAY)
            c.dot(x + side * (dx + 1), y + dy, SPRAY)


@cached_picture
def trip_picture(b: Breed, spot: Spot, t: Trip) -> Image.Image:
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if t.sign:
        c = Canvas(W, H)
        _sign(c, spot.x + SIGN_DX, spot.y)
        img.alpha_composite(c.img)
    if t.pet is not None:
        img.alpha_composite(render(b, t.pet, cx=spot.x + t.dx, floor=spot.y - t.hop))
    if t.puff or t.spray:
        c = Canvas(W, H)
        if t.puff:
            _puff(c, spot.x + t.dx, spot.y, t.puff, lines=t.pet is None)
        if t.spray and t.pet is not None:
            _spray(c, spot.x + t.dx + t.pet.head_dx, spot.y - 38 + t.pet.head_dy)
        img.alpha_composite(c.img)
    return img


@dataclass(frozen=True, eq=False)
class Walker(Pet):
    """A Pet that also draws Trip frames."""

    def render(self, pose: Pose | Trip) -> Image.Image:
        if isinstance(pose, Trip):
            return trip_picture(self.breed, self.spot, pose)
        return super().render(pose)


# --- Animations -------------------------------------------------------------------

LICK = Pose(stance="lick", eyes="blink", mouth="blep", head_dy=3)
LICK_UP = with_(LICK, mouth="flat", head_dy=0)
RUB = Pose(stance="scratch", eyes="happy", mouth="flat", tilt=6, head_dx=1)
RUB_IN = with_(RUB, tilt=10, head_dx=2, head_dy=1)
SHAKE = Pose(eyes="blink", mouth="flat", ears=10, head_dy=2)
# The trip: it looks toward the door, puts the sign up, hops off and dashes.
GOTTA_GO = Pose(eyes="up", mouth="flat", ears=-8, head_dx=1, tilt=6)
HOP = Pose(eyes="open", mouth="open", head_dx=2, tilt=4)
AWAY = Trip(sign=True)
BACK = Pose(eyes="happy", mouth="open", head_dx=-2, tilt=-4)


def _hops(pet: Pose, steps: tuple[int, ...], ms: int = 130) -> list:
    """Little hops sideways along the rug, past the sign: up on odd steps."""
    return [(Trip(pet=pet, dx=dx, hop=2 if i % 2 == 0 else 0, sign=True), ms) for i, dx in enumerate(steps)]


ANIMATIONS: dict[str, list[tuple[Pose | Trip, int]]] = {
    # Lick a paw: lift it, look at it, three licks, a pleased smile.
    "LickPaw": [
        (with_(LICK_UP, eyes="down"), 450),
        *[frame for _ in range(3) for frame in ((LICK, 200), (LICK_UP, 200))],
        (with_(LICK_UP, eyes="happy", mouth="smile"), 450),
        (NEUTRAL, 300),
    ],
    # Scratch the nose: an itch, then rub the muzzle on a raised paw.
    "ScratchNose": [
        (with_(NEUTRAL, eyes="half", mouth="flat", ear_right=-8), 400),
        *[frame for _ in range(3) for frame in ((RUB, 150), (RUB_IN, 150))],
        (with_(NEUTRAL, eyes="happy", mouth="smile"), 450),
        (NEUTRAL, 300),
    ],
    # Sneeze: ah... aah... CHOO, a head shake, then a sheepish blep.
    "Sneeze": [
        (Pose(eyes="half", mouth="o", ears=-4), 350),
        (Pose(eyes="half", mouth="open", ears=-6, head_dy=-1, tilt=-4), 400),
        (Trip(pet=Pose(eyes="blink", mouth="flat", ears=16, head_dy=3), spray=True), 160),
        (with_(SHAKE, head_dx=-1, tilt=-6), 110),
        (with_(SHAKE, head_dx=1, tilt=6), 110),
        (with_(SHAKE, head_dx=-1, tilt=-4), 110),
        (Pose(eyes="happy", mouth="blep"), 650),
        (NEUTRAL, 300),
    ],
    # Off to the bathroom: it looks to the door, puts its sign up beside
    # it, hops along the rug and dashes off in a puff of dust.
    "WalkOff": [
        (GOTTA_GO, 600),
        (Trip(pet=GOTTA_GO, sign=True), 500),
        (Trip(pet=Pose(eyes="happy", mouth="open", ears=-4), sign=True), 400),
        *_hops(HOP, (3, 6, 9, 11, OFF)),
        (Trip(dx=OFF, sign=True, puff=1), 180),
        (Trip(dx=OFF, sign=True, puff=2), 180),
        (AWAY, 400),
    ],
    # Away: only the sign on the rug.
    "Away": [(AWAY, 1000)],
    # Back again: a puff, it hops home, takes the sign down and wags. Under 3 s.
    "WalkBack": [
        (AWAY, 200),
        (Trip(dx=OFF, sign=True, puff=2), 120),
        (Trip(pet=BACK, dx=OFF, sign=True, puff=1), 120),
        *_hops(BACK, (OFF, 10, 7, 4, 2), ms=120),
        (Trip(pet=Pose(eyes="happy", mouth="open", ears=-4), sign=True), 300),
        *wag_cycle(with_(NEUTRAL, eyes="happy", mouth="open"), frames=8, amplitude=0.7, ms=90),
        (NEUTRAL, 300),
    ],
}
