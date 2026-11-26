"""Where the sprites come from: a folder, Habitica's asset CDN, or memory.

A sprite is named the way Habitica names it (`skin_915533`, `Pet-Wolf-Base`),
without the extension. A source gives a sprite's file bytes, or None when it
has no such sprite.

- `dir:<path>`: PNG files in a folder (`<name>.png`, else `<name>.gif`).
- `cdn`: Habitica's asset CDN, the place habiticalib loads from. Each
  sprite is downloaded once into a cache folder and read from there after,
  so a build offline still works once the cache is warm. Nothing is fetched
  when a module is imported: only a build asks for sprites.
- `MemorySource`: pictures held in memory, for the fixture and tests.

Habitica's art is CC-BY-NC-SA 3.0. Downloaded sprites stay in the cache
folder on the machine that builds; they never belong in a repository.
"""

from __future__ import annotations

import io
import logging
import re
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Protocol

from PIL import Image

log = logging.getLogger(__name__)

ASSETS_URL = "https://habitica-assets.s3.amazonaws.com/mobileApp/images/"
CACHE_FOLDER = "daruma_habitica"  # Inside the builder's data folder; in .gitignore.
# Habitica asks third-party tools to name themselves in this header.
CLIENT = "daruma-habitica-persona"
TIMEOUT = 20  # Seconds per download.
# Sprite names are letters, digits, '_' and '-'. Anything else could leave the folder.
_NAME = re.compile(r"[A-Za-z0-9_-]+")


class Source(Protocol):
    def fetch(self, name: str) -> bytes | None:
        """The sprite's file bytes, or None when there is no such sprite."""


def safe_name(name: str) -> bool:
    return _NAME.fullmatch(name) is not None


def load(source: Source, name: str) -> Image.Image | None:
    """The sprite as an RGBA picture (a GIF's first frame), or None."""
    if not safe_name(name):
        log.warning("habitica: skipped sprite with an odd name %r", name)
        return None
    data = source.fetch(name)
    if data is None:
        return None
    with Image.open(io.BytesIO(data)) as img:  # A GIF opens on its first frame.
        return img.convert("RGBA")


class MemorySource:
    """Sprites held as pictures."""

    def __init__(self, pictures: Mapping[str, Image.Image]) -> None:
        self._files: dict[str, bytes] = {}
        for name, img in pictures.items():
            out = io.BytesIO()
            img.save(out, "PNG")
            self._files[name] = out.getvalue()

    def fetch(self, name: str) -> bytes | None:
        return self._files.get(name)


class DirSource:
    """Sprites as files in a folder."""

    def __init__(self, folder: Path) -> None:
        self.folder = Path(folder)

    def fetch(self, name: str) -> bytes | None:
        if not safe_name(name):
            return None
        for suffix in (".png", ".gif"):
            path = self.folder / f"{name}{suffix}"
            if path.is_file():
                return path.read_bytes()
        return None


def download(url: str) -> bytes | None:
    """The file at `url`, or None when the server has no such file."""
    request = urllib.request.Request(url, headers={"x-client": CLIENT, "User-Agent": CLIENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:  # noqa: S310 - a fixed https URL
            return response.read()
    except urllib.error.HTTPError as err:
        if err.code in (403, 404):  # S3 answers 403 for a file it does not have.
            return None
        raise


class CdnSource:
    """Sprites from Habitica's asset CDN, kept in `folder` once downloaded."""

    def __init__(self, folder: Path, get: Callable[[str], bytes | None]) -> None:
        self.folder = Path(folder)
        self._cache = DirSource(self.folder)
        self._get = get  # download(), or a fake in tests.

    def fetch(self, name: str) -> bytes | None:
        if not safe_name(name):
            return None
        if (cached := self._cache.fetch(name)) is not None:
            return cached
        try:
            data = self._get(f"{ASSETS_URL}{name}.png")
        except OSError as err:  # Offline, or the CDN is down: the sprite counts as missing.
            log.warning("habitica: could not download sprite %s: %s", name, err)
            return None
        if data is None:
            return None
        self.folder.mkdir(parents=True, exist_ok=True)
        path = self.folder / f"{name}.png"
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(data)
        tmp.replace(path)
        return data


def source_from(spec: str, data_dir: Path | None, fixture: Callable[[], Source]) -> Source:
    """The source a `sprites:` option names: `fixture`, `cdn` or `dir:<path>`.

    `cdn` keeps its downloads in `data_dir`/daruma_habitica.
    """
    if spec == "fixture":
        return fixture()
    if spec == "cdn":
        if data_dir is None:
            raise ValueError("sprites: cdn needs the builder's data folder for its cache")
        return CdnSource(Path(data_dir) / CACHE_FOLDER, download)
    if spec.startswith("dir:"):
        return DirSource(Path(spec.removeprefix("dir:")).expanduser())
    raise ValueError(f"sprites: {spec!r} is not fixture, cdn or dir:<path>")
