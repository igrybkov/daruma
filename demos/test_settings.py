"""Screen tests of the Settings page: each row follows its switch, and a tap
flips it."""

from __future__ import annotations

from harness import expect


def _open_settings(device):
    device.advance(2)
    device.tap(160, 100)
    device.get_by_text("More").tap()
    tile = device.get_by_role("tile", name="Settings")
    if not tile.is_visible():
        w, h = device.screen_size()
        device.swipe(w * 3 // 4, h // 2, w // 4, h // 2)
    tile.tap()
    expect(device.get_by_role("app", "Settings")).to_be_visible()


def test_rows_follow_their_switches(device):
    _open_settings(device)
    sounds = device.get_by_role("switch", "Sounds")
    expect(sounds).to_have_value("on")
    expect(device.get_by_role("switch", "Do not disturb")).to_have_value("off")
    expect(device.get_by_role("switch", "Mic mute")).to_have_value("off")
    expect(device).to_match_screenshot("settings")
    # More rows than fit: a swipe up shows the rest.
    w, h = device.screen_size()
    device.swipe(w // 2, h * 3 // 4, w // 2, h // 4)
    expect(device.get_by_role("switch", "Temperature")).to_have_value("on")
    expect(device.get_by_role("switch", "Jokes")).to_have_value("on")
    device.swipe(w // 2, h // 4, w // 2, h * 3 // 4)
    # A tap turns Sounds off on the device and in HA.
    sounds.tap()
    expect(sounds).to_have_value("off")
    expect(device).to_have_entity("Sounds", False)
    # A change from HA shows without a tap.
    device.set("Sounds", True)
    expect(sounds).to_have_value("on")


def test_do_not_disturb_holds_sounds(device):
    _open_settings(device)
    sounds = device.get_by_role("switch", "Sounds")
    dnd = device.get_by_role("switch", "Do not disturb")
    dnd.tap()
    expect(dnd).to_have_value("on")
    # Do not disturb turns Sounds off for a while: the row says so.
    expect(sounds).to_have_value("held")
    expect(device).to_have_entity("Sounds", False)
    # It ends, and Sounds comes back as it was.
    dnd.tap()
    expect(dnd).to_have_value("off")
    expect(sounds).to_have_value("on")
