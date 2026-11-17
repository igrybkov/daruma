"""The pixel corgi persona: the corgi (breed.py) in its cozy room (cozy_room.py).

Warm plank walls, a window, a pothos (pothos.py) on the shelf, floor boards
and a red rug that changes color by weekday; the corgi sits on the rug.
The animations are in moods.py. This module is the persona's layers
(see personas.Spec).
"""

from __future__ import annotations

from daruma_pixel.personas import Spec
from daruma_shapes.pets.rig import Pet
from daruma_shapes.plants.pothos import POTHOS
from daruma_shapes.rooms.cozy_room import Room

from . import moods
from .breed import CORGI

# The room's warm browns and red rug are the corgi's.
ROOM = Room()
_pet = Pet(CORGI, ROOM, seat="floor", plant=POTHOS, plant_spot="shelf")

background, foreground, scene = _pet.background, _pet.foreground, _pet.scene
WINDOW = ROOM.window
_extra = _pet.layers()
plant, PLANT_STAGES, DEFAULT_STAGE = _extra["plant"], _extra["PLANT_STAGES"], _extra["DEFAULT_STAGE"]
RUG_COLORS, RUG_BY_WEEKDAY, RUG_BOX = _extra["RUG_COLORS"], _extra["RUG_BY_WEEKDAY"], _extra["RUG_BOX"]
room = ROOM.image

# Where focus's props stand (tests/test_props.py): the book in the lap. The
# glasses move with the head (tests/test_pet_props.py checks they stay on).
PROPS = {"focus": [(40, 55, 67, 75)]}

PERSONA = Spec("corgi", background=0x4A2A1A, animations=moods)
