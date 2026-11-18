"""The Sprite byte format: encoding pictures, and animation frames as deltas.

Plain Python (Pillow only, no ESPHome), so host tests can use it
(tests/test_frames.py). sprite.py turns the results into C++.

Pictures
--------
A picture is stored as runs, row by row, with a small palette. A run is
either one color, or "same as the row above" for its length, which turns
vertical stripes and flat blocks into a byte per row. Pixel art and
flat-color pictures shrink 10-30 times compared to plain RGB565. Runs never
cross the end of a row.

Each picture gets k index bits, enough for its palette plus its special
codes. With k < 8, a run is one byte: the index in the top k bits and the
length in the low 8 - k bits. A length field of 0 means a long run: the
next byte holds the length minus 2^(8 - k). With k = 8, a run is two bytes:
index, length - 1.

Pixels with alpha below 128 are see-through. They get their own palette
index, which the C++ side (sprite.h) reports as clear.

Codes after the palette:
- a whole picture: `colors` is "same as above";
- a patch (below): `colors` is "keep", `colors + 1` is "same as above".

Frame sets
----------
An animation's frames are often the same picture with a few pixels moved.
encode_set() stores a persona's frames together, with one shared palette. Each
frame is either a whole picture (a keyframe), or a patch on an earlier
frame (its base): the box where the two differ, where "keep" means the
base's pixel. A frame is drawn by drawing its base chain first, at most
MAX_DEPTH patches deep.

Gray and mono
-------------
For gray4 and mono screens (daruma: display_profile: colors), pictures
are reduced to the screen's grays first: each pixel to its nearest gray by
luminance, the same rule the device uses for what it paints itself
(profile.h quantize_gray). Pixel art at this size reads better that way
than dithered: a dither turns mid-tone walls and fur into noise.
"""

from __future__ import annotations

import math
import sys
from array import array
from collections import Counter
from dataclasses import dataclass
from itertools import compress
from operator import ne

CLEAR = -1  # A see-through pixel, among RGB565 values.
_KEEP = -2  # A patch pixel equal to its base's.

MAX_DEPTH = 4  # Patches on top of a keyframe, at most.
FIRST_DEPTH = 2  # The same for an animation's first frame: it is shown out of order.
CANDIDATES = 3  # Other bases tried per frame, the closest by changed pixels.
PREV_FACTOR = 0.9  # Cost weight of a patch on the frame before: it draws fastest.


def rgb565(r: int, g: int, b: int) -> int:
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)


def gray_for(mode: str, r: int, g: int, b: int) -> int:
    """profile.h quantize_gray(): 0/255 for mono, 0/85/170/255 for gray4."""
    y = (r * 299 + g * 587 + b * 114) // 1000
    return (255 if y >= 128 else 0) if mode == "mono" else ((y + 42) // 85) * 85


def reduce_colors(img, mode: str):
    """The picture in the screen's grays (`mode` gray4 or mono); unchanged
    for full color. See-through pixels stay see-through."""
    if mode not in ("gray4", "mono"):
        return img
    img = img.convert("RGBA")
    out = img.copy()
    src, dst = img.load(), out.load()
    for y in range(img.height):
        for x in range(img.width):
            r, g, b, a = src[x, y]
            if a >= 128:
                gray = gray_for(mode, r, g, b)
                dst[x, y] = (gray, gray, gray, 255)  # pragma: no mutate (Pillow clamps an alpha of 256)
    return out


def _screen_value(rgba: int, mode: str) -> int:
    """One RGBA pixel, packed in a native int, as screen_pixels() sees it."""
    r, g, b, a = rgba.to_bytes(4, sys.byteorder)
    if a < 128:
        return CLEAR
    if mode in ("gray4", "mono"):
        r = g = b = gray_for(mode, r, g, b)
    return rgb565(r, g, b)


def screen_pixels(img, mode: str = "full") -> list[int]:
    """The picture as the screen sees it: RGB565 per pixel, CLEAR for see-through.
    `mode` reduces the colors first, as reduce_colors() does. Pixel art has
    few colors, so each distinct one is worked out once."""
    raw = array("I", img.convert("RGBA").tobytes())
    value = {rgba: _screen_value(rgba, mode) for rgba in set(raw)}
    return list(map(value.__getitem__, raw))


def _bits(codes: int) -> int:
    return max(1, math.ceil(math.log2(codes)))


def _runs(codes: list[int], w: int, h: int, copy: int, bits: int) -> list[int]:
    """Row-by-row runs of palette codes, with `copy` for "same as the row above"."""
    short = (1 << (8 - bits)) - 1  # Longest run in one byte (k < 8).
    data: list[int] = []

    def put(i: int, n: int) -> None:
        while n > 0:
            # At 8 bits the long-run branch below writes the same two bytes.
            if bits == 8:  # pragma: no mutate
                take = min(n, 256)
                data.extend((i, take - 1))
            elif n <= short:
                take = n
                data.append((i << (8 - bits)) | n)
            else:
                take = min(n, short + 1 + 255)
                data.extend((i << (8 - bits), take - short - 1))
            n -= take

    for y in range(h):
        row = codes[y * w : (y + 1) * w]  # pragma: no mutate (a longer slice: the loops stop at w)
        above = codes[(y - 1) * w : y * w] if y else None
        x = 0
        while x < w:
            run = 1
            while x + run < w and row[x + run] == row[x]:
                run += 1
            same = 0
            if above is not None:
                while x + same < w and row[x + same] == above[x + same]:
                    same += 1
            if same >= run:  # pragma: no mutate (on a tie both runs decode the same)
                put(copy, same)
                x += same
            else:
                put(row[x], run)
                x += run
    return data


def encode_image(img, label: str, mode: str = "full") -> tuple[int, int, int, int, list[int], list[int]]:
    """A whole picture with its own palette: width, height, index bits, clear
    index (-1 if none), palette (RGB565) and data. `label` names it in errors.
    `mode` reduces the colors first (reduce_colors)."""
    w, h = img.size
    pixels = screen_pixels(img, mode)
    palette: list[int] = []
    index: dict[int, int] = {}
    for p in pixels:
        if p not in index:
            index[p] = len(palette)
            palette.append(p)
    copy = len(palette)
    if copy + 1 > 256:
        raise ValueError(f"{label}: {len(palette)} colors at RGB565; a sprite takes at most 255")
    bits = _bits(copy + 1)
    data = _runs([index[p] for p in pixels], w, h, copy, bits)
    return w, h, bits, index.get(CLEAR, -1), [0 if c == CLEAR else c for c in palette], data


# --- Frame sets -------------------------------------------------------------


@dataclass
class SetFrame:
    """One stored frame of a set. A keyframe has base -1 and covers the
    whole frame; a patch covers w x h at (x, y) of its base. Each has its
    own palette: a patch only needs the colors it paints."""

    base: int
    x: int
    y: int
    w: int
    h: int
    bits: int
    clear: int  # Palette index of see-through pixels, or -1.
    palette: list[int]  # RGB565; the clear entry is 0.
    data: list[int]
    depth: int  # Patches between it and its keyframe, itself included.

    @property
    def key(self) -> bool:
        return self.base < 0

    def size(self) -> int:
        """Flash bytes: data, palette, and the C++ object's fields."""
        return len(self.data) + 2 * len(self.palette) + 16


@dataclass
class FrameSet:
    width: int
    height: int
    frames: list[SetFrame]  # One per unique picture, in the order given.
    index: list[int]  # For each picture given: its frame.

    def size(self) -> int:
        return sum(f.size() for f in self.frames)


def _palette(pixels: list[int]) -> tuple[list[int], dict[int, int]]:
    counts = Counter(pixels)
    palette = sorted(counts, key=lambda c: -counts[c])
    return palette, {c: i for i, c in enumerate(palette)}


def _lanes(pixels: list[int]) -> int:
    """The pixels as one int, 32 bits (a lane) per pixel."""
    return int.from_bytes(array("i", pixels).tobytes(), "little")


def _differing_lanes(x: int, ones: int) -> int:
    """How many 32-bit lanes of `x` are not zero. The shifts fold every bit
    of a lane into its lowest bit; `ones` has only those lowest bits set."""
    x |= x >> 16
    x |= x >> 8
    x |= x >> 4
    x |= x >> 2
    x |= x >> 1
    return (x & ones).bit_count()


def encode_set(images, sequences: list[list[int]] | None = None, mode: str = "full", label: str = "frames") -> FrameSet:
    """Encodes pictures of one size as keyframes and patches.

    `sequences` lists the order frames play in, as indices into `images`:
    one list per animation, plus [first frame, blink] for a blink or a wink.
    The first entry of each list is shown out of order (an animation
    starting), so it stays at most FIRST_DEPTH deep. Every other frame
    prefers the frame before it as its base, since that is what the screen
    already shows. Pictures with the same pixels become one frame.
    """
    if not images:
        raise ValueError(f"{label}: no pictures")
    size = images[0].size
    for img in images:
        if img.size != size:
            raise ValueError(f"{label}: pictures of different sizes ({size}, {img.size})")
    w, h = size

    unique: dict[tuple, int] = {}
    index = []
    pixels: list[list[int]] = []
    for img in images:
        px = screen_pixels(img, mode)
        key = tuple(px)
        if key not in unique:
            unique[key] = len(pixels)
            pixels.append(px)
        index.append(unique[key])

    def keyframe(u: int) -> SetFrame:
        palette, at = _palette(pixels[u])
        n = len(palette)
        if n + 1 > 256:
            raise ValueError(f"{label}: {n} colors at RGB565; a sprite takes at most 255")
        bits = _bits(n + 1)
        data = _runs([at[p] for p in pixels[u]], w, h, n, bits)
        return SetFrame(-1, 0, 0, w, h, bits, at.get(CLEAR, -1), [0 if c == CLEAR else c for c in palette], data, 0)

    def patch(u: int, base: int, depth: int) -> SetFrame:
        a, b = pixels[u], pixels[base]
        diff = list(compress(range(w * h), map(ne, a, b)))
        x0, x1 = min(i % w for i in diff), max(i % w for i in diff) + 1
        y0, y1 = diff[0] // w, diff[-1] // w + 1
        palette, at = _palette([a[i] for i in diff])
        n = len(palette)
        if n + 2 > 256:
            raise ValueError(f"{label}: {n} colors at RGB565 in one patch; it takes at most 254")
        codes = []
        for y in range(y0, y1):
            row = slice(y * w + x0, y * w + x1)
            # pragma: no mutate block, the rows are the same length: strict never fails
            codes.extend(n if p == q else at[p] for p, q in zip(a[row], b[row], strict=True))
        bits = _bits(n + 2)
        data = _runs(codes, x1 - x0, y1 - y0, n + 1, bits)
        return SetFrame(
            base,
            x0,
            y0,
            x1 - x0,
            y1 - y0,
            bits,
            at.get(CLEAR, -1),
            [0 if c == CLEAR else c for c in palette],
            data,
            depth + 1,
        )

    lanes = [_lanes(px) for px in pixels]
    # A mask of 2s would count a lane that differs only in bit 0 at the lane
    # below it instead: the same totals, but for the very first pixel.
    # pragma: no mutate block, see above
    ones = _lanes([1] * (w * h))

    def changed(u: int, v: int) -> int:
        return _differing_lanes(lanes[u] ^ lanes[v], ones)

    frames: dict[int, SetFrame] = {}

    def place(u: int, prev: int | None, first: int | None, limit: int) -> None:
        """Stores picture u as the cheapest of a keyframe and patches on the
        frame before (prev), its animation's first frame and the closest
        others, among frames less than `limit` deep."""
        if u in frames:
            return
        options = [keyframe(u)]
        # The base the screen likely shows, then the closest few others.
        tried = set()
        for cand in (prev, first):
            if cand is not None and cand in frames and cand != u and frames[cand].depth < limit:
                tried.add(cand)
        others = sorted((changed(u, v), v) for v in frames if v not in tried and frames[v].depth < limit)
        tried.update(v for _, v in others[:CANDIDATES])
        for v in tried:
            options.append(patch(u, v, frames[v].depth))

        def cost(f: SetFrame) -> float:
            # A patch on the frame before needs no other drawing on the device.
            return f.size() * PREV_FACTOR if (not f.key and f.base == prev) else f.size()

        frames[u] = min(options, key=cost)

    # First frames first, so a picture that also plays inside another
    # animation still starts its own shallow.
    for seq in sequences or []:
        place(index[seq[0]], None, None, FIRST_DEPTH)
    for seq in sequences or []:
        for pos, i in enumerate(seq[1:], 1):
            place(index[i], index[seq[pos - 1]], index[seq[0]], MAX_DEPTH)
    for u in range(len(pixels)):  # Pictures no sequence named.
        place(u, None, None, FIRST_DEPTH)
    return FrameSet(w, h, [frames[u] for u in range(len(pixels))], index)


def decode_set(fs: FrameSet) -> list[list[int]]:
    """Every frame of a set as screen pixels, by following its base chain.
    For checks on the host; the device has its own decoder (frame_chain.h)."""
    w = fs.width
    out: list[list[int] | None] = [None] * len(fs.frames)

    def runs(f: SetFrame, copy: int) -> list[int]:
        codes, at = [], 0
        shift = 8 - f.bits
        mask = (1 << shift) - 1
        for y in range(f.h):
            x = 0
            while x < f.w:
                b = f.data[at]
                at += 1
                # At 8 bits the long-run branch below reads the same two bytes.
                if f.bits == 8:  # pragma: no mutate
                    i, run = b, f.data[at] + 1
                    at += 1
                else:
                    i, run = b >> shift, b & mask
                    if run == 0:
                        run = mask + 1 + f.data[at]
                        at += 1
                for k in range(run):
                    codes.append(codes[(y - 1) * f.w + x + k] if i == copy else i)
                x += run
        return codes

    def color(f: SetFrame, c: int) -> int:
        return CLEAR if c == f.clear else f.palette[c]

    def get(u: int) -> list[int]:
        if out[u] is None:
            f = fs.frames[u]
            n = len(f.palette)
            if f.key:
                px = [color(f, c) for c in runs(f, n)]
            else:
                px = list(get(f.base))
                for k, c in enumerate(runs(f, n + 1)):
                    if c != n:
                        px[(f.y + k // f.w) * w + f.x + k % f.w] = color(f, c)
            out[u] = px
        return out[u]

    return [get(u) for u in range(len(fs.frames))]
