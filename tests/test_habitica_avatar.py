"""Host test: the Habitica avatar compositor (pixel/persona-habitica).

    uv run pytest tests/test_habitica_avatar.py

The layer order is checked against a stack written out by hand in
habiticalib's order. Sprites here are made up in the test or come from the
fixture. Nothing touches the network.
"""

from __future__ import annotations

import hashlib
import io
import urllib.error
from dataclasses import replace
from pathlib import Path

import pytest
from PIL import Image

from daruma_personas import habitica
from daruma_personas.habitica import compose, downscale, fixture, sources
from daruma_personas.habitica.compose import BACKGROUND, MOUNT_BODY, MOUNT_HEAD, PET, RIDER, ZZZ, Layer
from daruma_personas.habitica.look import Hair, Look, from_user

CLEAR = (0, 0, 0, 0)

FULL_USER = {
    "preferences": {
        "skin": "s1",
        "shirt": "sh1",
        "size": "broad",
        "chair": "c1",
        "background": "b1",
        "costume": False,
        "sleep": True,
        "hair": {"color": "h1", "base": 2, "bangs": 3, "mustache": 4, "beard": 5, "flower": 6},
    },
    "items": {
        "currentPet": "P-1",
        "currentMount": "M-1",
        "gear": {
            "equipped": {
                "back": "back_x",
                "armor": "armor_x",
                "body": "body_x",
                "eyewear": "eyewear_x",
                "head": "head_x",
                "headAccessory": "headAccessory_x",
                "shield": "shield_x",
                "weapon": "weapon_x",
            },
            "costume": {"armor": "armor_c", "head": "head_base_0", "weapon": "weapon_c"},
        },
    },
    "stats": {"class": "rogue", "buffs": {"seafoam": False}},
}


# --- Look -------------------------------------------------------------------


def test_look_reads_the_user_object():
    look = from_user(FULL_USER)
    assert (look.skin, look.shirt, look.size, look.chair, look.background) == ("s1", "sh1", "broad", "c1", "b1")
    assert (look.costume, look.sleep, look.pet, look.mount, look.klass) == (False, True, "P-1", "M-1", "rogue")
    assert look.hair == Hair(color="h1", base=2, bangs=3, mustache=4, beard=5, flower=6)
    assert look.equipped["armor"] == "armor_x"
    assert look.costume_gear == {"armor": "armor_c", "head": "head_base_0", "weapon": "weapon_c"}
    assert look.buffs == frozenset()


def test_defaults():
    look = Look()
    assert (look.skin, look.shirt, look.size, look.chair, look.background) == ("915533", "black", "slim", "none", "")
    assert (look.costume, look.sleep, look.pet, look.mount, look.klass) == (False, False, "", "", "warrior")
    assert look.hair == Hair(color="red", base=0, bangs=0, mustache=0, beard=0, flower=0)
    assert (look.equipped, look.costume_gear, look.buffs) == ({}, {}, frozenset())


def test_every_buff_is_read():
    buffs = {"seafoam": True, "shinySeed": True, "snowball": True, "spookySparkles": True}
    assert from_user({"stats": {"buffs": buffs}}).buffs == set(buffs)


def test_look_defaults_and_odd_values():
    look = from_user({"preferences": "nonsense", "items": {"gear": {"equipped": {"armor": "", "cape": "c"}}}})
    assert look == Look()
    assert look.equipped == {}  # Empty gear and unknown slots are dropped.
    assert from_user({"stats": {"buffs": {"snowball": 1, "other": True}}}).buffs == {"snowball"}
    assert from_user({"preferences": {"hair": {"bangs": None, "color": None}}}).hair == Hair()


def test_costume_picks_the_gear_on_show():
    look = from_user(FULL_USER)
    assert look.gear["weapon"] == "weapon_x"
    assert replace(look, costume=True).gear["weapon"] == "weapon_c"
    assert from_user({"preferences": {"costume": True}, "items": {"gear": {"costume": {"head": "h"}}}}).gear == {
        "head": "h"
    }


def test_canonical_is_stable_and_tells_looks_apart():
    a = from_user(FULL_USER)
    shuffled = dict(FULL_USER, items=dict(FULL_USER["items"]))
    shuffled["items"]["gear"] = {"equipped": dict(reversed(list(FULL_USER["items"]["gear"]["equipped"].items())))}
    shuffled["items"]["gear"]["costume"] = dict(reversed(list(FULL_USER["items"]["gear"]["costume"].items())))
    assert from_user(shuffled).canonical() == a.canonical()
    assert '"buffs":[]' in a.canonical()
    assert replace(a, buffs=frozenset({"snowball", "seafoam"})).canonical().count('"seafoam","snowball"') == 1
    assert replace(a, shirt="other").canonical() != a.canonical()
    assert replace(a, equipped={"armor": "armor_y"}).canonical() != a.canonical()
    assert replace(a, costume_gear={"armor": "armor_y"}).canonical() != a.canonical()


# --- plan: what goes where --------------------------------------------------


def messages(caplog) -> list[str]:
    return [record.getMessage() for record in caplog.records]


def names(layers: list[Layer]) -> list[str]:
    return [layer.sprite for layer in layers]


def test_plan_is_habiticalib_order():
    look = replace(from_user(FULL_USER), sleep=False)
    rider = (24, 0)  # On a mount.
    want = [
        Layer("background_b1", (0, 0), BACKGROUND),
        Layer("Mount_Body_M-1", (24, 18), MOUNT_BODY),
        *(
            Layer(name, rider, RIDER)
            for name in (
                "chair_c1",
                "back_x",
                "skin_s1",
                "broad_shirt_sh1",
                "head_0",
                "broad_armor_x",
                "hair_bangs_3_h1",
                "hair_base_2_h1",
                "hair_mustache_4_h1",
                "hair_beard_5_h1",
                "body_x",
                "eyewear_x",
                "head_x",
                "headAccessory_x",
                "hair_flower_6",
                "shield_x",
                "weapon_x",
            )
        ),
        Layer("Mount_Head_M-1", (24, 18), MOUNT_HEAD),
        Layer("Pet-P-1", (0, 48), PET),
    ]
    assert compose.plan(look) == want


def test_plan_asleep_uses_the_sleep_skin_and_zzz():
    layers = compose.plan(from_user(FULL_USER))
    assert "skin_s1_sleep" in names(layers) and "skin_s1" not in names(layers)
    i = names(layers).index("zzz")
    assert layers[i] == Layer("zzz", (24, 0), ZZZ)
    assert names(layers)[i - 1] == "weapon_x" and names(layers)[i + 1] == "Mount_Head_M-1"


def test_plan_without_mount_pet_or_background():
    look = Look(skin="a", shirt="b", equipped={"weapon": "w"})
    assert compose.plan(look) == [
        Layer("skin_a", (24, 24), RIDER),
        Layer("slim_shirt_b", (24, 24), RIDER),
        Layer("head_0", (24, 24), RIDER),
        Layer("w", (24, 24), RIDER),
    ]


def test_base_0_gear_is_skipped_in_every_slot():
    gear = {slot: f"{slot}_base_0" for slot in ("back", "armor", "body", "eyewear", "head", "headAccessory")}
    gear |= {"shield": "shield_base_0", "weapon": "weapon_base_0"}
    look = Look(equipped=gear)
    assert names(compose.plan(look)) == ["skin_915533", "slim_shirt_black", "head_0"]
    # Another slot's base_0 is real gear: only the slot's own counts as nothing.
    assert compose.gear_sprite(Look(equipped={"head": "armor_base_0"}), "head") == "armor_base_0"


def test_costume_replaces_equipped_gear():
    look = replace(from_user(FULL_USER), costume=True)
    got = names(compose.plan(look))
    assert "broad_armor_c" in got and "weapon_c" in got
    assert not any(name.endswith("_x") for name in got)  # No equipped gear at all.
    assert "head_base_0" not in got


def test_armor_and_shirt_come_slim_or_broad():
    look = Look(equipped={"armor": "armor_a"})
    assert {"slim_armor_a", "slim_shirt_black"} <= set(names(compose.plan(look)))
    broad = names(compose.plan(replace(look, size="broad")))
    assert {"broad_armor_a", "broad_shirt_black"} <= set(broad)
    assert compose.gear_sprite(look, "weapon") is None


def test_hair_parts_and_chair_only_when_set():
    look = Look(hair=Hair(color="c", bangs=1), chair="none")
    got = names(compose.plan(look))
    assert [n for n in got if n.startswith("hair_")] == ["hair_bangs_1_c"]
    assert not any(n.startswith("chair_") for n in got)
    assert names(compose.plan(replace(look, chair="")))[0] == "skin_915533"


def test_buff_branch_keeps_only_buffs_and_the_hair_flower():
    look = replace(
        from_user(FULL_USER), sleep=False, buffs=frozenset({"seafoam", "shinySeed", "snowball", "spookySparkles"})
    )
    rider = [layer for layer in compose.plan(look) if layer.group == RIDER]
    assert names(rider) == ["ghost", "avatar_snowball_rogue", "avatar_floral_rogue", "seafoam_star", "hair_flower_6"]
    assert {layer.at for layer in rider} == {(24, 0)}
    no_flower = replace(look, hair=Hair(), buffs=frozenset({"seafoam"}))
    assert names(compose.plan(no_flower))[2:3] == ["seafoam_star"]
    assert "hair_flower_0" not in names(compose.plan(no_flower))


@pytest.mark.parametrize(
    ("buff", "sprite"),
    [
        ("spookySparkles", "ghost"),
        ("snowball", "avatar_snowball_rogue"),
        ("shinySeed", "avatar_floral_rogue"),
        ("seafoam", "seafoam_star"),
    ],
)
def test_each_buff_alone(buff, sprite):
    look = Look(klass="rogue", buffs=frozenset({buff}), hair=Hair(flower=2))
    assert compose.buff_sprites(look) == [sprite, "hair_flower_2"]


def test_groups_back_to_front():
    assert compose.GROUPS == ("background", "mount_body", "rider", "zzz", "mount_head", "pet")
    assert compose.CANVAS == (141, 147) and compose.ART == (47, 49)


def test_mount_offset():
    assert compose.rider_offset(Look()) == (24, 24)
    assert compose.rider_offset(Look(mount="m")) == (24, 0)


# --- downscale --------------------------------------------------------------


def pixels(img: Image.Image) -> list:
    return [img.getpixel((x, y)) for y in range(img.height) for x in range(img.width)]


def blocks(grid: list[str], colors: dict[str, tuple[int, int, int, int]]) -> Image.Image:
    """A picture from rows of letters, one letter per screen pixel."""
    img = Image.new("RGBA", (len(grid[0]), len(grid)))
    img.putdata([colors[c] for row in grid for c in row])
    return img


RED, BLUE, SOFT, FAINT = (200, 0, 0, 255), (0, 0, 200, 255), (0, 200, 0, 128), (0, 200, 0, 127)
LETTERS = {".": CLEAR, "r": RED, "b": BLUE, "s": SOFT, "f": FAINT, "x": (9, 9, 9, 0)}


def test_on_grid_takes_one_pixel_per_block():
    img = Image.new("RGBA", (6, 3), CLEAR)
    img.paste(RED, (0, 0, 3, 3))
    img.paste((1, 2, 3, 200), (3, 0, 6, 3))
    got = downscale.reduce(img)
    assert got.image.size == (2, 1)
    assert pixels(got.image) == [RED, (1, 2, 3, 255)]  # Soft alpha comes out opaque.
    assert got.non_uniform == 0


def test_five_opaque_pixels_keep_a_block_and_four_do_not():
    five = blocks(["rrr", "rr.", "..."], LETTERS)
    four = blocks(["rrr", "r..", "..."], LETTERS)
    assert downscale.reduce(five).image.getpixel((0, 0)) == RED
    assert downscale.reduce(four).image.getpixel((0, 0)) == CLEAR
    assert downscale.reduce(five).non_uniform == 1


def test_alpha_below_128_is_see_through():
    soft = blocks(["sss", "ss.", "..."], LETTERS)
    faint = blocks(["fff", "ff.", "..."], LETTERS)
    assert downscale.reduce(soft).image.getpixel((0, 0)) == (0, 200, 0, 255)
    assert downscale.reduce(faint).image.getpixel((0, 0)) == CLEAR


def test_most_common_color_wins_and_ties_go_to_the_first():
    assert downscale.reduce(blocks(["rbb", "rbb", "r.."], LETTERS)).image.getpixel((0, 0)) == BLUE
    assert downscale.reduce(blocks(["brr", "rrb", "bb."], LETTERS)).image.getpixel((0, 0)) == BLUE
    assert downscale.reduce(blocks(["rbr", "brb", "..."], LETTERS)).image.getpixel((0, 0)) == RED
    assert downscale.reduce(blocks(["rb.", "br.", "..."], LETTERS)).image.getpixel((0, 0)) == CLEAR


def test_uniform_blocks():
    # See-through pixels count as one color, whatever their RGB.
    assert downscale.reduce(blocks(["x..", "...", "..x"], LETTERS)).non_uniform == 0
    assert downscale.reduce(blocks(["rrr", "rrr", "rrb"], LETTERS)).non_uniform == 1
    assert downscale.reduce(blocks(["rrr", "rrr", "rrf"], LETTERS)).non_uniform == 1


def test_counts_every_non_uniform_block():
    img = blocks(["rrr" + "r.." + "...", "rrr" + "..." + "...", "rrr" + "..." + "..b"], LETTERS)
    got = downscale.reduce(img)
    assert pixels(got.image) == [RED, CLEAR, CLEAR]
    assert got.non_uniform == 2


@pytest.mark.parametrize("size", [(4, 3), (3, 5)])
def test_size_must_be_whole_blocks(size):
    with pytest.raises(ValueError, match="3x3"):
        downscale.reduce(Image.new("RGBA", size))


def test_any_mode_is_read_as_rgba():
    got = downscale.reduce(Image.new("RGB", (3, 3), (5, 6, 7)))
    assert got.image.getpixel((0, 0)) == (5, 6, 7, 255)


# --- compose ----------------------------------------------------------------


def solid(w: int, h: int, color) -> Image.Image:
    return Image.new("RGBA", (w, h), color)


def test_any_size_at_its_offset():
    shield = solid(103, 90, CLEAR)
    shield.paste(RED, (99, 87, 102, 90))  # The last whole block, past the usual 90.
    mount = solid(105, 105, CLEAR)
    mount.paste(BLUE, (102, 0, 105, 3))
    src = sources.MemorySource({"shield_big": shield, "Mount_Body_m": mount})
    look = Look(mount="m", equipped={"shield": "shield_big"})
    avatar = compose.compose(look, src)
    # Shield at (24, 0): its block (99, 87) lands on art (41, 29).
    assert avatar.groups[RIDER].getpixel((41, 29)) == RED
    # Mount body at (24, 18): its block (102, 0) lands on art (42, 6).
    assert avatar.groups[MOUNT_BODY].getpixel((42, 6)) == BLUE
    assert avatar.groups[RIDER].getbbox() == (41, 29, 42, 30)


def test_sprites_past_the_canvas_are_cut():
    pet = solid(150, 120, RED)  # From (0, 48) it runs past both edges.
    avatar = compose.compose(Look(pet="p"), sources.MemorySource({"Pet-p": pet}))
    assert avatar.groups[PET].getbbox() == (0, 16, 47, 49)


def test_layers_stack_in_order_within_a_group():
    src = sources.MemorySource({"skin_a": solid(90, 90, RED), "slim_shirt_black": solid(90, 90, BLUE)})
    avatar = compose.compose(Look(skin="a"), src)
    assert avatar.groups[RIDER].getpixel((8, 8)) == BLUE  # The shirt is over the skin.
    assert avatar.groups[RIDER].getpixel((7, 8)) == CLEAR
    assert avatar.missing == ["head_0"]


def test_flat_stacks_groups_back_to_front():
    src = sources.MemorySource({"Pet-p": solid(81, 99, BLUE), "skin_a": solid(90, 90, RED)})
    avatar = compose.compose(Look(skin="a", pet="p"), src)
    assert avatar.flat().getpixel((10, 20)) == BLUE  # The pet is in front of the rider.
    assert avatar.flat(RIDER).getpixel((10, 20)) == RED
    assert avatar.flat(PET, RIDER).getpixel((10, 20)) == RED  # In the order asked.
    assert avatar.flat().getpixel((30, 1)) == CLEAR


def test_missing_sprite_warns_and_the_rest_is_drawn(caplog):
    src = sources.MemorySource({"skin_a": solid(90, 90, RED)})
    with caplog.at_level("WARNING", logger="daruma_personas.habitica.compose"):
        avatar = compose.compose(Look(skin="a"), src)
    assert avatar.missing == ["slim_shirt_black", "head_0"]
    assert messages(caplog) == [
        "habitica: no sprite slim_shirt_black; the avatar is drawn without it",
        "habitica: no sprite head_0; the avatar is drawn without it",
    ]
    assert avatar.groups[RIDER].getpixel((8, 8)) == RED
    assert avatar.non_uniform == {"skin_a": 0}


def test_off_grid_blocks_are_logged_per_sprite(caplog):
    skin = solid(90, 90, CLEAR)
    skin.paste(RED, (0, 0, 2, 3))  # 6 of 9: kept, and counted.
    src = sources.MemorySource({"skin_a": skin, "head_0": solid(90, 90, CLEAR)})
    with caplog.at_level("INFO", logger="daruma_personas.habitica.compose"):
        avatar = compose.compose(Look(skin="a"), src)
    assert avatar.non_uniform == {"skin_a": 1, "head_0": 0}
    assert messages(caplog) == [
        "habitica: skin_a has 1 blocks off the 3x grid",
        "habitica: no sprite slim_shirt_black; the avatar is drawn without it",
    ]


# --- sources ----------------------------------------------------------------


def test_constants():
    assert sources.ASSETS_URL == "https://habitica-assets.s3.amazonaws.com/mobileApp/images/"
    assert sources.CACHE_FOLDER == "daruma_habitica"
    assert sources.CLIENT == "daruma-habitica-persona"
    assert sources.TIMEOUT == 20


def png(color=RED, size=(3, 3)) -> bytes:
    out = io.BytesIO()
    solid(*size, color).save(out, "PNG")
    return out.getvalue()


def gif() -> bytes:
    frames = [Image.new("P", (3, 3), 1), Image.new("P", (3, 3), 2)]
    for frame in frames:
        frame.putpalette([0, 0, 0, 200, 0, 0, 0, 0, 200] + [0] * 759)
    out = io.BytesIO()
    frames[0].save(out, "GIF", save_all=True, append_images=frames[1:])
    return out.getvalue()


def test_safe_names():
    assert sources.safe_name("Pet-Wolf-Base") and sources.safe_name("skin_915533")
    for bad in ("../x", "a/b", "a.png", "", "a b"):
        assert not sources.safe_name(bad)


def test_dir_source(tmp_path):
    (tmp_path / "a.png").write_bytes(png())
    (tmp_path / "b.gif").write_bytes(gif())
    (tmp_path / "c.png").write_bytes(png(BLUE))
    (tmp_path / "c.gif").write_bytes(gif())
    src = sources.DirSource(tmp_path)
    assert src.fetch("a") == png()
    assert sources.load(src, "b").getpixel((0, 0)) == RED  # A GIF's first frame.
    assert src.fetch("c") == png(BLUE)  # PNG first.
    assert src.fetch("nope") is None
    (tmp_path / "x").mkdir()
    (tmp_path / "x" / "y.png").write_bytes(png())
    assert src.fetch("x/y") is None


def test_load_skips_odd_names(caplog):
    src = sources.MemorySource({"a": solid(3, 3, RED)})
    with caplog.at_level("WARNING", logger="daruma_personas.habitica.sources"):
        assert sources.load(src, "../a") is None
    assert messages(caplog) == ["habitica: skipped sprite with an odd name '../a'"]
    assert sources.load(src, "b") is None
    assert sources.load(src, "a").mode == "RGBA"


class FakeCdn:
    def __init__(self, files: dict[str, bytes] | None = None, error: Exception | None = None) -> None:
        self.files = files or {}
        self.error = error
        self.asked: list[str] = []

    def __call__(self, url: str) -> bytes | None:
        self.asked.append(url)
        if self.error is not None:
            raise self.error
        return self.files.get(url)


def test_cdn_downloads_once_into_its_folder(tmp_path):
    url = sources.ASSETS_URL + "skin_a.png"
    cdn = FakeCdn({url: png()})
    other = sources.ASSETS_URL + "head_0.png"
    cdn = FakeCdn({url: png(), other: png(BLUE)})
    folder = tmp_path / "data" / "cache"  # Made with its parents.
    src = sources.CdnSource(folder, get=cdn)
    assert src.fetch("skin_a") == png()
    assert (folder / "skin_a.png").read_bytes() == png()
    assert src.fetch("skin_a") == png()
    assert src.fetch("head_0") == png(BLUE)  # Into the folder that is there now.
    assert cdn.asked == [url, other]
    assert sorted(p.name for p in folder.iterdir()) == ["head_0.png", "skin_a.png"]


def test_cdn_offline_uses_a_warm_cache(tmp_path):
    (tmp_path / "skin_a.png").write_bytes(png(BLUE))
    src = sources.CdnSource(tmp_path, get=FakeCdn(error=urllib.error.URLError("offline")))
    assert src.fetch("skin_a") == png(BLUE)


def test_cdn_offline_and_cold_counts_as_missing(tmp_path, caplog):
    src = sources.CdnSource(tmp_path / "cache", get=FakeCdn(error=urllib.error.URLError("offline")))
    with caplog.at_level("WARNING", logger="daruma_personas.habitica.sources"):
        assert src.fetch("skin_a") is None
    assert messages(caplog) == ["habitica: could not download sprite skin_a: <urlopen error offline>"]
    assert not (tmp_path / "cache").exists()


def test_cdn_missing_sprite_writes_nothing(tmp_path):
    cdn = FakeCdn()
    src = sources.CdnSource(tmp_path / "cache", get=cdn)
    assert src.fetch("nope") is None
    assert src.fetch("../nope") is None
    assert cdn.asked == [sources.ASSETS_URL + "nope.png"]
    assert not (tmp_path / "cache").exists()


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def test_download(monkeypatch):
    seen = []

    def urlopen(request, timeout):
        seen.append((request.full_url, request.get_header("X-client"), request.get_header("User-agent"), timeout))
        if request.full_url.endswith("gone.png"):
            raise urllib.error.HTTPError(request.full_url, 404, "Not Found", {}, None)
        if request.full_url.endswith("denied.png"):
            raise urllib.error.HTTPError(request.full_url, 403, "Forbidden", {}, None)
        if request.full_url.endswith("broken.png"):
            raise urllib.error.HTTPError(request.full_url, 500, "Oops", {}, None)
        return Response(b"data")

    monkeypatch.setattr(sources.urllib.request, "urlopen", urlopen)
    assert sources.download("https://x/ok.png") == b"data"
    assert seen == [("https://x/ok.png", sources.CLIENT, sources.CLIENT, sources.TIMEOUT)]
    assert sources.download("https://x/gone.png") is None
    assert sources.download("https://x/denied.png") is None
    with pytest.raises(urllib.error.HTTPError):
        sources.download("https://x/broken.png")


def test_source_from(tmp_path):
    marker = sources.MemorySource({})
    assert sources.source_from("fixture", None, lambda: marker) is marker
    cdn = sources.source_from("cdn", tmp_path, lambda: marker)
    assert isinstance(cdn, sources.CdnSource) and cdn.folder == tmp_path / "daruma_habitica"
    folder = sources.source_from(f"dir:{tmp_path}", None, lambda: marker)
    assert isinstance(folder, sources.DirSource) and folder.folder == tmp_path
    home = sources.source_from("dir:~/sprites", None, lambda: marker)
    assert home.folder == Path.home() / "sprites"
    with pytest.raises(ValueError, match="data folder"):
        sources.source_from("cdn", None, lambda: marker)
    with pytest.raises(ValueError, match="not fixture"):
        sources.source_from("web", None, lambda: marker)


# --- fixture ----------------------------------------------------------------

# Every fixture picture, pinned: a change to the drawing shows here first.
# After a change you meant, look at the pictures, then update the hashes.
FIXTURE_HASHES = {
    "background_fixture_meadow": "59b627be33c95086",
    "skin_fixture": "4dafdcd115e5d20a",
    "skin_fixture_sleep": "f9011a0798507768",
    "slim_shirt_fixture": "0c9ff2b0ffb45f35",
    "broad_shirt_fixture": "85268d5de3799251",
    "head_0": "679c5a422b98d7cf",
    "slim_armor_fixture_1": "ef0040e9136388dd",
    "broad_armor_fixture_1": "d9d053402f2c6f10",
    "hair_bangs_1_fixture": "5d84df2d195faa41",
    "hair_base_1_fixture": "0e79238a655c3b7d",
    "head_fixture_1": "30b8421f6e46e6f1",
    "weapon_fixture_1": "413c0dbf0703792f",
    "zzz": "6f0ed06fc46a360c",
    "Pet-Fixture-Blob": "b7ba2dcc8786e763",
    "Mount_Body_Fixture-Pony": "cccd8392108d067f",
    "Mount_Head_Fixture-Pony": "a35c3bf1e4eb67b4",
}


def picture_hash(img: Image.Image) -> str:
    return hashlib.sha256(f"{img.mode}{img.size}".encode() + img.tobytes()).hexdigest()[:16]


def test_fixture_pictures_are_pinned():
    assert {name: picture_hash(img) for name, img in fixture.pictures().items()} == FIXTURE_HASHES


def test_fixture_sizes_are_habiticas():
    sizes = {name: img.size for name, img in fixture.pictures().items()}
    assert sizes["background_fixture_meadow"] == (141, 147)
    assert sizes["Pet-Fixture-Blob"] == (81, 99)
    assert sizes[f"Mount_Body_{fixture.MOUNT}"] == sizes[f"Mount_Head_{fixture.MOUNT}"] == (135, 135)
    assert sizes["zzz"] == (40, 40)
    assert sizes["skin_fixture"] == (90, 90)


@pytest.mark.parametrize(
    "change",
    [{}, {"sleep": True}, {"mount": fixture.MOUNT}, {"size": "broad"}],
    ids=["plain", "asleep", "mounted", "broad"],
)
def test_fixture_look_has_every_sprite(change):
    look = replace(from_user(fixture.USER), **change)
    avatar = compose.compose(look, fixture.source())
    assert avatar.missing == []
    assert avatar.groups[RIDER].getbbox() is not None


def test_fixture_has_pieces_off_the_grid():
    avatar = compose.compose(replace(from_user(fixture.USER), sleep=True), fixture.source())
    off = {name: n for name, n in avatar.non_uniform.items() if n}
    assert off == {"hair_bangs_1_fixture": 4, "head_fixture_1": 10, "weapon_fixture_1": 28, "zzz": 28}


def test_fixture_reduces_to_art_pixels():
    avatar = compose.compose(from_user(fixture.USER), fixture.source())
    flat = avatar.flat()
    assert flat.size == (47, 49)
    assert {px[3] for px in pixels(flat)} == {255}  # The meadow fills it all.
    rider = avatar.groups[RIDER]
    # The figure is about 12 by 19 art pixels, plus its sword.
    assert rider.getbbox() == (17, 15, 31, 37)
    assert rider.getpixel((21, 24)) == (*fixture.EYE, 255)


def test_memory_source_round_trips():
    src = fixture.source()
    img = Image.open(io.BytesIO(src.fetch("skin_fixture"))).convert("RGBA")
    assert img.tobytes() == fixture.pictures()["skin_fixture"].tobytes()
    assert src.fetch("skin_other") is None


# --- the module: options and cache inputs ------------------------------------


def test_look_of_takes_a_pin_or_the_fixture():
    assert habitica.look_of({}) == from_user(fixture.USER)
    assert habitica.look_of({"look": "not a mapping"}) == from_user(fixture.USER)
    assert habitica.look_of({"look": {"preferences": {"skin": "z"}}}).skin == "z"


def test_sprite_names_include_the_sleeping_look_once():
    got = habitica.sprite_names(from_user(fixture.USER))
    assert got[:2] == ["background_fixture_meadow", "skin_fixture"]
    assert "skin_fixture_sleep" in got and "zzz" in got
    assert len(got) == len(set(got))


def test_cache_inputs_hash_the_look_and_sprites_not_the_token():
    plain = habitica.cache_inputs("habitica", {}, None)
    with_token = habitica.cache_inputs("habitica", {"token": "SECRET-TOKEN", "user_id": "SECRET-ID"}, None)
    assert with_token == plain
    assert not any("SECRET" in item for item in with_token)
    assert plain[0] == "look:" + from_user(fixture.USER).canonical()
    skin = hashlib.sha256(fixture.source().fetch("skin_fixture")).hexdigest()
    assert f"skin_fixture:{skin}" in plain
    other = habitica.cache_inputs("habitica", {"look": {"preferences": {"skin": "z"}}}, None)
    assert other != plain
    assert "skin_z:missing" in other


def test_cache_inputs_follow_the_sprite_files(tmp_path):
    options = {"look": {"preferences": {"skin": "a"}}, "sprites": f"dir:{tmp_path}"}
    (tmp_path / "skin_a.png").write_bytes(png(RED))
    first = habitica.cache_inputs("habitica", options, None)
    (tmp_path / "skin_a.png").write_bytes(png(BLUE))
    assert habitica.cache_inputs("habitica", options, None) != first
    assert f"skin_a:{hashlib.sha256(png(BLUE)).hexdigest()}" in habitica.cache_inputs("habitica", options, None)


def test_cache_inputs_skip_odd_names():
    options = {"look": {"preferences": {"skin": "../etc"}}}
    assert "skin_../etc:missing" in habitica.cache_inputs("habitica", options, None)


def test_cdn_sprites_go_to_the_data_folder(tmp_path, monkeypatch):
    asked = []

    def fake(url):
        asked.append(url)
        return None

    monkeypatch.setattr(sources, "download", fake)
    habitica.cache_inputs("habitica", {"sprites": "cdn"}, tmp_path)
    assert asked and all(url.startswith(sources.ASSETS_URL) for url in asked)
    assert sources.ASSETS_URL + "skin_fixture.png" in asked
