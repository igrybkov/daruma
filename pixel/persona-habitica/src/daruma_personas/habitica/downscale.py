"""Habitica's 3x sprites back to one pixel per art pixel.

Most Habitica layers are 3x pixel art: each art pixel is a 3x3 block of one
color, aligned to the avatar canvas. Some are not (some hair, a helmet, the
`zzz`, eyewear with soft edges). One rule covers both, block by block:

- A pixel with alpha below 128 is see-through.
- A block with 5 or more see-through pixels of its 9 is see-through.
- Otherwise it takes its most common opaque color; on a tie, the one met
  first, row by row.
- The result is fully opaque or fully see-through, nothing between.

On the grid every block is one color, so the rule takes that color: one
pixel per block. A block that is not one color is "non-uniform"; the build
logs how many each layer has.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from PIL import Image

BLOCK = 3
OPAQUE = 128  # Alpha at or above this is opaque.
MAJORITY = BLOCK * BLOCK // 2 + 1  # Opaque pixels a block needs to stay opaque.
CLEAR = (0, 0, 0, 0)


@dataclass(frozen=True)
class Reduced:
    image: Image.Image  # One pixel per block, alpha 0 or 255.
    non_uniform: int  # Blocks that were not one color (see-through counts as one color).


def _block(px, x0: int, y0: int) -> tuple[tuple[int, int, int, int], bool]:
    """The block's pixel by the rule, and whether the block was one color."""
    colors: Counter[tuple[int, int, int]] = Counter()
    clear = 0
    for y in range(y0, y0 + BLOCK):
        for x in range(x0, x0 + BLOCK):
            r, g, b, a = px[x, y]
            if a < OPAQUE:
                clear += 1
            else:
                colors[(r, g, b)] += 1  # pragma: no mutate (any equal step ranks colors the same)
    uniform = clear == BLOCK * BLOCK or (clear == 0 and len(colors) == 1)
    if clear >= MAJORITY:
        return CLEAR, uniform
    rgb = max(colors, key=colors.__getitem__)  # The first of the most common: a Counter keeps order.
    return (*rgb, 255), uniform  # pragma: no mutate (Pillow clips alpha to 255)


def reduce(layer: Image.Image) -> Reduced:
    """`layer` at a third of its size by the rule. Its size must be a multiple of 3."""
    layer = layer.convert("RGBA")
    if layer.width % BLOCK or layer.height % BLOCK:
        raise ValueError(f"A layer of {layer.size} is not whole 3x3 blocks")
    src = layer.load()
    out = Image.new("RGBA", (layer.width // BLOCK, layer.height // BLOCK), (0, 0, 0, 0))
    dst = out.load()
    non_uniform = 0
    for by in range(out.height):
        for bx in range(out.width):
            pixel, uniform = _block(src, bx * BLOCK, by * BLOCK)
            dst[bx, by] = pixel
            non_uniform += not uniform
    return Reduced(out, non_uniform)
