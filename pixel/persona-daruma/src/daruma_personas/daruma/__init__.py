"""The daruma as device personas, one per number of painted eyes.

    PERSONAS: daruma0, daruma1, daruma2 (see personas.Spec)
    build(0), build(1), build(2) -> personas.Persona

Each is a whole persona: room, window, plant, cushion colors and every
animation, for that many painted eyes. They use the same room and the same
crop box. Each Spec checks that box.

A `pixel_art:` config names this module and a persona in it:

    pixel_art:
      module: daruma_personas.daruma
      persona: daruma1

packages/persona_daruma.yaml makes the three one device persona, one per
goal stage (`pixel_art: goal:`). They share one frame set, so a frame that
differs only in the eyes is stored as a small patch on another frame
(sprite_codec.encode_set). Paint plays once when an eye gets painted
(`play_once` and the `paint` behavior).
"""

from __future__ import annotations

import functools
import sys

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
