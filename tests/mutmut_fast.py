"""A cheaper trampoline for mutmut: each function finds its target once per mutant.

mutmut puts a trampoline around every function of a mutated module. On
each call it reads the active mutant from os.environ, splits its name and
looks the function up. That makes the tests run about three times slower
than plain code. Here a plain function works out its target (the active
mutant, or the original) on its first call and calls it straight after.

The target changes only when the active mutant does. mutmut changes it
only through set_mutant_under_test, so the patched one bumps a
generation, and each wrapper works its target out again after a bump.

These still go through mutmut's own trampoline on every call:
- classmethods, generators, coroutines and async generators;
- the "stats" and "fail" modes, which record hits or raise;
- a function whose mutants dict has no "_mutmut_orig" yet.

mutmut_run.py calls install() before mutmut starts. The fork server and
the stats run are forks of that process, so both inherit it. This module
imports only mutmut: the decorator runs when a mutated module is
imported, so it must be in place before any module of ours is.

It relies on mutmut internals, a version uv.lock pins. CONTRACT lists
them, and tests/test_mutmut_fast.py fails when one moves.
"""

from __future__ import annotations

import inspect
import sys
from functools import wraps

import mutmut.mutation.trampoline as trampoline

ORIGINAL_WRAP = trampoline.wrap_in_trampoline
ORIGINAL_SET = trampoline.set_mutant_under_test
ORIG_KEY = "_mutmut_orig"
SLOW_MODES = ("stats", "fail")
# What this module relies on inside mutmut. test_mutmut_fast.py checks each.
CONTRACT = (
    "mutmut.mutation.trampoline.wrap_in_trampoline(mutants_dict, is_classmethod=False)",
    "mutmut.mutation.trampoline.set_mutant_under_test(name)",
    "mutmut.mutation.trampoline.get_mutant_under_test()",
    "the generated code fills mutants_dict['_mutmut_orig'] after the decorator runs",
    "the trampoline's modes 'stats' and 'fail'",
    "mutmut changes the mutant only through set_mutant_under_test",
)

_generation = 0


def bump() -> None:
    """Makes every wrapper work out its target again on its next call."""
    global _generation
    _generation += 1


def set_mutant_under_test(name: str | None) -> None:
    ORIGINAL_SET(name)
    bump()


def _plain(func) -> bool:
    return inspect.isfunction(func) and not (
        inspect.isgeneratorfunction(func) or inspect.iscoroutinefunction(func) or inspect.isasyncgenfunction(func)
    )


def _target(mutants_dict: dict, module: str):
    """What a function of `module` calls under the active mutant; None: mutmut's own trampoline."""
    name = trampoline.get_mutant_under_test()
    if name in SLOW_MODES:
        return None
    mod, _, mutant = name.rpartition(".")
    target = mutants_dict.get(mutant) if mod == module else None
    return target or mutants_dict[ORIG_KEY]


def _fast(func, slow, mutants_dict: dict):
    module = func.__module__
    # The generation it was worked out in, and the target.
    state = [-1, None]

    @wraps(func)
    def fast(*args, **kwargs):
        if state[0] != _generation:
            if ORIG_KEY not in mutants_dict:
                return slow(*args, **kwargs)
            state[0], state[1] = _generation, _target(mutants_dict, module)
        if state[1] is None:
            return slow(*args, **kwargs)
        return state[1](*args, **kwargs)

    fast._daruma_fast = True
    return fast


def wrap_in_trampoline(mutants_dict: dict, is_classmethod: bool = False):
    slow_decorator = ORIGINAL_WRAP(mutants_dict, is_classmethod)

    def decorator(func):
        slow = slow_decorator(func)
        if is_classmethod or not _plain(func):
            return slow
        return _fast(func, slow, mutants_dict)

    return decorator


def installed_in() -> list[str]:
    """The mutmut modules that hold the patched set_mutant_under_test."""
    return sorted(
        name
        for name, module in list(sys.modules.items())
        if name.split(".")[0] == "mutmut" and getattr(module, "set_mutant_under_test", None) is set_mutant_under_test
    )


def install(setattr=setattr) -> None:
    """Puts the cheap trampoline in place of mutmut's.

    mutmut's modules import set_mutant_under_test by name, so every copy
    of it is replaced. `setattr` lets a test undo it (monkeypatch.setattr).
    """
    import mutmut.__main__  # noqa: F401  Both import set_mutant_under_test by name.
    import mutmut.workers.isolation  # noqa: F401

    for name, module in list(sys.modules.items()):
        if name.split(".")[0] == "mutmut" and getattr(module, "set_mutant_under_test", None) is ORIGINAL_SET:
            setattr(module, "set_mutant_under_test", set_mutant_under_test)
    setattr(trampoline, "wrap_in_trampoline", wrap_in_trampoline)
