"""Screen tests of the quick panel: a swipe down from the top edge shows the
Settings rows as tiles, a tap flips one, and a swipe up closes it."""

from __future__ import annotations

from harness import expect


def _swipe_down(device):
    """From the top edge, as the panel wants."""
    w, h = device.screen_size()
    device.swipe(w // 2, 4, w // 2, h * 2 // 3)


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


def test_a_swipe_down_from_the_middle_opens_nothing(device):
    device.advance(2)
    w, h = device.screen_size()
    device.swipe(w // 2, h // 3, w // 2, h - 20)
    expect(device.get_by_role("panel", "Quick settings")).to_be_hidden()


def test_a_tap_closes_a_message(device):
    device.advance(2)
    device.show_message("Lunch is ready")
    bubble = device.get_by_text("Lunch is ready")
    expect(bubble).to_be_visible()
    w, h = device.screen_size()
    device.tap(w // 2, h // 3)
    expect(bubble).to_be_hidden()
    # That tap only closed the message: no menu opened.
    expect(device.get_by_text("More")).to_be_hidden()


def test_the_panel_opens_over_a_message(device):
    device.advance(2)
    device.show_message("Lunch is ready")
    _swipe_down(device)
    expect(device.get_by_role("panel", "Quick settings")).to_be_visible()


def test_do_not_disturb_holds_sounds(device):
    device.advance(2)
    _swipe_down(device)
    sounds = device.get_by_role("switch", "Sounds")
    dnd = device.get_by_role("switch", "Do not disturb")
    dnd.tap()
    expect(dnd).to_have_value("on")
    expect(sounds).to_have_value("held")
    # One page of tiles: a sideways swipe keeps the panel as it is.
    w, h = device.screen_size()
    device.swipe(w * 3 // 4, h // 4, w // 4, h // 4)
    device.swipe(w // 4, h // 4, w * 3 // 4, h // 4)
    expect(sounds).to_have_value("held")
    dnd.tap()
    expect(sounds).to_have_value("on")
