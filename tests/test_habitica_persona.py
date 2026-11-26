"""Host test: the Habitica persona (pixel/persona-habitica): the look from
the API, the room, the posed layers and the build.

    uv run pytest tests/test_habitica_persona.py

The API is faked: no test reaches Habitica. The frames themselves are
pinned by the frame goldens (tests/golden/frames/habitica).
"""

from __future__ import annotations

import io
import json
import subprocess
import urllib.error
from dataclasses import replace
from pathlib import Path

import pytest
from PIL import Image

from daruma_personas import habitica
from daruma_personas.habitica import actor, api, compose, fixture, moods, room, sources
from daruma_personas.habitica.look import from_user
from daruma_pixel import effects, personas

ROOT = Path(__file__).resolve().parents[1]
TOKEN, USER_ID = "SECRET-TOKEN-5150", "SECRET-USER-ID-77"
USER = {"preferences": {"skin": "abc", "sleep": True}, "items": {"currentPet": "P-1"}, "stats": {"class": "mage"}}


class FakeHabitica:
    """The HTTP layer: records each request and answers with `reply`, or raises `error`."""

    def __init__(self, reply=None, error: Exception | None = None) -> None:
        self.reply = reply if reply is not None else {"success": True, "data": {**USER, "_id": "x", "auth": "y"}}
        self.error = error
        self.asked: list[tuple[str, dict]] = []

    def __call__(self, url, headers):
        self.asked.append((url, dict(headers)))
        if self.error is not None:
            raise self.error
        return json.dumps(self.reply).encode()


@pytest.fixture(autouse=True)
def habitica_api(monkeypatch):
    fake = FakeHabitica()
    monkeypatch.setattr(api, "http_get", fake)
    monkeypatch.setattr(habitica, "_users", {})
    return fake


def messages(caplog) -> list[str]:
    return [record.getMessage() for record in caplog.records]


# --- the API ------------------------------------------------------------------


def test_constants():
    assert api.USER_URL == "https://habitica.com/api/v3/user"
    assert api.USER_FIELDS == "preferences,items.gear,items.currentPet,items.currentMount,stats.class"
    assert api.LAST_LOOK == "last_look.json"


def test_fetch_user_sends_one_request_with_the_headers(habitica_api):
    user = api.fetch_user(USER_ID, TOKEN, habitica_api)
    assert user == USER  # Only the parts that make the look.
    (url, headers), *more = habitica_api.asked
    assert more == []
    assert url == f"{api.USER_URL}?userFields={api.USER_FIELDS}"
    assert headers == {"x-api-user": USER_ID, "x-api-key": TOKEN, "x-client": f"{USER_ID}-daruma"}


@pytest.mark.parametrize(
    "reply",
    [[], {"success": False, "data": USER}, {"success": True}, {"success": True, "data": []}],
    ids=["not a mapping", "no success", "no data", "data not a mapping"],
)
def test_fetch_user_wants_a_user(reply):
    with pytest.raises(ValueError, match="no user"):
        api.fetch_user(USER_ID, TOKEN, FakeHabitica(reply))


def test_user_from_api_saves_the_last_look(tmp_path, caplog):
    with caplog.at_level("DEBUG"):
        assert api.user_from_api(USER_ID, TOKEN, tmp_path) == USER
    saved = api.last_look_path(tmp_path)
    assert saved == tmp_path / "daruma_habitica" / "last_look.json"
    assert saved.read_text() == json.dumps(USER, sort_keys=True, indent=1)
    assert TOKEN not in saved.read_text() and USER_ID not in saved.read_text()
    assert TOKEN not in caplog.text and USER_ID not in caplog.text


def test_offline_uses_the_last_look(tmp_path, monkeypatch, caplog):
    api.save_last_look(tmp_path, {"preferences": {"skin": "old"}})
    monkeypatch.setattr(api, "http_get", FakeHabitica(error=urllib.error.URLError("offline")))
    with caplog.at_level("WARNING"):
        assert api.user_from_api(USER_ID, TOKEN, tmp_path) == {"preferences": {"skin": "old"}}
    assert messages(caplog) == ["habitica: could not read the look (URLError); using the last look"]


def test_an_odd_reply_uses_the_last_look(tmp_path, monkeypatch):
    api.save_last_look(tmp_path, {"preferences": {"skin": "old"}})
    monkeypatch.setattr(api, "http_get", FakeHabitica({"success": False}))
    assert api.user_from_api(USER_ID, TOKEN, tmp_path)["preferences"]["skin"] == "old"


def test_offline_without_a_last_look_stops_the_build(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "http_get", FakeHabitica(error=urllib.error.URLError("offline")))
    with pytest.raises(api.LookUnavailable) as err:
        api.user_from_api(USER_ID, TOKEN, tmp_path)
    assert str(err.value) == "habitica: could not read the look (URLError), and no last look is saved"
    assert TOKEN not in str(err.value)
    with pytest.raises(api.LookUnavailable):
        api.user_from_api(USER_ID, TOKEN, None)


def test_the_last_look_is_replaced_in_a_new_folder(tmp_path):
    data = tmp_path / "data" / "esphome"
    api.save_last_look(data, {"a": 1})
    api.save_last_look(data, {"a": 2})
    assert api.read_last_look(data) == {"a": 2}
    assert sorted(p.name for p in api.last_look_path(data).parent.iterdir()) == ["last_look.json"]


def test_no_data_folder_saves_nothing(tmp_path):
    api.save_last_look(None, USER)
    assert api.read_last_look(None) is None
    assert api.read_last_look(tmp_path) is None


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def test_http_get(monkeypatch):
    seen = []

    def urlopen(request, timeout):
        seen.append((request.full_url, request.header_items(), timeout))
        return Response(b"{}")

    monkeypatch.undo()
    monkeypatch.setattr(api.urllib.request, "urlopen", urlopen)
    assert api.http_get("https://x/y", {"x-api-user": "u"}) == b"{}"
    assert seen == [("https://x/y", [("X-api-user", "u")], sources.TIMEOUT)]


# --- options: which look ------------------------------------------------------


def test_a_pinned_look_wins_over_the_api(habitica_api):
    pinned = {"preferences": {"skin": "pinned"}}
    assert habitica.user_of({"look": pinned, "token": TOKEN, "user_id": USER_ID}, None) is pinned
    assert habitica_api.asked == []


def test_the_api_needs_both_token_and_user_id(habitica_api):
    assert habitica.user_of({"token": TOKEN}, None) is fixture.USER
    assert habitica.user_of({"user_id": USER_ID}, None) is fixture.USER
    assert habitica.user_of({"look": "not a mapping"}, None) is fixture.USER
    assert habitica_api.asked == []
    assert habitica.user_of({"token": TOKEN, "user_id": USER_ID}, None) == USER


def test_one_request_per_build(habitica_api, tmp_path):
    options = {"token": TOKEN, "user_id": USER_ID, "source": f"dir:{tmp_path}"}
    inputs = habitica.cache_inputs("habitica", options, tmp_path)
    habitica.layers_of(options, tmp_path)
    assert len(habitica_api.asked) == 1
    assert not any(TOKEN in item or USER_ID in item for item in inputs)
    other = {"token": "another", "user_id": USER_ID, "source": f"dir:{tmp_path}"}
    habitica.cache_inputs("habitica", other, tmp_path)
    assert len(habitica_api.asked) == 2


def test_the_look_leaves_out_sleep_and_buffs():
    user = {"preferences": {"sleep": True}, "stats": {"buffs": {"seafoam": True}}}
    look = habitica.look_of({"look": user})
    assert (look.sleep, look.buffs) == (False, frozenset())
    awake = habitica.cache_inputs("habitica", {"look": {"preferences": {"sleep": False}}}, None)
    assert habitica.cache_inputs("habitica", {"look": user}, None) == awake


# --- the room -----------------------------------------------------------------


def stripes(rows: list[tuple[int, int, int]], w: int = 47) -> Image.Image:
    img = Image.new("RGBA", (w, len(rows)))
    for y, color in enumerate(rows):
        img.paste((*color, 255), (0, y, w, y + 1))
    return img


SKY, HAZE, HILL, GRASS = (100, 150, 250), (120, 160, 240), (90, 170, 80), (80, 160, 60)


def test_side_colors_split_at_the_horizon():
    bg = stripes([SKY, HAZE, HILL, GRASS, GRASS])
    assert room.side_colors(bg) == [SKY, SKY, GRASS, GRASS, GRASS]


def test_side_colors_take_each_rows_most_common_color():
    bg = stripes([SKY] * 3)
    bg.paste((*GRASS, 255), (0, 1, 20, 2))  # Under half of the row.
    bg.paste((*GRASS, 255), (0, 2, 47, 3))
    assert room.side_colors(bg) == [SKY, SKY, GRASS]


def test_one_color_is_all_sky():
    assert room.side_colors(stripes([SKY] * 4)) == [SKY] * 4


def test_room_around_a_background():
    bg = stripes([SKY] * 20 + [GRASS] * 29)
    bg.putpixel((0, 1), (1, 2, 3, 255))
    out = room.room(bg)
    assert out.size == (room.W, room.H) == (64, 48)
    assert out.getpixel((8, 0)) == (1, 2, 3, 255)  # The top row is cut: row 1 is the room's row 0.
    assert out.getpixel((0, 18)) == (*SKY, 255) and out.getpixel((63, 19)) == (*GRASS, 255)
    assert out.getpixel((7, 0)) == (*SKY, 255) and out.getpixel((55, 47)) == (*GRASS, 255)


def test_room_without_a_background():
    out = room.room(None)
    assert out.getpixel((0, 0)) == (*room.SKY, 255) and out.getpixel((63, 31)) == (*room.SKY, 255)
    assert out.getpixel((0, 32)) == (*room.GROUND, 255)
    assert room.room(Image.new("RGBA", (47, 49))).tobytes() == out.tobytes()


# --- the layers ---------------------------------------------------------------


def layers_for(user) -> actor.Layers:
    return habitica.layers_of({"look": user}, None)


RIDING = {**fixture.USER, "items": {**fixture.USER["items"], "currentMount": fixture.MOUNT}}


def test_the_rider_and_book_follow_the_mount():
    standing, riding = habitica.FIXTURE_LAYERS, layers_for(RIDING)
    assert standing.body_at == (16, 7)
    assert riding.body_at == (16, -1)
    assert standing.PROPS == {"focus": [(27, 29, 35, 33)]}
    assert riding.PROPS == {"focus": [(27, 21, 35, 25)]}


def test_the_pet_clears_the_plaque():
    assert actor.PLAQUE_CLEAR == 17
    assert habitica.FIXTURE_LAYERS.pet_shift == 2  # The fixture's pet starts at room column 15.
    far = solid_pet(left=20)
    assert far.pet_shift == 0
    assert solid_pet(left=0).pet_shift == 9
    assert solid_pet(left=None).pet_shift == 0


def solid_pet(left: int | None) -> actor.Layers:
    awake = compose.Avatar(groups={g: Image.new("RGBA", compose.ART) for g in compose.GROUPS})
    if left is not None:
        awake.groups[compose.PET].putpixel((left, 40), (1, 1, 1, 255))
    return actor.Layers(lambda: actor.Avatars(awake, awake, mounted=False))


def test_a_pose_moves_the_rider_and_the_pet_apart():
    layers = habitica.FIXTURE_LAYERS
    rest = layers.foreground(actor.Pose())
    hop = layers.foreground(actor.Pose(dy=-2))
    rider_box, pet_box = (17, 0, 47, 40), (16, 40, 30, 48)
    assert hop.crop(pet_box).tobytes() == rest.crop(pet_box).tobytes()
    assert hop.crop(rider_box).getbbox() != rest.crop(rider_box).getbbox()
    pet_hop = layers.foreground(actor.Pose(pet_dy=-2))
    assert pet_hop.crop((0, 36, 64, 48)).tobytes() != rest.crop((0, 36, 64, 48)).tobytes()


def ring(img: Image.Image) -> int:
    """Pixels of the thinking dots' dark ring."""
    return sum(1 for y in range(img.height) for x in range(img.width) if img.getpixel((x, y))[:3] == effects.DOT_RING)


def test_effects_stay_on_screen_on_a_mount():
    thinking = moods.ANIMATIONS["Thinking"][0][0]
    plain = replace(thinking, extras=())
    for layers in (habitica.FIXTURE_LAYERS, layers_for(RIDING)):
        # Three dots of eight ring pixels each, all on screen.
        assert ring(layers.foreground(thinking)) - ring(layers.foreground(plain)) == 24


def test_scene_is_room_then_foreground():
    layers = habitica.FIXTURE_LAYERS
    pose = moods.ANIMATIONS["Petted"][0][0]
    want = layers.background()
    want.alpha_composite(layers.foreground(pose))
    assert layers.scene(pose).tobytes() == want.tobytes()
    assert layers.background() is not layers.background()  # A copy each time.
    assert layers.WINDOW is None


def test_without_a_sleep_skin_the_eyes_stay_open():
    look = from_user(fixture.USER)
    source = sources.MemorySource({k: v for k, v in fixture.pictures().items() if k != "skin_fixture_sleep"})
    both = habitica.avatars(look, source)
    assert both.asleep is both.awake
    full = habitica.avatars(look, fixture.source())
    assert full.asleep is not full.awake
    assert full.asleep.missing == [] and full.mounted is False
    assert habitica.avatars(replace(look, mount=fixture.MOUNT), fixture.source()).mounted is True


def test_zzz_is_not_fetched():
    assert {"zzz"} == habitica.NOT_DRAWN
    both = habitica.avatars(from_user(fixture.USER), fixture.source())
    assert both.asleep.groups[compose.ZZZ].getbbox() is None


# --- the build ----------------------------------------------------------------


def frames(persona) -> list[bytes]:
    out = [persona.backdrop.tobytes()]
    for anim in persona.animations.values():
        out += [img.tobytes() for img, _ in anim.frames]
        out += [img.tobytes() for img in (anim.blink, anim.wink) if img is not None]
    return out


def test_every_way_to_build_the_fixture_gives_the_same_persona():
    spec = personas.build("habitica")
    assert habitica.PERSONA.name == "habitica" and habitica.PERSONA.background == habitica.BACKGROUND == 0x609C4C
    assert frames(habitica.build("habitica")) == frames(spec)
    built = habitica.build("habitica", options={"source": "fixture"}, data_dir=None)
    assert frames(built) == frames(spec)
    assert built.sprite_offset == spec.sprite_offset and built.background == 0x609C4C


def test_the_build_names_the_persona_and_draws_a_pinned_look():
    riding = habitica.build("rider", options={"look": RIDING})
    assert frames(riding) != frames(personas.build("habitica"))
    assert set(riding.animations) == set(moods.ANIMATIONS)


def test_blinks_close_the_eyes_of_the_first_frame():
    assert set(moods.BLINKS) == {"Neutral", "Sad", "Thinking", "Talking", "Focus"}
    for name, pose in moods.BLINKS.items():
        assert pose == replace(moods.ANIMATIONS[name][0][0], eyes_closed=True)
    assert moods.WINKS == {}


def test_reactions_during_focus_keep_the_rider_and_the_book_still():
    for name in ("PettedFocus", "StartledFocus", "CelebrateFocus"):
        for pose, _ms in moods.ANIMATIONS[name]:
            assert (pose.dx, pose.dy, pose.book) == (0, 0, True), name


# --- licensing: no Habitica art in the repository -----------------------------


def tracked() -> list[str]:
    """The files git tracks here. Skips in a copy of the checkout, such as
    mutmut's mutants/, which git does not track."""
    top = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=ROOT, capture_output=True, text=True)
    if top.returncode or Path(top.stdout.strip()).resolve() != ROOT:
        pytest.skip("not a git checkout of its own")
    return subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()


SPRITE_PREFIXES = ("skin_", "hair_", "broad_", "slim_", "head_", "shield_", "weapon_", "Pet-", "Mount_", "background_")


def test_no_habitica_sprite_or_cache_is_committed():
    files = tracked()
    assert files, "git ls-files found nothing"
    cache = [f for f in files if sources.CACHE_FOLDER in Path(f).parts]
    assert cache == []
    pictures = [f for f in files if Path(f).suffix.lower() in (".png", ".gif")]
    sprites = [f for f in pictures if Path(f).name.startswith(SPRITE_PREFIXES) or Path(f).stem == "zzz"]
    assert sprites == []


def test_the_review_check_would_catch_a_sprite():
    assert Path("art/x/Pet-Wolf-Base.png").name.startswith(SPRITE_PREFIXES)
    assert sources.CACHE_FOLDER in Path("build/daruma_habitica/skin_a.png").parts
