"""Tests of the scenario format and the GIF's touch marks. No device needed."""

from __future__ import annotations

from pathlib import Path

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
