"""One coverage report from the data of CI's coverage jobs.

    python tests/coverage_report.py --gcov build/ --save cpp.json
    python tests/coverage_report.py --lines cpp-*.json --python python.json --out coverage

C++ comes from gcc's --coverage data: --gcov reads every .gcda file in a
folder with gcc's gcov (JSON output, so gcc 10 or later). Each coverage job
saves its C++ lines with --save, while the build is still there. Python
comes as coverage.py JSON. The builds compile copies of the components, so
each file is mapped back to its place in this repository by its path. Line
counts of the same file add up. Only this repository's components/ and
pixel/ count.

Writes, in --out:
- coverage.lcov   every line of every file, for an editor or genhtml
- summary.md      per area (components/<name>, pixel), and the total
- files.md        per file, and the files no test compiled or loaded
"""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENTS = {p.name for p in (ROOT / "components").iterdir() if p.is_dir()}
SOURCES = ("*.cpp", "*.h", "*.py")

# {repository path: {line: count}}
Lines = dict[str, dict[int, int]]


def repo_path(path: str) -> str | None:
    """The file's path in this repository, or None for anything else."""
    parts = path.replace("\\", "/").split("/")
    for i in range(len(parts) - 2, -1, -1):
        if parts[i] == "components" and parts[i + 1] in COMPONENTS:
            return "/".join(parts[i:])
        if parts[i] == "pixel" and parts[i + 1] == "daruma_pixel":
            return "/".join(parts[i:])
    return None


def add(lines: Lines, path: str | None, counts: dict[int, int]) -> None:
    if path is None:
        return
    into = lines.setdefault(path, {})
    for n, c in counts.items():
        into[n] = into.get(n, 0) + c


def read_gcov(folder: Path, lines: Lines) -> None:
    """Every .gcda file in `folder`, through gcov."""
    data = sorted(str(p) for p in folder.rglob("*.gcda"))
    with tempfile.TemporaryDirectory() as tmp:
        for i in range(0, len(data), 100):
            cmd = ["gcov", "--json-format", "--stdout", *data[i : i + 100]]
            out = subprocess.run(cmd, cwd=tmp, check=True, capture_output=True, text=True).stdout
            for doc in out.splitlines():
                if doc.startswith("{"):
                    read_gcov_doc(json.loads(doc), lines)


def read_gcov_doc(doc: dict, lines: Lines) -> None:
    """One object file's lines: its source and every header it includes."""
    for entry in doc["files"]:
        counts = {ln["line_number"]: ln["count"] for ln in entry["lines"]}
        add(lines, repo_path(entry["file"]), counts)


def read_saved(file: Path, lines: Lines) -> None:
    for path, counts in json.loads(file.read_text()).items():
        add(lines, path, {int(n): c for n, c in counts.items()})


def read_python(file: Path, lines: Lines) -> None:
    for name, entry in json.loads(file.read_text())["files"].items():
        counts = dict.fromkeys(entry["missing_lines"], 0)
        counts.update(dict.fromkeys(entry["executed_lines"], 1))
        add(lines, repo_path(name), counts)


def area(path: str) -> str:
    """components/<name> or pixel."""
    parts = path.split("/")
    return "/".join(parts[:2]) if parts[0] == "components" else "pixel"


def language(path: str) -> str:
    return "Python" if path.endswith(".py") else "C++"


def percent(hit: int, total: int) -> str:
    return f"{100 * hit / total:.1f}%" if total else "-"


def tally(lines: Lines) -> dict[tuple[str, str], list[int]]:
    """{(area, language): [lines, lines run]}, with ("Total", language) too."""
    sums: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0])
    for path, counts in lines.items():
        run = sum(1 for c in counts.values() if c)
        for key in ((area(path), language(path)), ("Total", language(path))):
            sums[key][0] += len(counts)
            sums[key][1] += run
    return sums


def summary(lines: Lines) -> str:
    sums = tally(lines)
    areas = sorted({a for a, _ in sums} - {"Total"}) + ["Total"]
    rows = [
        "| Area | C++ lines | C++ run | Python lines | Python run |",
        "|---|---:|---:|---:|---:|",
    ]
    for a in areas:
        cells = []
        for lang in ("C++", "Python"):
            total, run = sums.get((a, lang), [0, 0])
            cells += [str(total) if total else "-", percent(run, total)]
        name = f"**{a}**" if a == "Total" else f"`{a}`"
        rows.append(f"| {name} | " + " | ".join(cells) + " |")
    return "\n".join(rows) + "\n"


def unreached() -> list[str]:
    """Source files in no report: never compiled or loaded by a test, or no code."""
    found = []
    for top in ("components", "pixel"):
        for pattern in SOURCES:
            found += [str(p.relative_to(ROOT)) for p in (ROOT / top).rglob(pattern)]
    return sorted(found)


def files(lines: Lines) -> str:
    rows = ["| File | Lines | Run |", "|---|---:|---:|"]
    for path in sorted(lines):
        counts = lines[path]
        run = sum(1 for c in counts.values() if c)
        rows.append(f"| `{path}` | {len(counts)} | {percent(run, len(counts))} |")
    missing = [p for p in unreached() if p not in lines]
    rows += ["", "Files in no report (no test compiled or loaded them, or they hold no code):", ""]
    rows += [f"- `{p}`" for p in missing]
    return "\n".join(rows) + "\n"


def lcov(lines: Lines) -> str:
    out = []
    for path in sorted(lines):
        counts = lines[path]
        out.append(f"SF:{path}")
        out += [f"DA:{n},{c}" for n, c in sorted(counts.items())]
        out += [f"LF:{len(counts)}", f"LH:{sum(1 for c in counts.values() if c)}", "end_of_record"]
    return "\n".join(out) + "\n"


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gcov", nargs="*", default=[], type=Path, help="folders with .gcda files")
    ap.add_argument("--lines", nargs="*", default=[], type=Path, help="files that --save wrote")
    ap.add_argument("--python", nargs="*", default=[], type=Path, help="coverage.py JSON files")
    ap.add_argument("--save", type=Path, help="write the lines read, for a later --lines")
    ap.add_argument("--out", type=Path, help="write the report here")
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    lines: Lines = {}
    for folder in args.gcov:
        read_gcov(folder, lines)
    for f in args.lines:
        read_saved(f, lines)
    for f in args.python:
        read_python(f, lines)
    if args.save:
        args.save.parent.mkdir(parents=True, exist_ok=True)
        args.save.write_text(json.dumps(lines))
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "coverage.lcov").write_text(lcov(lines))
        (args.out / "summary.md").write_text(summary(lines))
        (args.out / "files.md").write_text(files(lines))
    print(summary(lines))


if __name__ == "__main__":
    main()
