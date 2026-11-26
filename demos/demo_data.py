"""Made-up Home Assistant data for demos and tests.

The desktop build asks "Home Assistant" for calendar events and to-do items
through the API, and subscribes to the states the Controls tiles and the
Habitica module show. The
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
    "media_player.office": {
        "state": "playing",
        "media_title": "Rain on a Tin Roof",
        "media_artist": "Quiet Harbour",
        "volume_level": "0.35",
        # Pause, volume, previous, next and play.
        "supported_features": "16437",
    },
    "scene.movie_night": {"state": "unknown"},
    "fan.desk": {"state": "unavailable"},
    "cover.blinds": {"state": "open", "current_position": "40"},
    "sensor.office_co2": {"state": "640", "unit_of_measurement": "ppm"},
    "sensor.office_temperature": {"state": "21.5", "unit_of_measurement": "°C"},
    "switch.kettle": {"state": "off"},
    "light.ceiling": {"state": "on", "brightness": "255"},
    "light.floor_lamp": {"state": "off"},
    "fan.ceiling": {"state": "on", "percentage": "67", "percentage_step": "33.333333333333336"},
}

# A made-up Habitica hero, as the integration's entities show it (prefix
# `demo_hero`, the desktop build's `user`). The day has started and HP is
# up, so Start my day and Revive are unavailable. A button never pressed
# is "unknown"; one pressed holds the time it was.
HABITICA = {
    "sensor.demo_hero_health": {"state": "41.5"},
    "sensor.demo_hero_experience": {"state": "380"},
    "sensor.demo_hero_next_level": {"state": "520"},
    "sensor.demo_hero_mana": {"state": "22.4"},
    "sensor.demo_hero_max_mana": {"state": "45"},
    "sensor.demo_hero_level": {"state": "12"},
    "sensor.demo_hero_class": {"state": "healer"},
    "sensor.demo_hero_gold": {"state": "93.71"},
    "switch.demo_hero_rest_in_the_inn": {"state": "off"},
    "button.demo_hero_buy_a_health_potion": {"state": "unknown"},
    "button.demo_hero_start_my_day": {"state": "unavailable"},
    "button.demo_hero_revive_from_death": {"state": "unavailable"},
    "button.demo_hero_allocate_all_stat_points": {"state": "2026-01-05T08:12:00+00:00"},
}

# The tracks the demo player skips through.
TRACKS = ["Rain on a Tin Roof", "Lanterns at Dusk", "Paper Boats"]

# What a Controls action does to its entity's state.
FLIPS = {"on": "off", "off": "on", "playing": "paused", "paused": "playing"}


def _set_level_or_track(action: str, values: dict[str, str], data: dict[str, str]) -> None:
    """A level from a Controls panel, or a player's next or previous track."""
    if action == "light.turn_on":
        values["state"] = "on"
        values["brightness"] = str(round(int(data["brightness_pct"]) * 255 / 100))
    elif action == "fan.set_percentage":
        values["percentage"] = data["percentage"]
        values["state"] = "off" if data["percentage"] == "0" else "on"
    elif action == "media_player.volume_set":
        values["volume_level"] = data["volume_level"]
    elif action in ("media_player.media_next_track", "media_player.media_previous_track"):
        at = TRACKS.index(values["media_title"]) if values["media_title"] in TRACKS else 0
        step = 1 if action == "media_player.media_next_track" else -1
        values["media_title"] = TRACKS[(at + step) % len(TRACKS)]


@dataclass
class Task:
    uid: str
    title: str
    done: bool = False
    flag: str = ""  # "f" flagged, "o" overdue, "d" due today


# The habits the Habits app shows (script.demo_habits): id, title, up,
# down, value, count up, count down, period.
HABITS = [
    ("water", "Drink water", True, False, 6.2, 3, 0, "d"),
    ("stretch", "Stretch", True, False, 0.5, 1, 0, "d"),
    ("snack", "Late snack", True, True, -11.0, 1, 2, "w"),
    ("stairs", "Take the stairs", True, False, 12.0, 9, 0, "m"),
    ("scroll", "Doomscrolling", False, True, -22.0, 0, 1, "d"),
]
# The hero's sensors a score's reply carries, in the order of an S line
# without max HP.
HERO_STATS = ["health", "mana", "max_mana", "experience", "next_level", "gold", "level"]

# Each class's skills, as the skills script lists them: id, name, MP,
# level, target (s self, p party, t a task). Habitica's own numbers.
SKILLS = {
    "wizard": [
        ("fireball", "Burst of Flames", 10, 11, "t"),
        ("mpheal", "Ethereal Surge", 30, 12, "p"),
        ("earth", "Earthquake", 35, 13, "p"),
        ("frost", "Chilling Frost", 40, 14, "s"),
    ],
    "warrior": [
        ("smash", "Brutal Smash", 10, 11, "t"),
        ("defensive_stance", "Defensive Stance", 25, 12, "s"),
        ("valorous_presence", "Valorous Presence", 20, 13, "p"),
        ("intimidate", "Intimidating Gaze", 15, 14, "p"),
    ],
    "rogue": [
        ("pickpocket", "Pickpocket", 10, 11, "t"),
        ("backstab", "Backstab", 15, 12, "t"),
        ("tools_of_trade", "Tools of the Trade", 25, 13, "p"),
        ("stealth", "Stealth", 45, 14, "s"),
    ],
    "healer": [
        ("heal", "Healing Light", 15, 11, "s"),
        ("brightness", "Searing Brightness", 15, 12, "s"),
        ("protect_aura", "Protective Aura", 30, 13, "p"),
        ("heal_all", "Blessing", 25, 14, "p"),
    ],
}


@dataclass
class DemoHabit:
    id: str
    title: str
    up: bool
    down: bool
    value: float
    count_up: int
    count_down: int
    period: str

    def line(self) -> str:
        """The H line the device gets for it."""
        sides = f"{int(self.up)}\t{int(self.down)}"
        counts = f"{self.count_up}\t{self.count_down}"
        return f"H\t{self.id}\t{sides}\t{self.value}\t{counts}\t{self.period}\t{self.title}"

    def score(self, up: bool) -> None:
        if up:
            self.count_up += 1
            self.value += 0.5
        else:
            self.count_down += 1
            self.value -= 0.5


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

    entities: dict[str, dict[str, str]] = field(
        default_factory=lambda: {k: dict(v) for k, v in (CONTROLS | HABITICA).items()}
    )
    # Controls actions and Habitica button presses performed: (action, entity).
    controlled: list[tuple[str, str]] = field(default_factory=list)

    habits: list[DemoHabit] = field(default_factory=lambda: [DemoHabit(*h) for h in HABITS])
    # Scores the Habits app asked for: (habit id, direction).
    scored: list[tuple[str, str]] = field(default_factory=list)
    # What the next score answers, in the device's lines; None for an
    # ordinary reply with the hero's numbers.
    next_score: str | None = None
    # Casts the Skills list asked for: (skill id, task id or "").
    casts: list[tuple[str, str]] = field(default_factory=list)
    # What the next cast answers, in the device's lines; None for an
    # ordinary reply.
    next_cast: str | None = None

    # HA actions to refuse, as HA does when an entity is gone or a call
    # fails: "calendar.get_events", "todo.get_items".
    failing: set[str] = field(default_factory=set)
    # The error HA gives for a refused action.
    error: str = "demo: refused"
    # The home's time zone (an IANA name): its days start at local midnight.
    zone: str = "UTC"

    def _hero(self, name: str) -> float:
        return float(self.entity_value(f"sensor.demo_hero_{name}", None) or 0)

    def skills_reply(self, data: dict[str, str]) -> str:
        """The skills script, as the device's response template renders it."""
        if data.get("op") == "cast":
            return self._cast(data["id"], data.get("task", ""))
        cls = self.entity_value("sensor.demo_hero_class", None) or ""
        level, mp = self._hero("level"), self._hero("mana")
        rows = [f"C\t{cls}"]
        for sid, name, cost, need, target in SKILLS.get(cls, []):
            why = f"Needs level {need}" if level < need else (f"Needs {cost} MP" if mp < cost else "")
            rows.append(f"K\t{sid}\t{cost}\t{need}\t{target}\t{int(not why)}\t{name}\t{why}")
        return "\n".join(rows)

    def _cast(self, skill: str, task: str) -> str:
        self.casts.append((skill, task))
        reply, self.next_cast = self.next_cast, None
        return "R\t1" if reply is None else reply

    def habits_reply(self, data: dict[str, str]) -> str:
        """The habits script, as the device's response template renders it."""
        if data.get("op") == "score":
            return self._score(data["id"], data.get("direction", "up"))
        rows = [f"L\t{len(self.habits)}"]
        rows += [h.line() for h in self.habits]
        return "\n".join(rows)

    def _score(self, habit_id: str, direction: str) -> str:
        self.scored.append((habit_id, direction))
        reply, self.next_score = self.next_score, None
        if reply is not None:
            return reply
        for h in self.habits:
            if h.id == habit_id:
                h.score(direction == "up")
        hero = [self.entity_value(f"sensor.demo_hero_{k}", None) for k in HERO_STATS]
        hero.insert(1, "50")  # Max HP: no sensor.
        delta = "0.5" if direction == "up" else "-0.5"
        return f"R\t1\t{delta}\t0\t\nS\t" + "\t".join(v or "-1" for v in hero)

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

    def control(self, action: str, entity: str, data: dict[str, str] | None = None) -> bool:
        """A Controls tap: changes the entity as HA would. False for an entity HA lacks.
        `data` holds a level: brightness_pct for a light, percentage for a fan."""
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
        else:
            _set_level_or_track(action, values, data or {})
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
        if action == "script.demo_skills":
            return True, self.skills_reply(data)
        if action == "script.demo_habits":
            return True, self.habits_reply(data)
        if action == "weather.get_forecasts":
            return True, self.weather(data.get("type", "hourly"), now)
        if data.get("entity_id") in self.entities:
            return self.control(action, data["entity_id"], data), None
        if action == "todo.update_item":
            return self.check(data.get("item", ""), data.get("status") == "completed"), None
        return True, None
