"""Dogs on the pet rig (rig.py): the parts only a dog has.

A dog's nose and mouth (with a tongue: "blep", and a wide "grin" with the
tongue hanging out), folded "button" ears, and "sitting pretty" (the "beg"
stance: up on the hind legs, front paws held up). breed() makes a pet.Breed
with the dog's nose and mouth; a breed module adds the rest.

Ears: the corgi's tall pointed ears are pet.pointed_ears (a cat has them
too); button ears are here. The tailless butt wag is rig.py's "butt" tail.
"""

from __future__ import annotations

from daruma_pixel.pixelkit import Canvas, ellipse, mask, poly, rotate

from .rig import DARK, Breed, H, Rig, Stance, W

NOSE_SHINE = (120, 96, 92)
MOUTH = (132, 40, 48)
TONGUE = (240, 128, 140)
TONGUE_SHADE = (206, 92, 110)  # The groove down a long tongue.


def nose(c: Canvas, nx: int, ny: int) -> None:
    """A wide black nose with a shine on the left."""
    for x in range(nx - 2, nx + 3):
        for y in range(ny, ny + 2):
            c.dot(x, y, DARK)
    c.dot(nx - 1, ny, NOSE_SHINE)


def breed(**kwargs) -> Breed:
    """A pet.Breed with a dog's nose and mouth."""
    return Breed(nose=nose, mouth=mouth, **kwargs)


def mouth(c: Canvas, kind: str, x: int, y: int) -> None:
    if kind == "smile":
        for dx, dy in ((-3, 0), (-2, 1), (-1, 1), (0, 0), (1, 1), (2, 1), (3, 0)):
            c.dot(x + dx, y + dy, DARK)
    elif kind in ("open", "talk"):
        rows = 3 if kind == "open" else 2
        for dx in range(-2, 3):
            for dy in range(rows):
                c.dot(x + dx, y + dy, MOUTH)
        for dx in range(-1, 2):
            c.dot(x + dx, y + rows - 1, TONGUE)
        if kind == "open":
            c.dot(x, y + rows, TONGUE)
    elif kind == "grin":
        # A wide-open grin, corners pulled up, and a big tongue hanging out
        # over the chin: dark mouth on top, the tongue filling its lower
        # half and spilling down three more rows, a groove down the middle.
        for dx, dy in ((-4, 0), (4, 0)):
            c.dot(x + dx, y + dy, DARK)
        for dx in range(-3, 4):
            c.dot(x + dx, y + 1, MOUTH)
        for dx in range(-2, 3):
            c.dot(x + dx, y + 2, MOUTH if abs(dx) == 2 else TONGUE)
        for dy, half in ((3, 2), (4, 2), (5, 1)):
            for dx in range(-half, half + 1):
                c.dot(x + dx, y + dy, TONGUE)
        c.dot(x, y + 3, TONGUE_SHADE)
        c.dot(x, y + 4, TONGUE_SHADE)
    elif kind == "frown":
        for dx, dy in ((-3, 1), (-2, 0), (-1, 0), (0, 0), (1, 0), (2, 0), (3, 1)):
            c.dot(x + dx, y + dy + 1, DARK)
    elif kind == "o":
        for dx, dy in ((0, 0), (-1, 1), (1, 1), (0, 2)):
            c.dot(x + dx, y + dy, DARK)
    elif kind == "flat":
        for dx in range(-2, 3):
            c.dot(x + dx, y + 1, DARK)
    elif kind == "blep":
        for dx in range(-2, 3):
            c.dot(x + dx, y + 1, DARK)
        c.dot(x + 1, y + 2, TONGUE)
        c.dot(x + 1, y + 3, TONGUE)


def button_ears(c: Canvas, r: Rig) -> None:
    """Folded "button" ears: two small flaps at the top corners of the skull,
    with skull between them. Each rises a little from the head, folds over
    at a crease, and hangs forward with the tip toward the outer corner of
    the eye.

    `ears` and the twitches swing each flap around the outer end of its
    fold, so the ears move on their own: negative lifts the tip (alert,
    perked), positive lets it fall out and back (sad, scared, sleepy).
    """
    coat, p, head_pt = r.breed.coat, r.pose, r.hp
    ramp = coat.ear or coat.fur
    hw, hh = r.breed.head_r
    for side, twitch in ((-1, p.ear_left), (1, p.ear_right)):
        tilt = p.ears + twitch
        fold_in = head_pt(side * hw * 0.38, -hh + 0.5)
        fold_out = head_pt(side * (hw + 1.5), -hh + 3)
        # The rise above the fold: the ear's root before it folds over.
        crown, d = mask((W, H))
        poly(d, [fold_in, head_pt(side * hw * 0.62, -hh - 2), head_pt(side * hw * 0.92, -hh - 1), fold_out])
        c.paint(crown, ramp)
        # The flap: a triangle hanging forward from the fold, tip toward the eye.
        swing = -side * tilt * (1.6 if tilt < 0 else 0.8)
        tip = head_pt(side * hw * 0.8, -hh + 8.5)
        flap, d = mask((W, H))
        poly(d, rotate([fold_in, fold_out, tip], fold_out, swing))
        c.paint(flap, ramp)
        c.line([fold_in, fold_out], ramp.line)  # The fold.


def _begging_paws(c: Canvas, r: Rig) -> None:
    """Sitting pretty: forelegs bent at the elbow, paws curled and held up
    in front of the chest. The hind feet stay on the floor."""
    white = r.breed.coat.white
    cx, y = r.cx, r.chest_y
    arms, d = mask((W, H))
    for side in (-1, 1):
        # Upper leg from the shoulder down the side of the chest to the elbow,
        # then the forearm folds back up and in to the paw.
        poly(d, [(cx + side * 6, y - 7), (cx + side * 11, y - 5), (cx + side * 10, y + 4), (cx + side * 6, y + 3)])
        poly(d, [(cx + side * 7, y + 3), (cx + side * 11, y + 2), (cx + side * 8, y - 2), (cx + side * 4, y - 1)])
        ellipse(d, cx + side * 5, y - 1, 3, 2.5)
    c.paint(arms, white)
    for side in (-1, 1):  # Toe lines on the curled paws, pointing down.
        c.dot(cx + side * 5 - 1, y + 1, white.shadow)
        c.dot(cx + side * 5 + 1, y + 1, white.shadow)


SIT_PRETTY = Stance(rise=8, front=_begging_paws)  # Pose(stance="beg") on a breed with stances={"beg": SIT_PRETTY}.
