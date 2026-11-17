"""The Scene interface: everything behind a persona, swappable per persona.

room.py's Room, living_room.py's LivingRoom and studio.py's Studio are
scenes. pet.py's Pet puts a pet in one.
"""

from __future__ import annotations

from typing import Protocol

from PIL import Image


class Scene(Protocol):
    """Where a pet lives: everything behind it, swappable per persona.

    A scene is the backdrop and, if it has them, a window (where the device
    draws the sky and weather), a progress prop (a picture per stage of the
    progress signal, healthy and wilted, like a plant growing) and colors
    the device swaps by weekday (like a rug). room.py's Room is one scene,
    living_room.py's LivingRoom another. A scene with furniture to sit on
    may set `pet_floor`, the row the pet's feet rest on (see Pet.render).
    """

    window: tuple[int, int, int, int] | None  # Glass: x, y, width, height; None without one.

    def image(self) -> Image.Image:
        """The whole backdrop, glass included."""

    def background(self) -> Image.Image:
        """The backdrop, see-through where the glass is."""

    def layers(self) -> dict:
        """The scene's optional persona-module names: plant, PLANT_STAGES and
        DEFAULT_STAGE for a progress prop; RUG_COLORS, RUG_BY_WEEKDAY and
        RUG_BOX for weekday colors (see personas.py). Empty without either."""
