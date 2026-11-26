"""Screen tests of the Habitica module: the hero's stats from "HA", the
reactions they play, the Character app and its buttons.

The runner plays HA for the Habitica entities (HABITICA in demo_data.py,
prefix `demo_hero`): it sends their states when the device subscribes, and
records a button press. Nothing here talks to Habitica.
"""

from __future__ import annotations

from harness import expect

HP = "sensor.demo_hero_health"
LEVEL = "sensor.demo_hero_level"
INN = "switch.demo_hero_rest_in_the_inn"
POTION = "button.demo_hero_buy_a_health_potion"
REVIVE = "button.demo_hero_revive_from_death"


def _board(device):
    device.advance(2)
    device.tap(160, 100)
    device.get_by_text("More").tap()
    tile = device.get_by_role("tile", name="Character")
    if not tile.is_visible():
        w, h = device.screen_size()
        device.swipe(w * 3 // 4, h // 2, w // 4, h // 2)
    return tile


def _open_character(device):
    _board(device).tap()
    expect(device.get_by_role("app", "Character")).to_be_visible()


def test_the_sheet_shows_the_stats(device):
    tile = _board(device)
    expect(tile).to_have_value("Lv 12 · HP 42")
    tile.tap()
    expect(device.get_by_role("text", "Lv 12 · Healer")).to_have_value("93 gold")
    # HP rounds up; the max comes from the build (no sensor for it).
    expect(device.get_by_role("meter", "HP")).to_have_value("42 / 50")
    expect(device.get_by_role("meter", "XP")).to_have_value("380 / 520")
    expect(device.get_by_role("meter", "MP")).to_have_value("22 / 45")
    # Only the available buttons show.
    expect(device.get_by_role("button", "Buy potion")).to_be_visible()
    expect(device.get_by_role("button", "Allocate")).to_be_visible()
    expect(device.get_by_role("button", "Start my day")).to_be_hidden()
    expect(device.get_by_role("button", "Revive")).to_be_hidden()
    expect(device).to_match_screenshot("character")
    # The first values after the boot played nothing.
    assert device.state() not in ("level_up", "hurt", "fainted", "resting")


def test_the_potion_asks_first(device):
    _open_character(device)
    device.get_by_role("button", "Buy potion").tap()
    expect(device.get_by_role("text", "Buy a health potion for 25 gold?")).to_be_visible()
    assert not device.data.controlled
    expect(device).to_match_screenshot("potion")
    # Cancel asks nothing of HA.
    device.get_by_role("button", "Cancel").tap()
    expect(device.get_by_role("button", "Buy potion")).to_be_visible()
    assert not device.data.controlled
    # Buy presses the HA button.
    device.get_by_role("button", "Buy potion").tap()
    device.get_by_role("button", "Buy").tap()
    expect(device.get_by_role("button", "Buy potion")).to_be_visible()
    assert device.data.controlled == [("button.press", POTION)]
    # Other buttons press at once.
    device.get_by_role("button", "Allocate").tap()
    assert device.data.controlled[-1] == ("button.press", "button.demo_hero_allocate_all_stat_points")


def test_a_button_follows_its_availability(device):
    _open_character(device)
    expect(device.get_by_role("button", "Revive")).to_be_hidden()
    device.ha_state(REVIVE, "unknown")
    expect(device.get_by_role("button", "Revive")).to_be_visible()
    device.ha_state(POTION, "unavailable")
    expect(device.get_by_role("button", "Buy potion")).to_be_hidden()


def test_numbers_play_reactions(device):
    device.advance(2)
    device.ha_state(LEVEL, "13")
    expect(device).to_have_state("level_up")
    device.advance(4)
    device.ha_state(HP, "35")
    expect(device).to_have_state("hurt")
    device.advance(3)
    # The same number again plays nothing.
    device.ha_state(HP, "35")
    device.advance(0.5)
    assert device.state() != "hurt"
    # Under the threshold (1 HP): nothing.
    device.ha_state(HP, "34.5")
    device.advance(0.5)
    assert device.state() != "hurt"


def test_fainted_and_the_inn(device):
    device.advance(2)
    device.ha_state(INN, "on")
    expect(device).to_have_state("resting")
    device.ha_state(INN, "off")
    device.advance(0.5)
    assert device.state() != "resting"
    device.ha_state(HP, "0")
    expect(device).to_have_state(["hurt", "fainted"])
    expect(device).to_have_state("fainted", timeout=5)
    device.ha_state(HP, "50")
    device.advance(0.5)
    assert device.state() != "fainted"


def test_events_from_ha(device):
    device.advance(2)
    device.action("habitica_event", kind="drop", message="Found a Wolf egg!")
    expect(device).to_have_state("drop")
    expect(device.get_by_role("text", "Found a Wolf egg!")).to_be_visible()
    device.advance(8)
    device.action("habitica_event", kind="quest", message="Quest: 3 damage to the boss")
    expect(device.get_by_role("text", "Quest: 3 damage to the boss")).to_be_visible()
