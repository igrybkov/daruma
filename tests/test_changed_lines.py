"""changed_lines.py on a scratch git repository: moves, edits, new files."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import changed_lines as cl
import pytest

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="needs git")

BODY = "".join(f"line {n}\n" for n in range(1, 21))


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test")
    _git(tmp_path, "config", "commit.gpgsign", "false")
    for name in ("moved.h", "edited.py", "kept.py"):
        (tmp_path / "components" / "x").mkdir(parents=True, exist_ok=True)
        (tmp_path / "components" / "x" / name).write_text(BODY)
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "base")
    _git(tmp_path, "checkout", "-q", "-b", "branch")
    monkeypatch.setattr(cl, "ROOT", tmp_path)
    return tmp_path


def test_a_move_counts_only_its_edited_lines(repo: Path) -> None:
    new = repo / "src" / "esphome" / "components" / "x"
    new.mkdir(parents=True)
    _git(repo, "mv", "components/x/moved.h", "src/esphome/components/x/moved.h")
    _git(repo, "mv", "components/x/edited.py", "src/esphome/components/x/edited.py")
    (new / "edited.py").write_text(BODY.replace("line 7\n", "line seven\n"))
    (repo / "components" / "x" / "kept.py").write_text(BODY + "line 21\n")
    _git(repo, "commit", "-q", "-am", "move")
    paths = ["src/esphome/components/x/moved.h", "src/esphome/components/x/edited.py", "components/x/kept.py"]
    assert cl.changed_lines("main", paths) == {
        "src/esphome/components/x/edited.py": {7},
        "components/x/kept.py": {21},
    }


def test_only_the_asked_paths_and_untracked_files_whole(repo: Path) -> None:
    (repo / "components" / "x" / "kept.py").write_text(BODY + "line 21\n")
    (repo / "components" / "x" / "new.py").write_text("a\nb\n")
    assert cl.changed_lines("main", ["components/x/new.py"]) == {"components/x/new.py": {1, 2}}


def test_a_folder_stands_for_every_file_in_it(repo: Path) -> None:
    (repo / "components" / "x" / "kept.py").write_text(BODY + "line 21\n")
    (repo / "components" / "x" / "new.py").write_text("a\n")
    (repo / "components" / "xy").mkdir()
    (repo / "components" / "xy" / "other.py").write_text("b\n")
    assert cl.changed_lines("main", ["components/x"]) == {
        "components/x/kept.py": {21},
        "components/x/new.py": {1},
    }
