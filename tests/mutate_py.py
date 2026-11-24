"""Mutation tests of the Python that the host tests reach (mutmut).

    uv run python tests/mutate_py.py               every mutant: a report
    uv run python tests/mutate_py.py --diff BASE   the lines changed since BASE
    ... --shard 2/3                                one of three parts of either run

mutmut changes the code one small step at a time (a `<` to a `<=`, a
`True` to a `False`) and runs the tests that reach it. A change no test
notices "survived": the tests would miss that bug. The files and the
tests come from [tool.mutmut] in pyproject.toml. The runs include the
persona tests, even with DARUMA_SKIP_PERSONAS set: the persona frames are
what most of the drawing code is checked against.

--diff runs only the functions the branch changed. It fails when a
mutant on a changed line survives, or no test reaches it. Mark a line
`# pragma: no mutate` when no test can tell the change apart.

--shard K/N runs one of N parts, so N runners can share a run. A part is
a set of whole functions. Each function goes to the part with the least
cost so far, biggest first: the persona and shape functions cost the
most, since their mutants run the persona tests. Each part reports only
its own mutants. A mutant in no part, or in two, stops the run.
"""

from __future__ import annotations

import argparse
import ast
import os
import re
import signal
import subprocess
import sys
import tomllib
from pathlib import Path

from changed_lines import ROOT, changed_lines
from mutmut_run import STRAY_PREFIXES, module_name
from mutmut_steps import PREFIX as STEP_PREFIX

SHIM = Path(__file__).resolve().parent / "mutmut_run.py"

BAD = ("survived", "no tests")
_HUNK = re.compile(r"^@@ -(\d+)")
_SPINNER = re.compile(r"[\u2800-\u28ff]")  # The Braille dots of mutmut's progress spinner.


def source_paths() -> list[str]:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text())
    return config["tool"]["mutmut"]["source_paths"]


class OutOfTime(Exception):
    """mutmut ran past its time; the mutants it finished keep their results."""


def mutmut(*args: str, check: bool = True, minutes: float | None = None) -> subprocess.CompletedProcess:
    """Runs mutmut through the shim. Past `minutes` it stops mutmut and
    every process it started, and raises OutOfTime."""
    env = {k: v for k, v in os.environ.items() if k != "DARUMA_SKIP_PERSONAS"}
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
        print(*(line for line in err.splitlines() if line.startswith(STEP_PREFIX)), sep="\n", flush=True)
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


# What a mutant's tests cost, per line of its function, by its module's prefix.
WEIGHTS = (("daruma_personas.", 10), ("daruma_shapes.", 3), ("daruma_pixel", 2))


def weight(module: str) -> int:
    return next((w for prefix, w in WEIGHTS if module.startswith(prefix)), 1)


def source_files() -> list[str]:
    """Every Python file under [tool.mutmut] source_paths, relative to ROOT."""
    out = set()
    for entry in source_paths():
        path = ROOT / entry
        for file in [path] if path.is_file() else path.rglob("*.py"):
            out.add(file.relative_to(ROOT).as_posix())
    return sorted(out)


def all_targets() -> dict[str, tuple[str, tuple[int, int]]]:
    """Mutant-name glob -> (path, function span), for every function."""
    return {
        f"{module_name(path)}.{key}__mutmut_*": (path, (first, last))
        for path in source_files()
        for key, first, last in functions(path)
    }


def shards(targets: dict[str, tuple[str, tuple[int, int]]], count: int) -> list[list[str]]:
    """The globs split into `count` parts of about equal cost, the same way each time."""

    def cost(glob: str) -> int:
        path, (first, last) = targets[glob]
        return weight(module_name(path)) * (last - first + 1)

    parts: list[list[str]] = [[] for _ in range(count)]
    loads = [0] * count
    for glob in sorted(targets, key=lambda g: (-cost(g), g)):
        part = min(range(count), key=lambda i: (loads[i], i))
        parts[part].append(glob)
        loads[part] += cost(glob)
    return parts


class Unsharded(Exception):
    """A mutant is in no part, or in more than one."""


def check_shards(names: list[str], parts: list[list[str]]) -> None:
    """Fails unless each mutant name belongs to exactly one part."""
    part_of: dict[str, int] = {}
    for index, part in enumerate(parts):
        for glob in part:
            if glob in part_of or any(c in glob[: -len("__mutmut_*")] for c in "*?["):
                raise Unsharded(f"{glob} is in more than one part, or has glob characters")
            part_of[glob] = index
    if missing := sorted(n for n in names if _glob(n) not in part_of):
        raise Unsharded(f"{len(missing)} mutants in no part, such as {missing[0]}")


def parse_shard(text: str) -> tuple[int, int]:
    """'2/3' -> (1, 3): the part's index from 0, and the number of parts."""
    k, _, n = text.partition("/")
    if not (k.isdigit() and n.isdigit() and 1 <= int(k) <= int(n)):
        raise argparse.ArgumentTypeError(f"--shard takes K/N with 1 <= K <= N, not {text!r}")
    return int(k) - 1, int(n)


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


def run_all(shard: tuple[int, int] = (0, 1)) -> int:
    targets = all_targets()
    parts = shards(targets, shard[1])
    mine = parts[shard[0]]
    run = mutmut("run", *(mine if shard[1] > 1 else []), check=False)
    if run.returncode:
        print(tail(run.stdout + run.stderr), "mutmut failed.", sep="\n")
        return run.returncode
    status = results()
    check_shards(list(status), parts)
    if shard[1] > 1:
        print(f"Part {shard[0] + 1} of {shard[1]}: {len(mine)} of {len(targets)} functions.")
        status = {n: s for n, s in status.items() if _glob(n) in set(mine)}
    print(report(status))
    return 0


def _targets(changed: dict[str, set[int]]) -> dict[str, tuple[str, tuple[int, int]]]:
    """Mutant-name glob -> (path, function span), for each changed function."""
    targets = {}
    for path, lines in changed.items():
        for key, first, last in functions(path):
            if lines & set(range(first, last + 1)):
                targets[f"{module_name(path)}.{key}__mutmut_*"] = (path, (first, last))
    return targets


def run_diff(base: str, minutes: float | None = None, shard: tuple[int, int] = (0, 1)) -> int:
    changed = changed_lines(base, source_paths())
    every = _targets(changed)
    if not every:
        print(f"No changed functions in {', '.join(source_paths())} since {base}: nothing to mutate.")
        return 0
    parts = shards(every, shard[1])
    targets = {glob: every[glob] for glob in parts[shard[0]]}
    if not targets:
        print(f"Part {shard[0] + 1} of {shard[1]} has none of the {len(every)} changed functions.")
        return 0
    try:
        run = mutmut("run", *targets, check=False, minutes=minutes)
    except OutOfTime:
        run = None
    modules = sorted({module_name(path) for path, _ in targets.values()})
    names = list(results())
    check_shards([n for n in names if _glob(n) in every], parts)
    if missing := stray_names(names, modules):
        print(f"mutmut has no mutants under the module names {missing}: tests/mutate_py.py names them wrong.")
        return 1
    if run is None:
        return out_of_time(targets, minutes)
    if "nothing matches" in run.stdout + run.stderr:
        print("The changed functions have nothing to mutate.")
        return 0
    if run.returncode:
        # Most often a test fails before any mutation: then no result counts.
        print(tail(run.stdout + run.stderr), "mutmut failed.", sep="\n")
        return run.returncode
    bad = caught_none(targets, changed)
    for state, why in (
        ("survived", "a test runs the line but misses the change"),
        ("no tests", "no test runs the line"),
    ):
        if bad[state]:
            print(f"{state.capitalize()}: {why} ({len(bad[state])}):", *sorted(bad[state]), "", sep="\n")
    found = sum(map(len, bad.values()))
    print(f"{len(targets)} changed functions, {found} mutants on changed lines that no test catches.")
    return 1 if found else 0


def caught_none(targets: dict, changed: dict) -> dict[str, list[str]]:
    """state -> the mutants on changed lines that no test catches, as text."""
    bad: dict[str, list[str]] = {state: [] for state in BAD}
    for name, state in results().items():
        glob = _glob(name)
        if state not in BAD or glob not in targets:
            continue
        path, span = targets[glob]
        file_lines = (ROOT / path).read_text().splitlines()
        for line, before, after in mutant_lines(name, file_lines, span):
            if line in changed[path]:
                bad[state].append(f"{path}:{line}: {name}\n    - {before}\n    + {after}")
    return bad


def out_of_time(targets: dict, minutes: float | None) -> int:
    """Reports what mutmut found before its time ran out, and fails."""
    mine = {n: s for n, s in results().items() if _glob(n) in targets}
    left = [n for n, s in mine.items() if s == "not checked"]
    found = [f"{s:9} {n}" for n, s in sorted(mine.items()) if s in BAD]
    print(*found, sep="\n")
    print(f"Out of time after {minutes:g} minutes: {len(left)} mutants of the changed functions did not run.")
    print("Run make mutate-diff locally, or split the change.")
    return 1


def _glob(name: str) -> str:
    return f"{name.rpartition('__mutmut_')[0]}__mutmut_*"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--diff", metavar="BASE", help="only the lines changed since the merge base with BASE")
    parser.add_argument("--minutes", type=float, help="--diff: stop mutmut after this long, and fail")
    parser.add_argument("--shard", type=parse_shard, default=(0, 1), metavar="K/N", help="run part K of N")
    args = parser.parse_args()
    try:
        return run_diff(args.diff, args.minutes, args.shard) if args.diff else run_all(args.shard)
    except StrayNames as err:
        print(f"{err}: tests/mutmut_run.py maps the layouts to import names.")
        return 1
    except Unsharded as err:
        print(f"{err}: tests/mutate_py.py splits the mutants by function.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
