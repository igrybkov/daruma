"""Drawn personas, kept on disk so a test run draws each persona once.

Three test files check every pixel persona: test_frames.py,
test_persona_frames.py and test_props.py. Drawing the daruma takes most of
a minute, and pytest-xdist runs the files in separate processes. So build()
keeps each drawn persona as a pickle in $DARUMA_PERSONA_CACHE, the way
daruma_sprites keeps them between device builds.

The key hashes every Python file of the pixel packages, the persona's own
module, the persona name and the Python and Pillow versions. A change to
the art draws it again. tests/conftest.py points the folder into pytest's
cache. Unset or empty, nothing is kept and every call draws.

Two processes may draw the same persona at the same time. Both write the
same pickle through a temp file and os.replace, so the last one wins and a
reader never sees half a file.
"""

from __future__ import annotations

import hashlib
import importlib
import os
import pickle
import sys
from functools import cache
from pathlib import Path
from types import ModuleType

ENV = "DARUMA_PERSONA_CACHE"
_PIXEL = Path(__file__).resolve().parents[1] / "pixel"


def build(module: ModuleType | str, name: str):
    """The persona `name` of a pixel_art module, as daruma_sprites draws it:
    the module's own build(name), or personas.build() from its Spec."""
    if isinstance(module, str):
        module = importlib.import_module(module)
    path = _cache_path(module, name)
    if path is not None and path.is_file():
        try:
            with path.open("rb") as f:
                return pickle.load(f)
        except Exception:  # Unreadable or stale: draw again.
            pass
    persona = _draw(module, name)
    if path is not None:
        _store(path, persona)
    return persona


def _draw(module: ModuleType, name: str):
    if hasattr(module, "build"):
        return module.build(name)
    from daruma_pixel import personas

    return personas.build(name, module)


def _store(path: Path, persona) -> None:
    """Writes the pickle and drops the ones drawn from older sources."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
        with tmp.open("wb") as f:
            pickle.dump(persona, f, protocol=pickle.HIGHEST_PROTOCOL)
        tmp.replace(path)
        prefix = path.name.rsplit("-", 1)[0]
        for old in path.parent.glob(f"{prefix}-*.pickle"):
            if old != path:
                old.unlink(missing_ok=True)
    except Exception:  # Not picklable or not writable: no cache, same result.
        pass


def _cache_path(module: ModuleType, name: str) -> Path | None:
    folder = os.environ.get(ENV)
    if not folder:
        return None
    digest = hashlib.sha256(_sources_digest().encode())
    own = getattr(module, "__file__", None)
    if own:
        digest.update(Path(own).read_bytes())
    digest.update(f"{module.__name__}|{name}".encode())
    return Path(folder) / f"{module.__name__}.{name}-{digest.hexdigest()[:24]}.pickle"


@cache
def _sources_digest() -> str:
    """One hash of every pixel package's Python, and the versions that draw it."""
    import PIL

    digest = hashlib.sha256()
    for path in sorted(_PIXEL.glob("*/src/**/*.py")):
        digest.update(path.relative_to(_PIXEL).as_posix().encode())
        digest.update(path.read_bytes())
    digest.update(f"{PIL.__version__}|{sys.version_info[:3]}".encode())
    return digest.hexdigest()
