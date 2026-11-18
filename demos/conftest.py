"""pytest fixtures and the scenario collector for screen tests of the desktop build.

    uv sync
    uv run pytest demos

The `device` fixture starts a fresh desktop device per test, on the runner's
clock (see harness.py). The build happens once per session, in
$DARUMA_WORK (a temp folder by default). With pytest-xdist (`-n auto`, the default), the
workers share that build, and each device takes a free API port.

    @pytest.mark.persona("Pixel corgi")      # default: Eyes
    @pytest.mark.failing("todo.get_items")   # "HA" refuses these actions
    def test_pet(device):
        device.pet()
        expect(device).to_have_state("petted")

Golden pictures for `expect(device).to_match_screenshot(name)` live in
tests/golden/<persona>/<test name>/<name>.png. `--update-golden`
writes them from this run. A failing test leaves a trace in its tmp folder:
trace.gif of every frame, and the actual, expected and diff pictures.

Each scenario file (scenarios/*.yaml) is also a test: one per persona in
its `test_personas`, named <scenario>[<persona slug>], with the marker
`scenario`. It runs the snapshot and expect steps; its golden pictures live
in tests/golden/<persona>/<scenario>/. `--persona` and `--scenario` narrow
these tests. DARUMA_PERSONA_PATH adds the personas of folders outside
this repository (persona_path.py); their golden pictures live in each
folder's tests/golden/scenarios/.

    uv run pytest demos/scenarios/tour.yaml
    uv run pytest demos -m scenario --persona "Pixel corgi" --scenario tour
"""

from __future__ import annotations

import fcntl
import os
import pickle
import tempfile
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

import persona_path
import pytest
import scenario as scenarios
from demo_data import DemoData
from harness import GOLDEN_DIR, Build, Device, build, desktop_personas, slug
from media import encode_gif, frames_of

DEFAULT_PERSONA = "Eyes"

# A local time zone far from the tests' own (New York by default). The
# device must take its zone from "HA" and the harness must send the test's:
# if either falls back to this machine's zone, every clock is hours off, on
# every machine. The ESPHome build and the device inherit it too.
os.environ["TZ"] = "Pacific/Honolulu"
time.tzset()


def pytest_addoption(parser):
    parser.addoption("--update-golden", action="store_true", help="write golden pictures from this run")
    parser.addoption("--window", action="store_true", help="show the device's window while tests run")
    parser.addoption("--persona", default="", help="scenario tests: only these personas, comma-separated")
    parser.addoption("--scenario", default="", help="scenario tests: only these scenarios, comma-separated")


def pytest_configure(config):
    config.addinivalue_line("markers", "persona(name): the persona the device shows (default Eyes)")
    config.addinivalue_line(
        "markers", "clock(epoch=..., timezone=...): the wall clock at start and the time zone (default New York)"
    )
    config.addinivalue_line("markers", "failing(*actions): HA actions the runner refuses, until the test clears them")
    config.addinivalue_line("markers", "scenario: a scenario file run as a test (scenarios/*.yaml)")
    private = persona_path.personas()
    known = desktop_personas() + list(private)
    personas = _names(config.getoption("--persona"))
    unknown = [p for p in personas if p not in known]
    if unknown:
        raise pytest.UsageError(f"No persona named {unknown}; personas: {known}")
    names = [sc.name for sc in scenarios.all_scenarios()]
    unknown = [n for n in _names(config.getoption("--scenario")) if n not in names]
    if unknown:
        raise pytest.UsageError(f"No scenario named {unknown}; scenarios: {names}")
    config.stash[_PERSONAS] = personas or known
    config.stash[_PRIVATE] = private


_PERSONAS = pytest.StashKey[list[str]]()
_PRIVATE = pytest.StashKey[dict[str, persona_path.Folder]]()


def _names(option: str) -> list[str]:
    return [n.strip() for n in option.split(",") if n.strip()]


def _work() -> Path:
    return Path(os.environ.get("DARUMA_WORK", Path(tempfile.gettempdir()) / "daruma-demos"))


def pytest_collect_file(parent: pytest.Collector, file_path: Path) -> ScenarioFile | None:
    if file_path.suffix == ".yaml" and file_path.resolve().parent == scenarios.SCENARIO_DIR:
        return ScenarioFile.from_parent(parent, path=file_path)
    return None


class ScenarioFile(pytest.File):
    """A scenario file: one test per persona it tests."""

    def collect(self) -> Iterator[pytest.Function]:
        sc = scenarios.load(str(self.path))
        wanted = _names(self.config.getoption("--scenario"))
        if wanted and sc.name not in wanted:
            return
        for persona in self.config.stash[_PERSONAS]:
            if sc.runs_on(persona, test=True):
                item = pytest.Function.from_parent(
                    self, name=f"{sc.name}[{slug(persona)}]", callobj=_scenario_test(sc, persona)
                )
                item.add_marker(pytest.mark.scenario)
                yield item


def _scenario_test(sc: scenarios.Scenario, persona: str) -> Callable[..., None]:
    def test(request, device_build, tmp_path):
        folder = request.config.stash[_PRIVATE].get(persona)
        golden_root = folder.scenario_golden if folder else GOLDEN_DIR
        device = Device(
            device_build,
            tmp_path,
            persona=persona,
            window=request.config.getoption("--window"),
            golden=golden_root / slug(persona) / sc.name,
            update_golden=request.config.getoption("--update-golden"),
        )
        with _running(request, device, before_recording=lambda d: scenarios.run_setup(d, sc)):
            scenarios.run(device, sc, test=True)

    return test


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    setattr(item, f"rep_{report.when}", report)


def _base_port() -> int:
    # DARUMA_PORT: another API port, when another runner holds 6053.
    return int(os.environ.get("DARUMA_PORT", "6053"))


@pytest.fixture(scope="session")
def device_build(request) -> Build:
    """The desktop build, compiled once per session. It serves every time
    zone: each device sets its own when it starts."""
    work = _work()
    # Set when pytest-xdist runs the tests in several workers.
    run_id = getattr(request.config, "workerinput", {}).get("testrunuid")
    if run_id is None:
        return build(work / "build", port=_base_port())
    return _shared_build(work, run_id)


def _shared_build(work: Path, run_id: str) -> Build:
    """The build, made by the first worker that needs it.

    The others wait for it on a lock, then take it from a stamp file that
    names this test run, so a build from an earlier run is never taken.
    """
    work.mkdir(parents=True, exist_ok=True)
    stamp = work / "build.pickle"
    with open(work / "build.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if stamp.exists():
            with stamp.open("rb") as f:
                made_in, b = pickle.load(f)
            if made_in == run_id:
                return b
        b = build(work / "build", port=_base_port())
        with stamp.open("wb") as f:
            pickle.dump((run_id, b), f)
        return b


@pytest.fixture
def device(request, device_build, tmp_path):
    marker = request.node.get_closest_marker("persona")
    persona = marker.args[0] if marker else DEFAULT_PERSONA
    clock = request.node.get_closest_marker("clock")
    clock_args = dict(clock.kwargs) if clock else {}
    # Set before the device starts: it fetches as soon as "HA" connects.
    failing = request.node.get_closest_marker("failing")
    data = DemoData(failing=set(failing.args)) if failing else None
    b = Device(
        device_build,
        tmp_path,
        persona=persona,
        **clock_args,
        data=data,
        window=request.config.getoption("--window"),
        golden=GOLDEN_DIR / slug(persona) / request.node.name,
        update_golden=request.config.getoption("--update-golden"),
    )
    with _running(request, b) as running:
        yield running


@contextmanager
def _running(request, device: Device, *, before_recording: Callable[[Device], None] | None = None) -> Iterator[Device]:
    """Start the device, run `before_recording`, and record every frame
    after it. On a failure, write trace.gif of the recording."""
    device.start()
    failed = False
    try:
        if before_recording is not None:
            before_recording(device)
        device.record_start(device.workdir / "frames")
        yield device
    except BaseException:
        failed = True
        raise
    finally:
        # A fixture's test fails outside this block: its report tells.
        failed = failed or (getattr(request.node, "rep_call", None) is not None and request.node.rep_call.failed)
        try:
            frames_dir = device.record_stop()
            if failed and frames_dir is not None:
                frames = frames_of(frames_dir, device.skipped)
                if frames:
                    trace = device.workdir / "trace.gif"
                    encode_gif(frames, trace, 4000)
                    print(f"\nTrace: {trace}\nPictures: {device.workdir / 'results'}")
        finally:
            device.close()
