"""Made-up Home Assistant data for demos and tests.

The desktop build asks "Home Assistant" for calendar events and to-do items
through the API, and subscribes to the states the Controls tiles show. The
harness answers with these. Nothing here comes from a
real home: the names are invented, and every day looks the same, so runs
repeat exactly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

# (start hour, start minute, minutes long, title); hours in the home's time zone.
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

# The entities the Controls tiles show: the state and the attributes, as HA
# keeps them. The fan is unavailable, so a tile shows greyed out.
CONTROLS = {
    "light.desk_lamp": {"state": "on", "brightness": "153"},
    "media_player.office": {"state": "playing", "media_title": "Rain on a Tin Roof"},
    "scene.movie_night": {"state": "unknown"},
    "fan.desk": {"state": "unavailable"},
    "cover.blinds": {"state": "open", "current_position": "40"},
    "sensor.office_co2": {"state": "640", "unit_of_measurement": "ppm"},
    "sensor.office_temperature": {"state": "21.5", "unit_of_measurement": "°C"},
    "switch.kettle": {"state": "off"},
    "light.ceiling": {"state": "on", "brightness": "255"},
    "light.floor_lamp": {"state": "off"},
    "fan.ceiling": {"state": "on"},
}

# What a Controls action does to its entity's state.
FLIPS = {"on": "off", "off": "on", "playing": "paused", "paused": "playing"}


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

    entities: dict[str, dict[str, str]] = field(default_factory=lambda: {k: dict(v) for k, v in CONTROLS.items()})
    # Controls actions performed: (action, entity).
    controlled: list[tuple[str, str]] = field(default_factory=list)

    # HA actions to refuse, as HA does when an entity is gone or a call
    # fails: "calendar.get_events", "todo.get_items".
    failing: set[str] = field(default_factory=set)
    # The home's time zone (an IANA name): its days start at local midnight.
    zone: str = "UTC"

    def _at(self, day: date, hour: int = 0, minute: int = 0) -> int:
        """Epoch seconds of a local time on `day`."""
        return int(datetime.combine(day, time(hour, minute), ZoneInfo(self.zone)).timestamp())

    def _day_of(self, t: int) -> date:
        """The local date at epoch seconds `t`."""
        return datetime.fromtimestamp(t, ZoneInfo(self.zone)).date()

    def calendar(self, start: int, end: int) -> dict:
        """Events between two epoch seconds, in the shape the device wants."""
        rows: list[list] = []
        day = self._day_of(start)
        while self._at(day) < end:
            midnight, next_midnight = self._at(day), self._at(day + timedelta(days=1))
            if day.weekday() == 6 and start <= midnight < end:  # Sundays have an all-day event
                rows.append([midnight, next_midnight, 1, ALL_DAY])
            for hour, minute, length, title in DAY_EVENTS:
                t0 = self._at(day, hour, minute)
                if start <= t0 < end:
                    rows.append([t0, t0 + length * 60, 0, title])
            day += timedelta(days=1)
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
        today = self._day_of(now)
        return {"d": [[self._at(today + timedelta(days=d)), c, hi, lo, p, w] for d, c, hi, lo, p, w in WEATHER_DAYS]}

    def entity_value(self, entity: str, attribute: str | None) -> str | None:
        """An entity's state, or one of its attributes; None when HA has none."""
        values = self.entities.get(entity)
        if values is None:
            return None
        return values.get(attribute or "state")

    def control(self, action: str, entity: str) -> bool:
        """A Controls tap: changes the entity as HA would. False for an entity HA lacks."""
        values = self.entities.get(entity)
        if values is None:
            return False
        self.controlled.append((action, entity))
        domain, _, verb = action.partition(".")  # pragma: no mutate (an HA action has one dot)
        if domain == "scene" or domain == "script":
            values["state"] = "2026-01-01T19:00:00+00:00" if domain == "scene" else "off"
        elif verb in ("toggle", "media_play_pause"):
            values["state"] = FLIPS.get(values["state"], values["state"])
        elif verb in ("open_cover", "close_cover"):
            values["state"] = "open" if verb == "open_cover" else "closed"
            values["current_position"] = "100" if verb == "open_cover" else "0"
        return True

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
        if data.get("entity_id") in self.entities:
            return self.control(action, data["entity_id"]), None
        if action == "todo.update_item":
            return self.check(data.get("item", ""), data.get("status") == "completed"), None
        return True, None
