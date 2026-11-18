"""Runs mutmut, with this repository's layouts mapped to their import names.

    uv run python tests/mutmut_run.py run|results|show ...   as `mutmut ...`

mutmut names a mutant by its file's path, less a leading `src.`, and the
tests record a hit by the module's import name. The two agree for
src/esphome/components/<x>, but not for:

    pixel/<package>/src/<module>   imported as <module> (an editable install)
    demos/<module>                 imported as <module> (demos/ on sys.path)

mutate_py.py runs mutmut through this file, which names those mutants by
their import name. mutmut also puts only mutants/ and mutants/src first
on sys.path, while the editable installs keep pixel/*/src there: the
tests would import the code that mutmut never changed. This puts the
mutated pixel folders first and takes the originals off.

Code that runs when a module is imported (a persona's ANIMATIONS table)
is a second gap. mutmut charges those calls to the test that happens to
import the module first, often one that never looks at that persona.
This charges a call made under a module's top level to every test that
runs code of the same package (group()) as well. A cache (functools.cache,
cached_picture) hides calls the same way, so the stats run empties the
repository's caches before each test. With forkserver_warmup = "import" and only
outside modules in tests/mutmut_preload.txt, each mutant imports the
repository's modules afresh, with the mutant on.

It changes three functions inside mutmut, a version uv.lock pins.
mutate_py.py fails when a mutant name still starts with a path
(STRAY_PREFIXES): a newer mutmut that moves them would show up there.
"""

from __future__ import annotations

import functools
import gc
import re
import sys
from pathlib import Path

# A path prefix mutmut keeps in a name, and what replaces it.
_PREFIXES = [(re.compile(r"^pixel\.[^.]+\.src\."), ""), (re.compile(r"^demos\."), "")]
# Names that start like this were not mapped: their tests can't reach them.
STRAY_PREFIXES = ("pixel.", "src.", "demos.")


def import_name(dotted: str) -> str:
    """The import name of a module mutmut names `dotted` (its path, less `src.`)."""
    for pattern, replacement in _PREFIXES:
        dotted = pattern.sub(replacement, dotted)
    return dotted


def module_name(path: str) -> str:
    """The import name of a source file, as mutmut names its mutants here."""
    parts = Path(path).with_suffix("").parts
    if parts[0] == "src":
        parts = parts[1:]
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return import_name(".".join(parts))


def group(function: str) -> str:
    """The package a mangled function name belongs to, for import-time calls:
    esphome.components.<x>, daruma_shapes.<x>, daruma_personas.<x>, or the
    top-level module."""
    parts = function.split(".")
    if parts[0] == "esphome":
        return ".".join(parts[:3])
    if parts[0] in ("daruma_shapes", "daruma_personas"):
        return ".".join(parts[:2])
    return parts[0]


def spread(tests_by_function: dict[str, set[str]], at_import: set[str]) -> None:
    """Charges each function called at import to the tests that run code of its package."""
    by_group: dict[str, set[str]] = {}
    for function, tests in tests_by_function.items():
        by_group.setdefault(group(function), set()).update(tests)
    for function in at_import:
        tests_by_function.setdefault(function, set()).update(by_group.get(group(function), set()))


AT_IMPORT: set[str] = set()


def importing() -> bool:
    """True while the caller runs under the top level of a module being imported."""
    frame = sys._getframe(2)
    while frame is not None:
        if frame.f_code.co_name == "<module>" and frame.f_globals.get("__name__") != "__main__":
            return True
        frame = frame.f_back
    return False


def clear_caches() -> None:
    """Empties every functools cache of a module under the current folder."""
    here = Path.cwd()
    for obj in gc.get_objects():
        if not isinstance(obj, functools._lru_cache_wrapper):
            continue
        module = sys.modules.get(getattr(obj, "__module__", "") or "")
        file = getattr(module, "__file__", None)
        if file and Path(file).resolve().is_relative_to(here):
            obj.cache_clear()


class ClearCaches:
    """pytest plugin: each test starts with empty caches, so it calls what it uses."""

    def pytest_runtest_setup(self, item) -> None:
        clear_caches()


def _patch() -> None:
    import mutmut.__main__ as main
    import mutmut.mutation.file_mutation as file_mutation
    import mutmut.mutation.trampoline as trampoline
    import mutmut.utils.file_utils as file_utils
    import mutmut.utils.format_utils as format_utils
    from mutmut.runners.harness import PytestRunner
    from mutmut.state import state

    by_path = format_utils.get_mutant_name
    paths_first = file_utils.setup_source_paths

    def get_mutant_name(relative_source_path: Path, mutant_method_name: str) -> str:
        return import_name(by_path(relative_source_path, mutant_method_name))

    def setup_source_paths() -> None:
        paths_first()
        originals = {str(p.resolve()) for p in Path("pixel").glob("*/src")}
        sys.path[:] = [p for p in sys.path if str(Path(p or ".").resolve()) not in originals]
        for folder in sorted(Path("mutants", "pixel").glob("*/src"), reverse=True):
            sys.path.insert(0, str(folder.absolute()))

    run_stats = PytestRunner.run_stats

    record = trampoline.record_trampoline_hit

    def record_and_note_import(name: str, caller: str | None = None) -> None:
        record(name, caller=caller)
        if importing():
            AT_IMPORT.add(name)

    def run_stats_spread(self, *, tests):
        execute = self.execute_pytest

        def with_clear_caches(params, **kw):
            return execute(params, **{**kw, "plugins": [*kw.get("plugins", []), ClearCaches()]})

        self.execute_pytest = with_clear_caches
        try:
            return run_stats(self, tests=tests)
        finally:
            del self.execute_pytest
            spread(state().tests_by_mangled_function_name, AT_IMPORT)

    trampoline.record_trampoline_hit = record_and_note_import
    PytestRunner.run_stats = run_stats_spread
    # Each module imported the functions by name: replace every copy.
    for module in (format_utils, main, file_mutation):
        module.get_mutant_name = get_mutant_name
    for module in (file_utils, main):
        module.setup_source_paths = setup_source_paths


if __name__ == "__main__":
    _patch()
    from mutmut.__main__ import cli

    sys.argv[0] = "mutmut"
    sys.exit(cli())
