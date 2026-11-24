"""mutmut_steps.py and mutmut_run.py's copy: each mutmut internal they rely on is still there.

A split run keeps one part's mutants by wrapping the place mutmut picks
them. If a mutmut upgrade moves that place, every part would run every
mutant; mutate_py.py stops then, and these checks name what moved.
"""

from __future__ import annotations

import importlib
import inspect
import types
from pathlib import Path

import mutmut.__main__ as main
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


def test_mutmut_keeps_a_mutant_file_that_is_newer_than_its_source() -> None:
    source = _source(main.create_mutants_for_file)
    assert "if source_mtime < mutant_mtime:" in source, (
        "mutmut changed when it makes a file's mutants again: copy_also_but_sources relies on the times"
    )


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


def test_mutmut_picks_its_mutants_in_one_place() -> None:
    run = _source(main._run)
    assert "mutants, source_file_mutation_data_by_path = collect_source_file_mutation_data(" in run, (
        "mutmut's _run no longer gets its mutants from collect_source_file_mutation_data: parts would run them all"
    )
    assert "for mutation_data, mutant_name, result in mutants:" in run, "mutmut's mutant list changed its shape"


def test_a_part_keeps_every_nth_mutant(monkeypatch) -> None:
    mutants = [(None, f"m.x_f__mutmut_{i}", None) for i in range(1, 8)]
    collect = mutmut_steps._only_my_part(lambda **kw: (mutants, "data"))
    monkeypatch.delenv(mutmut_steps.PART, raising=False)
    assert collect(mutant_names=[]) == (mutants, "data")
    monkeypatch.setenv(mutmut_steps.PART, "2/3")
    kept, data = collect(mutant_names=[])
    assert [name for _, name, _ in kept] == mutmut_steps.part_of([name for _, name, _ in mutants], 1, 3)
    assert data == "data"
