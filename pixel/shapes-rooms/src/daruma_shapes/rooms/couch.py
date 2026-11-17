"""A velvet couch: a prop for a room (scene.py), drawn where it stands.

couch(img, at, colors) draws a couch with two plump back cushions, a seat
and rolled arms on short wooden legs, centered on the spot `at`, which is
the floor line it stands on. seat(at) is the spot a pet sits on: the top
of the seat cushions, in the middle.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from PIL import Image

from daruma_pixel.pixelkit import Canvas, Color, Ramp, ellipse, mask
from daruma_pixel.scene import Spot

HALF_LEFT, HALF_RIGHT = 44, 43  # From the middle to the outside of each arm.
SEAT_RISE = 7  # The seat's top edge, above the floor.


GREEN = Ramp(base=(50, 100, 76), shadow=(34, 72, 54), light=(76, 132, 100), line=(26, 54, 40))
GREEN_DARK = Ramp(base=(40, 82, 62), shadow=(28, 60, 44), light=(56, 106, 80), line=(22, 46, 34))


@dataclass(frozen=True)
class CouchColors:
    """Bottle-green velvet on dark wooden legs by default."""

    body: Ramp = field(default_factory=lambda: GREEN)  # Seat and arms.
    back: Ramp = field(default_factory=lambda: GREEN_DARK)  # The back cushions, in shade.
    outline: Color = (24, 40, 32)
    legs: Color = (92, 60, 40)


def seat(at: Spot) -> Spot:
    """Where a pet sits on a couch standing at `at`."""
    return Spot(at.x, at.y - SEAT_RISE)


def couch(img: Image.Image, at: Spot, colors: CouchColors, floor: Color, shadow: Color) -> None:
    """Draws the couch on img. `floor` is the floor's color under it: where
    the couch meets it, those pixels turn `shadow`."""
    size = img.size
    c = Canvas(*size)
    left, right = at.x - HALF_LEFT, at.x + HALF_RIGHT  # Outside of the arms.
    floor_y, top = at.y, seat(at).y
    _back(c, size, at, left, right, top, colors.back)
    _seat(c, size, at, left, right, top, floor_y, colors.body)
    _arms(c, size, at, left, right, floor_y, colors.body)
    # Base and short wooden legs.
    c.outline(colors.outline)
    for x in (left + 2, left + 13, right - 13, right - 2):
        for y in (floor_y + 1, floor_y + 2):
            c.dot(x, y, colors.legs)
            c.dot(x + 1, y, colors.legs)
    img.alpha_composite(c.img)
    # A soft shadow on the floor under the couch.
    px = img.load()
    for x in range(left + 1, right):
        if px[x, floor_y + 1][:3] == floor:
            px[x, floor_y + 1] = (*shadow, 255)


def _back(c: Canvas, size, at: Spot, left: int, right: int, top: int, ramp: Ramp) -> None:
    """Two plump back cushions, rounded at the top corners."""
    m, dm = mask(size)
    dm.rounded_rectangle((left + 5, at.y - 36, right - 5, top - 2), radius=5, fill=1)
    c.paint(m, ramp)
    for y in range(at.y - 34, top - 4):  # The seam between them, hidden behind a pet.
        c.dot(at.x, y, ramp.shadow)


def _seat(c: Canvas, size, at: Spot, left: int, right: int, top: int, floor_y: int, ramp: Ramp) -> None:
    """The top of the seat cushions, lit, and their front face."""
    m, dm = mask(size)
    dm.rectangle((left + 8, top - 4, right - 8, top), fill=1)
    c.paint(m, ramp, shade=False)
    for x in range(left + 8, right - 7):
        c.dot(x, top - 4, ramp.light)
    m, dm = mask(size)
    dm.rectangle((left + 8, top + 1, right - 8, floor_y - 1), fill=1)
    c.paint(m, ramp)
    for y in range(top + 1, floor_y - 1):  # Seam between the seat cushions.
        c.dot(at.x, y, ramp.line)
    for x in range(left + 8, right - 7):  # Piping along the front edge.
        c.dot(x, top + 1, ramp.shadow)


def _arms(c: Canvas, size, at: Spot, left: int, right: int, floor_y: int, ramp: Ramp) -> None:
    """Rolled tops over upright sides."""
    roll = at.y - 24
    for side in (-1, 1):
        outer = left if side < 0 else right
        inner = left + 10 if side < 0 else right - 10
        m, dm = mask(size)
        x_lo, x_hi = min(outer, inner), max(outer, inner)
        dm.rectangle((x_lo, roll, x_hi, floor_y - 1), fill=1)
        ellipse(dm, (x_lo + x_hi) / 2, roll, (x_hi - x_lo) / 2 + 1, 4)
        c.paint(m, ramp)
        # The roll's curl on the front, a dark crescent.
        cx = (x_lo + x_hi) / 2
        for dx, dy in ((-2, 0), (-1, 1), (0, 1), (1, 1), (2, 0), (-3, -1), (3, -1)):
            c.dot(round(cx + dx), roll + 1 + dy, ramp.shadow)
