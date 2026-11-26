"""Host test: `pixel_art: options` and the cache-key hook (daruma_sprites).

    uv run pytest tests/test_pixel_art_options.py

The options go to the module's build() and cache_inputs() as they are. Only
what cache_inputs() returns joins the drawn-persona cache key: a token in
the options never reaches the key, the cache file or the log.
"""

from __future__ import annotations

import hashlib
import logging
import sys

import esphome.config_validation as cv
import esphome_components  # noqa: F401
import pytest
from esphome.components import daruma_sprites as sprites
from esphome.core import CORE

TOKEN = "SECRET-TOKEN-1234"

# A pixel_art module with options: it counts its draws in a file next to it.
MODULE = """
from pathlib import Path

HERE = Path(__file__).parent


def cache_inputs(name, options, data_dir):
    with (HERE / "hook.log").open("a") as f:
        f.write(f"{name}|{data_dir}\\n")
    return [f"look:{options.get('look')}", 7]


def build(name, options, data_dir):
    with (HERE / "draws.log").open("a") as f:
        f.write("x")
    return {"name": name, "look": options.get("look"), "data_dir": str(data_dir)}
"""


@pytest.fixture
def config_dir(tmp_path, monkeypatch):
    """A loaded config in tmp_path, so CORE.data_dir is tmp_path/.esphome."""
    monkeypatch.delenv("ESPHOME_DATA_DIR", raising=False)
    CORE.reset()
    CORE.config_path = tmp_path / "device.yaml"
    sprites._build.cache_clear()
    yield tmp_path
    sprites._build.cache_clear()
    CORE.reset()
    sys.modules.pop("daruma_pixel_art_art", None)


@pytest.fixture
def script(config_dir):
    path = config_dir / "art" / "art.py"
    path.parent.mkdir()
    path.write_text(MODULE)
    return path


def draws(script) -> int:
    log = script.parent / "draws.log"
    return len(log.read_text()) if log.exists() else 0


def pickles(config_dir) -> list:
    return sorted((config_dir / ".esphome" / "daruma_pixel_art").glob("*.pickle"))


# --- schema -----------------------------------------------------------------


def test_schema_keeps_options_as_given():
    options = {"look": {"skin": "a"}, "token": TOKEN}
    conf = sprites.PIXEL_ART_SCHEMA({"module": "m", "persona": "p", "options": options})
    assert conf["options"] is options
    assert "options" not in sprites.PIXEL_ART_SCHEMA({"module": "m", "persona": "p"})


def test_schema_wants_a_mapping():
    with pytest.raises(cv.Invalid) as err:
        sprites.PIXEL_ART_SCHEMA({"module": "m", "persona": "p", "options": ["token"]})
    assert err.value.msg == "options must be a mapping"


def test_frozen():
    assert sprites._frozen(None) == ""
    assert sprites._frozen({"b": 1, "a": [2]}) == '{"a": [2], "b": 1}'
    assert sprites._frozen({}) == "{}"


# --- the cache key ----------------------------------------------------------


def test_without_extra_inputs_the_key_is_unchanged(script, config_dir):
    import PIL

    digest = hashlib.sha256()
    for path in sprites._script_sources(script):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    digest.update(f"p|{PIL.__version__}|{sys.version_info[:2]}".encode())
    want = config_dir / ".esphome" / "daruma_pixel_art" / f"p-{digest.hexdigest()[:24]}.pickle"
    assert sprites._cache_path(script, "p") == want
    assert sprites._cache_path(script, "p", []) == want


def test_extra_inputs_join_the_key_each_after_a_zero_byte(script, config_dir):
    import PIL

    digest = hashlib.sha256()
    for path in sprites._script_sources(script):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    digest.update(b"\0look:a")
    digest.update(b"\0sprite:1")
    digest.update(f"p|{PIL.__version__}|{sys.version_info[:2]}".encode())
    want = config_dir / ".esphome" / "daruma_pixel_art" / f"p-{digest.hexdigest()[:24]}.pickle"
    assert sprites._cache_path(script, "p", ["look:a", "sprite:1"]) == want


def test_extra_inputs_change_the_key(script):
    base = sprites._cache_path(script, "p")
    one = sprites._cache_path(script, "p", ["look:a"])
    assert one != base
    assert sprites._cache_path(script, "p", ["look:a"]) == one
    assert sprites._cache_path(script, "p", ["look:b"]) != one
    # Items are kept apart: two inputs are not their joined text.
    assert sprites._cache_path(script, "p", ["ab"]) != sprites._cache_path(script, "p", ["a", "b"])


def test_no_config_no_cache(script):
    CORE.reset()
    assert sprites._cache_path(script, "p") is None
    assert sprites._data_dir() is None


def test_data_dir(config_dir):
    assert sprites._data_dir() == config_dir / ".esphome"


def test_extra_inputs_from_the_hook(tmp_path):
    class WithHook:
        @staticmethod
        def cache_inputs(name, options, data_dir):
            return [name, options, data_dir, 3]

    assert sprites._extra_inputs(object(), "p", {"a": 1}, tmp_path) == []
    assert sprites._extra_inputs(WithHook, "p", {"a": 1}, tmp_path) == ["p", "{'a': 1}", str(tmp_path), "3"]
    assert sprites._extra_inputs(WithHook, "p", None, None) == ["p", "{}", "None", "3"]


# --- the build --------------------------------------------------------------


def test_build_hands_options_and_the_data_folder(script, config_dir):
    persona = sprites._build(script, "p", sprites._frozen({"look": "a", "token": TOKEN}))
    assert persona == {"name": "p", "look": "a", "data_dir": str(config_dir / ".esphome")}
    assert (script.parent / "hook.log").read_text() == f"p|{config_dir / '.esphome'}\n"


def test_the_token_never_reaches_the_cache_or_the_log(script, config_dir, caplog):
    with caplog.at_level(logging.DEBUG):
        sprites._build(script, "p", sprites._frozen({"look": "a", "token": TOKEN}))
    (cache,) = pickles(config_dir)
    assert TOKEN not in cache.name
    assert TOKEN.encode() not in cache.read_bytes()
    assert TOKEN not in caplog.text


def test_same_look_other_token_hits_the_cache(script, config_dir):
    sprites._build(script, "p", sprites._frozen({"look": "a", "token": TOKEN}))
    sprites._build.cache_clear()
    again = sprites._build(script, "p", sprites._frozen({"look": "a", "token": "another"}))
    assert again["look"] == "a"
    assert draws(script) == 1
    assert len(pickles(config_dir)) == 1


def test_other_look_draws_again(script, config_dir):
    sprites._build(script, "p", sprites._frozen({"look": "a"}))
    sprites._build.cache_clear()
    other = sprites._build(script, "p", sprites._frozen({"look": "b"}))
    assert other["look"] == "b"
    assert draws(script) == 2
    assert len(pickles(config_dir)) == 1  # The older drawing of the persona is gone.


def test_options_need_a_module_with_build():
    with pytest.raises(cv.Invalid) as err:
        sprites._draw(object(), "p", {"look": "a"})
    assert err.value.msg == "pixel_art options need a module with build(name, options=..., data_dir=...)"


def test_without_options_build_gets_the_name_only():
    class Plain:
        @staticmethod
        def build(name):
            return f"drew {name}"

    assert sprites._draw(Plain, "p") == "drew p"


# --- the config: options reach every goal stage ----------------------------

STAGED = """
from PIL import Image

from daruma_pixel.personas import Animation, Persona


def cache_inputs(name, options, data_dir):
    return [str(options.get("color"))]


def build(name, options, data_dir):
    color = options["color"]
    room = Image.new("RGBA", (4, 4), (color, 0, 0, 255))
    frame = Image.new("RGBA", (2, 2), (0, color, 0, 255) if name == "p" else (0, 0, color, 255))
    neutral = Animation([(frame, 100)])
    return Persona(background=color, backdrop=room, sprite_offset=(1, 1), animations={"Neutral": neutral})
"""


def test_from_script_hands_options_to_every_stage(config_dir):
    path = config_dir / "staged.py"
    path.write_text(STAGED)
    sys.modules.pop("daruma_pixel_art_staged", None)
    art = {"script": str(path), "persona": "p", "goal": {"done": "q"}, "options": {"color": 9, "token": TOKEN}}
    out = sprites._from_script({"pixel_art": art, "play_once": []})
    assert out["background"] == 9
    assert out["backdrop"].getpixel((0, 0)) == (9, 0, 0, 255)
    assert out["animations"]["Neutral"]["frames"][0]["image"].getpixel((0, 0)) == (0, 9, 0, 255)
    assert out["animations"]["Neutral:done"]["frames"][0]["image"].getpixel((0, 0)) == (0, 0, 9, 255)
    sys.modules.pop("daruma_pixel_art_staged", None)
