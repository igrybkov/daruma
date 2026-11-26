"""Screen tests of the Character app's Skills: the list from the skills
script, the question before a cast, the task picker, and the cast.

The runner plays the script (script.demo_skills, SKILLS in demo_data.py):
it lists the skills of the hero's class, ready by its level and mana, and
records each cast. Nothing here talks to Habitica.
"""

from __future__ import annotations

from harness import expect

CLASS = "sensor.demo_hero_class"
LEVEL = "sensor.demo_hero_level"
MANA = "sensor.demo_hero_mana"


def _open_skills(device):
    device.advance(2)
    device.tap(160, 100)
    device.get_by_text("More").tap()
    tile = device.get_by_role("tile", name="Character")
    while not tile.is_visible():
        w, h = device.screen_size()
        device.swipe(w * 3 // 4, h // 2, w // 4, h // 2)
    tile.tap()
    device.get_by_role("button", "Skills").tap()


def _hero(device, cls, level, mana):
    device.advance(2)
    device.ha_state(CLASS, cls)
    device.ha_state(LEVEL, str(level))
    device.ha_state(MANA, str(mana))


def test_a_healers_skills(device):
    _open_skills(device)
    expect(device.get_by_role("skill", "Healing Light")).to_have_value("15 MP")
    expect(device.get_by_role("skill", "Searing Brightness")).to_have_value("15 MP")
    # Not ready: grey, with the reason.
    expect(device.get_by_role("skill", "Protective Aura")).to_have_value("Needs level 13")
    expect(device).to_match_screenshot("skills")


def test_each_class_lists_its_skills(device):
    _hero(device, "rogue", 14, 30)
    _open_skills(device)
    expect(device.get_by_role("skill", "Pickpocket")).to_have_value("10 MP")
    expect(device.get_by_role("skill", "Stealth")).to_have_value("Needs 45 MP")
    for cls, ready, waits in (
        ("wizard", "Burst of Flames", "Chilling Frost"),
        ("warrior", "Brutal Smash", "Defensive Stance"),
    ):
        device.ha_state(CLASS, cls)
        device.get_by_role("button", "Back").tap()
        device.get_by_role("button", "Skills").tap()
        expect(device.get_by_role("skill", ready)).to_have_value("10 MP")
        expect(device.get_by_role("skill", waits)).to_have_value("Needs 40 MP" if cls == "wizard" else "25 MP")


def test_a_self_skill_asks_then_casts(device):
    _open_skills(device)
    device.get_by_role("skill", "Healing Light").tap()
    expect(device.get_by_role("text", "Cast Healing Light for 15 MP?")).to_be_visible()
    expect(device).to_match_screenshot("ask")
    assert device.data.casts == []
    device.get_by_role("button", "Cast").tap()
    expect(device).to_have_state("cast")
    expect(device.get_by_role("notice", "Healing Light!")).to_be_visible()
    assert device.data.casts == [("heal", "")]
    # MP comes off at once: 22.4 - 15.
    device.get_by_role("button", "Back").tap()
    expect(device.get_by_role("meter", "MP")).to_have_value("7 / 45")


def test_cancel_casts_nothing(device):
    _open_skills(device)
    device.get_by_role("skill", "Healing Light").tap()
    device.get_by_role("button", "Cancel").tap()
    expect(device.get_by_role("skill", "Healing Light")).to_be_visible()
    assert device.data.casts == []


def test_a_party_skill_without_the_question(device):
    _hero(device, "warrior", 14, 40)
    device.set("Ask before a cast", False)
    _open_skills(device)
    device.get_by_role("skill", "Valorous Presence").tap()
    expect(device).to_have_state("cast")
    assert device.data.casts == [("valorous_presence", "")]


def test_a_task_skill_picks_a_habit(device):
    _hero(device, "warrior", 12, 40)
    _open_skills(device)
    device.get_by_role("skill", "Brutal Smash").tap()
    device.get_by_role("button", "Late snack").tap()
    expect(device).to_have_state("cast")
    assert device.data.casts == [("smash", "snack")]


def test_a_failed_cast_gives_the_mana_back(device):
    _open_skills(device)
    device.data.next_cast = "R\t0"
    device.get_by_role("skill", "Healing Light").tap()
    device.get_by_role("button", "Cast").tap()
    expect(device.get_by_role("notice", "Couldn't cast")).to_be_visible()
    device.get_by_role("button", "Back").tap()
    expect(device.get_by_role("meter", "MP")).to_have_value("22 / 45")


def test_a_nudge_card_answers_with_its_skill(device):
    # As "Daruma: Habitica nudges" shows one: an info card with the skill.
    device.advance(2)
    device.show_prompt(
        "habitica_evening_skill",
        title="Before the day ends",
        body="2 dailies are still open. Hide with Stealth?",
        options=["Stealth", "Not now"],
        style="info",
    )
    device.get_by_role("button", "Stealth").tap()
    expect(device).to_fire_event("esphome.daruma_prompt", id="habitica_evening_skill", choice="Stealth")


def test_a_nudge_waits_for_a_focus_block(device):
    device.advance(2)
    device.action("pomodoro_start", minutes=25)
    device.show_prompt(
        "habitica_allocate",
        title="Stat points",
        body="Allocate your stat points?",
        options=["Allocate", "Not now"],
        style="info",
    )
    device.advance(2)
    expect(device.get_by_role("button", "Allocate")).to_be_hidden()
