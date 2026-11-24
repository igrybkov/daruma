"""Random events: the conditions, the shape of an event and the device's
overrides.

Plain Python with no ESPHome imports, like registry.py, so the rules can be
tested on their own (tests/test_random_events.py). persona.py wraps them in
the persona schema; the hub's final validation runs the persona checks
(registry.resolve_random_events).

A persona declares its events by name:

    random_events:
      lick_paw: { animation: LickPaw, frequency: 9 }
      walk_q:   { say: ["Walk time?"], when: { between: "16:00-18:00", weekdays: [mon-fri] } }
      bathroom: { enter: WalkOff, animation: Away, exit: WalkBack, for: 3min, say: ["brb"] }

A one-shot plays `animation` once, or only says or sounds. A spell sets
`for`: `enter`, then `animation` looping for that long, then `exit`.

`when:` keys combine with AND; a list inside a key combines with OR. An
empty `when:` always holds. `at:` events roll only at their minutes, never
in the random rolls.

Encodings, shared with the engine (random_events.h):

    dates      `(from, to)`, `month*100 + day`, inclusive; `from > to` wraps the year
    weekdays   bit `(weekday - 1)`, Sunday = bit 0 (ESPHome `ESPTime::day_of_week`
               is 1 = Sunday); 0 = any day
    between    `(from, to)`, minute of day, end exclusive; `from > to` wraps
               midnight; end may be 1440
    at         a list of minutes of day, 0..1439: `const uint16_t *at; uint8_t
               at_count;` (0 = none), like `times`. Python: `When.at: tuple[int, ...]`
    moods      `StateId` values; plus `bool sleeping`. Python: state names,
               which the registry checks are moods
    frequency  1..10; `MEAN_S[f]` for random rolls, `AT_CHANCE[f]` for scheduled rolls
    key        FNV-1a of `"random_events/<persona id>/<event name>"`
    animation indices  the index in `daruma_sprites._animations(config)`; -1 = none

The engine holds both tables; these copies are for the tests.
"""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass

from .registry import RegistryError, check_name

_MIN, _HOUR, _DAY = 60, 3600, 86400
# frequency -> mean interval in seconds. Index 0 is unused.
MEAN_S = (0, 90 * _DAY, 30 * _DAY, 14 * _DAY, 7 * _DAY, 3 * _DAY, _DAY, 6 * _HOUR, 2 * _HOUR, 30 * _MIN, 10 * _MIN)
# frequency -> chance in percent at a scheduled roll. Index 0 is unused.
AT_CHANCE = (0, 1, 5, 15, 25, 40, 55, 70, 85, 95, 100)

DEFAULT_FREQUENCY = 8
DAYS = ("sun", "mon", "tue", "wed", "thu", "fri", "sat")

CONF_ANIMATION = "animation"
CONF_ENTER = "enter"
CONF_EXIT = "exit"
CONF_FOR = "for"
CONF_SAY = "say"
CONF_SOUND = "sound"
CONF_FREQUENCY = "frequency"
CONF_COOLDOWN = "cooldown"
CONF_WHEN = "when"
CONF_MOODS = "moods"

_DATE = re.compile(r"^(\d\d)-(\d\d)$")
_TIME = re.compile(r"^(\d\d):(\d\d)$")


@dataclass(frozen=True)
class When:
    dates: tuple[tuple[int, int], ...] = ()
    weekdays: int = 0
    between: tuple[tuple[int, int], ...] = ()
    at: tuple[int, ...] = ()
    moods: tuple[str, ...] = ()


def _items(key: str, value) -> list:
    """One value or a list of them; an empty list is an error."""
    items = value if isinstance(value, list) else [value]
    if not items:
        raise RegistryError(f"when: {key}: an empty list; leave the key out instead")
    return items


def _date(text: str) -> int:
    match = _DATE.match(text)
    if match:
        month, day = int(match[1]), int(match[2])
        # 2024 is a leap year, so 02-29 is a date.
        if 1 <= month <= 12 and 1 <= day <= calendar.monthrange(2024, month)[1]:
            return month * 100 + day
    raise RegistryError(f"when: dates: '{text}' is no date; write MM-DD, like 04-01")


def _dates(value) -> tuple[tuple[int, int], ...]:
    out = []
    for item in _items("dates", value):
        start, sep, end = str(item).partition("..")
        out.append((_date(start), _date(end if sep else start)))
    return tuple(out)


def _day(text: str) -> int:
    if text not in DAYS:
        raise RegistryError(f"when: weekdays: '{text}' is no day (days: {', '.join(DAYS)})")
    return DAYS.index(text)


def _weekdays(value) -> int:
    mask = 0
    for item in _items("weekdays", value):
        start, sep, end = str(item).partition("-")
        first, last = _day(start), _day(end if sep else start)
        for step in range((last - first) % 7 + 1):
            mask |= 1 << (first + step) % 7
    return mask


def _minute(key: str, value, end: bool = False) -> int:
    """A "HH:MM" as a minute of day. 24:00 only as the end of a range."""
    if isinstance(value, int) and not isinstance(value, bool):
        # YAML reads an unquoted 16:00 as the number 960.
        hours, minutes = divmod(value, 60)
        raise RegistryError(f'when: {key}: {hours}:{minutes:02d} needs quotes: "{hours:02d}:{minutes:02d}"')
    match = _TIME.match(str(value))
    if not match or int(match[2]) > 59 or int(match[1]) * 60 + int(match[2]) > (1440 if end else 1439):
        raise RegistryError(f"when: {key}: '{value}' is no time; write HH:MM, like 09:00")
    return int(match[1]) * 60 + int(match[2])


def _between(value) -> tuple[tuple[int, int], ...]:
    out = []
    for item in _items("between", value):
        start, sep, end = str(item).partition("-")
        if not sep:
            raise RegistryError(f"when: between: '{item}' needs a start and an end, like 16:00-18:00")
        span = (_minute("between", start), _minute("between", end, end=True))
        if span[0] == span[1] % 1440:
            raise RegistryError(f"when: between: '{item}' starts where it ends")
        out.append(span)
    return tuple(out)


def _at(value) -> tuple[int, ...]:
    return tuple(_minute("at", item) for item in _items("at", value))


def _moods(value) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise RegistryError("when: moods: a list of moods, like [sleeping]")
    return tuple(value)


_PARSERS = {"dates": _dates, "weekdays": _weekdays, "between": _between, "at": _at, CONF_MOODS: _moods}


def parse_when(raw: dict) -> When:
    """The conditions of one event. Raises RegistryError for a bad one."""
    if not isinstance(raw, dict):
        raise RegistryError("when: a map of conditions, like { moods: [sleeping] }")
    unknown = [key for key in raw if key not in _PARSERS]
    if unknown:
        raise RegistryError(f"when: unknown key '{unknown[0]}' (keys: {', '.join(_PARSERS)})")
    if "at" in raw and "between" in raw:
        raise RegistryError("when: `at:` names its own minutes; drop `between:`")
    return When(**{key: _PARSERS[key](value) for key, value in raw.items()})


def check_shape(name: str, event: dict) -> None:
    """An event is a one-shot (animation, say or sound) or a spell (`for`
    with an animation; enter and exit optional)."""
    check_name(name, "Random event")
    if CONF_FOR in event:
        if CONF_ANIMATION not in event:
            raise RegistryError(f"random event '{name}': a spell (`for:`) needs the `animation:` it loops")
        return
    stray = [key for key in (CONF_ENTER, CONF_EXIT) if key in event]
    if stray:
        raise RegistryError(f"random event '{name}': `{stray[0]}:` belongs to a spell; add `for:`")
    if not any(key in event for key in (CONF_ANIMATION, CONF_SAY, CONF_SOUND)):
        raise RegistryError(f"random event '{name}': give it an animation, say or sound")


def merge_pool(persona_events: dict[str, dict], overrides: dict[str, dict | bool]) -> dict[str, dict]:
    """The persona's events with the device's overrides applied, in pool
    order: the persona's in their order, then the device's new ones.

    Override values come without schema defaults, so a partial one changes
    only the keys it names:

    - `false` removes the event; naming one the persona lacks is an error;
    - a dict for an existing event merges key by key; `when:` is replaced
      as a whole;
    - a dict for a new name adds an event, with the default frequency and
      `when:`, and must have a full shape.

    Every event an override touches is checked again (check_shape)."""
    pool = {name: dict(event) for name, event in persona_events.items()}
    for name, override in overrides.items():
        if override is False:
            if name not in pool:
                raise RegistryError(f"random event '{name}': false removes an event, but there is none by that name")
            del pool[name]
            continue
        base = pool.get(name, {CONF_FREQUENCY: DEFAULT_FREQUENCY, CONF_WHEN: {}})
        pool[name] = {**base, **override}
        check_shape(name, pool[name])
    return pool


# --- The device's pools and the build ---------------------------------------------

# Per persona. The engine counts them in a uint8_t.
MAX_EVENTS = 32


def device_pools(personas: list[tuple[str, dict, bool]], overrides: dict[str, dict]) -> dict[str, dict]:
    """persona id -> its events with the device's overrides (merge_pool), for
    every persona that takes events. `personas` holds (id, events, takes
    events); `overrides` is `daruma: random_events: personas:`."""
    takes = {pid: ok for pid, _, ok in personas}
    for pid in overrides:
        if pid not in takes:
            raise RegistryError(f"random_events: personas: no persona '{pid}' (personas: {', '.join(takes)})")
        if not takes[pid]:
            raise RegistryError(f"random_events: personas: {pid} has no random events")
    pools = {}
    for pid, events, ok in personas:
        if not ok:
            continue
        try:
            pool = merge_pool(events, overrides.get(pid, {}))
        except RegistryError as err:
            raise RegistryError(f"random_events: personas: {pid}: {err}") from err
        if len(pool) > MAX_EVENTS:
            raise RegistryError(f"{pid}: {len(pool)} random events; a persona has at most {MAX_EVENTS}")
        pools[pid] = pool
    return pools


def active(persona_events: list[dict], overrides: dict) -> bool:
    """The build makes the engine when a persona declares events or the
    device has overrides. Tunables alone don't turn it on."""
    return bool(overrides) or any(persona_events)


def fnv1a(text: str) -> int:
    """32-bit FNV-1a: an event's preference key."""
    value = 0x811C9DC5
    for byte in text.encode():
        value = ((value ^ byte) * 0x01000193) & 0xFFFFFFFF
    return value


@dataclass(frozen=True)
class Encoded:
    """One event as the engine's EventDef holds it (random_events.h)."""

    key: int
    spell: bool
    enter: int
    animation: int
    exit: int
    hold_ms: int
    frequency: int
    cooldown_s: int
    sound: str
    say: tuple[str, ...]
    when: When


def _amount(value, unit: str) -> int:
    """A time from the schema (a TimePeriod) in `unit`; 0 when unset."""
    return 0 if value is None else int(getattr(value, unit))


def encode_event(persona_id: str, name: str, event: dict, animations: list[str]) -> Encoded:
    """An event, checked by the schema and the registry, for the engine.
    Animations become indices into the persona's list; -1 for none."""

    def index(key: str) -> int:
        return animations.index(event[key]) if key in event else -1

    return Encoded(
        key=fnv1a(f"random_events/{persona_id}/{name}"),
        spell=CONF_FOR in event,
        enter=index(CONF_ENTER),
        animation=index(CONF_ANIMATION),
        exit=index(CONF_EXIT),
        hold_ms=_amount(event.get(CONF_FOR), "total_milliseconds"),
        frequency=event[CONF_FREQUENCY],
        cooldown_s=_amount(event.get(CONF_COOLDOWN), "total_seconds"),
        sound=event.get(CONF_SOUND, ""),
        say=tuple(event.get(CONF_SAY, ())),
        when=parse_when(event.get(CONF_WHEN, {})),
    )
