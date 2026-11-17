"""Load a component's Python file without ESPHome.

The components' packages import ESPHome, so the host tests load single
files by path. Each file gets the dotted name of its path from the
repository root (components.daruma.registry), and every test shares one
copy of it. Mutation testing (mutmut) relies on that name: it maps a
mutant to its tests by the module's name.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_component(relative: str):
    """The module at `relative` (a path under the repository root)."""
    path = ROOT / relative
    name = ".".join(Path(relative).with_suffix("").parts)
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader, path
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # Dataclasses look their module up here.
    spec.loader.exec_module(module)
    return module
