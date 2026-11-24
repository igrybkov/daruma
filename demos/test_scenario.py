"""Tests of the scenario format and the GIF's touch marks. No device needed."""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
from unittest.mock import ANY, MagicMock, call

import harness
import persona_path
import pytest
import scenario as scenarios
from harness import DeviceError
from media import with_touches


def test_caption_block_flattens_to_caption_then_its_steps():
    steps = [
        {"wait": 1},
        {
            "caption": "Start a focus block",
            "steps": [
                {"tap": {"text": "Focus"}},
                {"caption": "Inner", "steps": [{"wait": 2}]},
                {"wait": 1},
            ],
        },
        {"wait": 3},
    ]
    assert scenarios.flatten(steps) == [
        {"wait": 1},
        {"caption": "Start a focus block"},
        {"tap": {"text": "Focus"}},
        {"caption": "Inner"},
        {"wait": 2},
        {"caption": "Start a focus block"},  # back to the outer caption
        {"wait": 1},
        {"caption": ""},  # the block ends: no caption
        {"wait": 3},
    ]


@pytest.mark.parametrize(
    "step",
    [
        {"caption": "Flat"},  # the old flat form
        {"caption": "x", "steps": [], "wait": 1},
        {"caption": "x", "steps": {"wait": 1}},
    ],
)
def test_a_caption_must_hold_its_steps(step):
    with pytest.raises(DeviceError):
        scenarios.flatten([step])


def test_load_reads_nested_captions(tmp_path: Path):
    path = tmp_path / "nested.yaml"
    path.write_text(
        "name: nested\nsetup:\n  - wait: 1\nsteps:\n  - caption: Pet it\n    steps:\n      - pet: true\n  - show: sad\n"
    )
    sc = scenarios.load(str(path))
    assert sc.setup == [{"wait": 1}]
    assert sc.steps == [{"caption": "Pet it"}, {"pet": True}, {"caption": ""}, {"show": "sad"}]
    # covered_states() sees the steps inside a block.
    assert scenarios.covered_states(sc) == {"petted", "sad"}


# Each step kind and the device calls it makes. `expect` is the harness's
# assertion helper, recorded as `expect(<device or locator>)` calls.
STEP_CALLS = [
    ({"wait": 1.5}, [call.advance(1.5)]),
    ({"skip": "300"}, [call.skip(300.0)]),
    ({"tap": [10, 20]}, [call.tap(10, 20)]),
    ({"tap": {"text": "Ok"}}, [call.get_by_text("Ok", exact=True), call.get_by_text().tap(timeout=5)]),
    ({"tap": {"text": "ok", "exact": False}}, [call.get_by_text("ok", exact=False), call.get_by_text().tap(timeout=5)]),
    (
        {"tap": {"role": "button", "name": "Ok", "timeout": 2}},
        [call.get_by_role("button", "Ok"), call.get_by_role().tap(timeout=2)],
    ),
    ({"hold": {"at": [1, 2]}}, [call.hold(1, 2, seconds=1.5)]),
    ({"hold": {"at": [1, 2], "seconds": 3}}, [call.hold(1, 2, seconds=3)]),
    ({"swipe": {"from": [1, 2], "to": [3, 4]}}, [call.swipe(1, 2, 3, 4, seconds=0.25)]),
    ({"swipe": {"from": [1, 2], "to": [3, 4], "seconds": 1}}, [call.swipe(1, 2, 3, 4, seconds=1)]),
    ({"stroke": [5, 6]}, [call.stroke(5, 6)]),
    ({"pet": True}, [call.pet()]),
    ({"press": "home"}, [call.press("home")]),
    ({"press": {"input": "top"}}, [call.press("top", seconds=0.08)]),
    ({"press": {"input": "top", "seconds": 2}}, [call.press("top", seconds=2)]),
    ({"set": {"Window": "Rain", "Temp": 3}}, [call.set("Window", "Rain"), call.set("Temp", 3)]),
    ({"action": {"name": "wink", "times": 2}}, [call.action("wink", times=2)]),
    ({"show": "sad"}, [call.show("sad")]),
    ({"show": None}, [call.show("")]),
    ({"voice": "thinking"}, [call.voice("thinking")]),
    ({"voice": {"phase": "listening"}}, [call.voice("listening", "")]),
    ({"voice": {"phase": "replying", "text": "Hi"}}, [call.voice("replying", "Hi")]),
    ({"caption": 7}, [call.caption("7")]),
    ({"message": {"text": "Hi"}}, [call.show_message("Hi", 5)]),
    ({"message": {"text": "Hi", "seconds": 9}}, [call.show_message("Hi", 9)]),
    ({"prompt": {"id": "door", "title": "Door"}}, [call.show_prompt(id="door", title="Door")]),
    ({"update_prompt": {"id": "quiz", "marks": ["a"]}}, [call.update_prompt(id="quiz", marks=["a"])]),
    (
        {"snapshot": "x"},
        [call.expect(ANY), call.expect().to_match_screenshot("x", mask=[], tolerance=0, max_diff_pixels=0)],
    ),
    (
        {"snapshot": {"name": "y", "mask": [[1, 2, 3, 4]], "tolerance": 8, "max_diff_pixels": 20}},
        [
            call.expect(ANY),
            call.expect().to_match_screenshot("y", mask=[(1, 2, 3, 4)], tolerance=8, max_diff_pixels=20),
        ],
    ),
    ({"expect": {"state": "focus"}}, [call.expect(ANY), call.expect().to_have_state("focus", timeout=5)]),
    (
        {"expect": {"visible": {"text": "Ok"}, "timeout": 1}},
        [call.get_by_text("Ok", exact=True), call.expect(ANY), call.expect().to_be_visible(timeout=1)],
    ),
    (
        {"expect": {"hidden": {"role": "dialog"}}},
        [call.get_by_role("dialog", None), call.expect(ANY), call.expect().to_be_hidden(timeout=5)],
    ),
    (
        {"expect": {"event": {"type": "esphome.x", "name": "a"}, "timeout": 2}},
        [call.expect(ANY), call.expect().to_fire_event("esphome.x", timeout=2, name="a")],
    ),
    (
        {"expect": {"entity": {"name": "Phase", "value": "focus"}}},
        [call.expect(ANY), call.expect().to_have_entity("Phase", "focus", timeout=5)],
    ),
    ({"random_event": "lick_paw"}, [call.random_event("lick_paw")]),
    ({"random_event": None}, [call.random_event("")]),  # Rolls the pool.
]


@pytest.mark.parametrize(("step", "calls"), STEP_CALLS, ids=[str(s) for s, _ in STEP_CALLS])
def test_each_step_makes_its_device_calls(step, calls, monkeypatch):
    # One mock is the device and `expect`, so the calls of both keep their order.
    device = MagicMock()
    monkeypatch.setattr(scenarios, "expect", device.expect)
    before = copy.deepcopy(step)
    for _ in range(2):  # A scenario runs once per persona: a step must not change.
        device.reset_mock()
        scenarios.run_step(device, step, test=True)
        assert device.mock_calls == calls
    assert step == before


def test_a_snapshot_compares_only_in_test_mode(monkeypatch):
    device = MagicMock()
    monkeypatch.setattr(scenarios, "expect", device.expect)
    scenarios.run_step(device, {"snapshot": "x"}, test=False)
    assert device.mock_calls == []


@pytest.mark.parametrize(
    ("step", "error"),
    [
        ({"dance": 1}, "Unknown step 'dance'"),
        ({"wait": 1, "pet": True}, "A step has one key"),
        ({}, "A step has one key"),
        ({"expect": {"smell": "x"}}, "Unknown expectation 'smell'"),
        ({"tap": {"x": 1}}, "A part needs `text` or `role`"),
    ],
)
def test_a_bad_step_raises(step, error, monkeypatch):
    monkeypatch.setattr(scenarios, "expect", MagicMock())
    with pytest.raises(DeviceError, match=error):
        scenarios.run_step(MagicMock(), step, test=True)


def test_every_scenario_loads_with_one_key_steps():
    for sc in scenarios.all_scenarios():
        for step in sc.setup + sc.steps:
            assert len(step) == 1, f"{sc.path.name}: {step}"


def _folder(root: Path, scenarios_yaml: dict[str, str]) -> persona_path.Folder:
    """A DARUMA_PERSONA_PATH folder with one persona, Mine, and these scenario files."""
    (root / "packages").mkdir(parents=True)
    (root / "packages" / "persona_mine.yaml").write_text("daruma_sprites:\n  - id: mine\n    name: Mine\n")
    (root / "demos" / "scenarios").mkdir(parents=True)
    for name, text in scenarios_yaml.items():
        (root / "demos" / "scenarios" / f"{name}.yaml").write_text(text)
    return persona_path.Folder.at(root)


def test_a_folder_scenario_runs_on_its_own_personas_only(tmp_path: Path):
    folder = _folder(
        tmp_path,
        {
            "desk": "name: desk\npersonas: all\ntest_personas: all\nsteps:\n  - wait: 1\n",
            "picky": "name: picky\npersonas: [Mine, Eyes]\ntest_personas: [Eyes]\nsteps:\n  - wait: 1\n",
        },
    )
    desk, picky = scenarios.folder_scenarios([folder])
    assert (desk.name, desk.personas, desk.test_personas) == ("desk", ["Mine"], ["Mine"])
    assert (picky.personas, picky.test_personas) == (["Mine"], [])
    assert desk.runs_on("Mine", test=True)
    assert not desk.runs_on("Eyes", test=True)


def test_a_folder_scenario_may_not_take_a_daruma_name(tmp_path: Path):
    folder = _folder(tmp_path, {"mine": "name: tour\nsteps:\n  - wait: 1\n"})
    with pytest.raises(DeviceError, match="tour"):
        scenarios.folder_scenarios([folder])


def test_load_finds_a_folder_scenario_by_name(tmp_path: Path, monkeypatch):
    _folder(tmp_path, {"desk": "name: desk\nsteps:\n  - wait: 1\n"})
    monkeypatch.setenv(persona_path.ENV, str(tmp_path))
    sc = scenarios.load("desk")
    assert (sc.name, sc.personas) == ("desk", ["Mine"])
    assert [s.name for s in scenarios.every_scenario()][-1] == "desk"
    assert "desk" not in [s.name for s in scenarios.all_scenarios()]


@pytest.fixture
def scenario_dir(tmp_path: Path, monkeypatch) -> Path:
    """A scenario folder with one scenario at the top and two in a subfolder."""
    root = tmp_path / "scenarios"
    (root / "random_events").mkdir(parents=True)
    (root / "tour.yaml").write_text("name: tour\nsteps:\n  - wait: 1\n")
    (root / "random_events" / "spell.yaml").write_text("name: spell\nbuild: events\nsteps:\n  - wait: 1\n")
    (root / "random_events" / "sneeze.yaml").write_text("steps:\n  - wait: 1\n")
    monkeypatch.setattr(scenarios, "SCENARIO_DIR", root)
    return root


def test_load_finds_a_subfolder_scenario_by_its_key(scenario_dir: Path):
    sc = scenarios.load("random_events/spell")
    assert (sc.name, sc.group, sc.key, sc.build) == ("spell", "random_events", "random_events/spell", "events")
    # pytest loads it by its path: the same group.
    assert scenarios.load(str(scenario_dir / "random_events" / "spell.yaml")).key == "random_events/spell"
    top = scenarios.load("tour")
    assert (top.group, top.key, top.build) == ("", "tour", "standard")


def test_subfolder_scenarios_stay_out_of_the_gallery(scenario_dir: Path):
    assert [sc.key for sc in scenarios.all_scenarios()] == ["tour"]
    assert [sc.key for sc in scenarios.group_scenarios()] == ["random_events/sneeze", "random_events/spell"]


def test_daruma_gallery_holds_no_subfolder_scenario():
    assert all(sc.group == "" for sc in scenarios.all_scenarios())
    assert all(sc.group for sc in scenarios.group_scenarios())


def test_a_subfolder_scenario_keeps_its_goldens_in_the_same_subfolder(scenario_dir: Path):
    root = Path("/golden")
    assert scenarios.load("random_events/spell").golden(root, "Pixel corgi") == root / "pixel-corgi/random_events/spell"
    assert scenarios.load("tour").golden(root, "Pixel corgi") == root / "pixel-corgi/tour"


def test_an_unknown_build_fails_to_load(tmp_path: Path):
    path = tmp_path / "x.yaml"
    path.write_text("name: x\nbuild: fancy\nsteps:\n  - wait: 1\n")
    with pytest.raises(DeviceError, match="no build 'fancy'"):
        scenarios.load(str(path))


@pytest.mark.parametrize(
    ("variant", "events", "private", "name"),
    [
        ("standard", False, False, "daruma-desktop"),
        ("standard", True, False, "daruma-desktop-events"),
        ("standard", True, True, "daruma-desktop-events-private"),
        ("wide", True, False, "daruma-desktop-wide-events"),
    ],
)
def test_the_events_build_has_its_own_name(tmp_path: Path, monkeypatch, variant, events, private, name):
    monkeypatch.setattr(harness, "COVERAGE", None)
    extra = [_folder(tmp_path, {})] if private else []
    assert harness._build_name(variant, extra, events) == name


EVENTS_LINES = "daruma:\n  random_events:\n    enabled: false\n"


@pytest.mark.parametrize("private", [False, True])
def test_the_events_config_turns_the_engine_on_with_the_switch_off(tmp_path: Path, monkeypatch, private):
    monkeypatch.setattr(harness, "COVERAGE", None)
    extra = [_folder(tmp_path / "mine", {})] if private else []
    name = harness._build_name("standard", extra, events=True)
    yaml_name, found = harness._write_config(tmp_path, name, extra, events=True)
    text = (tmp_path / yaml_name).read_text()
    assert yaml_name == f"{name}.yaml"
    assert text.startswith(f"packages:\n  base: !include {harness.DEVICE_YAML}\n")
    assert text.endswith(EVENTS_LINES)
    assert ("private_0: !include" in text) == private
    assert list(found) == (["Mine"] if private else [])


def test_the_other_configs_leave_the_engine_alone(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(harness, "COVERAGE", None)
    extra = [_folder(tmp_path / "mine", {})]
    yaml_name, _ = harness._write_config(tmp_path, harness._build_name("standard", extra), extra)
    assert "random_events" not in (tmp_path / yaml_name).read_text()
    assert harness._write_config(tmp_path, "daruma-desktop", [], events=False)[0] == harness.DEVICE_YAML


def _demos_conftest():
    """demos/conftest.py as a module of its own: tests/ has a conftest.py too."""
    path = Path(__file__).parent / "conftest.py"
    spec = importlib.util.spec_from_file_location("demos_conftest_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_each_kind_of_shared_build_has_its_own_stamp(tmp_path: Path, monkeypatch):
    conftest = _demos_conftest()
    made = []

    def fake_build(out, *, events, port):
        made.append(events)
        return harness.Build(program=Path(f"program-{len(made)}"), clock_lib=Path("lib"), port=port)

    monkeypatch.setattr(conftest, "build", fake_build)
    standard = conftest._shared_build(tmp_path, "run-1", events=False)
    events = conftest._shared_build(tmp_path, "run-1", events=True)
    assert made == [False, True]
    assert standard.program != events.program
    assert sorted(p.name for p in tmp_path.iterdir()) == ["build-events.pickle", "build.lock", "build.pickle"]
    # Another worker of the same run takes each one from its stamp.
    assert conftest._shared_build(tmp_path, "run-1", events=True).program == events.program
    assert conftest._shared_build(tmp_path, "run-1", events=False).program == standard.program
    assert made == [False, True]
    # A new run builds again.
    conftest._shared_build(tmp_path, "run-2", events=True)
    assert made == [False, True, True]


def _frames(tmp_path: Path, times: list[int]) -> list[tuple[Path, float]]:
    from PIL import Image

    out = []
    for i, ms in enumerate(times[:-1]):
        p = tmp_path / f"f_{ms:08d}_{i:06d}.bmp"
        Image.new("RGB", (320, 240), (200, 200, 200)).save(p)
        out.append((p, (times[i + 1] - ms) / 1000))
    return out


def test_touch_marks_split_frames_and_keep_the_length(tmp_path: Path):
    from PIL import Image

    frames = _frames(tmp_path, [0, 2000, 4000])
    touches = [{"ms": 1000, "kind": "tap", "points": [(100, 100)], "ms_long": 0}]
    out = with_touches(frames, touches, [], tmp_path / "out", split_at=[3000])
    assert sum(d for _, d in out) == pytest.approx(4.0)
    # One format for ffmpeg's concat, which decodes every file like the first.
    assert {p.suffix for p, _ in out} == {".png"}
    names = [int(p.stem.split("_")[1]) for p, _ in out]
    assert names == sorted(names) and 3000 in names
    # The mark shows at the tap, and is gone once it has faded.
    at_tap = next(p for p, _ in out if int(p.stem.split("_")[1]) == 1000)
    assert Image.open(at_tap).convert("RGB").getpixel((100, 100)) != (200, 200, 200)
    late = next(p for p, _ in out if int(p.stem.split("_")[1]) == 3000)
    assert Image.open(late).convert("RGB").getpixel((100, 100)) == (200, 200, 200)


def test_no_touches_and_no_splits_leaves_frames_alone(tmp_path: Path):
    frames = _frames(tmp_path, [0, 1000, 2000])
    assert with_touches(frames, [], [], tmp_path / "out") == frames


def test_a_finger_mark_ends_when_the_screen_changes(tmp_path: Path):
    from PIL import Image

    frames = _frames(tmp_path, [0, 1100, 3000])
    Image.new("RGB", (320, 240), (20, 20, 20)).save(frames[1][0])  # A new screen at 1100.
    touches = [{"ms": 1000, "kind": "tap", "points": [(100, 100)], "ms_long": 0}]
    out = with_touches(frames, touches, [], tmp_path / "out")
    on_new = next(p for p, _ in out if int(p.stem.split("_")[1]) >= 1100)
    assert Image.open(on_new).convert("RGB").getpixel((100, 100)) == (20, 20, 20)


def test_a_button_label_stays_long_enough_to_read(tmp_path: Path):
    from PIL import Image

    frames = _frames(tmp_path, [0, 3000])
    touches = [{"ms": 1000, "kind": "press:home", "points": [], "ms_long": 80}]
    out = with_touches(frames, touches, [], tmp_path / "out")
    at_1800 = [p for p, _ in out if int(p.stem.split("_")[1]) <= 1800][-1]
    assert Image.open(at_1800).convert("RGB").getpixel((160, 216)) != (200, 200, 200)
