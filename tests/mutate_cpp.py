"""Mutation tests of the C++ that the host tests reach.

    uv run python tests/mutate_cpp.py               every mutant: a report
    uv run python tests/mutate_cpp.py --diff BASE   the lines changed since BASE

It changes one operator or number at a time in a component file (a `<`
to a `<=`, a `&&` to a `||`, a 7 to an 8), builds every host test that
includes that file, and runs them. A change that still builds and that
no test notices "survived": the tests would miss that bug. A change that
doesn't build doesn't count.

The files are the ones the C++ host tests include (tests/conftest.py),
found with the compiler. test_frames.cpp needs a fixture, so its headers
are left out. --diff fails when a mutant on a changed line survives.
Mark a line `// pragma: no mutate` when no test can tell the change apart.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from changed_lines import ROOT, changed_lines

# The same flags as tests/conftest.py, without the warnings.
FLAGS = ["-std=c++17", "-w"]
INCLUDES = ["components/daruma", "components/daruma_weather"]
SKIP_TESTS = {"test_frames"}

OPERATORS = [
    (r"<=", "<"),
    (r"(?<![<>=!])<(?![<=])", "<="),
    (r">=", ">"),
    (r"(?<![<>=!-])>(?![>=])", ">="),
    (r"==", "!="),
    (r"!=", "=="),
    (r"&&", "||"),
    (r"\|\|", "&&"),
    (r"\btrue\b", "false"),
    (r"\bfalse\b", "true"),
    (r"(?<![+=])\+(?![+=])", "-"),
    (r"(?<![-=>])-(?![-=>])", "+"),
    (r"\+\+", "--"),
    (r"--", "++"),
    (r"!(?!=)", ""),
    (r"\b(\d+)\b", None),  # a whole number n -> n + 1
]
NOT_CODE = re.compile(r"^\s*(#|//|\*|/\*|using |namespace |template|struct |class |enum )")
LITERAL = re.compile(r"\"(?:[^\"\\]|\\.)*\"|'(?:[^'\\]|\\.)*'")
PRAGMA = "pragma: no mutate"


@dataclass
class Mutant:
    path: str
    line: int
    before: str
    after: str
    text: str  # the whole mutated file


def tests() -> list[str]:
    return sorted(p.stem for p in (ROOT / "tests").glob("test_*.cpp") if p.stem not in SKIP_TESTS)


def compile_command(test: str, include: Path, components: Path, out: Path) -> list[str]:
    dirs = [include] + [components.parent / d for d in INCLUDES]
    return ["c++", *FLAGS, *(f"-I{d}" for d in dirs), str(ROOT / "tests" / f"{test}.cpp"), "-o", str(out)]


def headers_by_test(include: Path) -> dict[str, list[str]]:
    """Each test -> the component files it includes, directly or not."""
    out = {}
    for test in tests():
        command = compile_command(test, include, ROOT / "components", Path(os.devnull))[:-2] + ["-MM"]
        deps = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=True).stdout
        paths = {Path(os.path.realpath(ROOT / p)) for p in deps.replace("\\\n", " ").split()[1:]}
        out[test] = sorted(str(p.relative_to(ROOT)) for p in paths if p.is_relative_to(ROOT / "components"))
    return out


def _code_lines(text: str):
    """(line number, line, the code part with literals blanked) of each line worth mutating."""
    in_comment = False
    for number, line in enumerate(text.split("\n"), 1):
        if in_comment or line.lstrip().startswith("/*"):
            in_comment = "*/" not in line
            continue
        if NOT_CODE.match(line) or PRAGMA in line:
            continue
        code = LITERAL.sub(lambda m: " " * len(m[0]), line.split("//")[0])
        yield number, line, code


def mutants(path: str, only: set[int] | None) -> list[Mutant]:
    text = (ROOT / path).read_text()
    lines = text.split("\n")
    out = []
    for number, line, code in _code_lines(text):
        if only is not None and number not in only:
            continue
        for pattern, replacement in OPERATORS:
            for match in re.finditer(pattern, code):
                new = str(int(match[1]) + 1) if replacement is None else replacement
                mutated = line[: match.start()] + new + line[match.end() :]
                whole = "\n".join(lines[: number - 1] + [mutated] + lines[number:])
                out.append(Mutant(path, number, line.strip(), mutated.strip(), whole))
    return out


class Workers:
    """Scratch copies of components/, one per thread, so mutants build side by side."""

    def __init__(self, count: int):
        self.root = Path(tempfile.mkdtemp(prefix="daruma-mutate-"))
        self.free: queue.Queue[Path] = queue.Queue()
        for i in range(count):
            work = self.root / str(i)
            shutil.copytree(ROOT / "components", work / "components")
            (work / "include" / "esphome").mkdir(parents=True)
            (work / "include" / "esphome" / "components").symlink_to(work / "components")
            self.free.put(work)

    def run(self, mutant: Mutant, test_names: list[str]) -> str:
        work = self.free.get()
        target = work / mutant.path
        original = target.read_text()
        try:
            target.write_text(mutant.text)
            return _build_and_run(work, test_names)
        finally:
            target.write_text(original)
            self.free.put(work)

    def close(self):
        shutil.rmtree(self.root, ignore_errors=True)


def _build_and_run(work: Path, test_names: list[str]) -> str:
    """killed, survived, or invalid (it doesn't build)."""
    built = False
    for test in test_names:
        exe = work / test
        command = compile_command(test, work / "include", work / "components", exe)
        if subprocess.run(command, capture_output=True).returncode:
            continue
        built = True
        try:
            if subprocess.run([str(exe)], capture_output=True, timeout=10).returncode:
                return "killed"
        except subprocess.TimeoutExpired:
            return "killed"  # A test that hangs noticed the change too.
    return "survived" if built else "invalid"


def baseline(work: Path, test_names: list[str]) -> bool:
    """Whether every test builds and passes before any mutation. Without
    that, a mutant that doesn't build or a failing test would mean nothing."""
    for test in test_names:
        exe = work / test
        built = subprocess.run(
            compile_command(test, work / "include", work / "components", exe), capture_output=True, text=True
        )
        if built.returncode:
            print(f"{test} doesn't build:\n{built.stderr[-3000:]}")
            return False
        ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
        if ran.returncode:
            print(f"{test} fails before any mutation:\n{ran.stdout[-3000:]}")
            return False
    return True


def collect(diff: str | None) -> tuple[list[Mutant], dict[str, list[str]]]:
    """The mutants to run, and the tests that reach each file."""
    include = Path(tempfile.mkdtemp(prefix="daruma-include-"))
    try:
        (include / "esphome").mkdir()
        (include / "esphome" / "components").symlink_to(ROOT / "components")
        by_test = headers_by_test(include)
    finally:
        shutil.rmtree(include)
    tests_by_path: dict[str, list[str]] = {}
    for test, paths in by_test.items():
        for path in paths:
            tests_by_path.setdefault(path, []).append(test)
    if diff:
        lines = changed_lines(diff, sorted(tests_by_path))
        found = [m for path, only in lines.items() for m in mutants(path, only)]
    else:
        found = [m for path in sorted(tests_by_path) for m in mutants(path, None)]
    return found, tests_by_path


def report(found: list[Mutant], states: list[str]) -> list[Mutant]:
    survived = [m for m, s in zip(found, states, strict=True) if s == "survived"]
    for m in survived:
        print(f"{m.path}:{m.line}: survived\n    - {m.before}\n    + {m.after}")
    counts = {s: states.count(s) for s in ("killed", "survived", "invalid")}
    for path in sorted({m.path for m in found}):
        mine = [s for m, s in zip(found, states, strict=True) if m.path == path]
        killed, alive = mine.count("killed"), mine.count("survived")
        if killed + alive:
            print(f"  {path}: {killed} of {killed + alive} caught")
    print(f"{len(found)} mutants: {counts}")
    return survived


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--diff", metavar="BASE", help="only the lines changed since the merge base with BASE")
    parser.add_argument("--jobs", type=int, default=os.cpu_count() or 4)
    args = parser.parse_args()
    found, tests_by_path = collect(args.diff)
    if not found:
        print("No changed lines in the files the C++ host tests include: nothing to mutate.")
        return 0
    workers = Workers(args.jobs)
    try:
        if not baseline(workers.root / "0", sorted({t for m in found for t in tests_by_path[m.path]})):
            return 1
        with concurrent.futures.ThreadPoolExecutor(args.jobs) as pool:
            states = list(pool.map(lambda m: workers.run(m, tests_by_path[m.path]), found))
    finally:
        workers.close()
    survived = report(found, states)
    return 1 if survived and args.diff else 0


if __name__ == "__main__":
    sys.exit(main())
