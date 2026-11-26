"""mutate_py.py: mutant names, and --diff on a scratch project with a known gap."""

from __future__ import annotations

import json
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
import mutmut_steps
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

    _two_parts_on_another_runner(tmp_path, monkeypatch, capsys, status)


def _two_parts_on_another_runner(project: Path, monkeypatch, capsys, status: dict[str, str]) -> None:
    """Each part runs on a fresh copy of the project, as a CI runner does,
    and together they find what one run found."""
    found = {}
    survivors = 0
    for part in ((0, 2), (1, 2)):
        runner = project.parent / f"runner{part[0]}"
        shutil.copytree(project, runner, ignore=shutil.ignore_patterns("mutants"))
        monkeypatch.setattr(mutate_py, "ROOT", runner)
        monkeypatch.setattr(changed_lines, "ROOT", runner)
        code = mutate_py.run_diff("main", part=part)
        out = capsys.readouterr().out
        assert f"daruma-part: {part[0] + 1}/2 " in out
        mine = {n: s for n, s in mutate_py.results().items() if s != "not checked"}
        assert set(mine) == set(mutmut_steps.part_of(status, *part)), "a part runs its own mutants only"
        survivors += out.count("src/pkg/mod.py:2: pkg.mod.x_sign")
        assert code == (1 if "survived" in mine.values() else 0)
        found |= mine
    assert found == status, "the parts find what one run found"
    assert survivors == 2, "the parts report both survivors"


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


def test_a_part_switch_never_reaches_a_run_a_test_starts(tmp_path: Path, monkeypatch) -> None:
    script = tmp_path / "env.py"
    script.write_text("import json, os, sys\nprint(json.dumps(dict(os.environ)))\n")
    monkeypatch.setattr(mutate_py, "SHIM", script)
    monkeypatch.setenv(mutate_py.PART, "1/3")
    assert mutate_py.PART not in json.loads(mutate_py.mutmut("results").stdout)
    seen = json.loads(mutate_py.mutmut("results", env={mutate_py.PART: "2/3"}).stdout)
    assert seen[mutate_py.PART] == "2/3", "a switch passed on purpose gets through"


def test_the_parts_hold_every_mutant_exactly_once() -> None:
    names = [f"pkg.mod{m}.x_f{f}__mutmut_{i}" for m in range(3) for f in range(17) for i in range(1, 40)]
    for parts in (1, 2, 3):
        split = [mutmut_steps.part_of(reversed(names), k, parts) for k in range(parts)]
        held = [n for part in split for n in part]
        assert sorted(held) == sorted(names), "every mutant once, none twice"
        assert max(map(len, split)) - min(map(len, split)) <= 1
    # Interleaved: a function's mutants spread across the parts.
    slow = [n for n in names if ".x_f3__" in n and n.startswith("pkg.mod1.")]
    assert all(set(slow) & set(mutmut_steps.part_of(names, k, 3)) for k in range(3))


@pytest.mark.parametrize(("text", "part"), [("1/3", (0, 3)), ("3/3", (2, 3)), ("1/1", (0, 1))])
def test_parse_part(text: str, part: tuple[int, int]) -> None:
    assert mutmut_steps.parse_part(text) == part


@pytest.mark.parametrize("text", ["0/3", "4/3", "3", "a/b"])
def test_parse_part_rejects(text: str) -> None:
    with pytest.raises(ValueError):
        mutmut_steps.parse_part(text)


def test_targets_skip_files_that_are_not_python() -> None:
    # A component folder holds C++ headers next to its Python.
    changed = {
        "src/esphome/components/daruma_weather/weather.h": {1, 2, 3},
        "src/esphome/components/daruma_weather/__init__.py": set(range(1, 200)),
    }
    targets = mutate_py._targets(changed)
    assert targets
    assert {path for path, _ in targets.values()} == {"src/esphome/components/daruma_weather/__init__.py"}


@pytest.mark.parametrize(("functions", "parts"), [(0, "[1]"), (20, "[1]"), (21, "[1, 2, 3]")])
def test_more_than_the_threshold_of_functions_runs_in_three_parts(
    monkeypatch, tmp_path: Path, functions: int, parts: str
) -> None:
    targets = {f"m.x_f{i}__mutmut_*": ("m.py", (i, i)) for i in range(functions)}
    monkeypatch.setattr(mutate_py, "changed_lines", lambda base, paths: {})
    monkeypatch.setattr(mutate_py, "_targets", lambda changed: targets)
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "out"))
    assert mutate_py.PARTS_THRESHOLD == 20
    assert mutate_py.count_parts("main") == 0
    assert (tmp_path / "out").read_text() == f"parts={parts}\n"
