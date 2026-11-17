"""Screen tests of the Media app: the players of the device's room, their
buttons, and the commands the device sends Home Assistant.

The runner answers as three made-up players (demo_data.py): Living Room
plays, Kitchen is paused, Bedroom is off. Sorted by name, Living Room is
the last of three. A button changes the player as a real one would, and the
runner serves the covers itself.
"""

from __future__ import annotations

import pytest
from harness import expect

LIVING_ROOM = "media_player.living_room"


def _open_media(device):
    device.run_action("menu.app:media")
    expect(device.get_by_role("app", "Media")).to_be_visible()
    # The app waits a few seconds after "HA" connects before it asks.
    expect(device.get_by_role("heading", "Living Room")).to_be_visible(timeout=10)


def test_media_shows_the_playing_player(device):
    _open_media(device)
    expect(device.get_by_role("text", "Paper Lanterns")).to_have_value("title")
    expect(device.get_by_role("text", "The Quiet Tides")).to_have_value("artist")
    expect(device.get_by_role("text", "Harbor Lights")).to_have_value("album")
    expect(device.get_by_role("button", "Pause")).to_be_visible()
    expect(device.get_by_role("pager", "Players")).to_have_value("3/3")
    expect(device.get_by_role("image", "cover")).to_have_value("loaded", timeout=10)
    # The position runs on between replies. The cover arrives in real time,
    # so wait for a fixed moment on the device's clock before the picture.
    device.advance(20 - device.now())
    expect(device.get_by_role("slider", "position")).to_have_value("1:21 / 3:34")
    expect(device).to_match_screenshot("media")


def test_media_pause_and_play(device):
    _open_media(device)
    device.get_by_role("button", "Pause").tap()
    expect(device).to_call_action("media_player.media_pause", entity_id=LIVING_ROOM)
    # The screen answers at once, and the replies after agree.
    expect(device.get_by_role("button", "Play")).to_be_visible()
    device.advance(6)
    expect(device.get_by_role("button", "Play")).to_be_visible()
    device.get_by_role("button", "Play").tap()
    expect(device).to_call_action("media_player.media_play", entity_id=LIVING_ROOM)
    expect(device.get_by_role("button", "Pause")).to_be_visible()


def test_media_next_track(device):
    _open_media(device)
    device.get_by_role("button", "Next").tap()
    expect(device).to_call_action("media_player.media_next_track", entity_id=LIVING_ROOM)
    expect(device.get_by_role("text", "Morning Static")).to_be_visible(timeout=3)
    device.get_by_role("button", "Previous").tap()
    expect(device).to_call_action("media_player.media_previous_track", entity_id=LIVING_ROOM)
    expect(device.get_by_role("text", "Paper Lanterns")).to_be_visible(timeout=3)


def test_media_volume(device):
    _open_media(device)
    device.get_by_role("button", "Louder").tap()
    expect(device).to_call_action("media_player.volume_set", entity_id=LIVING_ROOM, volume_level="0.45")
    # The volume shows in place of the position for a moment.
    expect(device.get_by_role("slider", "volume")).to_have_value("45%")
    device.get_by_role("button", "Quieter").tap()
    device.get_by_role("button", "Quieter").tap()
    expect(device).to_call_action("media_player.volume_set", entity_id=LIVING_ROOM, volume_level="0.35")
    expect(device.get_by_role("slider", "volume")).to_have_value("35%")
    device.advance(3)
    expect(device.get_by_role("slider", "position")).to_be_visible()


def test_media_seek(device):
    _open_media(device)
    x, y, w, h = device.get_by_role("slider", "position").bounding_box()
    device.tap(x + w // 2, y + h // 2)
    # The middle of the bar is the middle of the track (3:34), give or take
    # a pixel.
    seek = expect(device).to_call_action("media_player.media_seek", entity_id=LIVING_ROOM)
    position = int(seek.data["seek_position"])
    assert abs(position - 107) <= 1, position
    expect(device.get_by_role("slider", "position")).to_have_value(f"1:{position - 60} / 3:34")


def test_media_swipe_changes_player(device):
    _open_media(device)
    w, h = device.screen_size()
    # Left: the next player, around to the first.
    device.swipe(w * 3 // 4, h * 3 // 4, w // 4, h * 3 // 4)
    expect(device.get_by_role("heading", "Bedroom")).to_be_visible()
    expect(device.get_by_role("text", "Off")).to_be_visible()
    expect(device.get_by_role("pager", "Players")).to_have_value("1/3")
    expect(device.get_by_role("button", "Next")).to_have_value("disabled")
    # Off: the middle button turns it on.
    device.get_by_role("button", "Turn on").tap()
    expect(device).to_call_action("media_player.turn_on", entity_id="media_player.bedroom")
    # The pick stays, though another player plays.
    device.advance(6)
    expect(device.get_by_role("heading", "Bedroom")).to_be_visible()
    # A tap on the dots goes on to the next player.
    device.get_by_role("pager", "Players").tap()
    expect(device.get_by_role("heading", "Kitchen")).to_be_visible()
    expect(device.get_by_role("text", "Morning Static")).to_be_visible()
    expect(device.get_by_role("button", "Play")).to_be_visible()
    # Kitchen's cover is a JPEG.
    expect(device.get_by_role("image", "cover")).to_have_value("loaded", timeout=10)
    # Right: back.
    device.swipe(w // 4, h * 3 // 4, w * 3 // 4, h * 3 // 4)
    expect(device.get_by_role("heading", "Bedroom")).to_be_visible()


def test_media_actions_work_while_closed(device):
    # Before the first reply, a button waits for it.
    device.run_action("media.play_pause")
    expect(device).to_call_action("media_player.media_pause", entity_id=LIVING_ROOM, timeout=10)
    # After it, a button acts at once on the player that played.
    device.run_action("media.next")
    expect(device).to_call_action("media_player.media_next_track", entity_id=LIVING_ROOM)


def test_media_board_tile_shows_the_title(device):
    device.advance(8)
    device.tap(160, 100)
    device.get_by_text("More").tap()
    w, h = device.screen_size()
    device.swipe(w * 3 // 4, h // 2, w // 4, h // 2)
    expect(device.get_by_role("tile", "Media")).to_have_value("Paper Lanterns")


@pytest.mark.failing("recorder.get_statistics")
def test_media_retries_after_an_error(device):
    device.run_action("menu.app:media")
    error = device.get_by_role("text", "Can't load the players")
    expect(error).to_be_visible(timeout=10)
    device.data.failing.clear()
    error.tap()
    expect(device.get_by_role("heading", "Living Room")).to_be_visible()


def test_media_empty_room(device):
    device.data.players.clear()
    device.run_action("menu.app:media")
    expect(device.get_by_role("text", "No media players in this room")).to_be_visible(timeout=10)
    # The header keeps the app's name.
    expect(device.get_by_role("heading", "Media")).to_be_visible()
