"""Splits the mutants of a --diff run into parts for several CI runners.

The plan job makes the mutants and records which tests reach each
function (mutmut's recorded run) once. Its stats give each test's time.
A mutant's cost is the time of the tests that reach its function. The
plan splits the mutants into parts of about equal cost, the costliest
mutant first, each to the part with the least cost so far.

A part costs time before it runs a mutant: a runner, the download of
the plan's mutants, and mutmut's start. So the plan splits only when
each part's mutants take well over that time. A small change runs as
one part.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

PLAN_FILE = Path("mutants") / "daruma-plan.json"
# mutmut 3.8.1 keeps its recorded run here (mutmut.stats.load_stats).
STATS_FILE = Path("mutants") / "mutmut-stats.json"
MAX_PARTS = 3
# What one more part costs before its first mutant, in seconds. Measured
# on the 24-function probe pull request, forced into three parts: about
# 16 s of runner setup and download, 6 s to load the stats and list the
# tests, and 8 s to report. Making the mutants again and the clean tests
# cost 40 s more there; parts skip both now (mutmut_run.py keeps the
# mutated copy, mutmut_steps.py leaves the clean tests to the plan). This
# doubles the 30 s left, for the wait for a free runner.
PART_FIXED_SECONDS = 60
# Split only when each part's mutants take this many times the fixed cost.
SPLIT_MARGIN = 2.0
# A mutant's seconds on a worker, as a share of its tests' recorded time.
# The recorded run times each test with mutmut's call tracking on, and
# most mutants die on their first failing test. On the probe the parts'
# mutant steps took 264 worker-seconds for 11,422 recorded seconds.
KILL_SHARE = 0.07


def mutant_function(name: str) -> str:
    """The function a mutant belongs to, as mutmut's stats name it."""
    return name.rpartition("__mutmut_")[0]


def costs(names: list[str], stats: dict) -> dict[str, float]:
    """Mutant name -> the recorded seconds of the tests that reach its function."""
    tests_by_function = stats["tests_by_mangled_function_name"]
    duration = stats["duration_by_test"]

    def cost(name: str) -> float:
        return sum(duration.get(test, 0.0) for test in tests_by_function.get(mutant_function(name), ()))

    return {name: cost(name) for name in names}


def part_count(total: float, workers: int, max_parts: int = MAX_PARTS) -> int:
    """How many parts to run `total` seconds of tests in: the most parts
    such that each part's mutants still take SPLIT_MARGIN times the fixed
    cost of a part, and at least one."""
    wall = total * KILL_SHARE / max(workers, 1)
    worth = math.floor(wall / (SPLIT_MARGIN * PART_FIXED_SECONDS))
    return max(1, min(max_parts, worth))


def split(cost: dict[str, float], count: int) -> list[list[str]]:
    """The mutants in `count` parts of about equal cost, the same way each time."""
    parts: list[list[str]] = [[] for _ in range(count)]
    loads = [0.0] * count
    for name in sorted(cost, key=lambda n: (-cost[n], n)):
        part = min(range(count), key=lambda i: (loads[i], i))
        parts[part].append(name)
        loads[part] += cost[name]
    return [sorted(part) for part in parts]


class Unsharded(Exception):
    """A mutant is in no part, or in more than one."""


def check_parts(names: list[str], parts: list[list[str]]) -> None:
    """Fails unless each mutant name is in exactly one part."""
    seen: dict[str, int] = {}
    for index, part in enumerate(parts):
        for name in part:
            if name in seen:
                raise Unsharded(f"{name} is in parts {seen[name] + 1} and {index + 1}")
            seen[name] = index
    if missing := sorted(set(names) - set(seen)):
        raise Unsharded(f"{len(missing)} mutants in no part, such as {missing[0]}")
    if extra := sorted(set(seen) - set(names)):
        raise Unsharded(f"{len(extra)} mutants in a part are not mutants of the run, such as {extra[0]}")


def mutmut_args(part: list[str], names: list[str]) -> list[str]:
    """What to pass mutmut run for a part: a function's glob when the part
    has all of its mutants, else the part's mutants of it by name."""
    by_function: dict[str, set[str]] = {}
    for name in names:
        by_function.setdefault(mutant_function(name), set()).add(name)
    mine = set(part)
    args = []
    for function, all_of_it in sorted(by_function.items()):
        if all_of_it <= mine:
            args.append(f"{function}__mutmut_*")
        else:
            args += sorted(all_of_it & mine)
    return args


def make(names: list[str], stats: dict, workers: int, max_parts: int = MAX_PARTS) -> dict:
    """The plan: the parts, and the estimate of each, in recorded seconds."""
    cost = costs(names, stats)
    count = part_count(sum(cost.values()), workers, max_parts)
    parts = split(cost, count)
    check_parts(names, parts)
    return {"names": sorted(names), "parts": parts, "estimates": [round(sum(cost[n] for n in p), 1) for p in parts]}


def save(plan: dict, root: Path) -> None:
    (root / PLAN_FILE).write_text(json.dumps(plan, indent=1))


def load(root: Path) -> dict:
    plan = json.loads((root / PLAN_FILE).read_text())
    check_parts(plan["names"], plan["parts"])
    return plan


def mark_mutants_newer(root: Path) -> None:
    """Makes the mutated copy newer than the sources. A part checks out
    the sources after the plan made its mutants; mutmut makes the mutants
    again when the source is newer (create_mutants_for_file)."""
    for folder, _, files in os.walk(root / "mutants"):
        for file in files:
            os.utime(Path(folder) / file)


def github_output(key: str, value: str) -> None:
    if path := os.environ.get("GITHUB_OUTPUT"):
        with open(path, "a") as out:
            out.write(f"{key}={value}\n")
