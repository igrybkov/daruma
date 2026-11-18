"""Tiny pixel-art toolkit: crisp shapes on a low-res canvas, auto outline, auto shading.

Shapes are drawn without anti-aliasing on a logical canvas (106x80 for the
BOX-3 at 3x). Each body part is its own mask, so poses can move, mirror or
rotate a part as geometry and still land on a hard pixel grid.
"""

from __future__ import annotations

import functools
import math
from collections.abc import Callable
from dataclasses import dataclass, field

from PIL import Image, ImageChops, ImageDraw

Color = tuple[int, int, int]
Point = tuple[float, float]


@dataclass(frozen=True)
class Ramp:
    """Three tones of one material. Light comes from the top left."""

    base: Color
    shadow: Color
    light: Color | None = None
    line: Color | None = None  # Inner contour where this part overlaps another.


def mask(size: tuple[int, int]) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("1", size, 0)
    return img, ImageDraw.Draw(img)


def ellipse(d: ImageDraw.ImageDraw, cx: float, cy: float, rx: float, ry: float) -> None:
    d.ellipse((round(cx - rx), round(cy - ry), round(cx + rx), round(cy + ry)), fill=1)


def poly(d: ImageDraw.ImageDraw, points: list[Point]) -> None:
    d.polygon([(round(x), round(y)) for x, y in points], fill=1)


def rotate(points: list[Point], pivot: Point, degrees: float) -> list[Point]:
    a = math.radians(degrees)
    c, s = math.cos(a), math.sin(a)
    px, py = pivot
    return [(px + (x - px) * c - (y - py) * s, py + (x - px) * s + (y - py) * c) for x, y in points]


def shear_rows(m: Image.Image, pivot_y: int, per_row: float, max_shift: int = 99) -> Image.Image:
    """Shift each row sideways in proportion to its distance from pivot_y.

    Bends a part around a hinge, the pixel-art way: no resampling, no blur.
    """
    w, h = m.size
    out = Image.new("1", m.size, 0)
    for y in range(h):
        dx = max(-max_shift, min(max_shift, round((y - pivot_y) * per_row)))
        out.paste(m.crop((0, y, w, y + 1)), (dx, y))
    return out


def shift(m: Image.Image, dx: int, dy: int) -> Image.Image:
    out = Image.new("1", m.size, 0)
    out.paste(m, (dx, dy))
    return out


def moved(m: Image.Image, dx: int, dy: int) -> Image.Image:
    """The mask seen from (dx, dy) away: out[x, y] is m[x + dx, y + dy], empty off the edge."""
    return shift(m, -dx, -dy)


def touching(m: Image.Image) -> Image.Image:
    """Pixels with at least one side neighbour (left, right, up, down) in m."""
    out = moved(m, 1, 0)
    for dx, dy in ((-1, 0), (0, 1), (0, -1)):
        out = ImageChops.logical_or(out, moved(m, dx, dy))
    return out


def subtract(a: Image.Image, b: Image.Image) -> Image.Image:
    """Pixels of a that are not in b."""
    return ImageChops.logical_and(a, ImageChops.logical_xor(b, Image.new("1", b.size, 1)))


def intersect(a: Image.Image, b: Image.Image) -> Image.Image:
    return ImageChops.logical_and(a, b)


@dataclass
class Canvas:
    """RGBA pixel canvas plus a silhouette mask of everything painted."""

    w: int
    h: int
    img: Image.Image = field(init=False)
    body: Image.Image = field(init=False)

    def __post_init__(self) -> None:
        self.img = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        self.body = Image.new("1", (self.w, self.h), 0)

    def paint(self, m: Image.Image, ramp: Ramp, shade: bool = True) -> None:
        """Fill a mask with a material: base, shadow toward bottom-right, light toward top-left.

        A pixel is shadow when the mask ends within (+2, +2) or (+1, +2) of
        it; else light when the mask ends at (-2, -2) but goes on to (+3, +3).
        An edge pixel next to an earlier part takes the ramp's line color.
        """
        layers = [(m, ramp.base)]
        if shade:
            dark = subtract(m, intersect(moved(m, 2, 2), moved(m, 1, 2)))
            layers.append((dark, ramp.shadow))
            if ramp.light:
                lit = subtract(subtract(m, dark), moved(m, -2, -2))
                layers.append((intersect(lit, moved(m, 3, 3)), ramp.light))
        if ramp.line:
            layers.append((intersect(m, touching(subtract(self.body, m))), ramp.line))
        for where, color in layers:
            self.img.paste((*color, 255), mask=where)
        self.body.paste(ImageChops.logical_or(self.body, m))

    def dot(self, x: int, y: int, color: Color) -> None:
        if 0 <= x < self.w and 0 <= y < self.h:
            self.img.putpixel((x, y), (*color, 255))
            self.body.putpixel((x, y), 1)

    def line(self, points: list[Point], color: Color) -> None:
        d = ImageDraw.Draw(self.img)
        d.line([(round(x), round(y)) for x, y in points], fill=(*color, 255), width=1)

    def outline(self, color: Color) -> None:
        """1-px outline around the whole silhouette."""
        edge = subtract(touching(self.body), self.body)
        self.img.paste((*color, 255), mask=edge)
        self.body.paste(ImageChops.logical_or(self.body, edge))


def cached_picture[**P](draw: Callable[P, Image.Image]) -> Callable[P, Image.Image]:
    """Draw each picture once: `draw` must give the same picture for the same
    (hashable) arguments. Every call gets its own copy to change."""
    memo = functools.cache(draw)

    @functools.wraps(draw)
    def picture(*args: P.args, **kwargs: P.kwargs) -> Image.Image:
        return memo(*args, **kwargs).copy()

    return picture


def upscale(img: Image.Image, factor: int) -> Image.Image:
    return img.resize((img.width * factor, img.height * factor), Image.NEAREST)
