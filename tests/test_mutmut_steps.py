"""mutmut_steps.py and mutate_plan.py: each mutmut internal they rely on is still there.

A planned run reuses the plan's mutants and stats in each part. If a
mutmut upgrade moves where it keeps them, or how it decides to record
again, a part would redo the recorded run. The no-stats guard stops it
then, and the planted run in test_mutate_py.py checks that. These checks
name what moved.
"""

from __future__ import annotations

import importlib
import inspect
import types
from pathlib import Path

import mutate_plan
import mutmut.__main__ as main
import mutmut.stats
import mutmut_run
import mutmut_steps
from mutmut.workers.isolation import ForkServerRunner


def _source(func) -> str:
    return inspect.getsource(inspect.unwrap(func))


def test_each_step_it_wraps_is_still_there() -> None:
    for module_name, path, step in mutmut_steps.STEPS:
        owner = importlib.import_module(module_name)
        for part in path.split("."):
            assert hasattr(owner, part), f"{module_name}.{path} is gone: the {step!r} step is not timed"
            owner = getattr(owner, part)
        assert callable(owner)
    assert callable(ForkServerRunner.startup), "ForkServerRunner.startup is gone: the mutants step is not timed"


def test_mutmuts_run_still_calls_the_steps_by_these_names() -> None:
    run = _source(main._run)
    for call in (
        "copy_also_copy_files()",
        "create_mutants(",
        "collect_or_load_stats(",
        "clean_test_exit_code = runner.run_clean_tests(",
        "runner.startup()",
    ):
        assert call in run, f"mutmut's _run no longer calls {call}"
    assert "run_forced_fail_test(runner)" in run
    assert "runner.run_forced_fail()" in _source(main.run_forced_fail_test)


def test_the_recorded_run_goes_through_run_stats_collection() -> None:
    stats = _source(main.collect_or_load_stats)
    assert stats.count("run_stats_collection(runner") == 2, (
        "collect_or_load_stats changed how it records: the no-stats guard wraps run_stats_collection"
    )
    assert "did_load = load_stats()" in stats
    assert "_apply_config_change_invalidation(" in stats


def test_the_stats_live_where_the_plan_ships_them() -> None:
    path = f'"{mutate_plan.STATS_FILE.as_posix()}"'
    assert path in _source(mutmut.stats.load_stats), f"mutmut no longer reads its stats from {path}"
    assert path in _source(mutmut.stats.save_stats), f"mutmut no longer writes its stats to {path}"
    for key in ("tests_by_mangled_function_name", "duration_by_test"):
        assert f'"{key}"' in _source(mutmut.stats.load_stats), f"mutmut's stats have no {key!r} any more"


def test_mutmut_keeps_a_mutant_file_that_is_newer_than_its_source() -> None:
    source = _source(main.create_mutants_for_file)
    assert "if source_mtime < mutant_mtime:" in source, (
        "mutmut changed when it makes a file's mutants again: mark_mutants_newer relies on the times"
    )


def test_install_wraps_and_the_guard_stops_a_second_recorded_run(monkeypatch) -> None:
    for module_name, path, _ in mutmut_steps.STEPS:
        owner, name = mutmut_steps._owner(module_name, path)
        monkeypatch.setattr(owner, name, getattr(owner, name))
    for name in ("collect_or_load_stats", "run_stats_collection"):
        monkeypatch.setattr(main, name, getattr(main, name))
    monkeypatch.setattr(ForkServerRunner, "startup", ForkServerRunner.startup)
    monkeypatch.setattr(main, "run_stats_collection", lambda *a, **k: "recorded")
    mutmut_steps.install()

    exits = []
    monkeypatch.setattr(mutmut_steps.os, "_exit", lambda code: exits.append(code))
    monkeypatch.setenv(mutmut_steps.NO_STATS, "1")
    main.run_stats_collection(None)
    assert exits == [mutmut_steps.STATS_AGAIN]
    monkeypatch.delenv(mutmut_steps.NO_STATS)
    assert main.run_stats_collection(None) == "recorded"


def test_also_copy_leaves_the_mutated_sources_alone(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    for path in ("pkg/mod.py", "pkg/data.txt", "docs/a.md", "mutants/pkg/mod.py"):
        (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / path).write_text(path)
    (tmp_path / "mutants/pkg/mod.py").write_text("mutated")
    config = types.SimpleNamespace(source_paths=["pkg"], also_copy=["pkg", "docs"])
    mutmut_run.copy_also_but_sources(config)
    assert (tmp_path / "mutants/pkg/mod.py").read_text() == "mutated"
    assert (tmp_path / "mutants/docs/a.md").read_text() == "docs/a.md"
    assert not (tmp_path / "mutants/pkg/data.txt").exists(), "copy_src_dir copies the source folders"


def test_a_part_skips_the_clean_tests(monkeypatch) -> None:
    calls = []
    clean = mutmut_steps._clean_in_the_plan(lambda self, tests: calls.append(tests) or 0)
    monkeypatch.setenv(mutmut_steps.NO_STATS, "1")
    assert clean(None, ["t"]) == 0 and calls == []
    monkeypatch.delenv(mutmut_steps.NO_STATS)
    assert clean(None, ["t"]) == 0 and calls == [["t"]]
