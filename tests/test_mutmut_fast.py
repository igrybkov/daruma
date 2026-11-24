"""mutmut_fast.py: the cheap trampoline picks what mutmut's own would, and
each mutmut internal it relies on is still there.

A mutmut upgrade that moves one of them fails here, by name. The planted
run in test_mutate_py.py checks that a real run uses the cheap trampoline.
"""

from __future__ import annotations

import ast
import asyncio
import functools
import importlib.util
import inspect
from pathlib import Path

import pytest

pytest.importorskip("mutmut", reason="needs mutmut (the mutation group)")

import mutmut  # noqa: E402
import mutmut.mutation.trampoline as trampoline  # noqa: E402
import mutmut_fast  # noqa: E402
from mutmut.mutation.file_mutation import mutate_file_contents  # noqa: E402

MUTMUT = Path(mutmut.__file__).parent
TRAMPOLINE = Path(trampoline.__file__)

SOURCE = """
def add(a, b=1):
    return a + b

def count(n):
    for i in range(n):
        yield i * 2

async def fetch(n):
    return n + 1

class Box:
    def __init__(self, n):
        self.n = n

    def grow(self, k):
        return self.n + k

    @classmethod
    def make(cls, n):
        return cls(n + 1)

    @staticmethod
    def half(n):
        return n // 2
"""
MODULE = "probe.mod"
CALLS = {
    "add": lambda ns: ns["add"](3, 4),
    "count": lambda ns: list(ns["count"](3)),
    "fetch": lambda ns: asyncio.run(ns["fetch"](1)),
    "grow": lambda ns: ns["Box"](5).grow(2),
    "make": lambda ns: ns["Box"].make(2).n,
    "half": lambda ns: ns["Box"].half(7),
}


def _outcome(call, ns):
    try:
        return repr(call(ns))
    except Exception as err:
        return type(err).__name__


def _load(code: str, wrap, monkeypatch, seen: list) -> dict:
    """Runs the generated code as module MODULE, under `wrap`. Each mutant
    and original it can tag notes its key in `seen` when it runs."""
    monkeypatch.setattr(trampoline, "wrap_in_trampoline", wrap)
    ns = {"__name__": MODULE}
    exec(compile(code, "<probe>", "exec"), ns)
    for name, mutants in ns.items():
        if not name.startswith("mutants_"):
            continue
        for key, func in mutants.items():
            if inspect.isfunction(func):  # A classmethod's is a bound method: mutmut looks it up by name.
                mutants[key] = _tagged(key, func, seen)
    return ns


def _tagged(key, func, seen):
    @functools.wraps(func)
    def tagged(*args, **kwargs):
        seen.append(key)
        return func(*args, **kwargs)

    return tagged


def _modes(names: list[str]) -> list[str]:
    return [
        "",
        "list_all_tests",
        "stats",
        "fail",
        f"{MODULE}.x_add__mutmut_999",
        "other.mod.x_add__mutmut_1",
        "probe.x_add__mutmut_1",
        *(f"{MODULE}.{name}" for name in names),
    ]


def test_the_cheap_trampoline_calls_what_mutmuts_own_calls(monkeypatch) -> None:
    generated = mutate_file_contents("mod.py", SOURCE)
    monkeypatch.setattr(trampoline, "record_trampoline_hit", lambda name, caller=None: None)
    seen_slow: list[str] = []
    seen_fast: list[str] = []
    slow = _load(generated.code, mutmut_fast.ORIGINAL_WRAP, monkeypatch, seen_slow)
    fast = _load(generated.code, mutmut_fast.wrap_in_trampoline, monkeypatch, seen_fast)

    assert fast["add"]._daruma_fast and fast["Box"].grow._daruma_fast and fast["Box"].half._daruma_fast
    for name in ("count", "fetch"):
        assert not hasattr(fast[name], "_daruma_fast"), f"{name} should keep mutmut's trampoline"
    assert not hasattr(fast["Box"].make, "_daruma_fast"), "a classmethod should keep mutmut's trampoline"

    differ = []
    try:
        for mode in _modes(list(generated.mutant_names)):
            # Set the mode the way a test can, not through set_mutant_under_test:
            # that one writes os.environ for good, and this test also runs in
            # mutant children.
            with monkeypatch.context() as m:
                m.setenv("MUTANT_UNDER_TEST", mode)
                mutmut_fast.bump()
                for call_name, call in CALLS.items():
                    seen_slow.clear()
                    seen_fast.clear()
                    want = (_outcome(call, slow), list(seen_slow))
                    got = (_outcome(call, fast), list(seen_fast))
                    if want != got:
                        differ.append(f"{mode or '(none)'} {call_name}: mutmut {want}, cheap {got}")
    finally:
        mutmut_fast.bump()
    assert not differ, "\n".join(differ)


def test_a_dict_with_no_original_yet_goes_through_mutmuts_trampoline(monkeypatch) -> None:
    mutants: dict = {}

    def f():
        return "f"

    def orig():
        return "orig"

    orig.__name__ = "x_f__mutmut_orig"
    f.__module__ = orig.__module__ = MODULE
    wrapped = mutmut_fast.wrap_in_trampoline(mutants)(f)
    try:
        with monkeypatch.context() as m:
            m.setenv("MUTANT_UNDER_TEST", "")
            mutmut_fast.bump()
            with pytest.raises(KeyError, match="_mutmut_orig"):
                wrapped()
            mutants["_mutmut_orig"] = orig
            assert wrapped() == "orig", "it must not cache the missing original"
    finally:
        mutmut_fast.bump()


# The contract: each mutmut internal mutmut_fast relies on.


def _params(func) -> list[tuple[str, object]]:
    return [(p.name, p.default) for p in inspect.signature(func).parameters.values()]


def test_mutmuts_trampoline_functions_keep_their_shape() -> None:
    empty = inspect.Parameter.empty
    assert _params(mutmut_fast.ORIGINAL_WRAP) == [("mutants_dict", empty), ("is_classmethod", False)], (
        "mutmut.mutation.trampoline.wrap_in_trampoline changed its parameters"
    )
    assert _params(mutmut_fast.ORIGINAL_SET) == [("name", empty)], "set_mutant_under_test changed its parameters"
    assert _params(trampoline.get_mutant_under_test) == [], "get_mutant_under_test changed its parameters"


def test_mutmuts_trampoline_keeps_its_modes() -> None:
    source = inspect.getsource(mutmut_fast.ORIGINAL_WRAP)
    for mode in mutmut_fast.SLOW_MODES:
        assert f'mutant_under_test == "{mode}"' in source, f"mutmut's trampoline no longer has the {mode!r} mode"
    assert 'mutants_dict["_mutmut_orig"]' in source, "mutmut's trampoline no longer calls mutants_dict['_mutmut_orig']"
    assert ".rpartition(" in source, "mutmut's trampoline no longer splits the mutant name at its last dot"


def test_the_generated_code_uses_the_patched_decorator_and_fills_the_original_after() -> None:
    code = mutate_file_contents("mod.py", "def add(a, b):\n    return a + b\n").code
    assert "from mutmut.mutation.trampoline import wrap_in_trampoline as _mutmut_mutated" in code, (
        "the generated code no longer imports wrap_in_trampoline from mutmut.mutation.trampoline"
    )
    decorated = code.index("@_mutmut_mutated(mutants_x_add__mutmut)")
    filled = code.index("mutants_x_add__mutmut['_mutmut_orig'] = ")
    assert decorated < filled, "the generated code no longer fills '_mutmut_orig' after the decorator"


def _sources():
    for path in sorted(MUTMUT.rglob("*.py")):
        yield path, path.read_text()


def _imports_set_by_name(tree: ast.Module) -> bool:
    return any(
        isinstance(node, ast.ImportFrom)
        and node.module == "mutmut.mutation.trampoline"
        and any(alias.name == "set_mutant_under_test" for alias in node.names)
        for node in ast.walk(tree)
    )


def test_only_set_mutant_under_test_changes_the_mutant() -> None:
    moved = [
        str(path.relative_to(MUTMUT))
        for path, text in _sources()
        if path != TRAMPOLINE and ("MUTANT_UNDER_TEST" in text or "_mutant_under_test " in text)
    ]
    assert not moved, f"mutmut sets the mutant outside set_mutant_under_test, in {moved}"
    tree = ast.parse(TRAMPOLINE.read_text())
    writers = [
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and any(
            marker in ast.unparse(node) for marker in ("global _mutant_under_test", "os.environ['MUTANT_UNDER_TEST'] =")
        )
    ]
    assert writers == ["set_mutant_under_test"], f"these trampoline functions set the mutant: {writers}"


def test_install_replaces_every_copy_of_set_mutant_under_test(monkeypatch) -> None:
    mutmut_fast.install(monkeypatch.setattr)
    assert trampoline.wrap_in_trampoline is mutmut_fast.wrap_in_trampoline
    importers = []
    for path, text in _sources():
        if _imports_set_by_name(ast.parse(text)):
            name = ".".join(path.relative_to(MUTMUT.parent).with_suffix("").parts)
            importers.append(name)
            assert importlib.util.find_spec(name), name
    assert importers, "no mutmut module imports set_mutant_under_test by name any more"
    missed = sorted((set(importers) | {"mutmut.mutation.trampoline"}) - set(mutmut_fast.installed_in()))
    assert not missed, f"install() did not replace set_mutant_under_test in {missed}"
