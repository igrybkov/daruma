"""A Habitica avatar as a pixel persona.

The build stacks the avatar's sprites the way habiticalib does
(compose.py), takes Habitica's 3x sprites back to one pixel per art pixel
(downscale.py), and poses the rider and the pet on their own (actor.py,
moods.py). The room is the avatar's Habitica background, 47x48 art pixels
at 5x, with plain sky and ground at its sides (room.py).

Options, from `daruma_sprites: pixel_art: options:`:

    source:  fixture (the default), cdn, or dir:<path>: where the sprites
             come from (sources.py).
    look:    a pinned look, in the shape of Habitica's user object
             (look.py). It wins over the API.
    token, user_id: read the look from Habitica's API at build time
             (api.py). Offline, the last look read.

Without a pin or a token, the look is the fixture's: a made-up avatar
drawn in this package (fixture.py). The public persona uses it, so no
Habitica art reaches the repository's pictures. The token is used for
the request only: never logged, saved or part of a cache key.

The look leaves out sleep and buffs: the inn and the buffs show at run
time, and changing them needs no new build.

Credits and license: the avatar art belongs to Habitica (habitica.com)
and its artists, under CC-BY-NC-SA 3.0
(https://creativecommons.org/licenses/by-nc-sa/3.0/). This package holds
none of it. With `source: cdn` the build downloads it to the builder's
data folder, and the firmware then holds that art: fine for your own
device, not for selling one. Habitica does not endorse this project.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

from daruma_pixel import personas
from daruma_pixel.personas import Persona, Spec

from . import api, fixture, moods, sources
from .actor import Avatars, Layers
from .compose import compose as compose_avatar
from .compose import plan
from .look import Look, from_user

BACKGROUND = 0x609C4C  # Any margin round the room: the ground.
NOT_DRAWN = frozenset({"zzz"})  # The persona draws its own (daruma_pixel.effects).

# The user objects read from the API in this process, so cache_inputs() and
# build() share one request. Keyed by a hash: the token stays out.
_users: dict[str, dict[str, Any]] = {}


def _api_user(user_id: str, token: str, data_dir: Path | None) -> dict[str, Any]:
    key = hashlib.sha256(f"{user_id}\0{token}".encode()).hexdigest()  # pragma: no mutate (any one-way key works)
    if key not in _users:
        _users[key] = api.user_from_api(user_id, token, data_dir)
    return _users[key]


def user_of(options: Mapping[str, Any], data_dir: Path | None) -> Mapping[str, Any]:
    """The user object the look comes from: the pin, the API, or the fixture."""
    pinned = options.get("look")
    if isinstance(pinned, Mapping):
        return pinned
    token, user_id = options.get("token"), options.get("user_id")
    if token and user_id:
        return _api_user(str(user_id), str(token), data_dir)
    return fixture.USER


def look_of(options: Mapping[str, Any], data_dir: Path | None = None) -> Look:
    """The look to draw, awake and without buffs."""
    return replace(from_user(user_of(options, data_dir)), sleep=False, buffs=frozenset())


def source_of(options: Mapping[str, Any], data_dir: Path | None) -> sources.Source:
    return sources.source_from(str(options.get("source", "fixture")), data_dir, fixture.source)


def sprite_names(look: Look) -> list[str]:
    """Every sprite the persona draws: the look's, and its sleeping look's (the blink)."""
    names = [layer.sprite for layer in plan(look) + plan(replace(look, sleep=True))]
    return [name for name in dict.fromkeys(names) if name not in NOT_DRAWN]


def avatars(look: Look, source: sources.Source) -> Avatars:
    """The look composed awake and asleep. Without a `_sleep` skin, the eyes stay open."""
    awake = compose_avatar(look, source)  # Awake: no zzz in the plan.
    asleep = compose_avatar(replace(look, sleep=True), source, NOT_DRAWN)
    if f"skin_{look.skin}_sleep" in asleep.missing:
        asleep = awake
    return Avatars(awake, asleep, mounted=bool(look.mount))


def layers_of(options: Mapping[str, Any], data_dir: Path | None) -> Layers:
    look = look_of(options, data_dir)
    source = source_of(options, data_dir)
    return Layers(lambda: avatars(look, source))


def build(name: str, options: Mapping[str, Any] | None = None, data_dir: Path | None = None) -> Persona:
    """The persona of the look the options name (the fixture's without any)."""
    layers = FIXTURE_LAYERS if not options else layers_of(options, data_dir)
    # pragma: no mutate block, build_spec does not read the Spec's name
    return personas.build_spec(Spec(name, background=BACKGROUND, layers=layers, animations=moods))


def cache_inputs(name: str, options: Mapping[str, Any], data_dir: Path | None) -> list[str]:
    """What the drawn persona depends on beyond the code (daruma_sprites's
    cache key): the look and a hash of every sprite it uses. With `cdn`, this
    downloads what the cache lacks."""
    look = look_of(options, data_dir)
    source = source_of(options, data_dir)
    out = [f"look:{look.canonical()}"]
    for sprite in sprite_names(look):
        data = source.fetch(sprite)
        out.append(f"{sprite}:{hashlib.sha256(data).hexdigest() if data is not None else 'missing'}")
    return out


FIXTURE_LAYERS = Layers(lambda: avatars(look_of({}), fixture.source()))
PERSONA = Spec("habitica", background=BACKGROUND, layers=FIXTURE_LAYERS, animations=moods)
