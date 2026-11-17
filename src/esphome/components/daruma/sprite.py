"""Build-time side of Sprite, the compressed picture format of the personas.

The byte format, the gray reduction and the frame-set encoder (keyframes and
patches) live in sprite_codec.py, plain Python that host tests can load.
This file turns their results into C++ (sprite.h).
"""

from __future__ import annotations

from pathlib import Path

import esphome.codegen as cg
from esphome.core import CORE

from .sprite_codec import encode_image, encode_set, gray_for, reduce_colors  # noqa: F401  (re-exported)

daruma_ns = cg.esphome_ns.namespace("Daruma")
Sprite = daruma_ns.class_("Sprite")

_cache: dict[str, cg.MockObj] = {}
_palettes: dict[tuple, cg.MockObj] = {}
_count = 0


def color_mode() -> str:
    """The screen's colors from the hub's display profile."""
    from esphome.components.daruma import build_profile

    return build_profile().colors


def encode(path: Path, mode: str = "full") -> tuple[int, int, int, int, list[int], list[int]]:
    """Returns width, height, index bits, clear index (-1 if none), palette, data."""
    from PIL import Image

    with Image.open(path) as img:
        return encode_image(img, str(path), mode)


def sprite_expression(path: str) -> cg.MockObj:
    """A `const Sprite *` for the PNG at `path` (absolute, or relative to the config). Same file, same sprite."""
    full = Path(CORE.relative_config_path(path)).resolve()
    mode = color_mode()
    key = f"{mode}:{full}"
    if key in _cache:
        return _cache[key]
    _cache[key] = _declare(*encode(full, mode))
    return _cache[key]


def sprite_from_image(img) -> cg.MockObj:
    """A `const Sprite *` for a PIL image, e.g. one drawn by Python at build time.

    Pictures with the same pixels share one sprite."""
    import hashlib

    img = img.convert("RGBA")
    mode = color_mode()
    key = f"image:{mode}:" + hashlib.sha1(repr(img.size).encode() + img.tobytes()).hexdigest()
    if key not in _cache:
        _cache[key] = _declare(*encode_image(img, "picture from Python", mode))
    return _cache[key]


def _declare(w, h, bits, clear, palette, data, patch: bool = False) -> cg.MockObj:
    """A `const Sprite *` to a constexpr Sprite at namespace scope. The data,
    the palette and the object all sit in flash; setup() runs no code for it."""
    global _count
    n = _count
    _count += 1
    # Frames of one persona often have the same palette: store it once.
    key = tuple(palette)
    if key not in _palettes:
        name = f"daruma_sprite_palette_{n}"
        cg.add_global(cg.RawStatement(f"static const uint16_t {name}[] = {{{','.join(map(str, palette))}}};"))
        _palettes[key] = name
    raw = f"daruma_sprite_data_{n}"
    cg.add_global(cg.RawStatement(f"static const uint8_t {raw}[] = {{{','.join(map(str, data))}}};"))
    obj = f"daruma_sprite_{n}"
    cg.add_global(
        cg.RawStatement(
            f"static constexpr Daruma::Sprite {obj}({w}, {h}, {bits}, {clear}, {len(palette)}, {_palettes[key]}, "
            f"{raw}, "
            f"{'true' if patch else 'false'});"
        )
    )
    return cg.RawExpression(f"&{obj}")


def frame_set(images, sequences: list[list[int]], label: str) -> tuple[list[tuple], list[int]]:
    """Animation frames as keyframes and patches (sprite_codec.encode_set).

    Returns the stored frames as (sprite, base, x, y), base -1 for a
    keyframe, and for each picture given the index of its stored frame."""
    fs = encode_set([img.convert("RGBA") for img in images], sequences, color_mode(), label)
    out = []
    for f in fs.frames:
        sprite = _declare(f.w, f.h, f.bits, f.clear, f.palette, f.data, not f.key)
        out.append((sprite, f.base, f.x, f.y))
    return out, fs.index


def art_path(art: str | None, name: str) -> str:
    """`name` inside the `art` folder as name.png, or `name` as given without one."""
    if art is None:
        return name
    return str(Path(art) / (name if name.endswith(".png") else f"{name}.png"))


def resolve_file(value: str) -> str:
    """The absolute path of a file a YAML value names.

    Like ESPHome's own file options (cv.file_): relative to the config
    folder first, then to the YAML file the value is written in. So a
    package fetched from git can name files next to it (`../pixel/daruma_pixel/personas.py`)
    wherever the device yaml is. Must run on the value as loaded, while it
    still knows its YAML file."""
    import esphome.config_validation as cv

    return str(cv.file_(value).resolve())


def resolve_dir(value: str) -> str:
    """As resolve_file(), for a folder."""
    import esphome.config_validation as cv

    return str(cv.directory(value).resolve())


def bundle_file(path: Path) -> None:
    """Adds a file the build reads but the config doesn't name as a path, so
    a config bundle (a remote build) carries it. ESPHome finds most files by
    walking the config; pictures named inside an `art` folder and Python art
    scripts it can't see. Files in ESPHome's git cache (packages and
    components fetched from git) are left out: the build server fetches
    them again. No-op on ESPHome versions without bundles."""
    try:
        from esphome.bundle import add_bundle_file
    except ImportError:
        return
    path = Path(CORE.relative_config_path(path)).resolve()
    if path.is_relative_to(Path(CORE.data_dir).resolve()):
        return
    add_bundle_file(path)


def check_art(art: str | None, name: str) -> None:
    path = Path(CORE.relative_config_path(art_path(art, name)))
    if not path.is_file():
        import esphome.config_validation as cv

        raise cv.Invalid(f"No picture at {path}")
    bundle_file(path)
