"""Persona folders outside this repository, named by DARUMA_PERSONA_PATH.

    DARUMA_PERSONA_PATH=/path/to/my-daruma-private:/path/to/another

The value is a list of folders, joined like PATH (":" on macOS and Linux).
Each folder is a repository of persona packages, laid out as
docs/private-packages.md describes, with its pictures where Daruma keeps
its own:

    packages/persona_*.yaml         persona packages; the desktop build adds them
    demos/scenarios/*.yaml          its own scenarios; they run on its personas only
    tests/golden/frames/<persona>/  goldens of every picture of its pixel personas
    tests/golden/<slug>/<scenario>/ goldens of the scenario tests
    docs/demos/                     its demo GIFs and stills

Two more variables move the pictures: DARUMA_PERSONA_GOLDEN (the golden
folder, default tests/golden) and DARUMA_PERSONA_DEMOS (default
docs/demos). A relative path is inside each folder; an absolute one is
used as it is.

Every tool reads it the same way: the desktop build (harness.py), the
scenario tests (conftest.py), the scenario files (scenario.py), the recorder (record.py), the frame goldens
(tests/persona_frames.py) and the prop check (tests/test_props.py). Their
pictures go to the folder, never into this repository.
"""

from __future__ import annotations

import hashlib
import importlib.util
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

ENV = "DARUMA_PERSONA_PATH"
GOLDEN_ENV = "DARUMA_PERSONA_GOLDEN"
DEMOS_ENV = "DARUMA_PERSONA_DEMOS"
GOLDEN = "tests/golden"
DEMOS = "docs/demos"
SCENARIOS = "demos/scenarios"


@dataclass(frozen=True)
class Folder:
    """One folder of DARUMA_PERSONA_PATH, and where its pictures go."""

    root: Path
    golden: Path  # Laid out as tests/golden: frames/<persona>/ and <slug>/<scenario>/.
    demos: Path

    @classmethod
    def at(cls, root: Path, golden: str | None = None, demos: str | None = None) -> Folder:
        """The folder at `root`; golden and demos default to the variables, then to GOLDEN and DEMOS."""
        golden = golden or os.environ.get(GOLDEN_ENV) or GOLDEN
        demos = demos or os.environ.get(DEMOS_ENV) or DEMOS
        return cls(root, root / Path(golden).expanduser(), root / Path(demos).expanduser())

    @property
    def packages(self) -> list[Path]:
        return sorted((self.root / "packages").glob("persona_*.yaml"))

    @property
    def scenarios(self) -> list[Path]:
        return sorted((self.root / SCENARIOS).glob("*.yaml"))

    @property
    def persona_names(self) -> list[str]:
        return [persona_name(p) for p in self.packages]

    @property
    def frame_golden(self) -> Path:
        return self.golden / "frames"

    @property
    def scenario_golden(self) -> Path:
        return self.golden


def folders(value: str | None = None) -> list[Folder]:
    """The folders named by `value`, or by DARUMA_PERSONA_PATH when it is None."""
    value = os.environ.get(ENV, "") if value is None else value
    found = []
    for part in value.split(os.pathsep):
        if not part.strip():
            continue
        root = Path(part).expanduser().resolve()
        if not (root / "packages").is_dir():
            raise ValueError(f"{ENV}: {root} has no packages/ folder")
        found.append(Folder.at(root))
    return found


def persona_name(package: Path) -> str:
    """The persona name a package adds to the Persona select: its first `name:`."""
    for line in package.read_text().splitlines():
        m = re.match(r"\s+name:\s*\"?([^\"#]+?)\"?\s*(#.*)?$", line)
        if m:
            return m.group(1)
    raise ValueError(f"No persona name in {package}")


def personas(found: list[Folder] | None = None) -> dict[str, Folder]:
    """Persona select name -> its folder, for every package of every folder."""
    out: dict[str, Folder] = {}
    for folder in folders() if found is None else found:
        for package in folder.packages:
            out[persona_name(package)] = folder
    return out


def load_yaml(path: Path) -> dict:
    """A package file as plain data; ESPHome tags (!include, !secret, ...) read as None."""
    import yaml

    class Loader(yaml.SafeLoader):
        pass

    Loader.add_multi_constructor("!", lambda loader, suffix, node: None)
    return yaml.load(path.read_text(), Loader=Loader) or {}  # noqa: S506 - a SafeLoader that drops ESPHome tags


@dataclass(frozen=True)
class PixelPersona:
    """A pixel_art persona of a package: what personas.build() needs."""

    name: str  # The name in the script (pixel_art: persona:).
    script: Path
    folder: Folder

    def module(self) -> ModuleType:
        return load_script(self.script)


def pixel_personas(found: list[Folder] | None = None) -> list[PixelPersona]:
    """Every pixel_art persona of the packages, with its goal-stage personas."""
    out = []
    for folder in folders() if found is None else found:
        for package in folder.packages:
            for entry in load_yaml(package).get("daruma_sprites") or []:
                art = entry.get("pixel_art") or {}
                if "script" not in art:
                    continue
                script = (package.parent / art["script"]).resolve()
                names = [art["persona"], *(art.get("goal") or {}).values()]
                out += [PixelPersona(n, script, folder) for n in names]
    return out


def load_script(script: Path) -> ModuleType:
    """A pixel_art script as a module, with its folder on the import path,
    the way daruma_sprites loads it in a device build."""
    folder = str(script.parent)
    if folder not in sys.path:
        sys.path.insert(0, folder)
    # The path's hash in the name: two folders may both have a persona.py.
    digest = hashlib.sha1(str(script.resolve()).encode()).hexdigest()[:10]
    name = f"daruma_persona_path_{script.stem}_{digest}"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, script)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # Registered first: dataclasses look their module up here.
    spec.loader.exec_module(module)
    return module
