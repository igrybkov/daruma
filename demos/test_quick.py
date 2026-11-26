"""Screen tests of the quick panel: a swipe down shows the Settings rows as
tiles, a tap flips one, and a swipe up closes it."""

from __future__ import annotations

from harness import expect


def _swipe_down(device):
    w, h = device.screen_size()
    device.swipe(w // 2, h // 6, w // 2, h * 2 // 3)


def test_tiles_follow_their_switches(device):
    device.advance(2)
    _swipe_down(device)
    panel = device.get_by_role("panel", "Quick settings")
    expect(panel).to_be_visible()
    sounds = device.get_by_role("switch", "Sounds")
    expect(sounds).to_have_value("on")
    expect(device.get_by_role("switch", "Mic mute")).to_have_value("off")
    expect(device).to_match_screenshot("panel")
    # A tap mutes the device, in HA too, and the panel stays open.
    sounds.tap()
    expect(sounds).to_have_value("off")
    expect(device).to_have_entity("Sounds", False)
    expect(panel).to_be_visible()
    # A change from HA shows without a tap.
    device.set("Sounds", True)
    expect(sounds).to_have_value("on")
    # A swipe up closes it.
    w, h = device.screen_size()
    device.swipe(w // 2, h * 2 // 3, w // 2, h // 6)
    expect(panel).to_be_hidden()


def test_a_tap_under_the_panel_closes_it(device):
    device.advance(2)
    _swipe_down(device)
    panel = device.get_by_role("panel", "Quick settings")
    expect(panel).to_be_visible()
    w, h = device.screen_size()
    device.tap(w // 2, h - 20)
    expect(panel).to_be_hidden()
    # That tap only closed the panel: no menu opened.
    expect(device.get_by_text("More")).to_be_hidden()


def test_a_swipe_down_closes_a_message_first(device):
    device.advance(2)
    device.show_message("Lunch is ready")
    expect(device.get_by_text("Lunch is ready")).to_be_visible()
    _swipe_down(device)
    expect(device.get_by_text("Lunch is ready")).to_be_hidden()
    expect(device.get_by_role("panel", "Quick settings")).to_be_hidden()
    # With the message gone, the next swipe opens the panel.
    _swipe_down(device)
    expect(device.get_by_role("panel", "Quick settings")).to_be_visible()
