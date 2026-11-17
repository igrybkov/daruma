"""One coverage report from the data of CI's coverage jobs.

    python tests/coverage_report.py --gcov build/ --save cpp.json
    python tests/coverage_report.py --lines cpp-*.json --python python.json \
        --tested-python python-tested.json --out coverage

C++ comes from gcc's --coverage data: --gcov reads every .gcda file in a
folder with gcc's gcov (JSON output, so gcc 10 or later). Each coverage job
saves its C++ lines with --save, while the build is still there. Python
comes as coverage.py JSON. The builds compile copies of the components, so
each file is mapped back to its place in this repository by its path. Line
counts of the same file add up. Only this repository's
src/esphome/components/ and pixel/ count.

Python has two numbers. --python holds every run: the host tests, and
ESPHome's config checks and code generation in the builds. Those run
whether a test checks them or not. --tested-python holds the host tests
alone. A Python line counts as tested only when the host tests run it.

Writes, in --out:
- coverage.lcov   every line of every file, for an editor or genhtml
- summary.md      per area (src/esphome/components/<name>, pixel), and the total
- files.md        per file, and the files no test compiled or loaded
- lines.json      every line's count, for tests/coverage_comment.py
- tested.json     every Python line of lines.json, counted from the host
                  tests alone (when the --tested-python file exists)
- cobertura-cpp.xml, cobertura-python.xml
                  Cobertura XML per language, for tools that read it
"""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENTS_DIR = "src/esphome/components"
COMPONENTS = {p.name for p in (ROOT / COMPONENTS_DIR).iterdir() if p.is_dir()}
SOURCES = ("*.cpp", "*.h", "*.py")

# {repository path: {line: count}}
Lines = dict[str, dict[int, int]]


def repo_path(path: str) -> str | None:
    """The file's path in this repository, or None for anything else."""
    parts = path.replace("\\", "/").split("/")
    for i in range(len(parts) - 2, -1, -1):
        if parts[i] == "components" and parts[i + 1] in COMPONENTS:
            return "/".join([COMPONENTS_DIR, *parts[i + 1 :]])
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
    """src/esphome/components/<name> or pixel."""
    if path.startswith(COMPONENTS_DIR + "/"):
        return "/".join(path.split("/")[:4])
    return "pixel"


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


def tested_lines(lines: Lines, host: Lines) -> Lines:
    """Every Python line of `lines`, with its count from the host tests alone.

    The lines are the same as in `lines`, so both Python numbers share one
    total. A file only the builds load counts as not tested.
    """
    return {
        path: {n: host.get(path, {}).get(n, 0) for n in counts}
        for path, counts in lines.items()
        if language(path) == "Python"
    }


def _summary_cells(sums: dict, tested: dict, a: str) -> list[str]:
    total, run = sums.get((a, "C++"), [0, 0])
    cells = [str(total) if total else "-", percent(run, total)]
    total, run = sums.get((a, "Python"), [0, 0])
    cells += [str(total) if total else "-", percent(tested.get((a, "Python"), [0, 0])[1], total)]
    return [*cells, percent(run, total)]


def summary(lines: Lines, tested: Lines | None = None) -> str:
    sums = tally(lines)
    tested_sums = tally(tested) if tested is not None else {}
    areas = sorted({a for a, _ in sums} - {"Total"}) + ["Total"]
    rows = [
        "| Area | C++ lines | C++ run | Python lines | Python tested | Python run in builds |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for a in areas:
        cells = _summary_cells(sums, tested_sums, a)
        if tested is None and cells[2] != "-":
            cells[3] = "?"
        name = f"**{a}**" if a == "Total" else f"`{a}`"
        rows.append(f"| {name} | " + " | ".join(cells) + " |")
    return "\n".join(rows) + "\n"


def unreached() -> list[str]:
    """Source files in no report: never compiled or loaded by a test, or no code."""
    found = []
    for top in (COMPONENTS_DIR, "pixel"):
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


def _rates(hits: list[int]) -> dict[str, str]:
    """Cobertura's line counts and share run, from every line's hit count."""
    run = sum(1 for c in hits if c)
    rate = f"{run / len(hits):.4f}" if hits else "0"
    return {"line-rate": rate, "lines-covered": str(run), "lines-valid": str(len(hits))}


def _cobertura_class(classes: ET.Element, path: str, counts: dict[int, int]) -> None:
    rate = _rates(list(counts.values()))["line-rate"]
    name = path.rsplit("/", 1)[-1]
    attrs = {"name": name, "filename": path, "line-rate": rate, "branch-rate": "0", "complexity": "0"}
    cls = ET.SubElement(classes, "class", attrs)
    ET.SubElement(cls, "methods")
    lines = ET.SubElement(cls, "lines")
    for n, c in sorted(counts.items()):
        ET.SubElement(lines, "line", {"number": str(n), "hits": str(c), "branch": "false"})


def cobertura(lines: Lines, lang: str) -> str:
    """One language's lines as Cobertura XML: a package per area, a class per file."""
    mine = {path: counts for path, counts in lines.items() if language(path) == lang}
    root = ET.Element("coverage", {"branch-rate": "0", "complexity": "0", "version": "1", "timestamp": "0"})
    root.attrib.update(_rates([c for counts in mine.values() for c in counts.values()]))
    root.attrib.update({"branches-covered": "0", "branches-valid": "0"})
    ET.SubElement(ET.SubElement(root, "sources"), "source").text = "."
    packages = ET.SubElement(root, "packages")
    for name in sorted({area(path) for path in mine}):
        paths = sorted(path for path in mine if area(path) == name)
        rate = _rates([c for path in paths for c in mine[path].values()])["line-rate"]
        attrs = {"name": name.replace("/", "."), "line-rate": rate, "branch-rate": "0", "complexity": "0"}
        classes = ET.SubElement(ET.SubElement(packages, "package", attrs), "classes")
        for path in paths:
            _cobertura_class(classes, path, mine[path])
    ET.indent(root)
    return '<?xml version="1.0" ?>\n' + ET.tostring(root, encoding="unicode") + "\n"


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gcov", nargs="*", default=[], type=Path, help="folders with .gcda files")
    ap.add_argument("--lines", nargs="*", default=[], type=Path, help="files that --save wrote")
    ap.add_argument("--python", nargs="*", default=[], type=Path, help="coverage.py JSON files")
    ap.add_argument("--tested-python", type=Path, help="coverage.py JSON of the host tests alone")
    ap.add_argument("--save", type=Path, help="write the lines read, for a later --lines")
    ap.add_argument("--out", type=Path, help="write the report here")
    return ap.parse_args()


def write_report(out: Path, lines: Lines, tested: Lines | None) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "coverage.lcov").write_text(lcov(lines))
    (out / "lines.json").write_text(json.dumps(lines))
    if tested is not None:
        (out / "tested.json").write_text(json.dumps(tested))
    (out / "summary.md").write_text(summary(lines, tested))
    (out / "files.md").write_text(files(lines))
    (out / "cobertura-cpp.xml").write_text(cobertura(lines, "C++"))
    (out / "cobertura-python.xml").write_text(cobertura(lines, "Python"))


def main() -> None:
    args = parse_args()
    lines: Lines = {}
    for folder in args.gcov:
        read_gcov(folder, lines)
    for f in args.lines:
        read_saved(f, lines)
    for f in args.python:
        read_python(f, lines)
    tested = None
    if args.tested_python and args.tested_python.exists():
        host: Lines = {}
        read_python(args.tested_python, host)
        tested = tested_lines(lines, host)
    if args.save:
        args.save.parent.mkdir(parents=True, exist_ok=True)
        args.save.write_text(json.dumps(lines))
    if args.out:
        write_report(args.out, lines, tested)
    print(summary(lines, tested))


if __name__ == "__main__":
    main()
