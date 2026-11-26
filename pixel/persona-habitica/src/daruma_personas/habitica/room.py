"""The room: the avatar's Habitica background, widened to fill the screen.

The background is 47x49 art pixels. At 5x, 48 rows fill the BOX-3's 240
lines, so the top row (sky) is cut. 64 columns fill its 320, so the
background stands in the middle with plain sides: each side row takes the
sky color above the horizon and the ground color below it, both taken
from the background. Plain sides also repeat cleanly on a wider screen,
where Habitica's own art would show seams.

Without a background, the whole room is the plain sky and ground.
"""

from __future__ import annotations

from collections import Counter

from PIL import Image

W, H = 64, 48
ART_X, ART_Y = 8, -1  # Where the avatar's 47x49 canvas sits in the room.
SKY = (150, 196, 236)  # Without a background.
GROUND = (96, 156, 76)


def _mode(colors) -> tuple[int, int, int]:
    """The most common color; on a tie, the first."""
    counts = Counter(colors)
    return max(counts, key=counts.__getitem__)


def _row(img: Image.Image, y: int) -> list[tuple[int, int, int]]:
    return [img.getpixel((x, y))[:3] for x in range(img.width)]


def _distance(a, b) -> int:
    return sum((a[i] - b[i]) ** 2 for i in range(3))


def side_colors(bg: Image.Image) -> list[tuple[int, int, int]]:
    """Per room row, the plain color of the sides: sky above the horizon, ground below.

    Sky is the top row's most common color, ground the bottom row's. The
    horizon is the first row whose most common color is nearer the ground.
    """
    rows = [_mode(_row(bg, y)) for y in range(bg.height)]
    sky, ground = rows[0], rows[-1]
    nearer_ground = (y for y, color in enumerate(rows) if _distance(color, ground) < _distance(color, sky))
    horizon = next(nearer_ground, len(rows))  # One color all the way down: all sky.
    return [sky if y < horizon else ground for y in range(bg.height)]


def room(background: Image.Image | None) -> Image.Image:
    """The 64x48 room around the avatar's background (a 47x49 picture, or None)."""
    if background is None or background.getbbox() is None:
        return _sides([SKY] * (H * 2 // 3) + [GROUND] * (H - H * 2 // 3))
    bg = background.convert("RGBA").crop((0, -ART_Y, background.width, background.height))
    out = _sides(side_colors(bg))
    out.alpha_composite(bg, (ART_X, 0))
    return out


def _sides(colors: list[tuple[int, int, int]]) -> Image.Image:
    """The room filled row by row with one color each."""
    column = Image.new("RGB", (1, len(colors)))
    column.putdata(colors)
    return column.resize((W, len(colors)), Image.NEAREST).convert("RGBA")
