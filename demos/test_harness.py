"""Tests of the harness: time zones, the demo calendar, and starting a device."""

from __future__ import annotations

import harness
import pytest
from demo_data import DemoData
from harness import EPOCH, TIMEZONE, Device, DeviceError, utc_offset

HOUR = 3600


@pytest.mark.parametrize(
    ("zone", "epoch", "offset"),
    [
        ("UTC", EPOCH, 0),
        # Daylight saving time in New York starts on 8 March 2026.
        ("America/New_York", EPOCH, -4 * HOUR),
        ("America/New_York", EPOCH - 4 * 24 * HOUR, -5 * HOUR),
        ("Australia/Sydney", EPOCH, 11 * HOUR),
    ],
)
def test_utc_offset_follows_the_zone_and_its_daylight_saving(zone, epoch, offset):
    assert utc_offset(zone, epoch) == offset


def test_utc_offset_refuses_an_unknown_zone():
    with pytest.raises(DeviceError, match="Nowhere/Land"):
        utc_offset("Nowhere/Land", EPOCH)


def test_the_default_start_is_10_am_in_the_default_zone():
    assert (EPOCH + utc_offset(TIMEZONE, EPOCH)) % (24 * HOUR) == 10 * HOUR


@pytest.mark.parametrize("zone", ["UTC", "America/New_York", "Australia/Sydney"])
def test_the_calendar_keeps_its_local_hours_in_any_zone(zone):
    morning = 1773223200  # Wednesday 11 March 2026, 10:00 UTC
    start = morning - utc_offset(zone, morning)  # 10:00 local time
    rows = DemoData(zone=zone).calendar(start, start + 6 * HOUR)["e"]
    local = [((t0 + utc_offset(zone, t0)) % (24 * HOUR) // 60, title) for t0, _, _, title in rows]
    assert local == [(11 * 60, "Design review"), (13 * 60, "Lunch with Sam"), (15 * 60 + 30, "Plant watering")]


def test_the_all_day_event_spans_a_local_sunday():
    data = DemoData(zone="America/Chicago")
    saturday_evening = 1794707970  # Saturday 14 November 2026, 19:59:30 in Chicago
    rows = data.calendar(saturday_evening, saturday_evening + 24 * HOUR)["e"]
    all_day = [r for r in rows if r[2] == 1]
    assert len(all_day) == 1
    start, end = all_day[0][:2]
    assert (start + utc_offset("America/Chicago", start)) % (24 * HOUR) == 0
    assert end - start == 24 * HOUR


def test_controls_entities_start_as_the_demos_show_them():
    data = DemoData()
    assert data.entity_value("light.desk_lamp", None) == "on"
    assert data.entity_value("light.desk_lamp", "brightness") == "153"
    assert data.entity_value("media_player.office", "media_title") == "Rain on a Tin Roof"
    assert data.entity_value("fan.desk", "") == "unavailable"
    assert data.entity_value("cover.blinds", "current_position") == "40"
    assert data.entity_value("sensor.office_co2", "unit_of_measurement") == "ppm"
    assert data.entity_value("sensor.office_temperature", None) == "21.5"
    assert data.entity_value("switch.kettle", None) == "off"
    # An attribute HA lacks, and an entity it lacks.
    assert data.entity_value("switch.kettle", "brightness") is None
    assert data.entity_value("light.nowhere", None) is None
    # Each run starts from the same states.
    data.entities["switch.kettle"]["state"] = "on"
    assert DemoData().entity_value("switch.kettle", None) == "off"


def test_habitica_entities_start_as_the_demos_show_them():
    data = DemoData()
    # The Controls entities are still there next to them.
    assert data.entity_value("light.desk_lamp", None) == "on"
    assert data.entity_value("sensor.demo_hero_health", None) == "41.5"
    assert data.entity_value("sensor.demo_hero_class", None) == "healer"
    assert data.entity_value("button.demo_hero_revive_from_death", None) == "unavailable"
    # A button press is recorded and changes nothing.
    assert data.answer("button.press", {"entity_id": "button.demo_hero_buy_a_health_potion"}) == (True, None)
    assert data.controlled == [("button.press", "button.demo_hero_buy_a_health_potion")]
    assert data.entity_value("button.demo_hero_buy_a_health_potion", None) == "unknown"


def test_the_habits_script_lists_in_the_device_lines():
    ok, text = DemoData().answer("script.demo_habits", {"op": "list"})
    lines = text.split("\n")
    assert ok and lines[0] == "L\t5" and len(lines) == 6
    assert lines[1] == "H\twater\t1\t0\t6.2\t3\t0\td\tDrink water"
    assert lines[3] == "H\tsnack\t1\t1\t-11.0\t1\t2\tw\tLate snack"
    assert lines[5] == "H\tscroll\t0\t1\t-22.0\t0\t1\td\tDoomscrolling"


def test_a_habit_score_counts_and_answers_with_the_hero():
    data = DemoData()
    ok, text = data.answer("script.demo_habits", {"op": "score", "id": "snack", "direction": "down"})
    assert ok and text == "R\t1\t-0.5\t0\t\nS\t41.5\t50\t22.4\t45\t380\t520\t93.71\t12"
    snack = data.habits[2]
    assert (snack.count_up, snack.count_down, snack.value) == (1, 3, -11.5)
    data.answer("script.demo_habits", {"op": "score", "id": "snack", "direction": "up"})
    assert (snack.count_up, snack.count_down, snack.value) == (2, 3, -11.0)
    assert data.answer("script.demo_habits", {"op": "score", "id": "water"})[1].startswith("R\t1\t0.5\t")
    assert data.scored == [("snack", "down"), ("snack", "up"), ("water", "up")]
    # A set answer goes once, and scores nothing.
    data.next_score = "R\t0\t0\t0\t"
    assert data.answer("script.demo_habits", {"op": "score", "id": "water", "direction": "up"})[1] == "R\t0\t0\t0\t"
    assert data.habits[0].count_up == 4 and data.next_score is None
    # A hero sensor HA lacks is -1.
    del data.entities["sensor.demo_hero_level"]
    assert data.answer("script.demo_habits", {"op": "score", "id": "x", "direction": "up"})[1].endswith("\t-1")


def test_the_skills_script_lists_the_heros_class():
    data = DemoData()
    ok, text = data.answer("script.demo_skills", {"op": "list"})
    assert ok and text.split("\n") == [
        "C\thealer",
        "K\theal\t15\t11\ts\t1\tHealing Light\t",
        "K\tbrightness\t15\t12\ts\t1\tSearing Brightness\t",
        "K\tprotect_aura\t30\t13\tp\t0\tProtective Aura\tNeeds level 13",
        "K\theal_all\t25\t14\tp\t0\tBlessing\tNeeds level 14",
    ]
    # Enough level but not enough mana.
    data.entities["sensor.demo_hero_level"]["state"] = "13"
    data.entities["sensor.demo_hero_class"]["state"] = "warrior"
    lines = data.answer("script.demo_skills", {"op": "list"})[1].split("\n")
    assert lines[2] == "K\tdefensive_stance\t25\t12\ts\t0\tDefensive Stance\tNeeds 25 MP"
    assert lines[3] == "K\tvalorous_presence\t20\t13\tp\t1\tValorous Presence\t"
    # A class it does not know: no skills. A sensor HA lacks reads 0.
    data.entities["sensor.demo_hero_class"]["state"] = "bard"
    assert data.answer("script.demo_skills", {"op": "list"})[1] == "C\tbard"
    del data.entities["sensor.demo_hero_level"]
    data.entities["sensor.demo_hero_class"]["state"] = "rogue"
    assert "\tNeeds level 11" in data.answer("script.demo_skills", {"op": "list"})[1]


def test_a_cast_is_recorded():
    data = DemoData()
    assert data.answer("script.demo_skills", {"op": "cast", "id": "smash", "task": "snack"}) == (True, "R\t1")
    assert data.answer("script.demo_skills", {"op": "cast", "id": "heal"}) == (True, "R\t1")
    data.next_cast = "R\t0"
    assert data.answer("script.demo_skills", {"op": "cast", "id": "heal", "task": ""})[1] == "R\t0"
    assert data.next_cast is None
    assert data.casts == [("smash", "snack"), ("heal", ""), ("heal", "")]


def test_a_refused_habits_script_says_why():
    data = DemoData(failing={"script.demo_habits"})
    assert data.reply("script.demo_habits", {"op": "list"}) == (False, None)
    assert data.error == "demo: refused"


@pytest.mark.parametrize(
    ("action", "entity", "values"),
    [
        ("light.toggle", "light.desk_lamp", {"state": "off", "brightness": "153"}),
        ("switch.toggle", "switch.kettle", {"state": "on"}),
        (
            "media_player.media_play_pause",
            "media_player.office",
            {
                "state": "paused",
                "media_title": "Rain on a Tin Roof",
                "media_artist": "Quiet Harbour",
                "volume_level": "0.35",
                "supported_features": "16437",
            },
        ),
        ("scene.turn_on", "scene.movie_night", {"state": "2026-01-01T19:00:00+00:00"}),
        ("cover.close_cover", "cover.blinds", {"state": "closed", "current_position": "0"}),
        ("cover.stop_cover", "cover.blinds", {"state": "open", "current_position": "40"}),
        ("fan.toggle", "fan.desk", {"state": "unavailable"}),
    ],
)
def test_a_controls_action_changes_its_entity(action, entity, values):
    data = DemoData()
    assert data.answer(action, {"entity_id": entity}) == (True, None)
    assert data.entities[entity] == values
    assert data.controlled == [(action, entity)]


def test_a_level_sets_brightness_and_speed():
    data = DemoData()
    assert data.answer("light.turn_on", {"entity_id": "light.floor_lamp", "brightness_pct": "40"}) == (True, None)
    assert data.entities["light.floor_lamp"] == {"state": "on", "brightness": "102"}
    data.control("light.turn_on", "light.floor_lamp", {"brightness_pct": "100"})
    assert data.entities["light.floor_lamp"]["brightness"] == "255"
    assert data.answer("fan.set_percentage", {"entity_id": "fan.ceiling", "percentage": "33"}) == (True, None)
    assert data.entities["fan.ceiling"]["percentage"] == "33"
    assert data.entities["fan.ceiling"]["state"] == "on"
    data.control("fan.set_percentage", "fan.ceiling", {"percentage": "0"})
    assert data.entities["fan.ceiling"]["state"] == "off"


def test_the_player_skips_tracks_and_sets_its_volume():
    data = DemoData()
    player = data.entities["media_player.office"]
    data.control("media_player.media_next_track", "media_player.office")
    assert player["media_title"] == "Lanterns at Dusk"
    data.control("media_player.media_next_track", "media_player.office")
    assert player["media_title"] == "Paper Boats"
    data.control("media_player.media_previous_track", "media_player.office")
    assert player["media_title"] == "Lanterns at Dusk"
    # Previous from the first track wraps around to the last.
    player["media_title"] = "Rain on a Tin Roof"
    data.control("media_player.media_previous_track", "media_player.office")
    assert player["media_title"] == "Paper Boats"
    player["media_title"] = "Something else"
    data.control("media_player.media_next_track", "media_player.office")
    assert player["media_title"] == "Lanterns at Dusk"
    data.control("media_player.volume_set", "media_player.office", {"volume_level": "0.75"})
    assert player["volume_level"] == "0.75"
    assert player["state"] == "playing"


def test_opening_a_cover_and_running_a_script():
    data = DemoData(entities={"cover.door": {"state": "closed"}, "script.night": {"state": "on"}})
    assert data.control("cover.open_cover", "cover.door")
    assert data.entities["cover.door"] == {"state": "open", "current_position": "100"}
    assert data.control("script.turn_on", "script.night")
    assert data.entities["script.night"] == {"state": "off"}
    # The music plays again after a pause.
    data.entities["media_player.x"] = {"state": "paused"}
    data.control("media_player.media_play_pause", "media_player.x")
    assert data.entities["media_player.x"]["state"] == "playing"


def test_an_action_on_an_entity_ha_lacks():
    data = DemoData()
    assert not data.control("light.toggle", "light.nowhere")
    assert data.controlled == []
    # answer() leaves it to the other actions: it does nothing.
    assert data.answer("light.toggle", {"entity_id": "light.nowhere"}) == (True, None)


def test_a_failed_start_stops_the_program(device_build, tmp_path, monkeypatch):
    started = []
    real_popen = harness.subprocess.Popen

    def popen(*args, **kwargs):
        started.append(real_popen(*args, **kwargs))
        return started[-1]

    monkeypatch.setattr(harness.subprocess, "Popen", popen)
    device = Device(device_build, tmp_path, persona="No such persona")
    with pytest.raises(DeviceError, match="No persona named"):
        device.start()
    assert len(started) == 1
    assert started[0].poll() is not None  # The program has ended.
