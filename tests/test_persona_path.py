"""DARUMA_PERSONA_PATH: persona folders outside this repository, for every tool.

A folder here is a made-up private repository: one package with a pixel
persona, "test_pup", drawn as the corgi. The tests check that each tool
finds it and keeps its pictures in the folder (demos/persona_path.py).
"""

import os
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace

import persona_frames
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "demos"))
import harness  # noqa: E402 - from demos/, put on the path above
import persona_path  # noqa: E402
import record  # noqa: E402

needs_personas = pytest.mark.skipif(bool(os.environ.get("DARUMA_SKIP_PERSONAS")), reason="DARUMA_SKIP_PERSONAS is set")

PACKAGE = """\
daruma_sprites:
  - id: test_pup
    name: Test pup
    pixel_art: { script: ../pixel/test_pup.py, persona: test_pup, goal: { done: test_pup_done } }
    theme: { frame: !secret not_read }
"""

SCRIPT = """\
from dataclasses import replace

from daruma_personas import corgi

PERSONA = replace(corgi.PERSONA, name="test_pup", layers=corgi.PERSONA.layers or corgi)
"""


@pytest.fixture
def folder(tmp_path) -> Path:
    root = tmp_path / "my-private"
    (root / "packages").mkdir(parents=True)
    (root / "pixel").mkdir()
    (root / "packages" / "persona_test_pup.yaml").write_text(PACKAGE)
    (root / "pixel" / "test_pup.py").write_text(SCRIPT)
    return root


def test_the_path_lists_folders_like_path(folder, tmp_path):
    other = tmp_path / "other"
    (other / "packages").mkdir(parents=True)
    found = persona_path.folders(os.pathsep.join([str(folder), "", str(other)]))
    assert [f.root for f in found] == [folder.resolve(), other.resolve()]
    assert persona_path.folders("") == []


def test_a_folder_needs_packages(tmp_path):
    with pytest.raises(ValueError, match="no packages/ folder"):
        persona_path.folders(str(tmp_path))


def test_the_pictures_go_where_daruma_keeps_its_own(folder, monkeypatch):
    monkeypatch.delenv(persona_path.GOLDEN_ENV, raising=False)
    monkeypatch.delenv(persona_path.DEMOS_ENV, raising=False)
    (f,) = persona_path.folders(str(folder))
    assert f.frame_golden == folder.resolve() / "tests" / "golden" / "frames"
    assert f.scenario_golden == folder.resolve() / "tests" / "golden"
    assert f.demos == folder.resolve() / "docs" / "demos"


def test_variables_move_the_pictures_inside_each_folder(folder, tmp_path, monkeypatch):
    monkeypatch.setenv(persona_path.GOLDEN_ENV, "art/golden")
    monkeypatch.setenv(persona_path.DEMOS_ENV, str(tmp_path / "site"))
    (f,) = persona_path.folders(str(folder))
    assert f.frame_golden == folder.resolve() / "art" / "golden" / "frames"
    assert f.demos == tmp_path / "site"


def test_personas_by_their_select_name(folder):
    found = persona_path.personas(persona_path.folders(str(folder)))
    assert found == {"Test pup": persona_path.Folder.at(folder.resolve())}


def test_pixel_personas_with_goal_stages_and_the_script_next_to_the_package(folder):
    found = persona_path.pixel_personas(persona_path.folders(str(folder)))
    assert [p.name for p in found] == ["test_pup", "test_pup_done"]
    assert {p.script for p in found} == {folder.resolve() / "pixel" / "test_pup.py"}


def test_the_desktop_build_includes_the_packages(folder, tmp_path):
    extra = persona_path.folders(str(folder))
    assert harness._build_name("standard", extra).endswith("-private")
    yaml_name, private = harness._write_config(tmp_path, "daruma-desktop-private", extra)
    text = (tmp_path / yaml_name).read_text()
    assert f"!include {folder.resolve() / 'packages' / 'persona_test_pup.yaml'}" in text
    assert private == {"Test pup": extra[0]}


def test_demos_of_a_folder_persona_go_to_its_folder(folder, tmp_path):
    (f,) = persona_path.folders(str(folder))
    build = SimpleNamespace(private_personas={"Test pup": f})

    def job(persona):
        return record.Job(build, None, persona, "standard", tmp_path / "work", tmp_path / "docs", 1, False, False)

    assert job("Test pup").demos() == f.demos
    assert job("Eyes").demos() == tmp_path / "docs"


@needs_personas
def test_frame_goldens_of_a_folder_persona_live_in_the_folder(folder, tmp_path, monkeypatch):
    monkeypatch.setenv(persona_path.ENV, str(folder))
    monkeypatch.setenv("DARUMA_WORK", str(tmp_path / "work"))
    monkeypatch.delenv(persona_path.GOLDEN_ENV, raising=False)
    assert "test_pup" in persona_frames.builds()
    assert persona_frames.main(["update", "test_pup"]) == 0
    golden = folder / "tests" / "golden" / "frames" / "test_pup"
    assert (golden / "persona.json").is_file()
    assert not (persona_frames.GOLDEN / "test_pup").exists()
    assert persona_frames.main(["check", "test_pup"]) == 0

    with Image.open(golden / "backdrop.png") as img:
        changed = img.convert("RGBA")
    changed.putpixel((0, 0), (1, 2, 3, 255))
    changed.save(golden / "backdrop.png")
    assert persona_frames.main(["check", "test_pup"]) == 1


def test_a_folder_persona_may_not_take_a_daruma_name(folder, monkeypatch):
    script = folder / "pixel" / "test_pup.py"
    script.write_text(SCRIPT.replace('name="test_pup"', 'name="corgi"'))
    (folder / "packages" / "persona_test_pup.yaml").write_text(PACKAGE.replace("persona: test_pup,", "persona: corgi,"))
    monkeypatch.setenv(persona_path.ENV, str(folder))
    with pytest.raises(ValueError, match="'corgi'"):
        persona_frames.builds()


@needs_personas
def test_the_preview_takes_a_module_and_a_name(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["personas", str(tmp_path), "daruma_personas.corgi:corgi"])
    runpy.run_module("daruma_pixel.personas", run_name="__main__")
    assert (tmp_path / "corgi" / "sheet.png").is_file()


def test_same_named_scripts_of_two_folders_stay_apart(tmp_path):
    scripts = []
    for name in ("a", "b"):
        script = tmp_path / name / "pixel" / "persona.py"
        script.parent.mkdir(parents=True)
        script.write_text(f"WHO = {name!r}\n")
        scripts.append(script)
    assert [persona_path.load_script(s).WHO for s in scripts] == ["a", "b"]
