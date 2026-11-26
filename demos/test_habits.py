"""Screen tests of the Habits app: habits from a script, taps that score
them, and the replies.

The runner plays the script (script.demo_habits, HABITS in demo_data.py):
it answers {op: list} and {op: score} as the device's response templates
render them. The desktop build has the habitica module too, so the app
shows the hero's stats row, and a reply's numbers play reactions.
"""

from __future__ import annotations

from harness import expect

SCRIPT = "script.demo_habits"


def _board(device):
    device.advance(2)
    device.tap(160, 100)
    device.get_by_text("More").tap()
    tile = device.get_by_role("tile", name="Habits")
    while not tile.is_visible():
        w, h = device.screen_size()
        device.swipe(w * 3 // 4, h // 2, w // 4, h // 2)
    return tile


def _open_habits(device):
    _board(device).tap()
    expect(device.get_by_role("row", "Drink water")).to_be_visible()


def test_the_list_and_the_stats_row(device):
    tile = _board(device)
    # Today's net: water 3, stretch 1, doomscrolling -1.
    expect(tile).to_have_value("+3 today")
    tile.tap()
    expect(device.get_by_role("row", "Drink water")).to_have_value("+3 today")
    expect(device.get_by_role("row", "Late snack")).to_have_value("+1 -2 this week")
    expect(device.get_by_role("text", "Lv 12")).to_have_value("93")
    # A habit with one side has one button.
    expect(device.get_by_role("button", "Drink water +")).to_be_visible()
    expect(device.get_by_role("button", "Drink water -")).to_be_hidden()
    expect(device.get_by_role("button", "Late snack -")).to_be_visible()
    expect(device).to_match_screenshot("habits")
    # More rows below.
    w, h = device.screen_size()
    device.swipe(w // 2, h * 3 // 4, w // 2, h // 4)
    expect(device.get_by_role("row", "Doomscrolling")).to_have_value("-1 today")
    expect(device.get_by_role("button", "Doomscrolling +")).to_be_hidden()
    expect(device.get_by_role("row", "Take the stairs")).to_have_value("+9 this month")


def test_a_tap_scores(device):
    _open_habits(device)
    device.get_by_role("button", "Drink water +").tap()
    expect(device).to_have_state("habit_up")
    expect(device.get_by_role("row", "Drink water")).to_have_value("+4 today")
    assert device.data.scored == [("water", "up")]
    device.advance(2)
    device.get_by_role("button", "Late snack -").tap()
    expect(device).to_have_state("habit_down")
    expect(device.get_by_role("row", "Late snack")).to_have_value("+1 -3 this week")
    assert device.data.scored[-1] == ("snack", "down")


def test_a_reply_levels_up_and_drops(device):
    _open_habits(device)
    device.data.next_score = "R\t1\t1\t0\tYou found a Wolf Egg!\nS\t41.5\t50\t22.4\t45\t10\t540\t94\t13"
    device.get_by_role("button", "Stretch +").tap()
    expect(device).to_have_state("level_up")
    expect(device.get_by_role("text", "Lv 13")).to_be_visible()
    # The drop plays once the level up is over. Its words show in the app.
    expect(device).to_have_state("drop", timeout=6)
    expect(device.get_by_role("notice", "You found a Wolf Egg!")).to_be_visible()


def test_an_error_takes_the_score_back(device):
    _open_habits(device)
    device.data.failing.add(SCRIPT)
    device.get_by_role("button", "Drink water +").tap()
    expect(device.get_by_role("notice", "Couldn't score")).to_be_visible()
    expect(device.get_by_role("row", "Drink water")).to_have_value("+3 today")
    expect(device).to_match_screenshot("error")
    # A rate limit says Habitica is busy.
    device.advance(4)
    device.data.error = "Rate limit exceeded, try again later"
    device.get_by_role("button", "Drink water +").tap()
    expect(device.get_by_role("notice", "Habitica is busy")).to_be_visible()
    expect(device.get_by_role("row", "Drink water")).to_have_value("+3 today")
    # The notice goes away on its own.
    device.advance(4)
    expect(device.get_by_role("notice")).to_be_hidden()


def test_quest_progress_shows_in_the_notice_line(device):
    _open_habits(device)
    device.data.next_score = "R\t1\t0.5\t3.46\t"
    device.get_by_role("button", "Drink water +").tap()
    expect(device.get_by_role("notice", "Quest +3.5")).to_be_visible()
    # It goes away on its own.
    device.advance(6)
    expect(device.get_by_role("notice")).to_be_hidden()
