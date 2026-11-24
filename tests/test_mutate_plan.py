"""mutate_plan.py: how many parts, and which mutants go to each.

The planted run in test_mutate_py.py runs a real plan in two parts.
"""

from __future__ import annotations

import os
import random
from pathlib import Path

import mutate_plan
import pytest


def _names(count: int, functions: int = 10) -> list[str]:
    return [f"pkg.mod.x_f{i % functions}__mutmut_{i // functions + 1}" for i in range(count)]


def _stats(seconds_by_function: dict[str, float]) -> dict:
    return {
        "tests_by_mangled_function_name": {f: [f"test_{f}"] for f in seconds_by_function},
        "duration_by_test": {f"test_{f}": s for f, s in seconds_by_function.items()},
    }


def test_a_mutant_costs_the_time_of_the_tests_that_reach_it() -> None:
    stats = {
        "tests_by_mangled_function_name": {"pkg.mod.x_f": ["a", "b"]},
        "duration_by_test": {"a": 1.5, "b": 0.5},
    }
    cost = mutate_plan.costs(["pkg.mod.x_f__mutmut_1", "pkg.mod.x_g__mutmut_1"], stats)
    assert cost == {"pkg.mod.x_f__mutmut_1": 2.0, "pkg.mod.x_g__mutmut_1": 0.0}


def _seconds_for(parts: int, workers: int = 4) -> float:
    """Recorded test seconds whose mutants fill `parts` parts just enough."""
    per_part = mutate_plan.SPLIT_MARGIN * mutate_plan.PART_FIXED_SECONDS
    return parts * per_part * workers / mutate_plan.KILL_SHARE


def test_small_work_runs_as_one_part() -> None:
    assert mutate_plan.part_count(0, workers=4) == 1
    assert mutate_plan.part_count(_seconds_for(2) * 0.99, workers=4) == 1


def test_parts_grow_with_the_work_up_to_three() -> None:
    assert mutate_plan.part_count(_seconds_for(2), workers=4) == 2
    assert mutate_plan.part_count(_seconds_for(3), workers=4) == 3
    assert mutate_plan.part_count(_seconds_for(30), workers=4) == 3
    assert mutate_plan.part_count(_seconds_for(30), workers=4, max_parts=1) == 1


def test_large_work_gives_three_balanced_parts() -> None:
    rng = random.Random(7)
    names = _names(600, functions=40)
    # A few slow functions, as the doll's are, among many fast ones.
    seconds = {f"pkg.mod.x_f{i}": (3000.0 if i < 4 else 100.0) * rng.uniform(0.5, 1.5) for i in range(40)}
    plan = mutate_plan.make(names, _stats(seconds), workers=4)
    assert len(plan["parts"]) == 3
    loads = plan["estimates"]
    assert max(loads) - min(loads) <= max(mutate_plan.costs(names, _stats(seconds)).values())
    assert max(loads) / min(loads) < 1.1
    mutate_plan.check_parts(names, plan["parts"])


def test_the_split_holds_every_mutant_exactly_once_and_is_the_same_each_time() -> None:
    names = _names(1000, functions=37)
    cost = {n: float(len(n) % 7) for n in names}
    for count in (1, 2, 3):
        parts = mutate_plan.split(cost, count)
        assert sorted(n for part in parts for n in part) == sorted(names)
        assert parts == mutate_plan.split(dict(reversed(cost.items())), count)
        mutate_plan.check_parts(names, parts)


def test_a_mutant_in_no_part_in_two_or_from_elsewhere_stops_the_run() -> None:
    names = ["a.x_f__mutmut_1", "a.x_f__mutmut_2"]
    with pytest.raises(mutate_plan.Unsharded, match="no part"):
        mutate_plan.check_parts(names, [["a.x_f__mutmut_1"], []])
    with pytest.raises(mutate_plan.Unsharded, match="parts 1 and 2"):
        mutate_plan.check_parts(names, [names, ["a.x_f__mutmut_1"]])
    with pytest.raises(mutate_plan.Unsharded, match="not mutants of the run"):
        mutate_plan.check_parts(names, [[*names, "a.x_g__mutmut_1"]])


def test_mutmut_gets_a_glob_for_a_whole_function_and_names_for_a_split_one() -> None:
    names = ["a.x_f__mutmut_1", "a.x_f__mutmut_2", "a.x_g__mutmut_1", "a.x_g__mutmut_2"]
    part = ["a.x_f__mutmut_1", "a.x_f__mutmut_2", "a.x_g__mutmut_2"]
    assert mutate_plan.mutmut_args(part, names) == ["a.x_f__mutmut_*", "a.x_g__mutmut_2"]


def test_a_saved_plan_loads_and_is_checked(tmp_path: Path) -> None:
    (tmp_path / "mutants").mkdir()
    plan = {"names": ["a.x_f__mutmut_1"], "parts": [["a.x_f__mutmut_1"]], "estimates": [1.0]}
    mutate_plan.save(plan, tmp_path)
    assert mutate_plan.load(tmp_path) == plan
    mutate_plan.save({**plan, "parts": [[]]}, tmp_path)
    with pytest.raises(mutate_plan.Unsharded):
        mutate_plan.load(tmp_path)


def test_the_mutants_end_up_newer_than_the_sources(tmp_path: Path) -> None:
    mutant = tmp_path / "mutants" / "src" / "mod.py"
    mutant.parent.mkdir(parents=True)
    mutant.write_text("")
    os.utime(mutant, (1, 1))
    source = tmp_path / "mod.py"
    source.write_text("")
    mutate_plan.mark_mutants_newer(tmp_path)
    assert mutant.stat().st_mtime >= source.stat().st_mtime


def test_github_output_appends_a_line(tmp_path: Path, monkeypatch) -> None:
    out = tmp_path / "out"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    mutate_plan.github_output("parts", "[1, 2]")
    assert out.read_text() == "parts=[1, 2]\n"
