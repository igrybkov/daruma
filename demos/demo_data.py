"""Made-up Home Assistant data for demos and tests.

The desktop build asks "Home Assistant" for calendar events and to-do items
through the API. The harness answers with these. Nothing here comes from a
real home: the names are invented, and every day looks the same, so runs
repeat exactly.
"""

from __future__ import annotations

from dataclasses import dataclass, field

DAY = 24 * 3600

# (start hour, start minute, minutes long, title); hours in the device's time zone (UTC).
DAY_EVENTS = [
    (9, 30, 15, "Team stand-up"),
    (11, 0, 60, "Design review"),
    (13, 0, 45, "Lunch with Sam"),
    (15, 30, 30, "Plant watering"),
    (17, 0, 60, "Pottery class"),
]
ALL_DAY = "Mom's birthday"

# The weather: a mild spring day that turns to showers in the afternoon.
# (hours from the start of the current hour, condition, °F, chance of rain %)
WEATHER_NOW = ("partlycloudy", 64.0, 8.0)  # condition, temperature, wind (mph)
WEATHER_HOURS = [
    (0, "partlycloudy", 64, 0),
    (1, "partlycloudy", 66, 0),
    (2, "cloudy", 67, 10),
    (3, "cloudy", 66, 30),
    (4, "rainy", 63, 60),
    (5, "pouring", 61, 80),
    (6, "rainy", 60, 50),
    (7, "cloudy", 58, 20),
    (8, "clear-night", 55, 0),
    (9, "clear-night", 53, 0),
    (10, "clear-night", 52, 0),
    (11, "clear-night", 51, 0),
]
# (days from today, condition, high, low, chance of rain %, wind mph)
WEATHER_DAYS = [(0, "rainy", 68, 49, 80, 12), (1, "sunny", 71, 50, 0, 6), (2, "partlycloudy", 69, 52, 10, 9)]


@dataclass
class Task:
    uid: str
    title: str
    done: bool = False
    flag: str = ""  # "f" flagged, "o" overdue, "d" due today


@dataclass
class DemoData:
    tasks: list[Task] = field(
        default_factory=lambda: [
            Task("t1", "Water the fern"),
            Task("t2", "Book the dentist", flag="d"),
            Task("t3", "Send the invoice", flag="o"),
            Task("t4", "Call the plumber", flag="f"),
            Task("t5", "Buy oat milk"),
            Task("t6", "Return library books", done=True),
        ]
    )

    # HA actions to refuse, as HA does when an entity is gone or a call
    # fails: "calendar.get_events", "todo.get_items".
    failing: set[str] = field(default_factory=set)

    def calendar(self, start: int, end: int) -> dict:
        """Events between two epoch seconds, in the shape the device wants."""
        rows: list[list] = []
        day = start - start % DAY
        while day < end:
            if day // DAY % 7 == 3 and start <= day < end:  # one day a week has an all-day event
                rows.append([day, day + DAY, 1, ALL_DAY])
            for hour, minute, length, title in DAY_EVENTS:
                t0 = day + hour * 3600 + minute * 60
                if start <= t0 < end:
                    rows.append([t0, t0 + length * 60, 0, title])
            day += DAY
        rows.sort(key=lambda r: r[0])
        return {"n": len(rows), "e": rows[:25]}

    def todo(self) -> dict:
        open_ = [t for t in self.tasks if not t.done]
        done = [t for t in self.tasks if t.done]
        rows = [[t.uid, t.title, "x" if t.done else t.flag] for t in open_ + done]
        return {"n": len(open_), "t": rows}

    def check(self, uid: str, done: bool) -> bool:
        for t in self.tasks:
            if t.uid == uid:
                t.done = done
                return True
        return False

    def weather(self, kind: str, now: int) -> dict:
        """weather.get_forecasts, in the shape the device's template makes."""
        if kind == "hourly":
            hour = now - now % 3600
            return {
                "u": "°F",
                "w": "mph",
                "c": WEATHER_NOW[0],
                "t": WEATHER_NOW[1],
                "ws": WEATHER_NOW[2],
                "h": [[hour + h * 3600, c, t, p] for h, c, t, p in WEATHER_HOURS],
            }
        day = now - now % DAY
        return {"d": [[day + d * DAY, c, hi, lo, p, w] for d, c, hi, lo, p, w in WEATHER_DAYS]}

    def reply(self, action: str, data: dict[str, str], now: int = 0) -> tuple[bool, dict | None]:
        """The reply to an HA action: refused when it is failing, else answer()."""
        if action in self.failing:
            return False, None
        return self.answer(action, data, now)

    def answer(self, action: str, data: dict[str, str], now: int = 0) -> tuple[bool, dict | None]:
        """Answer an HA action the device performs: (success, response)."""
        if action == "calendar.get_events":
            from datetime import datetime

            def epoch(text: str) -> int:
                return int(datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp())

            return True, self.calendar(epoch(data["start_date_time"]), epoch(data["end_date_time"]))
        if action in ("todo.get_items", "recorder.get_statistics"):
            return True, self.todo()
        if action == "weather.get_forecasts":
            return True, self.weather(data.get("type", "hourly"), now)
        if action == "todo.update_item":
            return self.check(data.get("item", ""), data.get("status") == "completed"), None
        return True, None
