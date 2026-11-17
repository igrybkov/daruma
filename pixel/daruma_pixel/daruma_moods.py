"""The daruma's moods and animations, for each number of painted eyes.

Same shape as corgi_moods.py: ANIMATIONS maps a name to a list of (Pose, ms)
frames that loops, BLINKS and WINKS map a name to one frame. The difference:
each exists three times, once per eye state. eyes(n) gives an object with
ANIMATIONS, BLINKS and WINKS for n painted eyes (0, 1 or 2), which is what
personas.build() reads from a persona's animations (personas.Spec).

Frames with closed eyes (blinks, the happy wobble, sleep, the fall in
Scared) are the same picture in every eye state, so the device stores
them once.

"Paint" is a one-shot, not a loop: a brush paints eye number n in. It
exists for n = 1 and 2. Its last frame is the first Neutral frame of the
same state, so the device can go straight on to Neutral after it.

LovedFocus, ScaredFocus and PaintFocus are Loved, Scared and Paint with
the incense burning: the looks for petted, startled, celebrate and paint
while a focus session is on (persona_daruma.yaml `during:`), so the incense
does not vanish under a reaction.
"""

from __future__ import annotations

import math
from types import SimpleNamespace

from .daruma import EYE_X, EYE_Y, Frame, Pose, _settle, with_

LOOPS = [
    "Neutral",
    "Happy",
    "Loved",
    "Sad",
    "Scared",
    "Sleepy",
    "Sleeping",
    "listening",
    "thinking",
    "talking",
    "Focus",
    "LovedFocus",
    "ScaredFocus",
]
ONE_SHOTS = ["Paint", "PaintFocus"]


def rock(base: Pose, angles: list[float], ms: int, **changes) -> list[tuple[Pose, int]]:
    return [(with_(base, tilt=a, **changes), ms) for a in angles]


def wobble(amplitude: float, steps: int = 8) -> list[float]:
    """One side-to-side swing, starting upright."""
    return [round(amplitude * math.sin(2 * math.pi * i / steps)) for i in range(steps)]


def _eye_canvas(index: int) -> tuple[int, int]:
    """Canvas position of an eye's centre on the upright doll."""
    f = Frame(0, _settle(0))
    x, y = f.pt((-1 if index == 0 else 1) * EYE_X, EYE_Y)
    return round(x), round(y)


def paint(n: int) -> list[tuple[Pose, int]]:
    """A brush comes in, dabs eye number n (1 or 2) full of ink, and leaves."""
    index = n - 1
    side = -1 if index == 0 else 1  # The brush comes from the eye's own side.
    ex, ey = _eye_canvas(index)
    before = Pose(painted=n - 1)
    look = Pose(painted=n - 1, brows="up", mouth="o", look=(side, -1))
    done = Pose(painted=n)
    work = with_(before, brows="up", mouth="flat")
    lifted = (ex + side * 4, ey - 3, side)
    return [
        (with_(look, brush=(ex + side * 8, ey - 1, side)), 260),
        (with_(look, brush=(ex + side * 3, ey - 2, side)), 160),
        (with_(work, brush=(ex, ey, side), wet=1), 220),
        (with_(work, brush=lifted, wet=1), 200),
        (with_(work, brush=(ex - side, ey + 1, side), wet=2), 220),
        (with_(work, brush=lifted, wet=2), 200),
        (with_(done, brows="up", mouth="flat", brush=(ex, ey, side)), 180),
        (with_(done, brows="up", mouth="o", brush=(ex + side * 8, ey - 1, side)), 220),
        (with_(done, brows="up", mouth="grin", extras=("sparkle",)), 700),
        (done, 300),
    ]


def animations(n: int) -> dict[str, list[tuple[Pose, int]]]:
    neutral = Pose(painted=n)
    happy = Pose(painted=n, eyes="happy", mouth="grin")
    happy_rest = Pose(painted=n, mouth="grin")
    loved = Pose(painted=n, eyes="happy", mouth="smile")
    sad = Pose(painted=n, brows="worried", mouth="frown", look=(0, 1), tilt=-3)
    scared = Pose(painted=n, eyes="wide", brows="up", mouth="o", extras=("sweat",))
    fall = with_(scared, eyes="shut", extras=())
    sleepy = Pose(painted=n, eyes="half", brows="low", mouth="flat")
    sleeping = Pose(painted=n, eyes="blink", brows="low", mouth="flat")
    focus = Pose(painted=n, mouth="flat", look=(0, 1), prop="incense")

    out = {
        # Mostly still. Now and then a tiny rock and a brow lift.
        "Neutral": [
            (neutral, 2600),
            (with_(neutral, tilt=3), 220),
            (with_(neutral, tilt=-2), 220),
            (neutral, 2200),
            (with_(neutral, brows="up"), 500),
            (neutral, 1800),
        ],
        # A weighted doll's joy: two quick wobbles, then a rest.
        "Happy": [*rock(happy, wobble(11), 90), *rock(happy, wobble(8), 90), (happy_rest, 1600)],
        "Loved": [
            *rock(with_(loved, extras=("hearts",)), wobble(6)[:4], 150),
            *rock(with_(loved, extras=("hearts2",)), wobble(6)[4:], 150),
            (with_(loved, extras=("hearts",)), 700),
            (with_(loved, eyes="open", extras=("hearts2",)), 900),
        ],
        "Sad": [(with_(sad, extras=("tear",)), 1400), (with_(sad, extras=("tear2",)), 1400)],
        # Knocked over, and back up: fall down seven times, get up eight.
        "Scared": [
            (scared, 700),
            (with_(fall, tilt=30), 70),
            (with_(fall, tilt=65), 70),
            (with_(scared, tilt=90, extras=()), 600),
            (with_(fall, tilt=55), 80),
            (with_(fall, tilt=20), 90),
            (with_(scared, tilt=-10, extras=()), 110),
            (with_(scared, tilt=6, extras=()), 130),
            (with_(scared, tilt=-3, extras=()), 160),
        ],
        # Nodding off: it leans, the eyes close, it catches itself.
        "Sleepy": [
            (sleepy, 1400),
            (with_(sleepy, tilt=4), 500),
            (with_(sleepy, eyes="blink", tilt=8), 900),
            (with_(sleepy, tilt=3), 300),
            (sleepy, 1500),
        ],
        # A slow rock while it sleeps.
        "Sleeping": [
            (with_(sleeping, tilt=-3, extras=("zzz",)), 1400),
            (with_(sleeping, extras=("zzz2",)), 700),
            (with_(sleeping, tilt=3, extras=("zzz",)), 1400),
            (with_(sleeping, extras=("zzz2",)), 700),
        ],
        "listening": [(Pose(painted=n, brows="one_up", mouth="flat", look=(1, 0), tilt=6), 1000)],
        "thinking": [(Pose(painted=n, brows="one_up", mouth="flat", look=(-1, -1), tilt=-5, extras=("dots",)), 1000)],
        "talking": [
            (Pose(painted=n, mouth="talk"), 200),
            (Pose(painted=n, mouth="smile"), 160),
            (Pose(painted=n, mouth="o"), 180),
            (Pose(painted=n, mouth="smile"), 160),
        ],
        # Sitting with incense through a focus session: long holds, the smoke
        # drifts, now and then the eyes close for a breath.
        "Focus": [
            (focus, 2200),
            (with_(focus, smoke=1), 1800),
            (with_(focus, smoke=2), 1800),
            (with_(focus, eyes="blink", brows="low"), 1600),
            (with_(focus, smoke=1, eyes="blink", brows="low"), 1400),
            (with_(focus, smoke=2), 1600),
        ],
    }
    if n >= 1:
        out["Paint"] = paint(n)
    # The reactions that can play while it sits with incense, with the
    # incense still there (persona_daruma.yaml `during:` picks them). Scared
    # falls the other way, away from the bowl.
    out["LovedFocus"] = with_incense(out["Loved"])
    out["ScaredFocus"] = with_incense([(with_(pose, tilt=-pose.tilt), ms) for pose, ms in out["Scared"]])
    if n >= 1:
        out["PaintFocus"] = with_incense(out["Paint"])
    return out


SMOKE_MS = 1800  # How long the smoke keeps one shape, as in Focus.


def with_incense(frames: list[tuple[Pose, int]]) -> list[tuple[Pose, int]]:
    """The same frames with the incense burning, its smoke changing shape at Focus's pace."""
    out, t = [], 0
    for pose, ms in frames:
        out.append((with_(pose, prop="incense", smoke=(t // SMOKE_MS) % 3), ms))
        t += ms
    return out


def blinks(n: int) -> dict[str, Pose]:
    a = animations(n)
    first = {key: frames[0][0] for key, frames in a.items()}
    return {key: with_(first[key], eyes="blink") for key in ("Neutral", "Sad", "Focus", "listening", "thinking")}


def winks(n: int) -> dict[str, Pose]:
    return {
        "Neutral": Pose(painted=n, eyes="wink"),
        "Happy": Pose(painted=n, eyes="wink", mouth="grin"),
    }


def eyes(n: int) -> SimpleNamespace:
    """The source object personas.build() reads, for n painted eyes."""
    return SimpleNamespace(ANIMATIONS=animations(n), BLINKS=blinks(n), WINKS=winks(n))


# Module-level defaults, one eye painted: the corgi_moods.py shape.
ANIMATIONS = animations(1)
BLINKS = blinks(1)
WINKS = winks(1)
