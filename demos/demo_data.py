"""Made-up Home Assistant data for demos and tests.

The desktop build asks "Home Assistant" for calendar events, to-do items,
the weather and media players through the API. The harness answers with
these. Nothing here comes from a real home: the names are invented, and
every day looks the same, so runs repeat exactly.
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


# Media players in the device's room. Features: HA's MediaPlayerEntityFeature
# bits for pause, seek, volume set, previous, next, turn on and off, volume
# step, stop and play.
MEDIA_FEATURES = 1 | 2 | 4 | 16 | 32 | 128 | 256 | 1024 | 4096 | 16384
MEDIA_AREA = "living_room"
# (title, artist, album, seconds, cover file). Made-up music: no real songs.
MEDIA_TRACKS = [
    ("Paper Lanterns", "The Quiet Tides", "Harbor Lights", 214, "lanterns.png"),
    ("Morning Static", "Juniper Vale", "Low Signal", 187, "static.jpg"),
    ("Slow Orbit", "Copper Moth", "Night Shift", 251, "orbit.png"),
]


@dataclass
class Player:
    entity: str
    name: str
    state: str  # playing, paused, idle or off
    track: int = 0
    position: float = 0.0  # seconds, at `since`
    since: int = -1  # wall seconds; -1 until the first answer
    volume: float = 0.4
    features: int = MEDIA_FEATURES

    def at(self, now: int) -> float:
        if self.since < 0:
            self.since = now
        if self.state != "playing":
            return self.position
        return min(self.position + now - self.since, MEDIA_TRACKS[self.track][3])

    def hold(self, now: int) -> None:
        """Freeze the position now, before the state changes."""
        self.position = self.at(now)
        self.since = now


def _players() -> list[Player]:
    return [
        Player("media_player.living_room", "Living Room", "playing", track=0, position=63.0),
        Player("media_player.kitchen", "Kitchen", "paused", track=1, position=20.0, volume=0.25),
        Player("media_player.bedroom", "Bedroom", "off"),
    ]


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

    players: list[Player] = field(default_factory=_players)
    # Where the covers are served (the harness's cover server); "" for none.
    cover_base: str = ""

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

    def media(self, now: int) -> dict:
        """The players, in the shape the Media app's template makes."""
        rows = sorted((self._media_row(p, now) for p in self.players), key=lambda r: r[1])
        return {"a": MEDIA_AREA, "p": rows}

    def _media_row(self, p: Player, now: int) -> list:
        """[entity, name, state, title, artist, album, picture, duration,
        position, volume, features]; a player that is off has no media."""
        if p.state == "off":
            return [p.entity, p.name, p.state, "", "", "", "", None, None, None, p.features]
        title, artist, album, seconds, cover = MEDIA_TRACKS[p.track]
        picture = ""
        if self.cover_base:
            # HA's access token changes every five minutes; the cache key stays.
            picture = f"{self.cover_base}/cover/{cover}?token=t{now // 300}&cache={p.track}"
        return [p.entity, p.name, p.state, title, artist, album, picture, seconds, p.at(now), p.volume, p.features]

    def command(self, action: str, data: dict[str, str], now: int) -> bool:
        """A media_player action: the player changes as a real one would."""
        player = next((p for p in self.players if p.entity == data.get("entity_id")), None)
        if player is None:
            return False
        player.hold(now)
        service = action.removeprefix("media_player.")
        if service == "media_play_pause":
            service = "media_pause" if player.state == "playing" else "media_play"
        states = {"media_play": "playing", "turn_on": "playing", "media_pause": "paused", "media_stop": "idle"}
        if service in states:
            player.state = states[service]
        elif service in ("media_next_track", "media_previous_track"):
            step = 1 if service == "media_next_track" else len(MEDIA_TRACKS) - 1
            player.track = (player.track + step) % len(MEDIA_TRACKS)
            player.position = 0.0
        elif service == "media_seek":
            player.position = float(data.get("seek_position", 0))
        else:
            return self._volume(player, service, data)
        return True

    @staticmethod
    def _volume(player: Player, service: str, data: dict[str, str]) -> bool:
        if service == "volume_set":
            player.volume = round(float(data.get("volume_level", player.volume)), 2)
        elif service in ("volume_up", "volume_down"):
            step = 0.1 if service == "volume_up" else -0.1
            player.volume = round(min(1.0, max(0.0, player.volume + step)), 2)
        else:
            return False
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
        if action == "recorder.get_statistics" and data.get("statistic_ids") == "daruma.media_players":
            # The Media app's carrier: its template renders the players.
            return True, self.media(now)
        if action == "todo.get_items":
            return True, self.todo()
        if action.startswith("media_player."):
            return self.command(action, data, now), None
        if action == "weather.get_forecasts":
            return True, self.weather(data.get("type", "hourly"), now)
        if action == "todo.update_item":
            return self.check(data.get("item", ""), data.get("status") == "completed"), None
        return True, None


COVER_SIZE = 300


def _cover_lanterns(draw) -> None:
    # Dusk over water, three paper lanterns.
    for y in range(COVER_SIZE):
        k = y / COVER_SIZE
        draw.line([(0, y), (COVER_SIZE, y)], fill=(int(24 + 200 * k), int(32 + 100 * k), int(84 - 30 * k)))
    draw.rectangle([0, 220, COVER_SIZE, COVER_SIZE], fill=(18, 28, 56))
    for x, y, r in ((80, 110, 34), (170, 80, 26), (232, 140, 30)):
        draw.ellipse([x - r, y - r, x + r, y + r], fill=(252, 196, 92), outline=(150, 60, 30), width=5)
        draw.line([(x, y - r - 18), (x, y - r)], fill=(40, 30, 30), width=3)
        draw.ellipse([x - r // 2, 236, x + r // 2, 244], fill=(200, 140, 70))


def _cover_static(draw) -> None:
    # Teal and cream bands with a low sun.
    for i in range(10):
        color = (40, 140, 140) if i % 2 == 0 else (238, 226, 196)
        draw.rectangle([0, i * 30, COVER_SIZE, i * 30 + 30], fill=color)
    draw.ellipse([90, 150, 210, 270], fill=(232, 96, 64))


def _cover_orbit(draw) -> None:
    # A planet with a ring, and a few stars.
    draw.rectangle([0, 0, COVER_SIZE, COVER_SIZE], fill=(26, 18, 48))
    for x, y in ((30, 40), (250, 30), (270, 220), (60, 250), (150, 20), (210, 120)):
        draw.ellipse([x - 3, y - 3, x + 3, y + 3], fill=(240, 236, 255))
    draw.ellipse([95, 95, 205, 205], fill=(214, 120, 70))
    draw.ellipse([50, 130, 250, 170], outline=(250, 220, 160), width=6)


COVERS = {"lanterns.png": _cover_lanterns, "static.jpg": _cover_static, "orbit.png": _cover_orbit}


def cover(name: str) -> tuple[bytes, str] | None:
    """A made-up album cover by file name: (bytes, content type), or None."""
    import io

    from PIL import Image, ImageDraw

    art = COVERS.get(name)
    if art is None:
        return None
    image = Image.new("RGB", (COVER_SIZE, COVER_SIZE))
    art(ImageDraw.Draw(image))
    out = io.BytesIO()
    if name.endswith(".jpg"):
        image.save(out, "JPEG", quality=85)
        return out.getvalue(), "image/jpeg"
    image.save(out, "PNG")
    return out.getvalue(), "image/png"
