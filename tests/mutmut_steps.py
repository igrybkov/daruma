"""Times mutmut's steps, and stops or guards them for a planned run.

mutmut run makes the mutants, records which tests reach which function
(the recorded run, or stats run), runs the clean tests and the forced
fail, then runs the mutants. install() wraps those steps:

- Each step writes `daruma-step: <name> <seconds>` to stderr (fd 2, past
  mutmut's output capture). mutate_py.py prints those lines.
- With DARUMA_MUTMUT_PLAN=1, mutmut stops after the recorded run. The
  plan job then has the mutants and the stats that the parts reuse.
- With DARUMA_MUTMUT_NO_STATS=1, a recorded run stops mutmut with an
  error. A part sets it: it must reuse the plan's stats, never redo them.

It relies on mutmut internals, a version uv.lock pins. STEPS names them,
and tests/test_mutmut_steps.py fails when one moves.
"""

from __future__ import annotations

import atexit
import functools
import os
import time

PLAN = "DARUMA_MUTMUT_PLAN"
NO_STATS = "DARUMA_MUTMUT_NO_STATS"
PREFIX = "daruma-step:"
# The exit code of a part that would redo the recorded run.
STATS_AGAIN = 3
# (module, attribute, step name): what install() wraps.
STEPS = (
    ("mutmut.__main__", "create_mutants", "generate"),
    ("mutmut.__main__", "collect_or_load_stats", "stats"),
    ("mutmut.workers.isolation", "ForkServerRunner.run_clean_tests", "clean"),
    ("mutmut.workers.isolation", "ForkServerRunner.run_forced_fail", "forced-fail"),
)


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


def _stats_then_stop(original):
    @functools.wraps(original)
    def stats(*args, **kwargs):
        result = original(*args, **kwargs)
        if os.environ.get(PLAN):
            note("planned", 0)
            raise SystemExit(0)
        return result

    return stats


def _no_stats_again(original):
    @functools.wraps(original)
    def run_stats_collection(*args, **kwargs):
        if os.environ.get(NO_STATS):
            os.write(2, b"daruma: this part would redo the recorded run; it must reuse the plan's stats\n")
            os._exit(STATS_AGAIN)
        return original(*args, **kwargs)

    return run_stats_collection


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
    main.collect_or_load_stats = _stats_then_stop(main.collect_or_load_stats)
    main.run_stats_collection = _no_stats_again(_timed(main.run_stats_collection, "recorded-run"))
    _time_mutants(ForkServerRunner)
