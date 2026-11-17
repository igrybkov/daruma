"""The corgi's moods and animations: each is a list of (Pose, milliseconds) frames that loops.

Add a posture: make a Pose with new numbers. Add an animation: list poses.
The mood poses and the wag are shared by every pet (rig.py).
"""

from __future__ import annotations

from daruma_shapes.pets.rig import (  # noqa: F401  (the mood poses are this module's API too)
    HAPPY,
    LISTENING,
    LOVED,
    NEUTRAL,
    READING,
    SAD,
    SCARED,
    SLEEPING,
    SLEEPY,
    TALKING,
    THINKING,
    Pose,
    wag_cycle,
    with_,
)

# Reading, petted or startled: the reactions over the focus keep the book.
LOVED_READING = with_(READING, eyes="heart", mouth="open", blush=True, ears=-4, extras=("hearts",))
SCARED_READING = with_(READING, eyes="small", mouth="o", ears=30, extras=("sweat",))

ANIMATIONS: dict[str, list[tuple[Pose, int]]] = {
    # Calm idle: breathing, an ear twitch, then a small lazy wag.
    "Neutral": [
        (NEUTRAL, 900),
        (with_(NEUTRAL, breath=1), 900),
        (with_(NEUTRAL, ear_right=-8), 160),
        (NEUTRAL, 700),
        *wag_cycle(NEUTRAL, frames=8, amplitude=0.5, ms=120),
    ],
    # Happy: two fast butt wags, then a short rest so the screen goes quiet.
    "Happy": [*wag_cycle(HAPPY), *wag_cycle(HAPPY), (HAPPY, 2000)],
    "Loved": [*wag_cycle(LOVED), *wag_cycle(LOVED), (LOVED, 600)],
    "Sad": [(SAD, 1400), (with_(SAD, breath=1), 1400)],
    "Scared": [(SCARED, 120), (with_(SCARED, head_dx=1), 120), (SCARED, 120), (with_(SCARED, head_dx=-1), 120)],
    "Sleepy": [(SLEEPY, 1200), (with_(SLEEPY, eyes="blink", head_dy=3), 900), (SLEEPY, 1500)],
    "Sleeping": [(SLEEPING, 1400), (with_(SLEEPING, breath=1), 1400)],
    "listening": [(LISTENING, 1000)],
    "thinking": [(THINKING, 1000)],
    "talking": [(TALKING, 1000)],
    # Reading through a focus session: long still holds, a breath, now and
    # then a page turn and an ear twitch. Calm, since it loops for minutes.
    "Focus": [
        (READING, 2500),
        (with_(READING, breath=1), 2000),
        (READING, 1500),
        (with_(READING, page=1), 180),
        (with_(READING, page=2), 180),
        (READING, 1500),
        (with_(READING, ear_right=-8), 160),
        (with_(READING, breath=1), 1400),
    ],
    # Reactions during focus (the persona's `during:`): it keeps its glasses
    # and book. Petted (and celebrating) while reading: heart eyes and the
    # butt wag; head, chest and book keep still together (rig.py).
    "LovedFocus": [*wag_cycle(LOVED_READING), *wag_cycle(LOVED_READING), (LOVED_READING, 600)],
    # Startled while reading: wide eyes, ears back, a tremble.
    "ScaredFocus": [(SCARED_READING, 120), (with_(SCARED_READING, breath=1), 120)],
}

# Single frames shown when the hub blinks or winks, per animation.
BLINKS: dict[str, Pose] = {
    "Neutral": with_(NEUTRAL, eyes="blink"),
    "Sad": with_(SAD, eyes="blink"),
    "Focus": with_(READING, eyes="blink"),
}
WINKS: dict[str, Pose] = {
    "Neutral": with_(NEUTRAL, eyes="wink"),
    "Happy": with_(HAPPY, eyes="wink", mouth="smile"),
}
