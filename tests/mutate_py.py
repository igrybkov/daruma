"""Mutation tests of the Python that the host tests reach (mutmut).

    uv run python tests/mutate_py.py               every mutant: a report
    uv run python tests/mutate_py.py --diff BASE   the lines changed since BASE

mutmut changes the code one small step at a time (a `<` to a `<=`, a
`True` to a `False`) and runs the tests that reach it. A change no test
notices "survived": the tests would miss that bug. The files and the
tests come from [tool.mutmut] in pyproject.toml. The persona tests are
the slowest host tests and add nothing here. mutmut runs the tests once per
mutant, so the runs skip them (DARUMA_SKIP_PERSONAS).

--diff runs only the functions the branch changed. It fails when a
mutant on a changed line survives, or no test reaches it. Mark a line
`# pragma: no mutate` when no test can tell the change apart.
"""

from __future__ import annotations

import argparse
import ast
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path

from changed_lines import ROOT, changed_lines

BAD = ("survived", "no tests")
_HUNK = re.compile(r"^@@ -(\d+)")
_SPINNER = re.compile(r"[\u2800-\u28ff]")  # The Braille dots of mutmut's progress spinner.


def source_paths() -> list[str]:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text())
    return config["tool"]["mutmut"]["source_paths"]


def mutmut(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    env = {**os.environ, "DARUMA_SKIP_PERSONAS": "1"}
    return subprocess.run(
        [sys.executable, "-m", "mutmut", *args], cwd=ROOT, env=env, capture_output=True, text=True, check=check
    )


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


def module_name(path: str) -> str:
    return ".".join(Path(path).with_suffix("").parts)


def results() -> dict[str, str]:
    """Mutant name -> status, for every mutant mutmut has run."""
    out = {}
    for line in mutmut("results", "--all", "true").stdout.splitlines():
        name, _, status = line.strip().rpartition(": ")
        if name:
            out[name] = status
    return out


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
    status = results()
    for name, state in sorted(status.items()):
        if state in BAD:
            print(f"{state:9} {name}")
    counts = {s: list(status.values()).count(s) for s in sorted(set(status.values()))}
    print(f"{len(status)} mutants: {counts}")
    return 0


def _targets(changed: dict[str, set[int]]) -> dict[str, tuple[str, tuple[int, int]]]:
    """Mutant-name glob -> (path, function span), for each changed function."""
    targets = {}
    for path, lines in changed.items():
        for key, first, last in functions(path):
            if lines & set(range(first, last + 1)):
                targets[f"{module_name(path)}.{key}__mutmut_*"] = (path, (first, last))
    return targets


def run_diff(base: str) -> int:
    changed = changed_lines(base, source_paths())
    targets = _targets(changed)
    if not targets:
        print(f"No changed functions in {', '.join(source_paths())} since {base}: nothing to mutate.")
        return 0
    run = mutmut("run", *targets, check=False)
    if "nothing matches" in run.stdout + run.stderr:
        print("The changed functions have nothing to mutate.")
        return 0
    if run.returncode:
        # Most often a test fails before any mutation: then no result counts.
        print(tail(run.stdout + run.stderr), "mutmut failed.", sep="\n")
        return run.returncode
    bad = []
    for name, state in results().items():
        glob = f"{name.rpartition('__mutmut_')[0]}__mutmut_*"
        if state not in BAD or glob not in targets:
            continue
        path, span = targets[glob]
        file_lines = (ROOT / path).read_text().splitlines()
        for line, before, after in mutant_lines(name, file_lines, span):
            if line in changed[path]:
                bad.append(f"{path}:{line}: {state}: {name}\n    - {before}\n    + {after}")
    print("\n".join(sorted(bad)))
    print(f"{len(targets)} changed functions, {len(bad)} mutants on changed lines that no test catches.")
    return 1 if bad else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--diff", metavar="BASE", help="only the lines changed since the merge base with BASE")
    args = parser.parse_args()
    return run_diff(args.diff) if args.diff else run_all()


if __name__ == "__main__":
    sys.exit(main())
