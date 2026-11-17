"""The coverage comment on a pull request, and the coverage rules.

    python tests/coverage_comment.py report/lines.json --tested report/tested.json \
        --base main/lines.json --base-tested main/tested.json \
        --diff pr.diff --out comment.md --status status.txt

lines.json and tested.json come from tests/coverage_report.py: this pull
request's run, and with --base and --base-tested the newest one from main.
--diff is `git diff -U0 --find-renames` from main to the pull request.

Python has two numbers. "Tested" counts only the lines the host tests run.
"Run in builds" also counts ESPHome's config checks and code generation,
which run in every build whether a test checks them or not. The rules use
the tested number for Python. C++ has one number: the host tests and the
screen tests both check it.

The rules:

- Changed lines: of the lines this pull request changes that coverage
  measures, at least --min-changed percent must run. A changed Python line
  counts as run only when the host tests run it. With no measured changed
  line, the rule passes.
- No drop: neither the C++ total nor the Python tested total may fall more
  than --max-drop percentage points below main's newest run. A number main
  has no data for passes.

The comment shows each rule's result, the changed lines no test runs, the
totals and a table per area. --status gets "pass" or "fail". The script
exits 0 either way, so CI can post the comment before the job fails.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from changed_lines import added_lines
from coverage_report import Lines, language, percent, tally

# The rules' thresholds. CI uses these defaults.
MIN_CHANGED = 80.0  # percent of the measured changed lines that must run
MAX_DROP = 0.5  # percentage points a total may fall below main's

MAX_FILES = 15

Sums = dict[tuple[str, str], list[int]]


@dataclass
class Rule:
    name: str
    ok: bool
    detail: str

    def row(self) -> str:
        return f"| {self.name} | {'pass' if self.ok else '**fail**'} | {self.detail} |"


@dataclass
class Inputs:
    lines: Lines
    tested: Lines | None
    base_lines: Lines | None
    base_tested: Lines | None
    changed: dict[str, set[int]]
    base_run: str = ""
    min_changed: float = MIN_CHANGED
    max_drop: float = MAX_DROP


def load(path: Path | None) -> Lines | None:
    """A lines.json or tested.json file; None when there is no such file."""
    if path is None or not path.exists():
        return None
    return {name: {int(n): c for n, c in counts.items()} for name, counts in json.loads(path.read_text()).items()}


def changed_lines(diff: str) -> dict[str, set[int]]:
    """{path: line numbers added or changed}, from a diff with no context lines.

    Make the diff with --find-renames and a pathspec that holds a moved
    file's old and new paths, so a move adds only the lines that changed.
    """
    return added_lines(diff)


def ranges(numbers: list[int]) -> str:
    """1, 2, 3, 7 as "1-3, 7"."""
    spans: list[list[int]] = []
    for n in numbers:
        if spans and n == spans[-1][1] + 1:
            spans[-1][1] = n
        else:
            spans.append([n, n])
    return ", ".join(str(a) if a == b else f"{a}-{b}" for a, b in spans)


def rule_lines(lines: Lines, tested: Lines | None) -> Lines:
    """The lines the rules count: C++ from every run, Python from the host tests.

    With no tested data, Python counts from every run too.
    """
    if tested is None:
        return lines
    return {path: tested.get(path, {}) if language(path) == "Python" else counts for path, counts in lines.items()}


def changed_counts(lines: Lines, changed: dict[str, set[int]]) -> tuple[int, int, dict[str, list[int]]]:
    """(changed lines run, measured changed lines, {path: changed lines not run})."""
    total = run = 0
    missed: dict[str, list[int]] = {}
    for path in sorted(changed):
        counts = lines.get(path, {})
        code = sorted(n for n in changed[path] if n in counts)
        not_run = [n for n in code if not counts[n]]
        total += len(code)
        run += len(code) - len(not_run)
        if not_run:
            missed[path] = not_run
    return run, total, missed


def changed_rule(run: int, total: int, minimum: float = MIN_CHANGED) -> Rule:
    name = f"Changed lines run (at least {minimum:g}%)"
    if not total:
        return Rule(name, True, "no changed line is measured code")
    return Rule(name, 100 * run / total >= minimum, f"{run} of {total} ({percent(run, total)})")


def share(sums: Sums | None, lang: str) -> float | None:
    """One language's total share run, in percent; None with no lines."""
    if not sums:
        return None
    total, run = sums.get(("Total", lang), [0, 0])
    return 100 * run / total if total else None


def drop_rule(label: str, now: float | None, base: float | None, max_drop: float = MAX_DROP) -> Rule:
    """The total may fall at most `max_drop` points below main's.

    The change is rounded to one decimal, as the comment prints it.
    """
    name = f"{label} total (at most {max_drop:g} points below main)"
    if now is None:
        return Rule(name, True, "no lines measured")
    if base is None:
        return Rule(name, True, f"{now:.1f}%; main has no number to compare")
    change = round(now - base, 1)
    return Rule(name, change >= -max_drop, f"{now:.1f}%, main {base:.1f}% ({change:+.1f})")


def tally_or_none(lines: Lines | None) -> Sums | None:
    return tally(lines) if lines is not None else None


def evaluate(i: Inputs) -> tuple[list[Rule], dict[str, list[int]]]:
    """The rules' results, and the changed lines no test runs."""
    run, total, missed = changed_counts(rule_lines(i.lines, i.tested), i.changed)
    sums, base = tally(i.lines), tally_or_none(i.base_lines)
    tested, base_tested = tally_or_none(i.tested), tally_or_none(i.base_tested)
    rules = [
        changed_rule(run, total, i.min_changed),
        drop_rule("C++", share(sums, "C++"), share(base, "C++"), i.max_drop),
        drop_rule("Python tested", share(tested, "Python"), share(base_tested, "Python"), i.max_drop),
    ]
    return rules, missed


def cell(sums: Sums | None, base: Sums | None, key: tuple[str, str]) -> str:
    """One share, with the change from main in brackets; "?" with no data."""
    if sums is None:
        return "?"
    total, run = sums.get(key, [0, 0])
    if not total:
        return "-"
    text = percent(run, total)
    if base and base.get(key, [0, 0])[0]:
        b_total, b_run = base[key]
        text += f" ({100 * run / total - 100 * b_run / b_total:+.1f})"
    return text


def areas_table(sums: Sums, base: Sums | None, tested: Sums | None, base_tested: Sums | None) -> str:
    rows = ["| Area | C++ | Python tested | Python run in builds |", "|---|---:|---:|---:|"]
    for a in sorted({a for a, _ in sums} - {"Total"}) + ["Total"]:
        name = f"**{a}**" if a == "Total" else f"`{a}`"
        cells = [
            cell(sums, base, (a, "C++")),
            cell(tested, base_tested, (a, "Python")),
            cell(sums, base, (a, "Python")),
        ]
        rows.append(f"| {name} | " + " | ".join(cells) + " |")
    return "\n".join(rows)


def missed_list(missed: dict[str, list[int]]) -> list[str]:
    if not missed:
        return []
    out = ["", "Changed lines no test runs (for Python: no host test):", ""]
    out += [f"- `{path}`: {ranges(numbers)}" for path, numbers in list(missed.items())[:MAX_FILES]]
    if len(missed) > MAX_FILES:
        out.append(f"- and {len(missed) - MAX_FILES} more files: see the coverage artifact")
    return out


def comment(i: Inputs, rules: list[Rule], missed: dict[str, list[int]]) -> str:
    sums, base = tally(i.lines), tally_or_none(i.base_lines)
    tested, base_tested = tally_or_none(i.tested), tally_or_none(i.base_tested)
    totals = (
        f"Total: C++ {cell(sums, None, ('Total', 'C++'))}. "
        f"Python: {cell(tested, None, ('Total', 'Python'))} tested, "
        f"{cell(sums, None, ('Total', 'Python'))} run in builds."
    )
    since = f"Change from main's run {i.base_run} in brackets." if base else "No coverage from main yet to compare."
    out = ["### Coverage", "", "| Rule | Result | Numbers |", "|---|---|---|", *(r.row() for r in rules)]
    out += missed_list(missed)
    out += ["", totals, ""]
    out += [
        "Python tested: lines the host tests run. Python run in builds also counts ESPHome's config checks",
        "and code generation, which run in every build. The rules use the tested number.",
        "",
    ]
    out += ["<details><summary>Per area</summary>", "", since, "", areas_table(sums, base, tested, base_tested)]
    out += ["", "</details>"]
    return "\n".join(out) + "\n"


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("lines", type=Path, help="this run's lines.json")
    ap.add_argument("--tested", type=Path, help="this run's tested.json")
    ap.add_argument("--base", type=Path, help="main's lines.json")
    ap.add_argument("--base-tested", type=Path, help="main's tested.json")
    ap.add_argument("--base-run", default="", help="main's run id, for the text")
    ap.add_argument("--diff", type=Path, required=True, help="git diff -U0 from main")
    ap.add_argument("--min-changed", type=float, default=MIN_CHANGED, help="percent of changed lines that must run")
    ap.add_argument("--max-drop", type=float, default=MAX_DROP, help="points a total may fall below main's")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--status", type=Path, help='write "pass" or "fail" here')
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    lines = load(args.lines)
    if lines is None:
        raise SystemExit(f"{args.lines}: no such file")
    i = Inputs(
        lines=lines,
        tested=load(args.tested),
        base_lines=load(args.base),
        base_tested=load(args.base_tested),
        changed=changed_lines(args.diff.read_text()),
        base_run=args.base_run,
        min_changed=args.min_changed,
        max_drop=args.max_drop,
    )
    rules, missed = evaluate(i)
    text = comment(i, rules, missed)
    args.out.write_text(text)
    if args.status:
        args.status.write_text("pass\n" if all(r.ok for r in rules) else "fail\n")
    print(text)


if __name__ == "__main__":
    main()
