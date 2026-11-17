"""Tiny pixel-art toolkit: crisp shapes on a low-res canvas, auto outline, auto shading.

Shapes are drawn without anti-aliasing on a logical canvas (106x80 for the
BOX-3 at 3x). Each body part is its own mask, so poses can move, mirror or
rotate a part as geometry and still land on a hard pixel grid.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from PIL import Image, ImageDraw

Color = tuple[int, int, int]
Point = tuple[float, float]


@dataclass
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
    src, dst = m.load(), out.load()
    for y in range(h):
        shift = max(-max_shift, min(max_shift, round((y - pivot_y) * per_row)))
        for x in range(w):
            if src[x, y]:
                nx = x + shift
                if 0 <= nx < w:
                    dst[nx, y] = 1
    return out


def shift(m: Image.Image, dx: int, dy: int) -> Image.Image:
    out = Image.new("1", m.size, 0)
    out.paste(m, (dx, dy))
    return out


def subtract(a: Image.Image, b: Image.Image) -> Image.Image:
    out = a.copy()
    pa, pb = out.load(), b.load()
    w, h = a.size
    for y in range(h):
        for x in range(w):
            if pb[x, y]:
                pa[x, y] = 0
    return out


def intersect(a: Image.Image, b: Image.Image) -> Image.Image:
    out = Image.new("1", a.size, 0)
    pa, pb, po = a.load(), b.load(), out.load()
    w, h = a.size
    for y in range(h):
        for x in range(w):
            if pa[x, y] and pb[x, y]:
                po[x, y] = 1
    return out


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
        """Fill a mask with a material: base, shadow toward bottom-right, light toward top-left."""
        px, mp, bp = self.img.load(), m.load(), self.body.load()
        below = self.body.copy().load()
        w, h = self.w, self.h

        def inside(x: int, y: int) -> bool:
            return 0 <= x < w and 0 <= y < h and mp[x, y]

        for y in range(h):
            for x in range(w):
                if not mp[x, y]:
                    continue
                color = ramp.base
                if shade:
                    if not inside(x + 2, y + 2) or not inside(x + 1, y + 2):
                        color = ramp.shadow
                    elif ramp.light and (not inside(x - 2, y - 2)) and inside(x + 3, y + 3):
                        color = ramp.light
                # Inner contour: an edge pixel sitting on top of an earlier part.
                if ramp.line:
                    for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                        if not inside(nx, ny) and 0 <= nx < w and 0 <= ny < h and below[nx, ny]:
                            color = ramp.line
                            break
                px[x, y] = (*color, 255)
                bp[x, y] = 1

    def dot(self, x: int, y: int, color: Color) -> None:
        if 0 <= x < self.w and 0 <= y < self.h:
            self.img.putpixel((x, y), (*color, 255))
            self.body.putpixel((x, y), 1)

    def line(self, points: list[Point], color: Color) -> None:
        d = ImageDraw.Draw(self.img)
        d.line([(round(x), round(y)) for x, y in points], fill=(*color, 255), width=1)

    def outline(self, color: Color) -> None:
        """1-px outline around the whole silhouette."""
        px, bp = self.img.load(), self.body.load()
        edge = []
        for y in range(self.h):
            for x in range(self.w):
                if bp[x, y]:
                    continue
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if 0 <= nx < self.w and 0 <= ny < self.h and bp[nx, ny]:
                        edge.append((x, y))
                        break
        for x, y in edge:
            px[x, y] = (*color, 255)
        for x, y in edge:
            bp[x, y] = 1


def upscale(img: Image.Image, factor: int) -> Image.Image:
    return img.resize((img.width * factor, img.height * factor), Image.NEAREST)
