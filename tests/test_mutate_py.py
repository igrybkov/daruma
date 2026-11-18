"""mutate_py.py: mutant names, and --diff on a scratch project with a known gap."""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import tomllib
from pathlib import Path

import changed_lines
import mutate_py
import pytest


@pytest.mark.parametrize(
    ("path", "module"),
    [
        ("src/esphome/components/daruma/registry.py", "esphome.components.daruma.registry"),
        ("src/esphome/components/daruma_sprites/__init__.py", "esphome.components.daruma_sprites"),
        ("tools/build.py", "tools.build"),
    ],
)
def test_module_name_is_the_name_mutmut_gives(path: str, module: str) -> None:
    assert mutate_py.module_name(path) == module


def test_mutant_module_drops_the_function_and_class() -> None:
    assert mutate_py.mutant_module("a.b.x_run__mutmut_3") == "a.b"
    assert mutate_py.mutant_module("a.b.xǁBoxǁgrow__mutmut_1") == "a.b"


def test_stray_names_are_the_modules_with_no_mutants() -> None:
    names = ["esphome.components.daruma.registry.x_f__mutmut_1"]
    modules = ["esphome.components.daruma.registry", "src.esphome.components.daruma.registry"]
    assert mutate_py.stray_names(names, modules) == ["src.esphome.components.daruma.registry"]


@pytest.mark.skipif(shutil.which("git") is None, reason="needs git")
def test_the_mutants_copy_has_every_top_level_entry() -> None:
    tracked = subprocess.run(
        ["git", "-C", str(mutate_py.ROOT), "ls-files"], capture_output=True, text=True, check=True
    ).stdout.split()
    config = tomllib.loads((mutate_py.ROOT / "pyproject.toml").read_text())["tool"]["mutmut"]
    copied = set(config["also_copy"]) | {"tests", "pyproject.toml"}
    assert sorted({path.split("/")[0] for path in tracked} - copied) == []


# A module with a gap: no test tells `>=` from `>`, because none passes 0.
MODULE = """def sign(n):
    if n >= 0:
        return 1
    return -1
"""
TEST = """from pkg.mod import sign


def test_sign():
    assert sign(5) == 1
    assert sign(-5) == -1
"""
CONFIG = """[tool.mutmut]
source_paths = ["src/pkg/mod.py"]
pytest_add_cli_args_test_selection = ["tests"]
pytest_add_cli_args = ["-p", "no:cacheprovider"]
process_isolation = "forkserver"
"""


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.mark.skipif(shutil.which("git") is None, reason="needs git")
@pytest.mark.skipif(importlib.util.find_spec("mutmut") is None, reason="needs mutmut (the mutation group)")
def test_diff_finds_a_survivor_on_a_changed_line(tmp_path: Path, monkeypatch, capsys) -> None:
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    (tmp_path / "src" / "pkg" / "__init__.py").write_text("")
    (tmp_path / "src" / "pkg" / "mod.py").write_text("def sign(n):\n    return 1\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_mod.py").write_text(TEST.replace("    assert sign(-5) == -1\n", ""))
    (tmp_path / "pyproject.toml").write_text(CONFIG)
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "-c", "user.email=t@example.com", "-c", "user.name=T", "commit", "-q", "-m", "base")
    (tmp_path / "src" / "pkg" / "mod.py").write_text(MODULE)
    (tmp_path / "tests" / "test_mod.py").write_text(TEST)
    monkeypatch.setattr(mutate_py, "ROOT", tmp_path)
    monkeypatch.setattr(changed_lines, "ROOT", tmp_path)

    assert mutate_py.run_diff("main") == 1
    out = capsys.readouterr().out
    assert "src/pkg/mod.py:2: survived" in out
    assert "+ if n > 0:" in out
