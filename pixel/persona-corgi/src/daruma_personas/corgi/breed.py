"""Front-facing Pembroke corgi: a dog breed on the pet rig (rig.py, dog.py).

Red and white: red head with tall erect ears and pink insides, a white
blaze down to a white muzzle, a white chest and legs, red sides and deeper
red haunches. No tail, so it wags its whole rear end (rig.py, "butt").

The persona (its room and layers) is this package's __init__.py; its moods are
moods.py.
"""

from __future__ import annotations

from PIL import Image

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


def _paw_up_legs(c: Canvas, r: Rig) -> None:
    """The planted foreleg, and the lifted one from the shoulder up to the
    paw (its tip is drawn over the face by _paw_on_face)."""
    white = r.breed.coat.white
    cx, floor, top = r.cx, r.floor, r.chest_y + 1
    px, py = cx + PAWS[r.pose.stance][0], floor + PAWS[r.pose.stance][1]
    planted, d = mask((W, H))
    x0 = cx - r.breed.leg_dx
    poly(d, [(x0 - 3, top), (x0 + 3, top), (x0 + 3, floor - 2), (x0 - 3, floor - 2)])
    ellipse(d, x0, floor - 2, 4, 2.5)
    c.paint(planted, white)
    c.dot(x0 - 1, floor - 2, white.shadow)  # Toe lines.
    c.dot(x0 + 1, floor - 2, white.shadow)
    # The elbow sticks out to the side; the forearm folds up across the chest.
    lifted, d = mask((W, H))
    poly(d, [(cx + 8, top - 10), (cx + 14, top - 8), (cx + 18, top + 1), (cx + 13, top + 3)])
    ellipse(d, cx + 15, top + 1, 3, 2.5)
    poly(d, [(cx + 12, top + 2), (cx + 17, top - 1), (px + 3, py + 1), (px - 2, py)])
    c.paint(lifted, LIFTED)


def _paw_on_face(c: Canvas, r: Rig) -> None:
    """The lifted paw over the face, its pink pads toward us; nose and mouth draw on top."""
    if r.pose.stance not in PAWS:
        return
    px, py = r.cx + PAWS[r.pose.stance][0], r.floor + PAWS[r.pose.stance][1]
    paw, d = mask((W, H))
    ellipse(d, px, py, 4, 3.5)
    c.paint(paw, LIFTED)
    pad = r.breed.coat.pink.base
    for dx, dy in ((-1, 1), (0, 1), (1, 1), (-1, 2), (0, 2), (1, 2), (-2, -1), (0, -2), (2, -1)):
        c.dot(px + dx, py + dy, pad)


PAW_UP = Stance(rise=0, front=_paw_up_legs)

CORGI = dog.breed(
    coat=Coat(outline=OUTLINE, fur=FUR, body=FUR, deep=FUR_DEEP, white=WHITE, pink=PINK),
    stances=dict.fromkeys(PAWS, PAW_UP),
    head_marks=_paw_on_face,
)


def render(p: Pose) -> Image.Image:
    return _render(CORGI, p)
