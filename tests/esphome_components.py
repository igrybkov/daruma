"""Lets host code import this repository's components by their ESPHome names.

    import esphome_components  # first
    from esphome.components.daruma import registry

ESPHome loads a component from a folder (external_components) as
esphome.components.<name>. esphome.components is a regular package, so a
folder on sys.path does not add to it. This module adds every
<entry>/esphome/components folder on sys.path to the package's __path__,
in sys.path order, so the first copy wins. mutmut relies on that: it puts
its mutated copy (mutants/src) on sys.path and takes the original off.
With no such folder on sys.path, it adds this repository's
src/esphome/components.

A build is not affected: ESPHome's own finder for external_components
comes before the package's __path__.
"""

from __future__ import annotations

import sys
from pathlib import Path

import esphome.components

COMPONENTS = Path(__file__).resolve().parents[1] / "src" / "esphome" / "components"


def _folders() -> list[str]:
    """The component folders on sys.path that the package does not search yet."""
    known = {str(Path(p).resolve()) for p in esphome.components.__path__}
    found = []
    for entry in sys.path:
        folder = Path(entry or ".", "esphome", "components")
        if folder.is_dir() and str(folder.resolve()) not in known:
            known.add(str(folder.resolve()))
            found.append(str(folder))
    return found


esphome.components.__path__ += _folders() or [str(COMPONENTS)]
