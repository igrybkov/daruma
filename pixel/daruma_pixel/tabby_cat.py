"""Tabby cat: a cat on the pet rig (pet.py, cat.py), and its persona module.

A brown-grey mackerel tabby: dark stripes down the flanks and round the
legs, an "M" on the forehead, stripes back from the eyes across the
cheeks, a pale muzzle and chin, a pink nose, big round yellow-green eyes
with a dark rim, tall pointed ears and white whiskers. The tail is ringed,
with a dark tip.

Calm and a little proud. At rest it sits with its tail curled round its
paws, the tip swaying, and now and then gives a slow blink or flicks an
ear. Happy: tail straight up with the tip hooked over. Petted: eyes shut,
purring, kneading. Celebrate: a play bow, a wiggle and a pounce. Sad: ears
out to the side, tail low. Scared: up on stiff legs, fur and tail puffed.
Asleep: curled up in a ball. While you focus, it watches a laser dot.

Its scene is a portrait studio (studio.py): a mottled brown backdrop on a
stand under a soft spotlight, a sage wall with a window on the side, cat
grass on the sill (the progress prop) and a velvet posing drape whose color
follows the weekday.

This module has the same names as every persona module (see personas.py).
"""

from __future__ import annotations

import math

from . import cat, pet
from .cat import Cat, CatPose, Look
from .pet import Breed, Coat, Rig, with_
from .pixelkit import Canvas, Ramp, ellipse, intersect, mask
from .studio import Studio

OUTLINE = (46, 34, 28)
FUR = Ramp(base=(150, 124, 96), shadow=(118, 94, 72), light=(176, 150, 118), line=(94, 72, 54))
BODY = Ramp(base=(144, 118, 92), shadow=(112, 90, 70), light=(170, 144, 114), line=(90, 70, 52))
DEEP = Ramp(base=(128, 104, 80), shadow=(100, 80, 62), light=(150, 124, 96), line=(84, 64, 48))
LEGS = Ramp(base=(160, 134, 104), shadow=(126, 102, 80), light=(184, 160, 128))  # No contour: legs and chest are one.
CREAM = Ramp(base=(226, 210, 184), shadow=(200, 182, 156), light=(240, 230, 210))  # Muzzle, chin, chest.
BIB = Ramp(base=(204, 184, 154), shadow=(180, 160, 132))  # The pale chest.
WARM = (176, 128, 92)  # The rufous bridge of the nose.
PINK = Ramp(base=(222, 160, 146), shadow=(196, 132, 120))
STRIPE = (60, 42, 32)

LOOK = Look(
    stripe=STRIPE,
    iris=Ramp(base=(212, 190, 76), shadow=(172, 154, 56), light=(232, 214, 120)),
    pupil=(20, 16, 14),
    rim=(40, 30, 24),
    nose=Ramp(base=(204, 116, 100), shadow=(168, 86, 72), light=(228, 150, 132)),
    mouth=(84, 60, 48),
    inside=(120, 40, 50),
    tongue=(236, 130, 140),
    whisker=(250, 248, 240),
    tail=Ramp(base=(146, 122, 98), shadow=(116, 94, 74), light=(170, 146, 118)),
    ring=(92, 70, 52),
)


def _stripe(c: Canvas, pts, color=STRIPE) -> None:
    for x, y in pts:
        c.dot(round(x), round(y), color)


def _head_marks(c: Canvas, r: Rig) -> None:
    """The pale muzzle and chin, the warm nose bridge, the "M" on the
    forehead, stripes back over the crown and across the cheeks, and the
    chest's pale bib with its necklace stripes."""
    hp = r.hp
    # Muzzle and chin.
    m, d = mask((pet.W, pet.H))
    for side in (-1, 1):
        x, y = hp(side * 2.5, 5)
        ellipse(d, x, y, 3, 2.5)
    x, y = hp(0, 8)
    ellipse(d, x, y, 2.5, 2)
    c.paint(m, CREAM, shade=False)
    # The bridge of the nose, between the eyes.
    for y in (0, 1, 2):
        x_, y_ = hp(0, y)
        c.dot(round(x_), round(y_), WARM)
    # The M: three short bars over the brow, joined at the bottom.
    # Lines run on up over the crown, as a tabby's do.
    _stripe(c, [hp(0, -11), hp(0, -10), hp(0, -8), hp(0, -7), hp(0, -6)])
    for side in (-1, 1):
        _stripe(c, [hp(side * 3, -11), hp(side * 3, -10), hp(side * 3, -9), hp(side * 2, -7), hp(side * 1, -6)])
        _stripe(c, [hp(side * 6, -9), hp(side * 6, -8), hp(side * 5, -7), hp(side * 4, -5)])
    # Cheek stripes: two from the outer corner of each eye, curving back.
    for side in (-1, 1):
        _stripe(c, [hp(side * 9, 0), hp(side * 10, 0), hp(side * 11, 1), hp(side * 12, 1)])
        _stripe(c, [hp(side * 8, 3), hp(side * 9, 3), hp(side * 10, 4), hp(side * 11, 5)])


def _body_marks(c: Canvas, r: Rig) -> None:
    """Mackerel stripes down each flank, curving with the body."""
    b = r.breed
    body, d = mask((pet.W, pet.H))
    ellipse(d, r.cx + r.sway, r.chest_y, *b.body_r)
    marks, d = mask((pet.W, pet.H))
    for side in (-1, 1):
        for k in range(3):
            x0 = r.cx + side * (8 + k * 3)
            for y in range(r.chest_y - 10 + k * 2, r.chest_y + 12):
                bend = round(((y - r.chest_y) / 12) ** 2 * 2) * side
                d.point((x0 + bend, y), fill=1)
    px = intersect(marks, body).load()
    for y in range(pet.H):
        for x in range(pet.W):
            if px[x, y]:
                c.dot(x, y, STRIPE)
    if r.pose.stance == "stiff":  # Fur on end: tufts stick out round the shoulders and sides.
        rx, ry = b.body_r
        for a in range(-150, -20, 13):
            t = math.radians(a)
            for k in (1, 2, 3):
                c.dot(
                    round(r.cx + r.sway + (rx + k) * math.cos(t)), round(r.chest_y + (ry + k) * math.sin(t)), BODY.base
                )


def _rear_marks(c: Canvas, r: Rig) -> None:
    """Arcs round each haunch; in a play bow, the raised rump behind."""
    b = r.breed
    if r.pose.stance == "bow":
        wiggle = round(r.pose.wag)
        rump, d = mask((pet.W, pet.H))
        ellipse(d, r.cx + wiggle, r.hip_y - 5, 19, 6)
        c.paint(rump, DEEP)
        for dx in (-7, -3, 3, 7):
            for dy in (-4, -3, -2):
                c.dot(r.cx + wiggle + dx + (dy + 3) * (1 if dx > 0 else -1), r.hip_y - 6 + dy, STRIPE)
    for side in (-1, 1):
        hx, hy = r.cx + side * b.haunch_dx, r.hip_y + 9
        for rad in (4, 7):
            for a in range(200, 341, 12):
                x = hx + side * rad * math.cos(math.radians(a))
                y = hy + rad * math.sin(math.radians(a)) * 0.9
                c.dot(round(x), round(y), STRIPE)


def _ears_and_chest(c: Canvas, r: Rig) -> None:
    """Drawn after the front legs: leg rings and the chest, then the ears."""
    cx, floor, top = r.cx, r.floor, r.chest_y + 1
    if r.pose.stance in ("sit", "knead_l", "knead_r", "stiff"):
        for side in (-1, 1):  # Rings round the front legs.
            x0 = cx + side * (r.breed.leg_dx + (2 if r.pose.stance == "stiff" else 0))
            for y in range(top + 4, floor - 4, 3):
                for dx in (-1, 0, 1):
                    c.dot(x0 + dx, y, STRIPE)
    if r.pose.stance not in ("loaf", "curl"):  # The pale bib, with a necklace stripe.
        m, d = mask((pet.W, pet.H))
        ellipse(d, cx + r.sway, r.chest_y - 7, 4, 5)
        c.paint(m, BIB, shade=False)
    _EARS(c, r)


_EARS = cat.ears_fn(LOOK)

BREED = Breed(
    coat=Coat(outline=OUTLINE, fur=FUR, body=BODY, deep=DEEP, white=LEGS, pink=PINK),
    nose=cat.nose_fn(LOOK),
    mouth=cat.mouth_fn(LOOK),
    ears_behind=_ears_and_chest,
    tail="cat",  # Drawn by cat.py, not the rig.
    stances=cat.stance_hooks(),
    leg=2,
    body_r=(13, 14),
    bib_r=(8, 12),
    leg_dx=4,
    haunch_dx=10,
    haunch_r=8,
    foot_dx=13,
    head_r=(14, 11),
    cheek_at=(10, 4),
    cheek_r=(5, 4),
    blaze=((0, 0), (0, 0), (0, 0)),
    muzzle_at=(0, 6),
    muzzle_r=(0.1, 0.1),
    nose_at=(0, 3),
    eye_at=(6, -1),
    head_marks=_head_marks,
    body_marks=_body_marks,
    rear_marks=_rear_marks,
)


# Per-stance body changes: a loaf is wide and low, a curl a wide ball, the
# scared cat up on stiff legs with its fur puffed out.
CAT = Cat(
    BREED,
    LOOK,
    shapes={
        "stiff": {"leg": 6, "body_r": (15, 15), "haunch_r": 8.5, "bib_r": (9, 13)},
        "loaf": {"body_r": (17, 10), "bib_r": (9, 8), "haunch_dx": 9, "foot_dx": 11},
        "curl": {"body_r": (20, 10), "bib_r": (0.1, 0.1), "haunch_dx": 12, "haunch_r": 9, "foot_dx": 14},
        "bow": {"body_r": (15, 9), "bib_r": (8, 7)},
        # Kneading: the chest stops short of the floor, so a raised paw shows.
        "knead_l": {"bib_r": (8, 8)},
        "knead_r": {"bib_r": (8, 8)},
    },
)
STUDIO = Studio()
BACKGROUND = 0x281C16  # The backdrop's darkest brown, for any margin round the scene.

# --- Layers (see personas.py) --------------------------------------------------------

WINDOW = STUDIO.window
globals().update(STUDIO.layers())  # plant, PLANT_STAGES, DEFAULT_STAGE, the drape's weekday colors


def foreground(pose: CatPose):
    return CAT.render(pose)


def background():
    return STUDIO.background()


def scene(pose: CatPose, plant_stage: int | None = None, wilted: bool = False):
    """The full picture: studio, cat grass (at DEFAULT_STAGE unless given), cat."""
    img = STUDIO.image()
    img.alpha_composite(plant(DEFAULT_STAGE if plant_stage is None else plant_stage, wilted))  # noqa: F821
    img.alpha_composite(CAT.render(pose))
    return img


# --- Moods and animations -------------------------------------------------------

NEUTRAL = CatPose(ears=-2)  # Sitting tall, tail curled round the paws.
HAPPY = CatPose(eyes="happy", mouth="smile", ears=-5, tail_shape="up")
LOVED = CatPose(eyes="happy", mouth="smile", blush=True, ears=-4, tail_shape="up", extras=("hearts",))
SAD = CatPose(eyes="sad", mouth="frown", ears=48, head_dy=2, tail_shape="low", extras=("tear",))
SCARED = CatPose(eyes="wide", mouth="o", ears=58, stance="stiff", tail_shape="puff", extras=("sweat",))
LOAF = CatPose(eyes="half", mouth="flat", ears=8, stance="loaf", head_dy=9)
SLEEPING = CatPose(
    eyes="blink", mouth="flat", ears=20, stance="curl", head_dy=11, tilt=-8, tail_shape="wrap", extras=("zzz",)
)
LISTENING = CatPose(eyes="open", mouth="flat", ears=-10, ear_left=-6, tilt=10)
THINKING = CatPose(eyes="up", mouth="flat", tilt=-8, extras=("dots",))
TALKING = CatPose(eyes="happy", mouth="talk", ears=-3)
PURR = CatPose(eyes="happy", mouth="smile", blush=True, ears=12, tilt=-6, tail_shape="up")
BOW = CatPose(eyes="slit", mouth="smile", ears=-8, stance="bow", head_dy=6, tail_shape="bow")
PROUD = CatPose(eyes="happy", mouth="mew", ears=-6, tail_shape="up", extras=("sparkle",))


def watch(dot: int, **changes) -> CatPose:
    """Watching the laser dot at `dot`: eyes down on it, the head turned a little."""
    look = -1 if dot < -4 else 1 if dot > 4 else 0
    return CatPose(eyes="down", pupils=look, mouth="flat", ears=-6, laser=dot, head_dx=look, tilt=-4 * look, **changes)


def sway(base: CatPose, side: int, ms: int = 260) -> list[tuple[CatPose, int]]:
    """One slow swing of the tail tip to one side and back."""
    return [(with_(base, wag=0.5 * side), ms), (with_(base, wag=1.0 * side), ms), (with_(base, wag=0.5 * side), ms)]


def quiver(base: CatPose, times: int, ms: int = 110) -> list[tuple[CatPose, int]]:
    """A happy tail's quick shiver."""
    return [(with_(base, wag=0.35 * (1 if i % 2 else -1)), ms) for i in range(times * 2)]


ANIMATIONS: dict[str, list[tuple[CatPose, int]]] = {
    # Calm idle: the tail tip sways, a breath, a slow blink, an ear flick.
    "Neutral": [
        (NEUTRAL, 1400),
        *sway(NEUTRAL, 1),
        (with_(NEUTRAL, breath=1), 1200),
        (with_(NEUTRAL, eyes="half"), 200),
        (with_(NEUTRAL, eyes="blink"), 450),
        (with_(NEUTRAL, eyes="half"), 200),
        (NEUTRAL, 1400),
        (with_(NEUTRAL, ear_right=16), 130),
        (NEUTRAL, 130),
        (with_(NEUTRAL, ear_right=16), 130),
        (with_(NEUTRAL, breath=1), 1400),
        *sway(NEUTRAL, -1),
        (NEUTRAL, 1200),
    ],
    # Happy: tail straight up, hooked at the tip, with a shiver.
    "Happy": [(HAPPY, 700), *quiver(HAPPY, 4), (HAPPY, 1800)],
    "Loved": [(LOVED, 600), *quiver(LOVED, 4), (with_(LOVED, breath=1), 600)],
    "Sad": [(SAD, 1400), (with_(SAD, breath=1), 1400)],
    # Scared: up on stiff legs, fur and tail puffed, trembling.
    "Scared": [(SCARED, 120), (with_(SCARED, head_dx=1), 120), (SCARED, 120), (with_(SCARED, head_dx=-1), 120)],
    # Sleepy: a loaf, paws tucked under, eyes drooping shut and opening.
    "Sleepy": [(LOAF, 1400), (with_(LOAF, eyes="blink"), 1000), (LOAF, 1200), (with_(LOAF, breath=1), 1200)],
    # Asleep: curled up in a ball, tail round the front, breathing.
    "Sleeping": [(SLEEPING, 1500), (with_(SLEEPING, breath=1), 1500)],
    "listening": [(LISTENING, 1000)],
    "thinking": [(THINKING, 1000)],
    "talking": [(TALKING, 1000)],
    # Focus: watches a laser dot dart about the drape on either side of it,
    # the tail tip twitching when it stops. The dot keeps to the drape
    # beside the paws, clear of the screen's bottom corners and info line.
    # Calm, since it loops for minutes.
    "Focus": [
        (watch(22), 2200),
        (watch(22, wag=0.6), 150),
        (watch(22, wag=1.0), 150),
        (watch(22), 1400),
        (watch(26), 900),
        (watch(-24), 2000),
        (watch(-24, wag=0.8), 150),
        (watch(-24), 1600),
        (watch(-24, ear_left=-8), 150),
        (watch(-21), 900),
        (watch(24), 2200),
        (watch(24, wag=1.0), 150),
        (watch(24, breath=1), 1800),
        (watch(20), 900),
    ],
    # Petted: eyes shut, purring, kneading with one front paw, then the other.
    "Petted": [
        (with_(PURR, stance="knead_l" if i % 2 == 0 else "knead_r", wag=0.3 if i % 2 else -0.3), 250) for i in range(8)
    ],
    # Celebrate: a play bow with a wiggle, a pounce, then sits up proud.
    "Celebrate": [
        (BOW, 300),
        (with_(BOW, wag=1.0), 150),
        (with_(BOW, wag=-1.0), 150),
        (with_(BOW, wag=1.0), 150),
        (with_(BOW, wag=-1.0), 150),
        (with_(PROUD, hop=2, eyes="wide", extras=()), 120),
        (with_(PROUD, hop=4, eyes="wide", extras=()), 160),
        (with_(PROUD, hop=2, eyes="wide", extras=()), 120),
        (PROUD, 500),
        *quiver(PROUD, 3),
        (with_(PROUD, mouth="smile"), 540),
    ],
}

# Single frames shown when the hub blinks or winks, per animation.
BLINKS: dict[str, CatPose] = {
    "Neutral": with_(NEUTRAL, eyes="blink"),
    "Sad": with_(SAD, eyes="blink"),
    "Focus": with_(watch(22), eyes="blink"),
}
WINKS: dict[str, CatPose] = {
    "Neutral": with_(NEUTRAL, eyes="wink"),
    "Happy": with_(HAPPY, eyes="wink"),
}
