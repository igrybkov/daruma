"""Screen tests of the Controls app: live state from "HA", and taps that act.

The runner plays HA for the tiles' entities (CONTROLS in demo_data.py): it
sends their states when the device subscribes, and changes them when a tap
performs an action.
"""

from __future__ import annotations

from harness import expect


def _open_controls(device):
    device.advance(2)
    device.tap(160, 100)
    device.get_by_text("More").tap()
    tile = device.get_by_role("tile", name="Controls")
    if not tile.is_visible():
        w, h = device.screen_size()
        device.swipe(w * 3 // 4, h // 2, w // 4, h // 2)
    tile.tap()
    expect(device.get_by_role("app", "Controls")).to_be_visible()


def test_tiles_show_live_state(device):
    _open_controls(device)
    expect(device.get_by_role("control", "Desk lamp")).to_have_value("On · 60%")
    expect(device.get_by_role("control", "Music")).to_have_value("Rain on a Tin Roof")
    expect(device.get_by_role("control", "Fan")).to_have_value("Unavailable")
    expect(device).to_match_screenshot("controls")
    # A tap toggles the light; HA's new state comes back to the tile.
    device.get_by_role("control", "Desk lamp").tap()
    expect(device.get_by_role("control", "Desk lamp")).to_have_value("Off")
    assert ("light.toggle", "light.desk_lamp") in device.data.controlled
    # A tap on an unavailable tile does nothing.
    device.get_by_role("control", "Fan").tap()
    assert all(entity != "fan.desk" for _, entity in device.data.controlled)
    # The entity coming back lights the tile up.
    device.ha_state("fan.desk", "on")
    expect(device.get_by_role("control", "Fan")).to_have_value("On")


def test_scene_and_second_page(device):
    _open_controls(device)
    device.get_by_role("control", "Movie").tap()
    assert ("scene.turn_on", "scene.movie_night") in device.data.controlled
    # A check mark for a moment, then the tile as it was.
    movie = device.get_by_role("control", "Movie")
    expect(movie).to_have_value("done")
    device.advance(2)
    expect(movie).to_have_value("")
    # More tiles than fit: a swipe shows the next page.
    w, h = device.screen_size()
    device.swipe(w * 3 // 4, h // 2, w // 4, h // 2)
    co2 = device.get_by_role("control", "CO2")
    expect(co2).to_have_value("640 ppm")
    expect(device.get_by_role("control", "Office")).to_have_value("21.5°")
    # HA pushes a new value; the tile follows without a tap.
    device.ha_state("sensor.office_co2", "712.4")
    expect(co2).to_have_value("712.4 ppm")
    # The blinds close from part way open.
    device.get_by_role("control", "Blinds").tap()
    expect(device.get_by_role("control", "Blinds")).to_have_value("Closed")
