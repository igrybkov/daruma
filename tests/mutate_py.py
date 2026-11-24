"""Mutation tests of the Python that the host tests reach (mutmut).

    uv run python tests/mutate_py.py               every mutant: a report
    uv run python tests/mutate_py.py --diff BASE   the lines changed since BASE
    ... --diff BASE --part 2/3                     part 2 of 3 of that run
    ... --diff BASE --count-parts                  how many parts CI runs

mutmut changes the code one small step at a time (a `<` to a `<=`, a
`True` to a `False`) and runs the tests that reach it. A change no test
notices "survived": the tests would miss that bug. The files and the
tests come from [tool.mutmut] in pyproject.toml. The runs include the
persona tests, even with DARUMA_SKIP_PERSONAS set: the persona frames are
what most of the drawing code is checked against.

--diff runs only the functions the branch changed. It fails when a
mutant on a changed line survives, or no test reaches it. Mark a line
`# pragma: no mutate` when no test can tell the change apart.

--diff BASE --part K/N runs part K of N of those mutants: every Nth in
sorted order, so the slow functions spread across the parts. Each part
runs the whole flow on its own runner and fails on its own survivors.
--count-parts tells CI how many parts a change needs (PARTS_THRESHOLD).
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import signal
import subprocess
import sys
import tomllib
from pathlib import Path

from changed_lines import ROOT, changed_lines
from mutmut_run import STRAY_PREFIXES, module_name
from mutmut_steps import PART, PART_PREFIX, parse_part, part_of
from mutmut_steps import PREFIX as STEP_PREFIX

SHIM = Path(__file__).resolve().parent / "mutmut_run.py"

BAD = ("survived", "no tests")
# CI splits a change of more than this many functions into PARTS parts.
# A pixel function's mutants take about 9 s of work, and a runner costs
# about 2.5 minutes before its first mutant (both measured on a
# 24-function pull request). One runner reaches the 12-minute budget at
# about 60 functions. Past 20, three runners finish well inside it.
PARTS_THRESHOLD = 20
PARTS = 3
_HUNK = re.compile(r"^@@ -(\d+)")
_SPINNER = re.compile(r"[\u2800-\u28ff]")  # The Braille dots of mutmut's progress spinner.


def source_paths() -> list[str]:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text())
    return config["tool"]["mutmut"]["source_paths"]


class OutOfTime(Exception):
    """mutmut ran past its time; the mutants it finished keep their results."""


def mutmut(
    *args: str, check: bool = True, minutes: float | None = None, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess:
    """Runs mutmut through the shim. Past `minutes` it stops mutmut and
    every process it started, and raises OutOfTime."""
    # A part's switch is for this run only, never for a run a test starts
    # inside it (the planted run in test_mutate_py.py).
    dropped = {"DARUMA_SKIP_PERSONAS", PART}
    env = {k: v for k, v in os.environ.items() if k not in dropped} | (env or {})
    command = [sys.executable, str(SHIM), *args]
    with subprocess.Popen(
        command, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True
    ) as proc:
        try:
            out, err = proc.communicate(timeout=None if minutes is None else minutes * 60)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.communicate()
            raise OutOfTime from None
    if args[:1] == ("run",):
        notes = (line for line in err.splitlines() if line.startswith((STEP_PREFIX, PART_PREFIX)))
        print(*notes, sep="\n", flush=True)
    if check and proc.returncode:
        raise subprocess.CalledProcessError(proc.returncode, command, out, err)
    return subprocess.CompletedProcess(command, proc.returncode, out, err)


def tail(output: str, lines: int = 40) -> str:
    """The end of mutmut's output, without its spinner's redrawn lines."""
    kept = [line for line in output.replace("\r", "\n").splitlines() if line.strip() and not _SPINNER.search(line)]
    return "\n".join(kept[-lines:])


def functions(path: str) -> list[tuple[str, int, int]]:
    """(mutmut's key, first line, last line) of each function mutmut mutates."""
    tree = ast.parse((ROOT / path).read_text())
    out = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.append((f"x_{node.name}", node))
        elif isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    out.append((f"xǁ{node.name}ǁ{item.name}", item))
    return [(key, min([n.lineno] + [d.lineno for d in n.decorator_list]), n.end_lineno) for key, n in out]


def mutant_module(name: str) -> str:
    """The module of a mutant name (`pkg.mod.x_func__mutmut_3` -> `pkg.mod`)."""
    return re.split(r"\.x[_ǁ]", name, maxsplit=1)[0]


def stray_names(names: list[str], modules: list[str]) -> list[str]:
    """The modules among `modules` that no mutant name belongs to.

    A file whose mutants mutmut names differently than module_name() would
    otherwise match no glob, and --diff would pass without running a test.
    """
    known = {mutant_module(n) for n in names}
    return sorted(m for m in modules if m not in known)


class StrayNames(Exception):
    """mutmut named mutants by a path: tests/mutmut_run.py did not map them."""


def results() -> dict[str, str]:
    """Mutant name -> status, for every mutant mutmut has run."""
    out = {}
    for line in mutmut("results", "--all", "true").stdout.splitlines():
        name, _, status = line.strip().rpartition(": ")
        if name:
            out[name] = status
    if stray := sorted(n for n in out if n.startswith(STRAY_PREFIXES)):
        raise StrayNames(f"{len(stray)} mutants named by their path, such as {stray[0]}")
    return out


def package(module: str) -> str:
    """The part of the code a module belongs to, for the report."""
    parts = module.split(".")
    if parts[0] == "esphome":
        return ".".join(parts[:3])
    if parts[0] in ("daruma_shapes", "daruma_personas"):
        return ".".join(parts[:2])
    if parts[0] == "daruma_pixel":
        return parts[0]
    return "demos"


def report(status: dict[str, str]) -> str:
    """The surviving and untested mutants, then a count per part of the code."""
    lines = []
    for title, state in (
        ("Survived: a test runs the code but misses the change", "survived"),
        ("No tests: no test runs the code", "no tests"),
    ):
        names = sorted(n for n, s in status.items() if s == state)
        if names:
            lines += [f"{title} ({len(names)}):", *(f"  {n}" for n in names), ""]
    totals: dict[str, dict[str, int]] = {}
    for name, state in status.items():
        counts = totals.setdefault(package(mutant_module(name)), {})
        counts[state] = counts.get(state, 0) + 1
    states = ("killed", "timeout", "survived", "no tests")
    lines.append(f"{'':40} {'mutants':>8} " + " ".join(f"{s:>9}" for s in states))
    for part in sorted(totals):
        counts = totals[part]
        lines.append(f"{part:40} {sum(counts.values()):>8} " + " ".join(f"{counts.get(s, 0):>9}" for s in states))
    every = {s: list(status.values()).count(s) for s in sorted(set(status.values()))}
    lines.append(f"{len(status)} mutants: {every}")
    return "\n".join(lines)


def _hunks(diff: str):
    """Each hunk of a unified diff: (the original lines, the indexes of the changed ones)."""
    old, changed = [], []
    for line in diff.splitlines():
        if _HUNK.match(line):
            if old:
                yield old, changed
            old, changed = [], []
        elif line.startswith(" ") or (line.startswith("-") and not line.startswith("---")):
            if line.startswith("-"):
                changed.append(len(old))
            old.append(line[1:].strip())
    if old:
        yield old, changed


def mutant_lines(name: str, file_lines: list[str], span: tuple[int, int]) -> list[tuple[int, str, str]]:
    """The file lines a mutant changes: (line, before, after).

    mutmut numbers a mutant's lines from the start of its function, which
    may be a comment above it, so each hunk is found in the function's
    lines by its text.
    """
    diff = mutmut("show", name).stdout
    after = [line[1:].strip() for line in diff.splitlines() if line.startswith("+") and not line.startswith("+++")]
    out = []
    stripped = [line.strip() for line in file_lines]
    for old, changed in _hunks(diff):
        # The diff may start at comment lines above the function.
        for start in range(max(0, span[0] - 1 - len(old)), span[1] - len(old) + 1):
            if stripped[start : start + len(old)] == old:
                out += [(start + i + 1, old[i], " / ".join(after)) for i in changed]
                break
    return out


def run_all() -> int:
    run = mutmut("run", check=False)
    if run.returncode:
        print(tail(run.stdout + run.stderr), "mutmut failed.", sep="\n")
        return run.returncode
    print(report(results()))
    return 0


def _targets(changed: dict[str, set[int]]) -> dict[str, tuple[str, tuple[int, int]]]:
    """Mutant-name glob -> (path, function span), for each changed function."""
    targets = {}
    for path, lines in changed.items():
        for key, first, last in functions(path):
            if lines & set(range(first, last + 1)):
                targets[f"{module_name(path)}.{key}__mutmut_*"] = (path, (first, last))
    return targets


def github_output(key: str, value: str) -> None:
    if path := os.environ.get("GITHUB_OUTPUT"):
        with open(path, "a") as out:
            out.write(f"{key}={value}\n")


def count_parts(base: str) -> int:
    """How many parts CI runs the change in; also the job's `parts` output."""
    functions = len(_targets(changed_lines(base, source_paths())))
    count = PARTS if functions > PARTS_THRESHOLD else 1
    print(f"{functions} changed functions: {count} part(s).")
    github_output("parts", json.dumps(list(range(1, count + 1))))
    return 0


def run_diff(base: str, minutes: float | None = None, part: tuple[int, int] = (0, 1)) -> int:
    changed = changed_lines(base, source_paths())
    targets = _targets(changed)
    if not targets:
        print(f"No changed functions in {', '.join(source_paths())} since {base}: nothing to mutate.")
        return 0
    label = f"Part {part[0] + 1} of {part[1]}" if part[1] > 1 else "This run"
    env = {PART: f"{part[0] + 1}/{part[1]}"} if part[1] > 1 else {}
    try:
        run = mutmut("run", *targets, check=False, minutes=minutes, env=env)
    except OutOfTime:
        run = None
    names = [n for n in results() if _glob(n) in targets]
    if missing := stray_names(names, sorted({module_name(path) for path, _ in targets.values()})):
        print(f"mutmut has no mutants under the module names {missing}: tests/mutate_py.py names them wrong.")
        return 1
    status = {n: s for n, s in results().items() if n in set(part_of(names, *part))}
    if run is None:
        return out_of_time(status, minutes)
    if "nothing matches" in run.stdout + run.stderr:
        print("The changed functions have nothing to mutate.")
        return 0
    if run.returncode:
        # Most often a test fails before any mutation: then no result counts.
        print(tail(run.stdout + run.stderr), "mutmut failed.", sep="\n")
        return run.returncode
    if part[1] > 1 and f"{PART_PREFIX} {part[0] + 1}/{part[1]} " not in run.stderr:
        print(f"{label}: mutmut ran every mutant, not its part. tests/mutmut_steps.py no longer splits them.")
        return 1
    return report_diff(label, status, targets, changed)


def report_diff(label: str, status: dict[str, str], targets: dict, changed: dict) -> int:
    bad = caught_none(status, targets, changed)
    for state, why in (
        ("survived", "a test runs the line but misses the change"),
        ("no tests", "no test runs the line"),
    ):
        if bad[state]:
            print(f"{state.capitalize()}: {why} ({len(bad[state])}):", *sorted(bad[state]), "", sep="\n")
    found = sum(map(len, bad.values()))
    print(f"{label}: {len(status)} mutants, {found} on changed lines that no test catches.")
    return 1 if found else 0


def caught_none(status: dict[str, str], targets: dict, changed: dict) -> dict[str, list[str]]:
    """state -> the mutants on changed lines that no test catches, as text."""
    bad: dict[str, list[str]] = {state: [] for state in BAD}
    for name, state in status.items():
        glob = _glob(name)
        if state not in BAD or glob not in targets:
            continue
        path, span = targets[glob]
        file_lines = (ROOT / path).read_text().splitlines()
        for line, before, after in mutant_lines(name, file_lines, span):
            if line in changed[path]:
                bad[state].append(f"{path}:{line}: {name}\n    - {before}\n    + {after}")
    return bad


def out_of_time(status: dict[str, str], minutes: float | None) -> int:
    """Reports what mutmut found before its time ran out, and fails."""
    left = [n for n, s in status.items() if s == "not checked"]
    found = [f"{s:9} {n}" for n, s in sorted(status.items()) if s in BAD]
    print(*found, sep="\n")
    print(f"Out of time after {minutes:g} minutes: {len(left)} mutants of the part did not run.")
    print("Run make mutate-diff locally, or split the change.")
    return 1


def _glob(name: str) -> str:
    return f"{name.rpartition('__mutmut_')[0]}__mutmut_*"


def _part(text: str) -> tuple[int, int]:
    try:
        return parse_part(text)
    except ValueError as err:
        raise argparse.ArgumentTypeError(str(err)) from None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--diff", metavar="BASE", help="only the lines changed since the merge base with BASE")
    parser.add_argument("--part", type=_part, default=(0, 1), metavar="K/N", help="--diff: run part K of N")
    parser.add_argument("--count-parts", action="store_true", help="--diff: how many parts CI runs the change in")
    parser.add_argument("--minutes", type=float, help="--diff: stop mutmut after this long, and fail")
    args = parser.parse_args()
    try:
        if args.diff and args.count_parts:
            return count_parts(args.diff)
        return run_diff(args.diff, args.minutes, args.part) if args.diff else run_all()
    except StrayNames as err:
        print(f"{err}: tests/mutmut_run.py maps the layouts to import names.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
