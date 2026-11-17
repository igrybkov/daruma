"""The pixel corgi persona: the corgi (corgi.py) in its cozy room (room.py).

Warm plank walls, a window, a shelf with the plant, floor boards and a red
rug that changes color by weekday. The animations are in corgi_moods.py.
This module is the persona's layers (see personas.Spec).
"""

from __future__ import annotations

from . import corgi_moods
from .corgi import CORGI
from .personas import Spec
from .pet import Pet
from .room import Room

ROOM = Room()
_pet = Pet(CORGI, ROOM)

background, foreground, scene = _pet.background, _pet.foreground, _pet.scene
WINDOW = ROOM.window
_extra = ROOM.layers()
plant, PLANT_STAGES, DEFAULT_STAGE = _extra["plant"], _extra["PLANT_STAGES"], _extra["DEFAULT_STAGE"]
RUG_COLORS, RUG_BY_WEEKDAY, RUG_BOX = _extra["RUG_COLORS"], _extra["RUG_BY_WEEKDAY"], _extra["RUG_BOX"]
room = ROOM.image

# Where focus's props stand (tests/test_props.py): the book in the lap. The
# glasses move with the head (tests/test_pet_props.py checks they stay on).
PROPS = {"focus": [(40, 55, 67, 75)]}

PERSONA = Spec("corgi", background=0x4A2A1A, animations=corgi_moods)
