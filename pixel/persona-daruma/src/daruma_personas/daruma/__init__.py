"""The daruma as device personas, one per number of painted eyes.

    PERSONAS: daruma0, daruma1, daruma2 (see personas.Spec)
    build(0), build(1), build(2) -> personas.Persona

Each is a whole persona: room, window, plant, cushion colors and every
animation, for that many painted eyes. They use the same room and the same
crop box, so frames that do not show the eyes are the same pictures in all
three and the device stores them once. Each Spec checks that box.

A `pixel_art:` config names this module and a persona in it:

    pixel_art:
      module: daruma_personas.daruma
      persona: daruma1

What the firmware still needs: a way to switch between the three personas
as eyes get painted, and a way to play "Paint" once and then go back to
the mood. The sprite component stores any animation name, so Paint is
built and stored already; nothing plays it yet.

Eye overlays, a smaller option: eye_overlays() returns, for every frame of
the blank-eyed persona, the patch that turns it into the one- or two-eyed
frame. See its docstring for what the device would need.
"""

from __future__ import annotations

import functools
import hashlib
import sys
from dataclasses import dataclass

from PIL import Image

from daruma_pixel import personas

from . import doll, moods

EYE_STATES = (0, 1, 2)


def persona_name(eyes_painted: int) -> str:
    return f"daruma{eyes_painted}"


def build(eyes_painted: int | str):
    """personas.build() for the daruma with this many painted eyes (0, 1 or 2).

    Also takes the persona name ("daruma0" .. "daruma2").
    """
    if isinstance(eyes_painted, str):
        names = {persona_name(n): n for n in EYE_STATES}
        if eyes_painted not in names:
            raise ValueError(f"No daruma persona {eyes_painted!r}; use one of {sorted(names)}")
        eyes_painted = names[eyes_painted]
    if eyes_painted not in EYE_STATES:
        raise ValueError(f"eyes_painted is 0, 1 or 2, not {eyes_painted}")
    return personas.build(persona_name(eyes_painted), sys.modules[__name__])


def _check_box(persona, eyes_painted: int) -> None:
    # Timing probe: not for merge.
    """All eye states must crop the same box, or no frame is shared between them."""
    if eyes_painted == 0:
        return
    offset, a = _blank_box()
    b = persona.animations["Neutral"].frames[0][0].size
    if offset != persona.sprite_offset or a != b:
        raise ValueError(f"daruma{eyes_painted} crops {persona.sprite_offset} {b}, daruma0 {offset} {a}")


@functools.cache
def _blank_box() -> tuple[tuple[int, int], tuple[int, int]]:
    # Timing probe: not for merge.
    """daruma0's crop: where its frames go, and their size."""
    ref = build(0)
    return ref.sprite_offset, ref.animations["Neutral"].frames[0][0].size


PERSONAS = tuple(
    personas.Spec(
        persona_name(n),
        background=doll.BACKGROUND,
        layers=doll,
        animations=moods.eyes(n),
        check=lambda persona, n=n: _check_box(persona, n),
    )
    for n in EYE_STATES
)


@dataclass
class Patch:
    image: Image.Image  # See-through except where the eyes differ.
    x: int  # Where it goes on the frame.
    y: int


@dataclass
class Overlays:
    """Eye patches for one animation. Each entry is [patch for 1 eye, patch for 2 eyes]."""

    frames: list[list[Patch | None]]
    blink: list[Patch | None] | None = None
    wink: list[Patch | None] | None = None


def eye_overlays() -> dict[str, Overlays]:
    """Per animation: the patches that turn the blank-eyed persona into the others.

    The device would store the blank-eyed persona only, plus these patches.
    It draws a frame (or the blink or wink) as usual, then the patch for
    the current eye count on top, at (x, y) within the frame. None means
    that picture looks the same in that state (closed eyes, for example).
    Paint is left out: it is its own one-shot animation and is stored
    whole.

    Patches with the same pixels are the same object, so they can be
    stored once.
    """
    base = build(0)
    states = {n: build(n) for n in (1, 2)}
    shared: dict[str, Image.Image] = {}

    def patches(pick) -> list[Patch | None]:
        row = []
        for n in (1, 2):
            patch = diff_patch(pick(base), pick(states[n]))
            if patch:
                h = hashlib.sha1(patch.image.tobytes() + repr(patch.image.size).encode()).hexdigest()
                patch.image = shared.setdefault(h, patch.image)
            row.append(patch)
        return row

    out: dict[str, Overlays] = {}
    for key, anim in base.animations.items():
        entry = Overlays(
            frames=[
                patches(lambda persona, i=i, key=key: persona.animations[key].frames[i][0])
                for i in range(len(anim.frames))
            ]
        )
        if anim.blink is not None:
            entry.blink = patches(lambda persona, key=key: persona.animations[key].blink)
        if anim.wink is not None:
            entry.wink = patches(lambda persona, key=key: persona.animations[key].wink)
        out[key] = entry
    return out


def diff_patch(a: Image.Image, b: Image.Image) -> Patch | None:
    """The smallest picture that, drawn over a, gives b."""
    a, b = a.convert("RGBA"), b.convert("RGBA")
    pa, pb = a.load(), b.load()
    xs, ys = [], []
    for y in range(a.height):
        for x in range(a.width):
            if pa[x, y] != pb[x, y]:
                xs.append(x)
                ys.append(y)
    if not xs:
        return None
    box = (min(xs), min(ys), max(xs) + 1, max(ys) + 1)
    img = Image.new("RGBA", (box[2] - box[0], box[3] - box[1]), (0, 0, 0, 0))
    pi = img.load()
    for y in range(box[1], box[3]):
        for x in range(box[0], box[2]):
            if pa[x, y] != pb[x, y]:
                if pb[x, y][3] < 128:
                    raise ValueError("an eye patch would need to clear a pixel")
                pi[x - box[0], y - box[1]] = pb[x, y]
    return Patch(img, box[0], box[1])
