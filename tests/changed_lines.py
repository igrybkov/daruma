"""The lines a branch changes, for the mutation scripts' --diff mode.

The changes count from the merge base with BASE, so commits that landed on
BASE later are not this branch's. Uncommitted changes count too, and a new
file that git doesn't track yet counts whole.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_HUNK = re.compile(r"^@@ -\S+ \+(\d+)(?:,(\d+))? @@", re.MULTILINE)


def _git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, check=True).stdout


def _added_lines(diff: str) -> set[int]:
    lines = set()
    for match in _HUNK.finditer(diff):
        start, count = int(match[1]), int(match[2] or 1)
        lines.update(range(start, start + count))
    return lines


def changed_lines(base: str, paths: list[str]) -> dict[str, set[int]]:
    """Path (relative to the repository root) -> its added or changed lines."""
    merge_base = _git("merge-base", base, "HEAD").strip()
    changed = {}
    for path in paths:
        lines = _added_lines(_git("diff", "-U0", merge_base, "--", path))
        if lines:
            changed[path] = lines
    for path in _git("ls-files", "--others", "--exclude-standard", "--", *paths).split():
        changed[path] = set(range(1, len((ROOT / path).read_text().splitlines()) + 1))
    return changed
