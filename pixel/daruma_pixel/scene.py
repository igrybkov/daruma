"""Scenes, spots and props: what stands behind a persona, and where things go.

A scene is the backdrop: room.py's Room, living_room.py's LivingRoom,
studio.py's Studio. It publishes its spots, the named places where things
go (a floor, a seat, a shelf, a sill). Actors and props know nothing about
any scene: they draw at a spot the persona passes in. A persona picks the
scene, the actor, the progress prop, and which spot each one gets.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Protocol

from PIL import Image

W, H = 106, 80


@dataclass(frozen=True)
class Spot:
    """A place in a scene. `x` is the column a thing centers on, `y` the row
    it stands on (a pot's foot on a shelf, a pet's feet on a seat) or hangs
    from (a hook in the ceiling)."""

    x: int
    y: int


class Scene(Protocol):
    """Everything behind an actor, swappable per persona.

    A scene is the backdrop and, if it has them, a window (where the device
    draws the sky and weather), spots for actors and props, and colors the
    device swaps by weekday (like a rug).
    """

    window: tuple[int, int, int, int] | None  # Glass: x, y, width, height; None without one.
    spots: Mapping[str, Spot]  # Named places: "floor", "seat", "shelf", "sill", ...

    def image(self) -> Image.Image:
        """The whole backdrop, glass included."""

    def background(self) -> Image.Image:
        """The backdrop, see-through where the glass is."""

    def layers(self) -> dict:
        """The scene's weekday colors as persona-module names: RUG_COLORS,
        RUG_BY_WEEKDAY and RUG_BOX (see personas.py). Empty without any."""


@dataclass(frozen=True)
class Grower:
    """A progress prop: one picture per stage of the progress signal, healthy
    or wilted, like a plant growing. `draw(stage, wilted, at)` gives a
    scene-sized layer with the prop's anchor on the spot `at`."""

    draw: Callable[[int, bool, Spot], Image.Image]
    stages: int
    default_stage: int  # What previews and the flat scene show.

    def at(self, spot: Spot) -> Callable[..., Image.Image]:
        """plant(stage, wilted=False): this prop drawn at `spot`."""

        def plant(stage: int, wilted: bool = False) -> Image.Image:
            return self.draw(stage, wilted, spot)

        return plant

    def layers(self, spot: Spot) -> dict:
        """The persona-module names for this prop at `spot`: plant,
        PLANT_STAGES and DEFAULT_STAGE (see personas.py)."""
        return {"plant": self.at(spot), "PLANT_STAGES": self.stages, "DEFAULT_STAGE": self.default_stage}


class PropLayer:
    """A scene-sized layer for one prop, drawn in the prop's own frame.

    The prop draws as if its anchor were at `anchor`; every pixel then moves
    by whole pixels so the anchor lands on the spot. Moving after rounding
    keeps the pixel art exact: the prop is the same picture on any spot.
    """

    def __init__(self, anchor: tuple[int, int], at: Spot, size: tuple[int, int] = (W, H)) -> None:
        self.img = Image.new("RGBA", size, (0, 0, 0, 0))
        self.px = self.img.load()
        self.w, self.h = size
        self.dx, self.dy = at.x - anchor[0], at.y - anchor[1]

    def dot(self, x: float, y: float, c) -> None:
        x, y = round(x) + self.dx, round(y) + self.dy
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[x, y] = (*c, 255)

    def filled(self, x: int, y: int) -> bool:
        x, y = x + self.dx, y + self.dy
        return 0 <= x < self.w and 0 <= y < self.h and self.px[x, y][3] > 0


# Colors by the day of the week, in the colors people most often "see" the
# days in (weekday-color synesthesia, and the meme that Thursday is brown):
# white Sunday, blue Monday, yellow Tuesday, green Wednesday, brown Thursday,
# pink Friday, purple Saturday. Three per day (edge, main, shadow), Sunday
# first: a scene's rug, throw or drape takes them.
WEEKDAY_COLORS = (
    ((184, 150, 104), (236, 228, 210), (204, 192, 170)),  # Sunday: white
    ((204, 170, 112), (58, 92, 160), (44, 70, 126)),  # Monday: blue
    ((236, 214, 160), (222, 182, 48), (180, 144, 32)),  # Tuesday: yellow
    ((206, 172, 100), (62, 128, 76), (46, 98, 58)),  # Wednesday: green
    ((206, 164, 110), (100, 62, 40), (78, 46, 30)),  # Thursday: brown, obviously
    ((228, 190, 144), (214, 104, 146), (172, 78, 114)),  # Friday: pink
    ((206, 166, 108), (112, 70, 150), (86, 52, 118)),  # Saturday: purple
)
