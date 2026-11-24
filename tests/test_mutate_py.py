"""mutate_py.py: mutant names, and --diff on a scratch project with a known gap."""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
import time
import tomllib
import types
from pathlib import Path

import changed_lines
import mutate_py
import mutmut_run
import pytest


@pytest.mark.parametrize(
    ("path", "module"),
    [
        ("src/esphome/components/daruma/registry.py", "esphome.components.daruma.registry"),
        ("src/esphome/components/daruma_sprites/__init__.py", "esphome.components.daruma_sprites"),
        ("tools/build.py", "tools.build"),
        ("pixel/daruma-pixel/src/daruma_pixel/pixelkit.py", "daruma_pixel.pixelkit"),
        ("pixel/shapes-pets/src/daruma_shapes/pets/__init__.py", "daruma_shapes.pets"),
        ("pixel/persona-corgi/src/daruma_personas/corgi/moods.py", "daruma_personas.corgi.moods"),
        ("demos/scenario.py", "scenario"),
    ],
)
def test_module_name_is_the_name_mutmut_gives(path: str, module: str) -> None:
    assert mutate_py.module_name(path) == module


def test_mutant_module_drops_the_function_and_class() -> None:
    assert mutate_py.mutant_module("a.b.x_run__mutmut_3") == "a.b"
    assert mutate_py.mutant_module("a.b.xǁBoxǁgrow__mutmut_1") == "a.b"


@pytest.mark.parametrize(
    ("function", "group"),
    [
        ("esphome.components.daruma.registry.x_check", "esphome.components.daruma"),
        ("daruma_shapes.pets.rig.x__tail", "daruma_shapes.pets"),
        ("daruma_personas.corgi.moods.x_animations", "daruma_personas.corgi"),
        ("daruma_pixel.pixelkit.x_mask", "daruma_pixel"),
        ("scenario.x_load", "scenario"),
    ],
)
def test_group_is_the_package_a_function_belongs_to(function: str, group: str) -> None:
    assert mutmut_run.group(function) == group


def test_spread_charges_an_import_time_call_to_the_tests_of_its_package() -> None:
    tests = {
        "daruma_personas.corgi.moods.x_animations": {"test_first"},
        "daruma_personas.corgi.breed.x_render": {"test_corgi"},
        "daruma_personas.daruma.doll.x_egg": {"test_daruma"},
    }
    mutmut_run.spread(tests, {"daruma_personas.corgi.moods.x_animations"})
    assert tests["daruma_personas.corgi.moods.x_animations"] == {"test_first", "test_corgi"}
    assert tests["daruma_personas.daruma.doll.x_egg"] == {"test_daruma"}


def test_importing_is_true_only_under_a_module_top_level(monkeypatch) -> None:
    def probe():
        return (lambda: mutmut_run.importing())()

    assert not probe()
    seen = {}
    code = compile("seen['at_import'] = probe()", "<scratch>", "exec")
    exec(code, {"__name__": "scratch", "probe": probe, "seen": seen})
    assert not seen["at_import"], "exec'd code is no import"
    module = types.ModuleType("scratch")
    module.__dict__.update(probe=probe, seen=seen)
    monkeypatch.setitem(sys.modules, "scratch", module)
    exec(code, module.__dict__)
    assert seen["at_import"]


def test_clear_caches_empties_only_the_caches_under_the_folder(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "cached_here.py").write_text("import functools\n@functools.cache\ndef f(x):\n    return [x]\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.chdir(tmp_path)
    import cached_here

    first = cached_here.f(1)
    assert cached_here.f(1) is first
    mutmut_run.clear_caches()
    assert cached_here.f(1) is not first


def test_a_name_that_starts_with_a_path_stops_the_run(monkeypatch) -> None:
    out = "    daruma_pixel.pixelkit.x_mask__mutmut_1: killed\n    pixel.x.src.y.x_f__mutmut_1: survived\n"
    monkeypatch.setattr(mutate_py, "mutmut", lambda *a, **k: subprocess.CompletedProcess(a, 0, out, ""))
    with pytest.raises(mutate_py.StrayNames):
        mutate_py.results()


def test_report_lists_survivors_and_untested_code_then_counts_per_part() -> None:
    status = {
        "daruma_pixel.pixelkit.x_mask__mutmut_1": "killed",
        "daruma_pixel.pixelkit.x_mask__mutmut_2": "survived",
        "daruma_shapes.pets.rig.x_render__mutmut_1": "no tests",
        "esphome.components.daruma.registry.x_f__mutmut_1": "timeout",
        "scenario.x_flatten__mutmut_1": "killed",
    }
    report = mutate_py.report(status).splitlines()
    assert report[:2] == [
        "Survived: a test runs the code but misses the change (1):",
        "  daruma_pixel.pixelkit.x_mask__mutmut_2",
    ]
    assert "No tests: no test runs the code (1):" in report
    rows = {line.split()[0]: line.split()[1:] for line in report if line.startswith(("daruma", "esphome", "demos"))}
    assert rows["daruma_pixel"] == ["2", "1", "0", "1", "0"]
    assert rows["daruma_shapes.pets"] == ["1", "0", "0", "0", "1"]
    assert rows["esphome.components.daruma"] == ["1", "0", "1", "0", "0"]
    assert rows["demos"] == ["1", "1", "0", "0", "0"]


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
# The call at import runs in mutmut's fork server, before it forks a
# mutant: a trampoline that kept its target past the fork would miss the
# mutant, and no mutant would be killed.
MODULE = """def sign(n):
    if n >= 0:
        return 1
    return -1


ONE = sign(1)
"""
# In a mutant child the test notes whether sign is mutmut_fast's trampoline.
TEST = """import os

from pkg.mod import sign


def test_sign():
    mutant = os.environ.get("MUTANT_UNDER_TEST", "")
    if "__mutmut_" in mutant:
        with open(os.environ["DARUMA_PROBE"], "a") as probe:
            probe.write(f"{mutant} {getattr(sign, '_daruma_fast', False)}\\n")
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
    _git(
        tmp_path,
        "-c",
        "user.email=t@example.com",
        "-c",
        "user.name=T",
        "-c",
        "commit.gpgsign=false",
        "commit",
        "-q",
        "-m",
        "base",
    )
    (tmp_path / "src" / "pkg" / "mod.py").write_text(MODULE)
    (tmp_path / "tests" / "test_mod.py").write_text(TEST)
    monkeypatch.setattr(mutate_py, "ROOT", tmp_path)
    monkeypatch.setattr(changed_lines, "ROOT", tmp_path)
    probe = tmp_path / "probe.txt"
    monkeypatch.setenv("DARUMA_PROBE", str(probe))

    assert mutate_py.run_diff("main") == 1
    out = capsys.readouterr().out
    assert "Survived: a test runs the line but misses the change (2):\nsrc/pkg/mod.py:2: pkg.mod.x_sign" in out
    assert "+ if n > 0:" in out
    status = mutate_py.results()
    assert "killed" in status.values(), status
    # tests/mutmut_fast.py: a mutmut upgrade must not drop the cheap trampoline.
    seen = dict(line.split() for line in probe.read_text().splitlines())
    assert set(seen) == set(status), "each mutant ran the probe test"
    assert set(seen.values()) == {"True"}, "a mutant ran under mutmut's own trampoline, not mutmut_fast's"


def test_mutmut_past_its_minutes_stops_with_its_children(tmp_path: Path, monkeypatch) -> None:
    child = tmp_path / "child.pid"
    script = tmp_path / "slow.py"
    script.write_text(
        "import subprocess, sys, time\n"
        f"p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
        f"open({str(child)!r}, 'w').write(str(p.pid))\n"
        "time.sleep(60)\n"
    )
    monkeypatch.setattr(mutate_py, "SHIM", script)
    with pytest.raises(mutate_py.OutOfTime):
        mutate_py.mutmut("run", minutes=0.05)
    pid = int(child.read_text())
    with pytest.raises(ProcessLookupError):
        for _ in range(50):
            os.kill(pid, 0)
            time.sleep(0.1)
