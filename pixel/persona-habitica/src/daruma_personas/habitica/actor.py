"""The avatar as a persona's layers: the room, and the avatar posed in it.

A Pose moves the rider (with its mount) and the pet on their own, closes
the eyes (the `_sleep` skin), and adds effects and the focus book. The
layers are what daruma_pixel.personas needs: background(), foreground(pose),
scene(pose), WINDOW (none: the sky is Habitica's) and PROPS.

Effects stand where a Habitica figure's head is, from the rider's place:
its body canvas (30x30 art pixels) puts the head at about x 10..20, y 8..20.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import cached_property

from PIL import Image

from daruma_pixel import effects
from daruma_pixel.pixelkit import Canvas

from . import room
from .compose import MOUNT_BODY, MOUNT_HEAD, PET, RIDER, Avatar

PLAQUE_CLEAR = 17  # The first room column right of the pomodoro plaque (72 px from 6, at 5x), with a gap.
BOOK = (11, 22, 19, 26)  # In the rider's body canvas: x0, y0, x1, y1, end exclusive.
COVER, PAGE, PAGE_LINE = (122, 52, 40), (246, 238, 214), (190, 176, 150)
SPARKLE = (255, 236, 140)
EFFECTS_TOP = 4  # The highest the effects anchor goes, so zzz and dots stay on screen on a mount.
HEART_ROWS = (".X.X.", "XXXXX", ".XXX.", "..X..")


@dataclass(frozen=True)
class Pose:
    dy: int = 0  # The rider (and mount), down.
    dx: int = 0
    pet_dy: int = 0
    eyes_closed: bool = False  # The `_sleep` skin.
    extras: tuple[str, ...] = ()  # zzz, sweat, dots, hearts, sparkle
    step: int = 0  # Moves an effect: zzz drift, hearts and sparkles swap places.
    book: bool = False
    page: int = 0  # The book's turning page, 0 or 1.


@dataclass(frozen=True)
class Avatars:
    awake: Avatar
    asleep: Avatar  # The same look with the `_sleep` skin.
    mounted: bool


class Layers:
    """The persona's layers for one look. `avatars` is called once, on first use."""

    WINDOW = None

    def __init__(self, avatars: Callable[[], Avatars]) -> None:
        self._avatars = avatars

    @cached_property
    def avatars(self) -> Avatars:
        return self._avatars()

    @cached_property
    def body_at(self) -> tuple[int, int]:
        """Where the rider's 30x30 body canvas starts in the room."""
        return room.ART_X + 8, room.ART_Y + (0 if self.avatars.mounted else 8)

    @cached_property
    def pet_shift(self) -> int:
        """How far right the pet moves to clear the plaque."""
        box = self.avatars.awake.groups[PET].getbbox()
        return 0 if box is None else max(0, PLAQUE_CLEAR - (room.ART_X + box[0]))

    @cached_property
    def PROPS(self) -> dict[str, list[tuple[int, int, int, int]]]:  # noqa: N802 - the name personas look for
        bx, by = self.body_at
        x0, y0, x1, y1 = BOOK
        return {"focus": [(bx + x0, by + y0, bx + x1, by + y1)]}

    def background(self) -> Image.Image:
        return self._room.copy()

    @cached_property
    def _room(self) -> Image.Image:
        return room.room(self.avatars.awake.groups["background"])

    @cached_property
    def _rider_open(self) -> Image.Image:
        return self.avatars.awake.flat(MOUNT_BODY, RIDER, MOUNT_HEAD)

    @cached_property
    def _rider_closed(self) -> Image.Image:
        return self.avatars.asleep.flat(MOUNT_BODY, RIDER, MOUNT_HEAD)

    def foreground(self, pose: Pose) -> Image.Image:
        out = Image.new("RGBA", (room.W, room.H), (0, 0, 0, 0))
        rider = self._rider_closed if pose.eyes_closed else self._rider_open
        out.alpha_composite(_moved(rider, room.ART_X + pose.dx, room.ART_Y + pose.dy))
        bx, by = self.body_at
        c = Canvas(room.W, room.H)
        if pose.book:
            _book(c, bx + pose.dx, by + pose.dy, pose.page)
        out.alpha_composite(c.img)
        pet = self.avatars.awake.groups[PET]
        out.alpha_composite(_moved(pet, room.ART_X + self.pet_shift, room.ART_Y + pose.pet_dy))
        fx = Canvas(room.W, room.H)
        _extras(fx, pose, bx + pose.dx, max(by, EFFECTS_TOP) + pose.dy)
        out.alpha_composite(fx.img)
        return out

    def scene(self, pose: Pose) -> Image.Image:
        out = self.background()
        out.alpha_composite(self.foreground(pose))
        return out


def _moved(img: Image.Image, x: int, y: int) -> Image.Image:
    """`img` placed at (x, y) on a room-sized picture; what falls outside is cut."""
    out = Image.new("RGBA", (room.W, room.H), (0, 0, 0, 0))
    out.paste(img, (x, y))
    return out


def _book(c: Canvas, bx: int, by: int, page: int) -> None:
    """An open book held in front, in the rider's hands."""
    x0, y0, x1, y1 = BOOK
    for y in range(by + y0, by + y1):
        for x in range(bx + x0, bx + x1):
            edge = y == by + y1 - 1 or x in (bx + x0, bx + x1 - 1)
            c.dot(x, y, COVER if edge else PAGE)
    spine = bx + (x0 + x1) // 2
    for y in range(by + y0, by + y1 - 1):
        c.dot(spine, y, COVER)
    c.dot(spine - 2 + 3 * page, by + y0 + 1, PAGE_LINE)  # The turning page.
    c.dot(spine - 3 + 3 * page, by + y0 + 2, PAGE_LINE)


def _heart(c: Canvas, x: int, y: int) -> None:
    for row, line in enumerate(HEART_ROWS):
        for col, ch in enumerate(line):
            if ch == "X":
                c.dot(x + col, y + row, effects.HEART)
    c.dot(x + 1, y + 1, effects.HEART_SHINE)


def _sparkle(c: Canvas, x: int, y: int) -> None:
    for d in (-2, -1, 0, 1, 2):
        # pragma: no mutate block, the cross is the same mirrored
        c.dot(x + d, y, SPARKLE)
        c.dot(x, y + d, SPARKLE)


def _extras(c: Canvas, pose: Pose, bx: int, by: int) -> None:
    """Effects round the head. zzz, sweat and dots are daruma_pixel.effects'
    (placed by its cx and floor); hearts and sparkles are drawn closer in."""
    # effects draws round (cx, top), top = floor - 64. zzz: x cx+20..cx+37,
    # y top+1..top+20, right of the head and rising as it drifts. Sweat: a
    # drop at cx+18, top+20, by the left brow, clear of a weapon on the
    # right. Dots: x cx+21..cx+34, y top+4..top+15.
    if "zzz" in pose.extras:
        effects.extras(c, ("zzz",), bx + 3, by + 58 - pose.step)
    if "sweat" in pose.extras:
        effects.extras(c, ("sweat",), bx - 10, by + 57)
    if "dots" in pose.extras:
        effects.extras(c, ("dots",), bx, by + 58)
    swap = pose.step % 2
    if "hearts" in pose.extras:
        for x, y in ((bx + 2, by + 9 - swap), (bx + 21, by + 4 + swap), (bx + 24, by + 11 - swap)):
            _heart(c, x, y)
    if "sparkle" in pose.extras:
        for x, y in ((bx + 4 - swap, by + 6), (bx + 26, by + 3 + swap), (bx + 25 - swap, by + 15)):
            _sparkle(c, x, y)
