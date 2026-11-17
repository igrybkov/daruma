"""The coverage comment on a pull request.

    python tests/coverage_comment.py report/lines.json --base main/lines.json \
        --diff pr.diff --out comment.md

lines.json comes from tests/coverage_report.py: this pull request's run,
and with --base the newest one from main. --diff is `git diff -U0` from
main to the pull request. The comment holds:

- the share of the lines this pull request changes that the tests run,
  and the changed lines no test runs, per file;
- the total per language, with the change from main;
- per area, in a fold.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from coverage_report import Lines, percent, tally

HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")
MAX_FILES = 15


def load(path: Path) -> Lines:
    return {name: {int(n): c for n, c in counts.items()} for name, counts in json.loads(path.read_text()).items()}


def changed_lines(diff: str) -> dict[str, set[int]]:
    """{path: line numbers added or changed}, from a diff with no context lines."""
    changed: dict[str, set[int]] = {}
    path = None
    for line in diff.splitlines():
        if line.startswith("+++ "):
            name = line[4:]
            path = name[2:] if name.startswith("b/") else None
            continue
        m = HUNK.match(line)
        if m and path:
            start, count = int(m[1]), int(m[2] or 1)
            changed.setdefault(path, set()).update(range(start, start + count))
    return changed


def ranges(numbers: list[int]) -> str:
    """1, 2, 3, 7 as "1-3, 7"."""
    spans: list[list[int]] = []
    for n in numbers:
        if spans and n == spans[-1][1] + 1:
            spans[-1][1] = n
        else:
            spans.append([n, n])
    return ", ".join(str(a) if a == b else f"{a}-{b}" for a, b in spans)


def cell(sums: dict, base: dict | None, key: tuple[str, str]) -> str:
    total, run = sums.get(key, [0, 0])
    if not total:
        return "-"
    text = percent(run, total)
    if base and base.get(key, [0, 0])[0]:
        b_total, b_run = base[key]
        text += f" ({100 * run / total - 100 * b_run / b_total:+.1f})"
    return text


def areas_table(sums: dict, base: dict | None) -> str:
    rows = ["| Area | C++ | Python |", "|---|---:|---:|"]
    for a in sorted({a for a, _ in sums} - {"Total"}) + ["Total"]:
        name = f"**{a}**" if a == "Total" else f"`{a}`"
        rows.append(f"| {name} | {cell(sums, base, (a, 'C++'))} | {cell(sums, base, (a, 'Python'))} |")
    return "\n".join(rows)


def changed_report(lines: Lines, changed: dict[str, set[int]]) -> list[str]:
    """How many changed lines the tests run, and which they don't."""
    total = run = 0
    missed: list[str] = []
    for path in sorted(changed):
        counts = lines.get(path, {})
        code = sorted(n for n in changed[path] if n in counts)
        not_run = [n for n in code if not counts[n]]
        total += len(code)
        run += len(code) - len(not_run)
        if not_run:
            missed.append(f"- `{path}`: {ranges(not_run)}")
    if not total:
        return ["No line this pull request changes is code the tests measure."]
    out = [f"Changed lines the tests run: **{run} of {total}** ({percent(run, total)})."]
    if missed:
        out += ["", "Changed lines no test runs:", "", *missed[:MAX_FILES]]
        if len(missed) > MAX_FILES:
            out.append(f"- and {len(missed) - MAX_FILES} more files: see the coverage artifact")
    return out


def comment(lines: Lines, base_lines: Lines | None, changed: dict[str, set[int]], base_run: str) -> str:
    sums = tally(lines)
    base = tally(base_lines) if base_lines else None
    since = f"Change from main's run {base_run} in brackets." if base else "No coverage from main yet to compare."
    total = f"Total: C++ {cell(sums, base, ('Total', 'C++'))}, Python {cell(sums, base, ('Total', 'Python'))}."
    out = ["### Coverage", "", *changed_report(lines, changed), "", total, since, ""]
    out += ["<details><summary>Per area</summary>", "", areas_table(sums, base), "", "</details>"]
    return "\n".join(out) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("lines", type=Path, help="this run's lines.json")
    ap.add_argument("--base", type=Path, help="main's lines.json")
    ap.add_argument("--base-run", default="", help="main's run id, for the text")
    ap.add_argument("--diff", type=Path, required=True, help="git diff -U0 from main")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    base = load(args.base) if args.base and args.base.exists() else None
    text = comment(load(args.lines), base, changed_lines(args.diff.read_text()), args.base_run)
    args.out.write_text(text)
    print(text)


if __name__ == "__main__":
    main()
