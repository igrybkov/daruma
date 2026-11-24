"""Times mutmut's steps, and keeps one part's mutants for a split run.

mutmut run makes the mutants, records which tests reach which function
(the recorded run, or stats run), runs the clean tests and the forced
fail, then runs the mutants. install() wraps those steps:

- Each step writes `daruma-step: <name> <seconds>` to stderr (fd 2, past
  mutmut's output capture). mutate_py.py prints those lines.
- With DARUMA_MUTMUT_PART=K/N, mutmut runs only part K of N of the
  mutants it picked: every Nth in sorted order (part_of). Each part runs
  the whole flow on its own runner. It writes `daruma-part: K/N <kept>
  of <all>`, so mutate_py.py can tell the split took place.

It relies on mutmut internals, a version uv.lock pins. STEPS names them,
and tests/test_mutmut_steps.py fails when one moves.
"""

from __future__ import annotations

import atexit
import functools
import os
import time

PART = "DARUMA_MUTMUT_PART"
PREFIX = "daruma-step:"
PART_PREFIX = "daruma-part:"
# (module, attribute, step name): what install() wraps.
STEPS = (
    ("mutmut.__main__", "create_mutants", "generate"),
    ("mutmut.__main__", "collect_or_load_stats", "stats"),
    ("mutmut.__main__", "run_stats_collection", "recorded-run"),
    ("mutmut.workers.isolation", "ForkServerRunner.run_clean_tests", "clean"),
    ("mutmut.workers.isolation", "ForkServerRunner.run_forced_fail", "forced-fail"),
)


def part_of(names, part: int, parts: int) -> list[str]:
    """Part `part` (from 0) of `parts`: every parts-th name in sorted order,
    so a slow function's mutants spread across the parts."""
    return sorted(names)[part::parts]


def parse_part(text: str) -> tuple[int, int]:
    """'2/3' -> (1, 3): the part's index from 0, and the number of parts."""
    k, _, n = text.partition("/")
    if not (k.isdigit() and n.isdigit() and 1 <= int(k) <= int(n)):
        raise ValueError(f"a part is K/N with 1 <= K <= N, not {text!r}")
    return int(k) - 1, int(n)


def note(step: str, seconds: float) -> None:
    os.write(2, f"{PREFIX} {step} {seconds:.1f}s\n".encode())


def _timed(original, step: str):
    @functools.wraps(original)
    def timed(*args, **kwargs):
        start = time.monotonic()
        try:
            return original(*args, **kwargs)
        finally:
            note(step, time.monotonic() - start)

    return timed


def _owner(module_name: str, path: str):
    import importlib

    owner = importlib.import_module(module_name)
    *parents, name = path.split(".")
    for parent in parents:
        owner = getattr(owner, parent)
    return owner, name


def _only_my_part(original):
    """collect_source_file_mutation_data, less the mutants of other parts."""

    @functools.wraps(original)
    def collect(*args, **kwargs):
        mutants, data = original(*args, **kwargs)
        if not os.environ.get(PART):
            return mutants, data
        part, parts = parse_part(os.environ[PART])
        mine = set(part_of((name for _, name, _ in mutants), part, parts))
        kept = [m for m in mutants if m[1] in mine]
        os.write(2, f"{PART_PREFIX} {part + 1}/{parts} {len(kept)} of {len(mutants)}\n".encode())
        return kept, data

    return collect


def _time_mutants(runner_class) -> None:
    """Times the mutant step: from the runner's startup to mutmut's exit."""
    startup = runner_class.startup

    @functools.wraps(startup)
    def timed_startup(self, *args, **kwargs):
        start, pid = time.monotonic(), os.getpid()
        atexit.register(lambda: os.getpid() == pid and note("mutants", time.monotonic() - start))
        return startup(self, *args, **kwargs)

    runner_class.startup = timed_startup


def install() -> None:
    import mutmut.__main__ as main
    from mutmut.workers.isolation import ForkServerRunner

    for module_name, path, step in STEPS:
        owner, name = _owner(module_name, path)
        setattr(owner, name, _timed(getattr(owner, name), step))
    main.collect_source_file_mutation_data = _only_my_part(main.collect_source_file_mutation_data)
    _time_mutants(ForkServerRunner)
