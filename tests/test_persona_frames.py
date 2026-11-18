"""Every picture of every pixel persona matches its golden, pixel by pixel.

    uv run pytest tests/test_persona_frames.py

One test per persona; see persona_frames.py for the layout of the goldens.
A refactor of the pixel art must leave every test passing. A change to
the art fails here: look at the pictures it writes, then accept them with

    make update-frames CONFIRM=1

Builds every persona, a minute or two. DARUMA_SKIP_PERSONAS=1 skips it.
"""

import os

import persona_frames
import pytest

pytestmark = pytest.mark.skipif(bool(os.environ.get("DARUMA_SKIP_PERSONAS")), reason="DARUMA_SKIP_PERSONAS is set")


@pytest.mark.parametrize("label", sorted(persona_frames.builds()))
def test_frames_match_goldens(label):
    out = persona_frames.results_folder()
    report = []
    for name, persona in persona_frames.personas_of(label, persona_frames.builds()[label]).items():
        problems = persona_frames.check(name, persona, out, persona_frames.golden_of(label))
        report += [f"{name}/{p}" for p in problems]
    shown = "\n  ".join(report[:40])
    more = f"\n  ... and {len(report) - 40} more" if len(report) > 40 else ""
    assert not report, f"{len(report)} golden files differ (pictures in {out}):\n  {shown}{more}"
