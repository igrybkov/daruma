"""Front-facing Pembroke corgi: a dog breed on the pet rig (rig.py, dog.py).

Red and white: red head with tall erect ears and pink insides, a white
blaze down to a white muzzle, a white chest and legs, red sides and deeper
red haunches. No tail, so it wags its whole rear end (rig.py, "butt").

The persona (its room and layers) is this package's __init__.py; its moods are
moods.py.
"""

from __future__ import annotations

from PIL import Image, ImageDraw

from daruma_pixel.pixelkit import Canvas, Ramp, ellipse, mask, poly
from daruma_shapes.pets import dog
from daruma_shapes.pets.rig import Coat, H, Pose, Rig, Stance, W, with_  # noqa: F401  (W, H, Pose, with_: the corgi's API)
from daruma_shapes.pets.rig import render as _render

OUTLINE = (58, 32, 24)
FUR = Ramp(base=(222, 136, 58), shadow=(182, 96, 40), light=(242, 170, 92), line=(150, 74, 32))
FUR_DEEP = Ramp(base=(196, 112, 46), shadow=(160, 82, 34), line=(140, 68, 30))  # Haunches behind the body.
WHITE = Ramp(base=(250, 242, 228), shadow=(214, 198, 180), light=(255, 255, 250), line=(196, 178, 160))
PINK = Ramp(base=(236, 150, 150), shadow=(206, 116, 120))
# A lifted foreleg: white, with a darker contour so it reads over the white chest and muzzle.
LIFTED = Ramp(base=WHITE.base, shadow=WHITE.shadow, light=WHITE.light, line=(164, 116, 92))

# Paw up: the left foreleg (on the viewer's right) lifted to the face, the
# other planted. The stance names where the paw is, from the middle of the
# body and the floor: at the mouth to lick it, at the side of the muzzle to
# rub the nose. The paw stays put while the head moves against it.
PAWS = {"lick": (3, -31), "scratch": (8, -37)}


def _planted_leg(d: ImageDraw.ImageDraw, r: Rig) -> None:
    """The planted foreleg, part of the chest's shape so it has no seam."""
    x0, top = r.cx - r.breed.leg_dx, r.chest_y + 1
    poly(d, [(x0 - 3, top), (x0 + 3, top), (x0 + 3, r.floor - 2), (x0 - 3, r.floor - 2)])
    ellipse(d, x0, r.floor - 2, 4, 2.5)


def _toes(c: Canvas, r: Rig) -> None:
    """Toe lines on the planted paw, and a soft shadow up its inner side so
    it reads as a leg. The lifted leg goes over the face (_lifted_leg)."""
    x0, shadow = r.cx - r.breed.leg_dx, r.breed.coat.white.shadow
    c.dot(x0 - 1, r.floor - 2, shadow)
    c.dot(x0 + 1, r.floor - 2, shadow)
    for y in range(r.floor - 9, r.floor - 1):
        c.dot(x0 + 4, y, shadow)


def _lifted_leg(c: Canvas, r: Rig) -> None:
    """The lifted foreleg, drawn after the head so the paw stays joined to
    it: the elbow at the side of the chest, the forearm folded up to the
    face, and the paw showing its pink pads. Nose and mouth draw on top."""
    if r.pose.stance not in PAWS:
        return
    ex, ey = r.cx + 8, r.chest_y - 3  # The elbow, on the chest.
    px, py = r.cx + PAWS[r.pose.stance][0], r.floor + PAWS[r.pose.stance][1]
    lifted, d = mask((W, H))
    ellipse(d, ex, ey, 3, 3)
    poly(d, [(ex - 3, ey), (ex + 2, ey + 2), (px + 3, py + 1), (px - 2, py)])
    ellipse(d, px, py, 4, 3.5)
    c.paint(lifted, LIFTED)
    pad = r.breed.coat.pink.base
    for dx, dy in ((-1, 1), (0, 1), (1, 1), (-1, 2), (0, 2), (1, 2), (-2, -1), (0, -2), (2, -1)):
        c.dot(px + dx, py + dy, pad)


PAW_UP = Stance(rise=0, front=_toes, chest=_planted_leg)

CORGI = dog.breed(
    coat=Coat(outline=OUTLINE, fur=FUR, body=FUR, deep=FUR_DEEP, white=WHITE, pink=PINK),
    stances=dict.fromkeys(PAWS, PAW_UP),
    head_marks=_lifted_leg,
)


def render(p: Pose) -> Image.Image:
    return _render(CORGI, p)
