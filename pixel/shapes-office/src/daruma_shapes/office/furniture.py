"""Office furniture: a desk and a high-back chair, props drawn at a spot.

desk(img, at, colors) draws a desk whose top edge is the row `at.y`,
centered on `at.x`: a lit top, a front with two drawers. chair(img, at,
ramp, outline) draws a high-back office chair centered on `at.x`, its back
going down behind a desk whose top is the row `at.y`.
"""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image, ImageDraw

from daruma_pixel.pixelkit import Canvas, Color, Ramp, mask
from daruma_pixel.scene import Spot


@dataclass(frozen=True)
class DeskColors:
    top: Color
    edge: Color  # The lit front edge of the top.
    front: Color
    line: Color  # Drawer outlines and the seam under the top.
    handle: Color


def desk(img: Image.Image, at: Spot, colors: DeskColors, width: int | None = None) -> None:
    """A desk across `width` pixels (the whole picture by default), down to
    the bottom of the picture. A drawer panel sits near each end."""
    w, h = img.size
    width = w if width is None else width
    x0, y = at.x - width // 2, at.y
    x1 = x0 + width
    d = ImageDraw.Draw(img)
    d.rectangle((x0, y, x1, y + 4), fill=colors.top)
    d.line((x0, y, x1, y), fill=colors.edge)
    d.rectangle((x0, y + 5, x1, h), fill=colors.front)
    d.line((x0, y + 5, x1, y + 5), fill=colors.line)
    for x in (x0 + 12, x1 - 13):  # Drawer panels.
        d.rectangle((x - 9, y + 8, x + 9, h - 2), outline=colors.line)
        d.rectangle((x - 2, y + 12, x + 2, y + 12), fill=colors.handle)


def chair(img: Image.Image, at: Spot, ramp: Ramp, outline: Color) -> None:
    """A high-back office chair behind a desk whose top is at `at`."""
    c = Canvas(*img.size)
    back, d = mask(img.size)
    d.rounded_rectangle((at.x - 27, at.y - 31, at.x + 27, at.y + 4), radius=8, fill=1)
    c.paint(back, ramp)
    for x in (at.x - 18, at.x + 18):  # Stitched panels.
        c.line([(x, at.y - 25), (x, at.y)], ramp.shadow)
    c.outline(outline)
    img.alpha_composite(c.img)
