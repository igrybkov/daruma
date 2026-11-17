"""Keeps docs/architecture/ small and its references true."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TOPICS = ROOT / "docs" / "architecture"
MAX_LINES = 300

LINK = re.compile(r"\]\(([^)#\s]+)(?:#([^)\s]+))?\)")
CODE_PATH = re.compile(r"`([\w.-]+(?:/[\w.<>-]+)+/?)`")
HEADING = re.compile(r"^#{1,6} (.+)$", re.MULTILINE)
FENCE = re.compile(r"^```.*?^```", re.MULTILINE | re.DOTALL)


def _anchor(heading: str) -> str:
    text = re.sub(r"[^\w\s-]", "", heading.strip().lower())
    return re.sub(r"\s", "-", text)


def _anchors(path: Path) -> set[str]:
    text = FENCE.sub("", path.read_text())
    return {_anchor(h) for h in HEADING.findall(text)}


def _topics() -> list[Path]:
    return sorted(TOPICS.glob("*.md"))


@pytest.mark.parametrize("doc", _topics(), ids=lambda p: p.name)
def test_topic_stays_short(doc):
    lines = len(doc.read_text().splitlines())
    assert lines <= MAX_LINES, f"{doc.name} has {lines} lines; split it by kind of work"


@pytest.mark.parametrize("doc", _topics(), ids=lambda p: p.name)
def test_links_resolve(doc):
    text = FENCE.sub("", doc.read_text())
    for target, anchor in LINK.findall(text):
        if "://" in target:
            continue
        path = (doc.parent / target).resolve()
        assert path.exists(), f"{doc.name}: no file {target}"
        if anchor and path.suffix == ".md":
            assert anchor in _anchors(path), f"{doc.name}: no heading #{anchor} in {target}"


@pytest.mark.parametrize("doc", _topics(), ids=lambda p: p.name)
def test_code_paths_exist(doc):
    text = FENCE.sub("", doc.read_text())
    for ref in CODE_PATH.findall(text):
        if "<" in ref:
            continue
        assert (ROOT / ref).exists(), f"{doc.name}: no path {ref}"
