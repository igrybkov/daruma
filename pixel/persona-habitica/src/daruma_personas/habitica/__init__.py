"""A Habitica avatar as a pixel persona: the compositor, its sprite sources
and fixture layers.

The device shows the avatar at one pixel per art pixel, so the build takes
Habitica's 3x sprites back down (downscale.py) after it stacks them the way
habiticalib does (compose.py). The look says which sprites (look.py). The
sprites come from a folder, Habitica's asset CDN, or the fixture drawn in
this package (sources.py, fixture.py).

Options, from `daruma_sprites: pixel_art: options:`:

    look:    a pinned look, in the shape of Habitica's user object
             (look.py). Without one, the fixture's look.
    sprites: fixture (the default), cdn, or dir:<path>.

The build reads nothing else from the options. A token there is never
read, hashed or logged by this package.

Credits and license: the avatar art belongs to Habitica (habitica.com) and
its artists, under CC-BY-NC-SA 3.0
(https://creativecommons.org/licenses/by-nc-sa/3.0/). This package holds
none of it. With `sprites: cdn` the build downloads it to the builder's
data folder, and the firmware then holds that art: fine for your own
device, not for selling one. Habitica does not endorse this project.

This package does not declare a persona yet, so discover() skips it.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

from . import fixture, sources
from .compose import plan
from .look import Look, from_user


def look_of(options: Mapping[str, Any]) -> Look:
    """The pinned look, or the fixture's."""
    pinned = options.get("look")
    return from_user(pinned if isinstance(pinned, Mapping) else fixture.USER)


def source_of(options: Mapping[str, Any], data_dir: Path | None) -> sources.Source:
    return sources.source_from(str(options.get("sprites", "fixture")), data_dir, fixture.source)


def sprite_names(look: Look) -> list[str]:
    """Every sprite the persona draws: the look's, and its sleeping look's (the blink)."""
    names = [layer.sprite for layer in plan(look) + plan(replace(look, sleep=True))]
    return list(dict.fromkeys(names))


def cache_inputs(name: str, options: Mapping[str, Any], data_dir: Path | None) -> list[str]:
    """What the drawn persona depends on beyond the code (daruma_sprites's
    cache key): the look and a hash of every sprite it uses. With `cdn`, this
    downloads what the cache lacks."""
    look = look_of(options)
    source = source_of(options, data_dir)
    out = [f"look:{look.canonical()}"]
    for sprite in sprite_names(look):
        data = source.fetch(sprite)
        out.append(f"{sprite}:{hashlib.sha256(data).hexdigest() if data is not None else 'missing'}")
    return out
