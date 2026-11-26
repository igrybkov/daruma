"""Fixture sprites: a made-up avatar in Habitica's sprite format, drawn here.

Nothing here is traced or copied from Habitica's art. The pictures only
share the format: the canvas sizes, the offsets, the names and the 3x
pixel scale. They let the compositor, the tests and the public persona run
without one Habitica sprite in the repository.

The figure: a person with a skin, two hair layers, a shirt in a slim and a
broad form, armor in both forms, a helmet with a plume, a sword, a small
round pet, a pony to ride and a meadow behind. Some pieces are off the 3x
grid on purpose, as some of Habitica's are: hair strands one screen pixel
wide, a plume with soft alpha, a sword shifted by one pixel, and `zzz`
drawn at screen size with soft alpha.
"""

from __future__ import annotations

from functools import cache

from PIL import Image, ImageDraw

from .sources import MemorySource

# The look, in the shape of Habitica's user object. All values are made up.
USER = {
    "preferences": {
        "skin": "fixture",
        "shirt": "fixture",
        "size": "slim",
        "chair": "none",
        "background": "fixture_meadow",
        "costume": False,
        "sleep": False,
        "hair": {"color": "fixture", "base": 1, "bangs": 1, "mustache": 0, "beard": 0, "flower": 0},
    },
    "items": {
        "currentPet": "Fixture-Blob",
        "currentMount": "",
        "gear": {
            "equipped": {
                "armor": "armor_fixture_1",
                "head": "head_fixture_1",
                "weapon": "weapon_fixture_1",
                "shield": "shield_base_0",
                "back": "back_base_0",
            },
        },
    },
    "stats": {"buffs": {}},
}
MOUNT = "Fixture-Pony"  # Set items.currentMount to this to ride.

SKIN = (232, 182, 140)
SKIN_SHADE = (200, 146, 108)
EYE = (40, 30, 36)
MOUTH = (186, 92, 92)
HAIR = (120, 66, 160)  # A purple no skin tone is mistaken for.
HAIR_DARK = (88, 46, 122)
SHIRT = (64, 150, 132)
SHIRT_SHADE = (44, 116, 102)
METAL = (176, 184, 198)
METAL_DARK = (122, 130, 146)
BELT = (110, 72, 44)
SHOE = (78, 52, 40)
PLUME = (214, 60, 70)
BLADE = (226, 232, 240)
HILT = (150, 100, 40)
PET = (120, 200, 96)
PET_SHADE = (84, 160, 72)
PONY = (196, 150, 104)
PONY_SHADE = (156, 112, 76)
MANE = (90, 60, 44)
ZZZ = (240, 244, 255)

SKY = ((150, 196, 236), (168, 208, 240), (190, 222, 244))
HILL = (120, 170, 120)
GRASS = (96, 156, 76)
GRASS_EDGE = (70, 126, 58)
PATH = (196, 170, 120)
TRUNK = (110, 76, 50)
LEAVES = (60, 118, 64)
ROCK = (140, 140, 150)
FLOWER = (240, 220, 90)

BODY = 30  # Body layers are 90x90 screen pixels: 30x30 art pixels.


def _art(w: int, h: int) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img)


def _three(img: Image.Image) -> Image.Image:
    """Art pixels to screen pixels: each a 3x3 block, as Habitica's sprites are."""
    return img.resize((img.width * 3, img.height * 3), Image.NEAREST)


def _boxes(d: ImageDraw.ImageDraw, color, *boxes: tuple[int, int, int, int]) -> None:
    for box in boxes:
        d.rectangle(box, fill=color)


def skin(asleep: bool) -> Image.Image:
    """Head, hands, legs and shoes. Asleep, the eyes are closed."""
    img, d = _art(BODY, BODY)
    _boxes(d, SKIN, (11, 13, 18, 20), (9, 23, 10, 24), (19, 23, 20, 24))
    _boxes(d, SKIN_SHADE, (11, 20, 18, 20), (12, 26, 13, 27), (16, 26, 17, 27))
    _boxes(d, SHOE, (11, 28, 13, 28), (16, 28, 18, 28))
    if asleep:
        _boxes(d, SKIN_SHADE, (12, 16, 13, 16), (16, 16, 17, 16))
    else:
        _boxes(d, EYE, (13, 16, 13, 16), (16, 16, 16, 16))
    _boxes(d, MOUTH, (14, 18, 15, 18))
    return _three(img)


def head_0() -> Image.Image:
    img, d = _art(BODY, BODY)
    _boxes(d, SKIN_SHADE, (10, 16, 10, 17), (19, 16, 19, 17))  # Ears.
    return _three(img)


def shirt(broad: bool) -> Image.Image:
    img, d = _art(BODY, BODY)
    x0, x1 = (11, 18) if broad else (12, 17)
    _boxes(d, SHIRT, (x0, 21, x1, 25), (x0 - 2, 21, x0 - 1, 22), (x1 + 1, 21, x1 + 2, 22))
    _boxes(d, SHIRT_SHADE, (x0, 25, x1, 25))
    return _three(img)


def armor(broad: bool) -> Image.Image:
    img, d = _art(BODY, BODY)
    x0, x1 = (11, 18) if broad else (12, 17)
    _boxes(d, METAL, (x0, 21, x1, 24), (x0 - 2, 21, x0 - 1, 22), (x1 + 1, 21, x1 + 2, 22))
    _boxes(d, METAL_DARK, (x0, 24, x1, 24), (x0 + 2, 22, x1 - 2, 22))
    _boxes(d, BELT, (x0, 25, x1, 25))
    return _three(img)


def hair_bangs() -> Image.Image:
    img, d = _art(BODY, BODY)
    _boxes(d, HAIR, (11, 13, 18, 14), (11, 15, 11, 16), (18, 15, 18, 15))
    _boxes(d, HAIR_DARK, (13, 14, 14, 14))
    big = _three(img)
    draw = ImageDraw.Draw(big)
    # Off the grid: a strand one screen pixel wide (too thin to keep), and
    # one two pixels wide (kept).
    draw.line((40, 45, 40, 50), fill=(*HAIR, 255))
    draw.rectangle((51, 45, 52, 50), fill=(*HAIR_DARK, 255))
    return big


def hair_base() -> Image.Image:
    img, d = _art(BODY, BODY)
    _boxes(d, HAIR, (11, 11, 18, 12), (10, 13, 10, 19), (19, 13, 19, 19))
    _boxes(d, HAIR_DARK, (10, 18, 10, 19), (19, 18, 19, 19))
    return _three(img)


def helmet() -> Image.Image:
    img, d = _art(BODY, BODY)
    _boxes(d, METAL, (10, 10, 19, 13))
    _boxes(d, METAL_DARK, (10, 13, 19, 13), (14, 10, 15, 10))
    big = _three(img)
    draw = ImageDraw.Draw(big)
    # A plume with soft alpha, off the grid.
    draw.rectangle((40, 20, 49, 29), fill=(*PLUME, 200))
    draw.rectangle((43, 16, 47, 19), fill=(*PLUME, 100))
    return big


def sword() -> Image.Image:
    img, d = _art(BODY, BODY)
    _boxes(d, BLADE, (21, 12, 21, 22))
    _boxes(d, HILT, (20, 23, 22, 23), (21, 24, 21, 25))
    big = _three(img)
    # One screen pixel to the right: every block of it is off the grid.
    shifted = Image.new("RGBA", big.size, (0, 0, 0, 0))
    shifted.paste(big, (1, 0))
    return shifted


def zzz() -> Image.Image:
    """40x40 at screen size, soft alpha: never on the grid."""
    img, d = _art(40, 40)
    for x, y, size, alpha in ((22, 2, 8, 255), (30, 12, 6, 200), (34, 20, 4, 140)):
        d.line((x, y, x + size, y), fill=(*ZZZ, alpha), width=2)
        d.line((x + size, y, x, y + size), fill=(*ZZZ, alpha), width=2)
        d.line((x, y + size, x + size, y + size), fill=(*ZZZ, alpha), width=2)
    return img


def pet() -> Image.Image:
    """A round pet, 81x99 like Habitica's, standing at its bottom left."""
    img, d = _art(27, 33)
    d.ellipse((7, 24, 17, 32), fill=PET)
    _boxes(d, PET_SHADE, (8, 31, 16, 32))
    _boxes(d, PET, (8, 22, 9, 24), (15, 22, 16, 24))  # Ears.
    _boxes(d, EYE, (10, 27, 10, 27), (14, 27, 14, 27))
    return _three(img)


def mount_body() -> Image.Image:
    """A pony's body, 135x135 like Habitica's mounts; its back meets the rider's hips."""
    img, d = _art(45, 45)
    _boxes(d, PONY, (4, 20, 26, 27))
    _boxes(d, PONY_SHADE, (4, 27, 26, 27), (5, 28, 6, 35), (23, 28, 24, 35), (9, 28, 10, 34), (19, 28, 20, 34))
    _boxes(d, MANE, (1, 20, 3, 21), (0, 22, 1, 27))  # Tail.
    return _three(img)


def mount_head() -> Image.Image:
    """The pony's neck and head, drawn in front of the rider."""
    img, d = _art(45, 45)
    _boxes(d, PONY, (24, 11, 28, 22), (27, 9, 33, 14))
    _boxes(d, MANE, (23, 9, 24, 19))
    _boxes(d, EYE, (30, 10, 30, 10))
    _boxes(d, PONY_SHADE, (32, 13, 33, 14))
    return _three(img)


def background() -> Image.Image:
    """A meadow, 141x147. Not made to tile: a rock at the left, a tree at the right."""
    img, d = _art(47, 49)
    for i, color in enumerate(SKY):
        _boxes(d, color, (0, i * 9, 46, i * 9 + 8))
    _boxes(d, SKY[2], (0, 27, 46, 30))
    d.polygon([(0, 31), (8, 25), (16, 29), (27, 22), (38, 28), (46, 24), (46, 34), (0, 34)], fill=HILL)
    _boxes(d, GRASS, (0, 34, 46, 48))
    _boxes(d, GRASS_EDGE, (0, 34, 46, 34))
    d.polygon([(19, 48), (22, 35), (25, 35), (30, 48)], fill=PATH)
    _boxes(d, TRUNK, (40, 26, 41, 38))
    d.ellipse((35, 14, 46, 27), fill=LEAVES)
    d.ellipse((1, 38, 6, 42), fill=ROCK)
    for x, y in ((10, 44), (34, 41), (44, 46)):
        _boxes(d, FLOWER, (x, y, x, y))
    return _three(img)


@cache
def pictures() -> dict[str, Image.Image]:
    """Every fixture sprite by its name in USER's look (plus the pony and both sizes)."""
    return {
        "background_fixture_meadow": background(),
        "skin_fixture": skin(asleep=False),
        "skin_fixture_sleep": skin(asleep=True),
        "slim_shirt_fixture": shirt(broad=False),
        "broad_shirt_fixture": shirt(broad=True),
        "head_0": head_0(),
        "slim_armor_fixture_1": armor(broad=False),
        "broad_armor_fixture_1": armor(broad=True),
        "hair_bangs_1_fixture": hair_bangs(),
        "hair_base_1_fixture": hair_base(),
        "head_fixture_1": helmet(),
        "weapon_fixture_1": sword(),
        "zzz": zzz(),
        "Pet-Fixture-Blob": pet(),
        f"Mount_Body_{MOUNT}": mount_body(),
        f"Mount_Head_{MOUNT}": mount_head(),
    }


def source() -> MemorySource:
    """The fixture sprites as a sprite source."""
    return MemorySource(pictures())
