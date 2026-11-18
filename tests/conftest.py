"""Collects the host C++ tests: each tests/test_*.cpp is one pytest test.

    uv run pytest tests/test_layout.cpp   # one C++ test
    uv run pytest tests -m cpp            # every C++ test
    uv run pytest tests -m "not cpp"      # every Python test

The test builds the file with the host's c++ (or $CXX, cpp_build.py)
and runs it. The program prints FAIL lines and exits non-zero when a
check fails.

The headers include each other as an ESPHome build sees them
(esphome/components/<name>/...). src/ has that layout, so the tests
compile with -I src.

Importing esphome_components first lets the Python tests import the
components by their ESPHome names (esphome.components.daruma.registry).
test_frames.cpp needs a fixture; test_frames.py builds and runs it.

For coverage: CXXFLAGS adds compiler flags (--coverage), and
DARUMA_CPP_OUT names a folder that keeps the programs and their data.
"""

import json
import os
import signal
import subprocess
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import cpp_build
import esphome_components  # noqa: F401
import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
COMPONENTS = ROOT / "src" / "esphome" / "components"
# Paths relative to HERE. Built and run by their own Python tests.
NOT_COLLECTED = {Path("test_frames.cpp")}


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "cpp: a host C++ test (tests/test_*.cpp)")


# Each test's time in mutmut's first full run, while mutmut runs a mutant.
# Filled at collection: mutmut's fork server imports this file once, before
# any mutant, and forks each mutant's run from it.
MUTANT_DURATIONS: dict[str, float] = {}
# A test under a mutant may take this many times its clean time, plus a
# second, before it fails.
MUTANT_SLOWDOWN = 10


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Under mutmut, run a mutant's fastest tests first.

    mutmut stops at the first failing test (-x) but passes the tests in no
    set order. A fast test kills most mutants, so it saves the slow persona
    tests for the mutants that survive it. The times are in
    mutmut-stats.json at the root of mutmut's copy.
    """
    MUTANT_DURATIONS.clear()
    stats = ROOT / "mutmut-stats.json"
    if os.environ.get("MUTANT_UNDER_TEST") in (None, "", "fail") or not stats.exists():
        return
    MUTANT_DURATIONS.update(json.loads(stats.read_text()).get("duration_by_test", {}))
    items.sort(key=lambda item: MUTANT_DURATIONS.get(item.nodeid, 0.0))


class MutantTimeout(Exception):
    """A test ran far longer under a mutant than in the clean run."""


@pytest.hookimpl(wrapper=True)
def pytest_runtest_call(item: pytest.Item) -> Iterator[None]:
    """Under mutmut, fail a test that runs far past its clean time.

    A mutant can make a loop run forever. mutmut's own timeout counts all
    of a mutant's tests, so it waits long after the first one hangs.
    """
    if item.nodeid not in MUTANT_DURATIONS:
        return (yield)

    def expire(signum: int, frame: Any) -> None:
        raise MutantTimeout(item.nodeid)

    previous = signal.signal(signal.SIGALRM, expire)
    signal.setitimer(signal.ITIMER_REAL, 1 + MUTANT_SLOWDOWN * MUTANT_DURATIONS[item.nodeid])
    try:
        return (yield)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def pytest_collect_file(parent: pytest.Collector, file_path: Path) -> "CppFile | None":
    """Only the test_*.cpp files in this folder, not in its subfolders."""
    path = file_path.resolve()
    if path.parent != HERE or not path.match("test_*.cpp"):
        return None
    if path.relative_to(HERE) in NOT_COLLECTED:
        return None
    return CppFile.from_parent(parent, path=file_path)


class CppFailure(Exception):
    """A step that exited non-zero, with what it printed."""


class CppFile(pytest.File):
    def collect(self) -> Iterator["CppTest"]:
        yield CppTest.from_parent(self, name=self.path.stem)


class CppTest(pytest.Item):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.add_marker(pytest.mark.cpp)

    def runtest(self) -> None:
        if not cpp_build.available():
            pytest.skip("needs a c++ compiler")
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(os.environ.get("DARUMA_CPP_OUT") or tmp)
            out.mkdir(parents=True, exist_ok=True)
            binary = out / self.path.stem
            extra = os.environ.get("CXXFLAGS", "").split()
            args = [
                "-std=c++17",
                "-Wall",
                "-Wextra",
                *extra,
                f"-I{ROOT / 'src'}",
                f"-I{COMPONENTS / 'daruma'}",
                f"-I{COMPONENTS / 'daruma_weather'}",
                str(self.path),
            ]
            _check("build", cpp_build.build(args, binary, extra))
            _check("run", subprocess.run([str(binary)], capture_output=True, text=True, check=False))

    def repr_failure(self, excinfo: pytest.ExceptionInfo[BaseException], style: Any = None) -> Any:
        if isinstance(excinfo.value, CppFailure):
            return str(excinfo.value)
        return super().repr_failure(excinfo, style)

    def reportinfo(self) -> tuple[Path, None, str]:
        return self.path, None, self.name


def _check(step: str, done: subprocess.CompletedProcess) -> None:
    if done.returncode:
        raise CppFailure(f"{step} exited {done.returncode}\n{done.stdout}{done.stderr}".rstrip())
