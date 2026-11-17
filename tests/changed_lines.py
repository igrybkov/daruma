"""The lines a branch changes, for the mutation scripts' --diff mode.

The changes count from the merge base with BASE, so commits that landed on
BASE later are not this branch's. Uncommitted changes count too, and a new
file that git doesn't track yet counts whole.

One diff of the whole tree, with rename detection, so a moved file counts
only the lines that changed in it. A pathspec per file would hide the old
path, and git would see every moved file as new.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def _git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, check=True).stdout


def added_lines(diff: str) -> dict[str, set[int]]:
    """{path: line numbers added or changed}, from a diff with no context lines.

    A file's path is its new one (`+++ b/<path>`). A pure rename has no
    such line and no hunks, so it adds nothing. A pure deletion of lines
    keeps its path with no lines.
    """
    changed: dict[str, set[int]] = {}
    path = None
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            path = None
        elif line.startswith("+++ "):
            name = line[4:]
            path = name[2:] if name.startswith("b/") else None
        elif path and (m := _HUNK.match(line)):
            start, count = int(m[1]), int(m[2] or 1)
            changed.setdefault(path, set()).update(range(start, start + count))
    return changed


def changed_lines(base: str, paths: list[str]) -> dict[str, set[int]]:
    """Path (relative to the repository root) -> its added or changed lines."""
    merge_base = _git("merge-base", base, "HEAD").strip()
    diff = _git("diff", "-U0", "--find-renames", "--no-color", "--no-ext-diff", merge_base)
    wanted = set(paths)
    changed = {path: lines for path, lines in added_lines(diff).items() if path in wanted and lines}
    for path in _git("ls-files", "--others", "--exclude-standard", "--", *paths).split():
        changed[path] = set(range(1, len((ROOT / path).read_text().splitlines()) + 1))
    return changed
