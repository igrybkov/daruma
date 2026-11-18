"""Host test: the pixel kit's mask operations, against plain per-pixel rules.

    uv run pytest tests/test_pixelkit.py

The kit works on whole masks with Pillow. Each test here spells out the
same rule pixel by pixel and checks both agree on random masks.
"""

from __future__ import annotations

import random
import unittest

try:
    from PIL import Image, ImageDraw
except ImportError:  # pragma: no cover
    Image = None

if Image is not None:
    from daruma_personas.daruma import doll
    from daruma_pixel import personas, pixelkit

W, H = 30, 24
SIDES = ((1, 0), (-1, 0), (0, 1), (0, -1))


def _random_mask(rng: random.Random, size=(W, H)) -> Image.Image:
    m = Image.new("1", size, 0)
    d = ImageDraw.Draw(m)
    for _ in range(rng.randint(1, 4)):
        x, y = rng.randint(-5, size[0]), rng.randint(-5, size[1])
        box = (x, y, x + rng.randint(1, 14), y + rng.randint(1, 14))
        (d.ellipse if rng.random() < 0.5 else d.rectangle)(box, fill=1)
    for _ in range(rng.randint(0, 12)):  # Lone pixels, notches and tips.
        m.putpixel((rng.randrange(size[0]), rng.randrange(size[1])), rng.randint(0, 1))
    return m


def _set(m: Image.Image, x: int, y: int) -> bool:
    return 0 <= x < m.width and 0 <= y < m.height and bool(m.getpixel((x, y)))


def _bits(m: Image.Image) -> list[bool]:
    return [_set(m, x, y) for y in range(m.height) for x in range(m.width)]


def _paint_color(m, below, ramp, shade, x, y):
    """The color paint() gives pixel (x, y) of mask m, painted over `below`."""
    color = ramp.base
    if shade:
        if not _set(m, x + 2, y + 2) or not _set(m, x + 1, y + 2):
            color = ramp.shadow
        elif ramp.light and not _set(m, x - 2, y - 2) and _set(m, x + 3, y + 3):
            color = ramp.light
    if ramp.line:
        for nx, ny in ((x + dx, y + dy) for dx, dy in SIDES):
            if not _set(m, nx, ny) and _set(below, nx, ny):
                color = ramp.line
    return color


@unittest.skipIf(Image is None, "needs Pillow")
class Canvas(unittest.TestCase):
    def test_paint_shades_and_lines_like_the_pixel_rule(self):
        rng = random.Random(1)
        for i in range(60):
            c = pixelkit.Canvas(W, H)
            c.paint(_random_mask(rng), pixelkit.Ramp((9, 9, 9), (8, 8, 8)), shade=False)
            below, before = c.body.copy(), c.img.copy()
            m = _random_mask(rng)
            ramp = pixelkit.Ramp((1, 2, 3), (4, 5, 6), rng.choice([None, (7, 8, 9)]), rng.choice([None, (10, 11, 12)]))
            shade = rng.random() < 0.8
            c.paint(m, ramp, shade)
            for y in range(H):
                for x in range(W):
                    want = (
                        (*_paint_color(m, below, ramp, shade, x, y), 255) if _set(m, x, y) else before.getpixel((x, y))
                    )
                    self.assertEqual(c.img.getpixel((x, y)), want, f"case {i} at {(x, y)}")
                    self.assertEqual(_set(c.body, x, y), _set(m, x, y) or _set(below, x, y))

    def test_outline_rings_the_silhouette(self):
        rng = random.Random(2)
        for i in range(60):
            c = pixelkit.Canvas(W, H)
            c.paint(_random_mask(rng), pixelkit.Ramp((1, 1, 1), (2, 2, 2)))
            body, before = c.body.copy(), c.img.copy()
            c.outline((5, 5, 5))
            for y in range(H):
                for x in range(W):
                    edge = not _set(body, x, y) and any(_set(body, x + dx, y + dy) for dx, dy in SIDES)
                    want = (5, 5, 5, 255) if edge else before.getpixel((x, y))
                    self.assertEqual(c.img.getpixel((x, y)), want, f"case {i} at {(x, y)}")
                    self.assertEqual(_set(c.body, x, y), edge or _set(body, x, y))


@unittest.skipIf(Image is None, "needs Pillow")
class Masks(unittest.TestCase):
    def test_subtract_intersect_and_moved(self):
        rng = random.Random(3)
        for _ in range(40):
            a, b = _random_mask(rng), _random_mask(rng)
            dx, dy = rng.randint(-3, 3), rng.randint(-3, 3)
            pts = [(x, y) for y in range(H) for x in range(W)]
            self.assertEqual(_bits(pixelkit.subtract(a, b)), [_set(a, *p) and not _set(b, *p) for p in pts])
            self.assertEqual(_bits(pixelkit.intersect(a, b)), [_set(a, *p) and _set(b, *p) for p in pts])
            self.assertEqual(_bits(pixelkit.moved(a, dx, dy)), [_set(a, x + dx, y + dy) for x, y in pts])

    def test_shear_rows_moves_each_row_whole_pixels(self):
        rng = random.Random(4)
        for _ in range(20):
            m = _random_mask(rng)
            pivot, per_row, cap = rng.randint(0, H), rng.uniform(-1, 1), rng.randint(1, 5)
            out = pixelkit.shear_rows(m, pivot, per_row, cap)
            for y in range(H):
                s = max(-cap, min(cap, round((y - pivot) * per_row)))
                self.assertEqual([_set(out, x, y) for x in range(W)], [_set(m, x - s, y) for x in range(W)], f"row {y}")


@unittest.skipIf(Image is None, "needs Pillow")
class DollMasks(unittest.TestCase):
    """The doll's own mask steps, on the doll's canvas size."""

    def test_smooth_drops_tips_and_fills_notches(self):
        rng = random.Random(5)
        for i in range(30):
            m = _random_mask(rng, (doll.W, doll.H))
            got = doll._smooth(m.copy())
            want = Image.new("1", m.size, 0)
            for y in range(doll.H):
                for x in range(doll.W):
                    n = sum(_set(m, x + dx, y + dy) for dx, dy in SIDES)
                    want.putpixel((x, y), 1 if (n >= 2 if _set(m, x, y) else n >= 3) else 0)
            self.assertEqual(_bits(got), _bits(doll._trim_caps(want)), f"case {i}")

    def test_trim_caps_drops_a_short_end_row(self):
        m = Image.new("1", (doll.W, doll.H), 0)
        m.paste(1, (20, 10, 22, 11))  # A 2-pixel nub ...
        m.paste(1, (10, 11, 30, 14))  # ... on a 20-pixel row.
        m.paste(1, (15, 14, 25, 15))  # A 10-pixel bottom row: kept, not 3x shorter.
        out = doll._trim_caps(m.copy())
        self.assertFalse(any(_set(out, x, 10) for x in range(doll.W)))
        self.assertEqual(_bits(out.crop((0, 11, doll.W, doll.H))), _bits(m.crop((0, 11, doll.W, doll.H))))

    def test_mirror_copies_the_left_half(self):
        m = _random_mask(random.Random(6), (doll.W, doll.H))
        out = doll._mirror(m)
        for y in range(doll.H):
            for x in range(doll.W):
                src = 2 * doll.CX - x if x > doll.CX and 2 * doll.CX - x >= 0 else x
                self.assertEqual(_set(out, x, y), _set(m, src, y), (x, y))

    def test_crescent_is_the_far_rim(self):
        m = _random_mask(random.Random(7), (doll.W, doll.H))
        out = doll._crescent(m, 3, 2)
        for y in range(doll.H):
            for x in range(doll.W):
                self.assertEqual(_set(out, x, y), _set(m, x, y) and not _set(m, x + 3, y + 2), (x, y))


@unittest.skipIf(Image is None, "needs Pillow")
class Pictures(unittest.TestCase):
    def test_cached_picture_draws_once_and_hands_out_copies(self):
        calls = []

        @pixelkit.cached_picture
        def draw(color):
            calls.append(color)
            return Image.new("RGBA", (2, 2), color)

        first = draw((1, 2, 3, 255))
        first.putpixel((0, 0), (0, 0, 0, 0))
        again = draw((1, 2, 3, 255))
        self.assertEqual(calls, [(1, 2, 3, 255)])
        self.assertEqual(again.getpixel((0, 0)), (1, 2, 3, 255))
        self.assertIsNot(first, again)

    def test_rgb565_shifts_and_marks_see_through(self):
        img = Image.new("RGBA", (3, 1))
        img.putpixel((0, 0), (255, 255, 255, 255))
        img.putpixel((1, 0), (8, 4, 9, 128))
        img.putpixel((2, 0), (200, 100, 50, 127))
        self.assertEqual(personas.rgb565(img), bytes((31, 63, 31, 1, 1, 1, 255, 255, 255)))


if __name__ == "__main__":
    unittest.main()
