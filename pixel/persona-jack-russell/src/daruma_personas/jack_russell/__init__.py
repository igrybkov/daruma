"""Jack Russell terrier: a dog breed on the pet rig (rig.py, dog.py), and its persona module.

Small, compact and short-legged, mostly white. A warm caramel head with a
white blaze from the forehead down the middle to a white muzzle; black
nose, dark brown eyes, white chin and chest. Folded "button" ears in the
same caramel, flopping forward. One caramel patch on the left flank and a
brown saddle on the haunch where the tail starts. The tail is carried up:
brown at the root, caramel, then a cream tip.

Alert and eager: it sits up straight on its couch and looks at you. The
tail is its signal: fast wags when happy, petted or celebrating, the odd wag
at rest, held low when sad. To celebrate it "sits pretty": up on its hind
legs, front paws held up, mouth open in a grin with a big tongue out. It
sleeps curled up on the seat (curled(), its own drawing: the rig only sits).

Its scene is its own living room (living_room.py): a green velvet couch it
sits on, an arched window, a hanging spider plant and a weekday throw.

This module is the persona: it has the names every persona module has
(see personas.Spec).
"""

from __future__ import annotations

from PIL import Image

from daruma_pixel import effects
from daruma_pixel.personas import Spec
from daruma_pixel.pixelkit import Canvas, Ramp, ellipse, intersect, mask, poly, rotate
from daruma_shapes.pets import dog, rig
from daruma_shapes.pets.rig import Coat, Pet, Pose, Rig, wag_cycle, with_
from daruma_shapes.plants.spider_plant import SPIDER_PLANT
from daruma_shapes.rooms.living_room import LivingRoom

OUTLINE = (52, 36, 30)
TAN = Ramp(base=(228, 164, 98), shadow=(194, 128, 70), light=(242, 192, 134), line=(156, 100, 56))
EAR = Ramp(
    base=(206, 138, 76), shadow=(170, 108, 56), light=(222, 160, 98), line=(120, 74, 38)
)  # Flaps, a shade deeper.
SADDLE = Ramp(base=(160, 98, 54), shadow=(128, 76, 42), light=(186, 124, 74), line=(110, 64, 36))
WHITE = Ramp(base=(250, 248, 242), shadow=(214, 208, 198), light=(255, 255, 255), line=(166, 156, 144))
CHEST = Ramp(base=(250, 248, 242), shadow=(222, 216, 206), light=(255, 255, 255))  # No contour on a white body.
HAUNCH = Ramp(base=(236, 232, 224), shadow=(204, 198, 188), line=(182, 174, 162))  # White, a shade back.
CREAM = Ramp(base=(246, 232, 204), shadow=(222, 204, 170))  # The tail tip.
PINK = Ramp(base=(236, 150, 150), shadow=(206, 116, 120))
EYE = (52, 30, 20)  # Dark brown.


def _haunch_saddle(c: Canvas, r: Rig) -> None:
    """A brown saddle on the right haunch, where the tail starts."""
    b = r.breed
    haunch, d = mask((rig.W, rig.H))
    ellipse(d, r.cx + b.haunch_dx, r.hip_y + 9, b.haunch_r, b.haunch_r)
    patch, d = mask((rig.W, rig.H))
    ellipse(d, r.cx + b.haunch_dx + 3, r.hip_y + 4, 6, 5)
    c.paint(intersect(patch, haunch), SADDLE)


def _flank_patch(c: Canvas, r: Rig) -> None:
    """One caramel patch on the left flank."""
    b = r.breed
    body, d = mask((rig.W, rig.H))
    ellipse(d, r.cx + r.sway, r.chest_y, *b.body_r)
    left, d = mask((rig.W, rig.H))
    ellipse(d, r.cx - 13, r.chest_y + 1, 5, 7)
    c.paint(intersect(left, body), TAN)


def _stop(c: Canvas, r: Rig) -> None:
    """The stop: a shade where the muzzle meets the skull, each side of the blaze."""
    for side in (-1, 1):
        for x, y in ((side * 3.5, 0), (side * 4, 1)):
            px, py = r.hp(x, y)
            c.dot(round(px), round(py), TAN.shadow)


BREED = dog.breed(
    coat=Coat(outline=OUTLINE, fur=TAN, body=WHITE, deep=HAUNCH, white=WHITE, pink=PINK, eye=EYE, bib=CHEST, ear=EAR),
    ears_behind=None,
    ears_front=dog.button_ears,
    stances={"beg": dog.SIT_PRETTY},
    tail="carried",
    leg=2,
    body_r=(13, 14),
    bib_r=(9, 12),
    leg_dx=5,
    leg_gap=False,  # No pale gap between the front legs on its white chest.
    haunch_dx=10,
    haunch_r=7.5,
    foot_dx=13,
    # A wedge: a flat-topped skull narrowing through caramel cheeks to a long,
    # narrow white muzzle, with the nose near its end.
    head_r=(11, 10),
    cheek_at=(6, 4),
    cheek_r=(5, 5),
    blaze=((-1, -9), (1, -9), (2.5, 1), (-2.5, 1)),
    muzzle_at=(0, 7),
    muzzle_r=(4.5, 5),
    nose_at=(0, 5),
    eye_at=(5, -1),
    head_marks=_stop,
    rear_marks=_haunch_saddle,
    body_marks=_flank_patch,
    tail_base=(14, 4),
    tail_len=16,
    tail_colors=(SADDLE, TAN, CREAM),
    tail_band=(5, 11),
)

# Its own living room (living_room.py): it sits on a green velvet couch,
# under a hanging spider plant, by an arched window.
ROOM = LivingRoom()
BACKGROUND = 0x76503A  # For any margin round the room.


def curled(p: Pose) -> Image.Image:
    """Asleep, curled up on the seat: lying on its side, the rear and its
    saddle to the right, the head resting on its front paws at the left end,
    the tail wrapped along the front toward its nose.

    Uses the pose's eyes (blink: asleep), ears (they flop out as it relaxes),
    breath (the body rises a pixel) and extras (zzz above the head).
    """
    c = Canvas(rig.W, rig.H)
    seat = ROOM.spots["seat"]
    sx, floor = seat.x, seat.y  # Drawn round the middle of the seat.
    b = p.breath
    # The body, a long low oval, and the rear haunch on its right end.
    body, d = mask((rig.W, rig.H))
    ellipse(d, sx + 4, floor - 8.5 - b / 2, 16, 6.5 + b / 2)
    c.paint(body, WHITE)
    rear, d = mask((rig.W, rig.H))
    ellipse(d, sx + 14, floor - 10 - b / 2, 8.5, 7.5)
    c.paint(rear, HAUNCH)
    saddle, d = mask((rig.W, rig.H))
    ellipse(d, sx + 17, floor - 14 - b, 6, 4.5)
    c.paint(intersect(saddle, rear), SADDLE)
    flank, d = mask((rig.W, rig.H))
    ellipse(d, sx + 4, floor - 8 - b / 2, 4.5, 3)
    c.paint(intersect(flank, body), TAN)
    # The tail: from under the rear, along the front of the body, tip toward the head.
    pts = [
        (sx + 21, floor - 5),
        (sx + 17, floor - 2.5),
        (sx + 11, floor - 1.5),
        (sx + 4, floor - 1.5),
        (sx - 2, floor - 2.5),
    ]
    bands = ((SADDLE, 0, 1), (TAN, 1, 3), (CREAM, 3, 4))
    for ramp, lo, hi in bands:
        m, d = mask((rig.W, rig.H))
        for i in range(lo, hi + 1):
            x, y = pts[i]
            r = 2.0 - 1.1 * i / (len(pts) - 1)
            ellipse(d, x, y, r, r)
        for i in range(lo, hi):
            (x0, y0), (x1, y1) = pts[i], pts[i + 1]
            for t in (0.25, 0.5, 0.75):
                r = 2.0 - 1.1 * (i + t) / (len(pts) - 1)
                ellipse(d, x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, r, r)
        c.paint(m, ramp)
    # Front paws, side by side under the chin.
    paws, d = mask((rig.W, rig.H))
    ellipse(d, sx - 18, floor - 3, 3.5, 2.2)
    ellipse(d, sx - 11, floor - 2.5, 3.5, 2.2)
    c.paint(paws, WHITE)
    c.dot(sx - 19, floor - 3, WHITE.shadow)
    c.dot(sx - 12, floor - 2, WHITE.shadow)
    # The head, resting on the paws, tipped a little toward the rear.
    hx, hy, tilt = sx - 14, floor - 10, 8

    def hp(x: float, y: float) -> tuple[float, float]:
        return rotate([(hx + x, hy + y)], (hx, hy + 4), tilt)[0]

    head, d = mask((rig.W, rig.H))
    ellipse(d, *hp(0, 0), 9.5, 7.5)
    for side in (-1, 1):
        ellipse(d, *hp(side * 5, 3), 4.5, 4)
    c.paint(head, TAN)
    blaze, d = mask((rig.W, rig.H))
    poly(d, [hp(-1, -7), hp(1, -7), hp(2.5, 1), hp(-2.5, 1)])
    ellipse(d, *hp(0, 4.5), 4.5, 3.5)
    c.paint(blaze, WHITE)
    for side in (-1, 1):  # Button ears, flopped out to the sides.
        flap, d = mask((rig.W, rig.H))
        fold_in, fold_out = hp(side * 4, -6.5), hp(side * 9.5, -3)
        drop = 1 + max(0.0, p.ears) / 10
        poly(d, [fold_in, fold_out, hp(side * 11, 2 + drop), hp(side * 7.5, 0)])
        c.paint(flap, EAR)
        c.line([fold_in, fold_out], EAR.line)
    nx, ny = (round(v) for v in hp(0, 3))
    dog.nose(c, nx, ny)
    for side in (-1, 1):  # Closed eyes: soft arcs.
        ex, ey = (round(v) for v in hp(side * 4.5, -1))
        kind = p.eyes if p.eyes in ("blink", "half") else "blink"
        for dx in (-1, 0, 1):
            c.dot(ex + dx, ey + (1 if kind == "blink" else 0), EYE if kind == "half" or dx == 0 else rig.DARK)
    c.outline(OUTLINE)
    effects.extras(c, p.extras, sx - 23, floor + 20)
    return c.img


class CouchPet(Pet):
    """The pet rig on the couch, plus its own pose: curled up asleep (stance "curl")."""

    def render(self, pose: Pose) -> Image.Image:
        return curled(pose) if pose.stance == "curl" else super().render(pose)


_pet = CouchPet(BREED, ROOM, seat="seat", plant=SPIDER_PLANT, plant_spot="hook")
# Where focus's prop stands (tests/test_props.py): the ball in its mouth.
PROPS = {"focus": [(49, 30, 58, 39)]}
background, foreground, scene = _pet.background, _pet.foreground, _pet.scene
WINDOW = ROOM.window
_extra = _pet.layers()
plant, PLANT_STAGES, DEFAULT_STAGE = _extra["plant"], _extra["PLANT_STAGES"], _extra["DEFAULT_STAGE"]
RUG_COLORS, RUG_BY_WEEKDAY, RUG_BOX = _extra["RUG_COLORS"], _extra["RUG_BY_WEEKDAY"], _extra["RUG_BOX"]

# --- Moods and animations -------------------------------------------------------

NEUTRAL = Pose(ears=-3, head_dy=-1)  # Alert: sits up, ears forward, eyes on you.
HAPPY = with_(rig.HAPPY, ears=-6, blush=False)
SAD = with_(rig.SAD, tail=0.0)
LOVED = with_(rig.LOVED, ears=-6, blush=False)
SCARED = with_(rig.SCARED, tail=0.1)
SLEEPY = with_(rig.SLEEPY, tail=0.4)
SLEEPING = Pose(stance="curl", eyes="blink", ears=20, extras=("zzz",))  # Curled up on the seat (curled()).
LISTENING = with_(rig.LISTENING, ears=-6, ear_left=-4)
THINKING = with_(rig.THINKING, tail=0.8)
TALKING = with_(rig.TALKING, blush=False)
# Focus: a tennis ball held in its mouth, which keeps it busy. The head
# stays put in every frame with the ball, reactions during focus too, so
# the ball's pixels never move (tests/test_props.py).
GUARDING = Pose(eyes="down", mouth="flat", ears=-8, head_dy=1, tail=0.9, prop="ball")
PETTED = Pose(eyes="happy", mouth="grin", ears=10, head_dy=1, tilt=-6)
SIT_PRETTY = Pose(stance="beg", eyes="happy", mouth="grin", ears=-6)
SCARED_GUARD = with_(SCARED, prop="ball")  # Startled, it keeps hold of the ball.
PETTED_GUARD = with_(PETTED, prop="ball", tilt=0)  # Leans into the hand without tipping its head (and the ball).
HAPPY_GUARD = with_(GUARDING, eyes="happy", ears=-6)  # Celebrates with the ball in its mouth: no sitting pretty.


def fast_wag(base: Pose, times: int, ms: int = 70) -> list[tuple[Pose, int]]:
    """Quick tail wags: four frames each, a little over a quarter second."""
    return wag_cycle(base, frames=4, ms=ms) * times


ANIMATIONS: dict[str, list[tuple[Pose, int]]] = {
    # Alert idle: breathing, an ear twitch, and now and then a short wag.
    "Neutral": [
        (NEUTRAL, 900),
        (with_(NEUTRAL, breath=1), 900),
        (with_(NEUTRAL, ear_right=-8), 160),
        (NEUTRAL, 900),
        *wag_cycle(NEUTRAL, frames=6, amplitude=0.6, ms=90),
        *wag_cycle(NEUTRAL, frames=6, amplitude=0.6, ms=90),
        (NEUTRAL, 1200),
    ],
    # Happy: a burst of fast tail wags, then a short rest.
    "Happy": [*fast_wag(HAPPY, 5), (HAPPY, 1800)],
    "Loved": [*fast_wag(LOVED, 5), (LOVED, 600)],
    "Sad": [(SAD, 1400), (with_(SAD, breath=1), 1400)],
    "Scared": [(SCARED, 120), (with_(SCARED, head_dx=1), 120), (SCARED, 120), (with_(SCARED, head_dx=-1), 120)],
    "Sleepy": [(SLEEPY, 1200), (with_(SLEEPY, eyes="blink", head_dy=3), 900), (SLEEPY, 1500)],
    "Sleeping": [(SLEEPING, 1400), (with_(SLEEPING, breath=1), 1400)],
    "listening": [(LISTENING, 1000)],
    "thinking": [(THINKING, 1000)],
    "talking": [(TALKING, 1000)],
    # Focus: busy with the ball in its mouth, eyes down, ears perked, tail still.
    # Now and then an ear twitch, a quick look up at you, a tail flick.
    # Calm, since it loops for minutes.
    "Focus": [
        (GUARDING, 2500),
        (with_(GUARDING, breath=1), 2000),
        (with_(GUARDING, ear_left=-6), 160),
        (GUARDING, 1800),
        (with_(GUARDING, eyes="open"), 1200),
        (GUARDING, 1500),
        (with_(GUARDING, wag=0.5), 160),
        (GUARDING, 160),
        (with_(GUARDING, wag=0.5), 160),
        (with_(GUARDING, breath=1), 1400),
    ],
    # Petted: leans into the hand, ears relaxed, tail going flat out.
    "Petted": fast_wag(PETTED, 7),
    # Celebrate: sits pretty, grinning, with a little bounce on every wag.
    "Celebrate": [
        *[(with_(pose, head_dy=1 if i % 2 else 0), ms) for i, (pose, ms) in enumerate(fast_wag(SIT_PRETTY, 8, 80))],
        (SIT_PRETTY, 440),
    ],
    # Reactions during focus (the persona's `during:`): the ball stays in its
    # mouth and the head stays where it is.
    "PettedFocus": fast_wag(PETTED_GUARD, 7),
    "ScaredFocus": [(SCARED_GUARD, 120), (with_(SCARED_GUARD, breath=1), 120)],
    "CelebrateFocus": [*fast_wag(HAPPY_GUARD, 8, 80), (HAPPY_GUARD, 440)],
}

# Single frames shown when the hub blinks or winks, per animation.
BLINKS: dict[str, Pose] = {
    "Neutral": with_(NEUTRAL, eyes="blink"),
    "Sad": with_(SAD, eyes="blink"),
    "Focus": with_(GUARDING, eyes="blink"),
}
WINKS: dict[str, Pose] = {
    "Neutral": with_(NEUTRAL, eyes="wink"),
    "Happy": with_(HAPPY, eyes="wink", mouth="smile"),
    "Celebrate": with_(SIT_PRETTY, eyes="wink"),
}

PERSONA = Spec("jack_russell", background=BACKGROUND)
