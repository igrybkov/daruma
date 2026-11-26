"""The avatar's animations: each state as poses of the rider and the pet.

The rider (with its mount) and the pet move on their own. The pet follows
half a beat behind: it breathes and hops after the rider. Closed eyes are
the look's `_sleep` skin: the blink, sleep and sleepiness.

Focus holds a book. A reaction during focus (`...Focus`) keeps the rider
and the book still, so the book stays in the picture (PROPS, during:).
"""

from __future__ import annotations

from dataclasses import replace

from .actor import Pose

REST = Pose()
READING = Pose(book=True)


def _with(pose: Pose, **changes) -> Pose:
    return replace(pose, **changes)


def _breathing(base: Pose, ms: int) -> list[tuple[Pose, int]]:
    """Rider down a pixel and back; the pet bobs up half a period later."""
    rider = (0, 0, 1, 1)
    pet = (-1, 0, 0, -1)
    return [(_with(base, dy=base.dy + r, pet_dy=p), ms) for r, p in zip(rider, pet, strict=True)]


def _hop(base: Pose, ms: int) -> list[tuple[Pose, int]]:
    """A hop: the rider up three pixels and down; the pet one frame after."""
    heights = (0, -2, -3, -2, 0, 0)
    pet = (0, 0, -2, -3, -2, 0)
    return [(_with(base, dy=r, pet_dy=p, step=i), ms) for i, (r, p) in enumerate(zip(heights, pet, strict=True))]


def _shake(base: Pose, ms: int) -> list[tuple[Pose, int]]:
    return [(_with(base, dx=dx, pet_dy=p), ms) for dx, p in ((1, 0), (-1, -1), (1, -2), (-1, 0))]


def _still(base: Pose, ms: int, steps: int = 2) -> list[tuple[Pose, int]]:
    """The rider still: only the effects move."""
    return [(_with(base, step=i), ms) for i in range(steps)]


SAD = Pose(dy=1, extras=("sweat",))
SLEEPY = Pose(dy=1, eyes_closed=True, extras=("zzz",))
LOVED = Pose(extras=("hearts",))
SCARED = Pose(extras=("sweat",))
THINKING = Pose(extras=("dots",))
CELEBRATE = Pose(extras=("sparkle",))

ANIMATIONS: dict[str, list[tuple[Pose, int]]] = {
    "Neutral": _breathing(REST, 500),
    "Happy": _hop(REST, 120) + [(REST, 600)],
    "Sad": _breathing(SAD, 700),
    "Loved": _hop(LOVED, 140),
    "Scared": _shake(SCARED, 90),
    "Sleepy": _breathing(SLEEPY, 800),
    "Sleeping": [(_with(SLEEPY, step=i, pet_dy=-(i % 2)), 700) for i in range(3)],
    "Thinking": _breathing(THINKING, 600),
    "Talking": [(REST, 180), (_with(REST, dy=-1), 180)],
    "Focus": [(READING, 1400), (_with(READING, page=1), 600)],
    "Petted": _hop(LOVED, 110) + [(LOVED, 400)],
    "Startled": _shake(SCARED, 70) + [(_with(SCARED, pet_dy=-3), 200)],
    "Celebrate": _hop(CELEBRATE, 110) + _hop(CELEBRATE, 110),
    # Reactions during focus: the rider and the book stay put.
    "PettedFocus": _still(_with(READING, extras=("hearts",)), 300),
    "StartledFocus": [(_with(READING, extras=("sweat",), pet_dy=p), 120) for p in (0, -2, -3, 0)],
    "CelebrateFocus": _still(_with(READING, extras=("sparkle",)), 250),
}

# The first frame with the eyes closed, where the eyes are open.
BLINKS: dict[str, Pose] = {
    name: _with(frames[0][0], eyes_closed=True)
    for name, frames in ANIMATIONS.items()
    if name in ("Neutral", "Sad", "Thinking", "Talking", "Focus")
}
WINKS: dict[str, Pose] = {}
