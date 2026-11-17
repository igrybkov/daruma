"""Screen tests of the Calendar app: the agenda, the day view, and fetch errors.

The runner answers calendar.get_events with the same made-up day every day
(demo_data.py): five events, and an all-day one on one day of the week.
"""

from __future__ import annotations

import pytest
from harness import expect

# The text the app shows when "HA" refuses a fetch (text_error in
# packages/app_calendar.yaml).
ERROR = "Can't load the calendar"


def _open_calendar(device):
    device.advance(2)
    device.tap(160, 100)
    device.get_by_text("More").tap()
    device.get_by_role("tile", name="Calendar").tap()
    expect(device.get_by_role("app", "Calendar")).to_be_visible()


def test_agenda_day_opens_its_day_view(device):
    _open_calendar(device)
    # The agenda waits a few seconds after "HA" connects before it asks.
    expect(device.get_by_role("row", "Today")).to_be_visible(timeout=10)
    w, h = device.screen_size()
    device.swipe(w // 2, h * 3 // 4, w // 2, h // 3)
    # A tap on a day's heading opens that day.
    device.get_by_role("row", "Tomorrow").tap()
    expect(device.get_by_role("heading", "Tomorrow")).to_be_visible()
    expect(device.get_by_role("row", "Design review")).to_be_visible()
    device.advance(1)
    expect(device).to_match_screenshot("tomorrow")
    # The arrows move a day; today marks its next event.
    device.get_by_role("button", "Previous").tap()
    expect(device.get_by_role("heading", "Today")).to_be_visible()
    expect(device.get_by_role("row", "Design review")).to_have_value("next")
    # Swipes move a day too, and a tap on the label goes back to today.
    device.swipe(w * 3 // 4, h // 2, w // 4, h // 2)
    expect(device.get_by_role("heading", "Tomorrow")).to_be_visible()
    device.get_by_role("heading", "Tomorrow").tap()
    expect(device.get_by_role("heading", "Today")).to_be_visible()
    # Back goes to the agenda, scrolled as it was, then out of the app.
    device.press("home")
    expect(device.get_by_role("row", "Tomorrow")).to_be_visible()
    expect(device.get_by_role("heading", "Today")).to_be_hidden()
    device.press("home")
    expect(device.get_by_role("app", "Calendar")).to_be_hidden()


@pytest.mark.failing("calendar.get_events")
def test_calendar_retries_after_an_error(device):
    _open_calendar(device)
    error = device.get_by_role("text", ERROR)
    expect(error).to_be_visible(timeout=10)
    # "HA" answers again; a tap on the message asks at once.
    device.data.failing.clear()
    error.tap()
    expect(device.get_by_role("row", "Today")).to_be_visible()
    # A day outside the agenda is fetched on its own, and retried the same way.
    device.get_by_role("row", "Today").tap()
    device.data.failing.add("calendar.get_events")
    device.get_by_role("button", "Previous").tap()
    expect(device.get_by_role("heading", "Yesterday")).to_be_visible()
    expect(error).to_be_visible()
    device.data.failing.clear()
    error.tap()
    expect(device.get_by_role("row", "Team stand-up")).to_be_visible()
