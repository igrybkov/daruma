"""pytest fixtures for screen tests of the desktop build.

    uv run --with pytest --with aioesphomeapi==46.30.0 --with pillow --with pyyaml \\
        pytest demos

The `daruma` fixture starts a fresh desktop device per test, on the runner's
clock (see harness.py). The build happens once per session, in
$DARUMA_WORK (a temp folder by default).

    @pytest.mark.persona("Pixel corgi")      # default: Eyes
    def test_pet(device):
        device.pet()
        expect(device).to_have_state("petted")

Golden pictures for `expect(device).to_match_screenshot(name)` live in
tests/golden/<persona>/<test name>/<name>.png. `--update-golden`
writes them from this run. A failing test leaves a trace in its tmp folder:
trace.gif of every frame, and the actual and diff pictures.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness import GOLDEN_DIR, Device, build, slug  # noqa: E402
from media import encode_gif, frames_of  # noqa: E402

DEFAULT_PERSONA = "Eyes"


def pytest_addoption(parser):
    parser.addoption("--update-golden", action="store_true", help="write golden pictures from this run")
    parser.addoption("--window", action="store_true", help="show the device's window while tests run")


def pytest_configure(config):
    config.addinivalue_line("markers", "persona(name): the persona the device shows (default Eyes)")
    config.addinivalue_line("markers", "clock(epoch=..., timezone=...): the wall clock at start and the time zone")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    setattr(item, f"rep_{report.when}", report)


@pytest.fixture(scope="session")
def device_builds():
    """The desktop build for a time zone, compiled once per session."""
    work = Path(os.environ.get("DARUMA_WORK", Path(tempfile.gettempdir()) / "daruma-demos"))
    # DARUMA_PORT: another API port, when another runner holds 6053.
    port = int(os.environ.get("DARUMA_PORT", "6053"))
    builds = {}

    def get(timezone: str):
        if timezone not in builds:
            builds[timezone] = build(work / "build", port=port, timezone=timezone)
        return builds[timezone]

    return get


@pytest.fixture
def device(request, device_builds, tmp_path):
    marker = request.node.get_closest_marker("persona")
    persona = marker.args[0] if marker else DEFAULT_PERSONA
    clock = request.node.get_closest_marker("clock")
    clock_args = dict(clock.kwargs) if clock else {}
    # A time zone builds the desktop program for it (the board's clock), and
    # "HA" sends it with the time.
    timezone = clock_args.setdefault("timezone", "UTC")
    b = Device(device_builds(timezone), tmp_path, persona=persona, **clock_args, window=request.config.getoption("--window"),
              golden=GOLDEN_DIR / slug(persona) / request.node.name,
              update_golden=request.config.getoption("--update-golden"))
    b.start()
    b.record_start(tmp_path / "frames")
    try:
        yield b
    finally:
        failed = getattr(request.node, "rep_call", None) is not None and request.node.rep_call.failed
        try:
            frames_dir = b.record_stop()
            if failed and frames_dir is not None:
                frames = frames_of(frames_dir, b.skipped)
                if frames:
                    trace = tmp_path / "trace.gif"
                    encode_gif(frames, trace, 4000)
                    print(f"\nTrace: {trace}\nPictures: {tmp_path / 'results'}")
        finally:
            b.close()
