"""The coverage rules in coverage_comment.py: diff parsing, thresholds, missing data."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import coverage_comment as cc
import coverage_report as cr
import pytest

DIFF = """\
diff --git a/components/x/a.cpp b/components/x/a.cpp
--- a/components/x/a.cpp
+++ b/components/x/a.cpp
@@ -3,0 +4,3 @@ void f() {
+  one();
+  two();
+  three();
@@ -10 +13 @@ void g() {
-  old();
+  new_();
diff --git a/components/x/gone.py b/components/x/gone.py
--- a/components/x/gone.py
+++ /dev/null
@@ -1,2 +0,0 @@
-import os
-print(os)
"""


def test_changed_lines_reads_hunks() -> None:
    assert cc.changed_lines(DIFF) == {"components/x/a.cpp": {4, 5, 6, 13}}


def test_changed_lines_skips_a_pure_deletion() -> None:
    diff = "+++ b/pixel/daruma_pixel/p.py\n@@ -5,2 +4,0 @@\n"
    assert cc.changed_lines(diff) == {"pixel/daruma_pixel/p.py": set()}


# git diff -U0 --find-renames: a pure move, then a move with one edited line.
RENAMES = """\
diff --git a/components/x/moved.h b/src/esphome/components/x/moved.h
similarity index 100%
rename from components/x/moved.h
rename to src/esphome/components/x/moved.h
diff --git a/components/x/edited.py b/src/esphome/components/x/edited.py
similarity index 97%
rename from components/x/edited.py
rename to src/esphome/components/x/edited.py
index 1111111..2222222 100644
--- a/components/x/edited.py
+++ b/src/esphome/components/x/edited.py
@@ -7 +7 @@ def f():
-    old()
+    new_()
"""


def test_changed_lines_counts_only_the_edits_of_moved_files() -> None:
    assert cc.changed_lines(RENAMES) == {"src/esphome/components/x/edited.py": {7}}


def test_changed_lines_keeps_no_path_from_the_file_before() -> None:
    # The pure move has no +++ line; its hunk-free section must not reuse
    # the previous file's path.
    diff = DIFF.split("diff --git a/components/x/gone.py")[0] + RENAMES.split("diff --git a/components/x/edited.py")[0]
    diff += "@@ -1 +1 @@\n-a\n+b\n"
    assert cc.changed_lines(diff) == {"components/x/a.cpp": {4, 5, 6, 13}}


def test_ranges() -> None:
    assert cc.ranges([1, 2, 3, 7, 9, 10]) == "1-3, 7, 9-10"


@pytest.mark.parametrize(("run", "total", "ok"), [(8, 10, True), (79, 100, False), (80, 100, True), (0, 0, True)])
def test_changed_rule_threshold(run: int, total: int, ok: bool) -> None:
    assert cc.changed_rule(run, total, 80).ok is ok


def test_changed_rule_with_no_measured_line_says_so() -> None:
    rule = cc.changed_rule(0, 0)
    assert rule.ok and "no changed line" in rule.detail


@pytest.mark.parametrize(
    ("now", "base", "ok"),
    [
        (75.0, 75.5, True),  # exactly the limit
        (75.0, 75.54, True),  # prints as -0.5
        (75.0, 75.56, False),  # prints as -0.6
        (80.0, 75.0, True),
    ],
)
def test_drop_rule_threshold(now: float, base: float, ok: bool) -> None:
    assert cc.drop_rule("C++", now, base, 0.5).ok is ok


def test_drop_rule_without_main_passes_and_says_so() -> None:
    rule = cc.drop_rule("Python tested", 70.0, None)
    assert rule.ok and "main has no number" in rule.detail


def test_rule_lines_counts_python_only_when_tested() -> None:
    lines = {"components/x/a.cpp": {1: 3}, "components/x/b.py": {1: 1, 2: 1}}
    tested = cr.tested_lines(lines, {"components/x/b.py": {1: 1}})
    rules = cc.rule_lines(lines, tested)
    assert rules == {"components/x/a.cpp": {1: 3}, "components/x/b.py": {1: 1, 2: 0}}


def test_tested_lines_keep_files_only_builds_load() -> None:
    lines = {"components/x/__init__.py": {1: 1, 2: 1}, "components/x/a.cpp": {1: 1}}
    assert cr.tested_lines(lines, {}) == {"components/x/__init__.py": {1: 0, 2: 0}}


def inputs(**kw) -> cc.Inputs:
    lines = {"components/x/a.cpp": {4: 1, 5: 1, 6: 0, 13: 1}, "components/x/b.py": {1: 1, 2: 1}}
    defaults = {
        "lines": lines,
        "tested": cr.tested_lines(lines, {"components/x/b.py": {1: 1, 2: 0}}),
        "base_lines": lines,
        "base_tested": cr.tested_lines(lines, {"components/x/b.py": {1: 1, 2: 0}}),
        "changed": {"components/x/a.cpp": {4, 5, 6, 13}},
    }
    return cc.Inputs(**{**defaults, **kw})


def test_evaluate_counts_changed_lines() -> None:
    rules, missed = cc.evaluate(inputs())
    assert [r.ok for r in rules] == [False, True, True]
    assert rules[0].detail.startswith("3 of 4")
    assert missed == {"components/x/a.cpp": [6]}


def test_evaluate_changed_python_line_run_only_by_builds_is_missed() -> None:
    rules, missed = cc.evaluate(inputs(changed={"components/x/b.py": {2}}))
    assert not rules[0].ok
    assert missed == {"components/x/b.py": [2]}


def test_evaluate_python_tested_drop_fails() -> None:
    base_tested = {"components/x/b.py": {1: 1, 2: 1}}
    rules, _ = cc.evaluate(inputs(changed={}, base_tested=base_tested))
    assert [r.ok for r in rules] == [True, True, False]


def test_evaluate_main_without_tested_file_is_no_baseline() -> None:
    i = inputs(changed={}, base_tested=None)
    rules, _ = cc.evaluate(i)
    assert all(r.ok for r in rules)
    assert "main has no number" in rules[2].detail
    text = cc.comment(i, rules, {})
    assert "Python: 50.0% tested, 100.0% run in builds." in text


def test_evaluate_no_main_at_all() -> None:
    i = inputs(base_lines=None, base_tested=None)
    rules, missed = cc.evaluate(i)
    assert rules[1].ok and rules[2].ok
    assert "No coverage from main yet" in cc.comment(i, rules, missed)


def test_main_writes_comment_and_status(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    i = inputs()
    (tmp_path / "lines.json").write_text(json.dumps(i.lines))
    (tmp_path / "tested.json").write_text(json.dumps(i.tested))
    (tmp_path / "pr.diff").write_text(DIFF)
    argv = ["coverage_comment.py", str(tmp_path / "lines.json"), "--tested", str(tmp_path / "tested.json")]
    argv += ["--base", str(tmp_path / "missing.json"), "--diff", str(tmp_path / "pr.diff")]
    argv += ["--out", str(tmp_path / "comment.md"), "--status", str(tmp_path / "status")]
    monkeypatch.setattr(sys, "argv", argv)
    cc.main()
    assert (tmp_path / "status").read_text() == "fail\n"
    assert "| Changed lines run (at least 80%) | **fail** | 3 of 4 (75.0%) |" in (tmp_path / "comment.md").read_text()
