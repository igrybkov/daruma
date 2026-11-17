"""Front-facing Pembroke corgi: a dog breed on the pet rig (pet.py, dog.py).

Red and white: red head with tall erect ears and pink insides, a white
blaze down to a white muzzle, a white chest and legs, red sides and deeper
red haunches. No tail, so it wags its whole rear end (pet.py, "butt").

Its room, layers and moods are in preview.py and moods.py.
"""

from __future__ import annotations

from PIL import Image

from . import dog
from .pet import Coat, H, Pose, W, with_  # noqa: F401  (W, H, Pose, with_: the corgi's API)
from .pet import render as _render
from .pixelkit import Ramp

OUTLINE = (58, 32, 24)
FUR = Ramp(base=(222, 136, 58), shadow=(182, 96, 40), light=(242, 170, 92), line=(150, 74, 32))
FUR_DEEP = Ramp(base=(196, 112, 46), shadow=(160, 82, 34), line=(140, 68, 30))  # Haunches behind the body.
WHITE = Ramp(base=(250, 242, 228), shadow=(214, 198, 180), light=(255, 255, 250), line=(196, 178, 160))
PINK = Ramp(base=(236, 150, 150), shadow=(206, 116, 120))

CORGI = dog.breed(coat=Coat(outline=OUTLINE, fur=FUR, body=FUR, deep=FUR_DEEP, white=WHITE, pink=PINK))


def render(p: Pose) -> Image.Image:
    return _render(CORGI, p)
