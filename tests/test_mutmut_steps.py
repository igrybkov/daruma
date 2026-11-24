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

import mutate_plan
import mutmut.__main__ as main
import mutmut.stats
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
    for call in ("create_mutants(", "collect_or_load_stats(", "runner.run_clean_tests(", "runner.startup()"):
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
