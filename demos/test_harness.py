"""Tests of the harness's time zones and the demo calendar. No device needed."""

from __future__ import annotations

import pytest
from demo_data import DemoData
from harness import EPOCH, TIMEZONE, DeviceError, utc_offset

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
