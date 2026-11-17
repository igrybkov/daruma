"""Collects the host C++ tests: each tests/test_*.cpp is one pytest test.

    uv run pytest tests/test_layout.cpp   # one C++ test
    uv run pytest tests -m cpp            # every C++ test
    uv run pytest tests -m "not cpp"      # every Python test

The test builds the file with the host's c++ and runs it. The program
prints FAIL lines and exits non-zero when a check fails.

The headers include each other as an ESPHome build sees them
(esphome/components/<name>/...), so the tests compile against a scratch
folder where esphome/components points at this repository's components/.
test_frames.cpp needs a fixture; test_frames.py builds and runs it.

For coverage: CXXFLAGS adds compiler flags (--coverage), and
DARUMA_CPP_OUT names a folder that keeps the programs and their data.
"""

import os
import shutil
import subprocess
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
# Built and run by their own Python tests.
NOT_COLLECTED = {"test_frames.cpp"}


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "cpp: a host C++ test (tests/test_*.cpp)")


def pytest_collect_file(parent: pytest.Collector, file_path: Path) -> "CppFile | None":
    if file_path.suffix == ".cpp" and file_path.name.startswith("test_") and file_path.name not in NOT_COLLECTED:
        return CppFile.from_parent(parent, path=file_path)
    return None


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
        if shutil.which("c++") is None:
            pytest.skip("needs a c++ compiler")
        with tempfile.TemporaryDirectory() as tmp:
            include = Path(tmp) / "include"
            (include / "esphome").mkdir(parents=True)
            (include / "esphome" / "components").symlink_to(ROOT / "components")
            out = Path(os.environ.get("DARUMA_CPP_OUT") or tmp)
            out.mkdir(parents=True, exist_ok=True)
            binary = out / self.path.stem
            _run(
                "build",
                [
                    "c++",
                    "-std=c++17",
                    "-Wall",
                    "-Wextra",
                    *os.environ.get("CXXFLAGS", "").split(),
                    f"-I{include}",
                    f"-I{ROOT / 'components' / 'daruma'}",
                    f"-I{ROOT / 'components' / 'daruma_weather'}",
                    str(self.path),
                    "-o",
                    str(binary),
                ],
            )
            _run("run", [str(binary)])

    def repr_failure(self, excinfo: pytest.ExceptionInfo[BaseException], style: Any = None) -> Any:
        if isinstance(excinfo.value, CppFailure):
            return str(excinfo.value)
        return super().repr_failure(excinfo, style)

    def reportinfo(self) -> tuple[Path, None, str]:
        return self.path, None, self.name


def _run(step: str, cmd: list[str]) -> None:
    done = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if done.returncode:
        raise CppFailure(f"{step} exited {done.returncode}\n{done.stdout}{done.stderr}".rstrip())
