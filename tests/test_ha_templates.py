"""Jinja templates that HA renders for the device, run here with Jinja2.

The desktop runner answers HA calls in the device's own shape, so it never
runs these templates. These tests render them from the package and the
blueprint files, with a fixed `now()`.
"""

import ast
import datetime
import json
import re
from pathlib import Path

import jinja2
import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
TODAY = datetime.date(2026, 11, 26)


class _Loader(yaml.SafeLoader):
    """Reads ESPHome and HA yaml: every tag (!lambda, !input, ...) as its text."""


def _tag(loader, _suffix, node):
    return loader.construct_scalar(node) if isinstance(node, yaml.ScalarNode) else None


_Loader.add_multi_constructor("!", _tag)


def _load(path: Path):
    return yaml.load(path.read_text(), Loader=_Loader)  # noqa: S506 (a SafeLoader subclass)


def _find(node, pred):
    """Every mapping under node for which pred holds."""
    if isinstance(node, dict):
        if pred(node):
            yield node
        for value in node.values():
            yield from _find(value, pred)
    elif isinstance(node, list):
        for value in node:
            yield from _find(value, pred)


def _env(now: datetime.datetime) -> jinja2.Environment:
    env = jinja2.Environment(autoescape=False, undefined=jinja2.StrictUndefined)  # noqa: S701 (renders JSON)
    env.globals["now"] = lambda: now
    env.filters["to_json"] = json.dumps
    return env


def _substitute(text: str, values: dict) -> str:
    return re.sub(r"\$\{(\w+)\}", lambda m: str(values[m.group(1)]), text)


# --- Tasks: todo.get_items ---------------------------------------------------

TASKS = _load(ROOT / "packages" / "app_tasks.yaml")


def _todo_template(**vars_) -> str:
    action = next(_find(TASKS["script"], lambda n: n.get("action") == "todo.get_items"))
    return _substitute(action["response_template"], {**TASKS["defaults"], **vars_})


def _render_todo(items, **vars_) -> dict:
    now = datetime.datetime.combine(TODAY, datetime.time(12, 0))
    out = _env(now).from_string(_todo_template(**vars_)).render(response={"todo.dailies": {"items": items}})
    return json.loads(out)


def _item(uid, status="needs_action", due=None):
    item = {"uid": uid, "summary": f"Task {uid}", "status": status}
    if due is not None:
        item["due"] = due
    return item


# The four kinds of Habitica daily, as HA's to-do list shows them, and an
# open one from a day the person never started.
DAILIES = [
    _item("open-today", due="2026-11-26"),
    _item("done-today", status="completed", due="2026-11-28"),
    _item("not-due", due="2026-11-30"),
    _item("grey"),
    _item("yesterday", due="2026-11-25"),
]


def test_tasks_lists_every_open_item_by_default():
    r = _render_todo(DAILIES)
    assert r["n"] == 4
    assert [t[0] for t in r["t"]] == ["open-today", "not-due", "grey", "yesterday", "done-today"]


def test_due_today_only_keeps_open_items_due_today_or_before():
    r = _render_todo(DAILIES, due_today_only="true")
    assert r["n"] == 2
    assert [t[0] for t in r["t"]] == ["open-today", "yesterday", "done-today"]


def test_due_today_only_keeps_done_items_of_any_date():
    r = _render_todo([_item("done-later", status="completed", due="2026-12-24")], due_today_only="true")
    assert r == {"n": 0, "t": [["done-later", "Task done-later", "x"]]}


def test_due_today_only_reads_the_date_of_a_due_time():
    items = [_item("later-today", due="2026-11-26T18:00:00+00:00"), _item("tomorrow", due="2026-11-27T08:00:00+00:00")]
    r = _render_todo(items, due_today_only="true")
    assert [t[0] for t in r["t"]] == ["later-today"]


@pytest.mark.parametrize("only", ["false", "true"])
def test_marks_overdue_and_due_today(only):
    flags = {t[0]: t[2] for t in _render_todo(DAILIES, due_today_only=only)["t"]}
    assert flags["open-today"] == "d"
    assert flags["yesterday"] == "o"
    assert flags["done-today"] == "x"


def test_all_done_when_every_due_daily_is_done():
    items = [_item("done", status="completed", due="2026-11-28"), _item("not-due", due="2026-11-30")]
    assert _render_todo(items, due_today_only="true")["n"] == 0


# --- Blueprint: focus scores a Habitica habit ---------------------------------

FOCUS = _load(ROOT / "blueprints" / "automation" / "habitica_focus_habit.yaml")
ALL_ENDS = ["focus_done", "goal_reached", "bonus"]


def _state(state, event_type=None):
    return {"state": state, "attributes": {"event_type": event_type} if event_type else {}}


def _scores(from_state, to_state, events=ALL_ENDS) -> bool:
    template = FOCUS["conditions"][0]["value_template"]
    trigger = {"from_state": from_state, "to_state": to_state}
    out = _env(datetime.datetime.now()).from_string(template).render(trigger=trigger, events=events)
    return out.strip() == "True"


def test_focus_blueprint_defaults_to_every_end_of_a_block():
    assert FOCUS["blueprint"]["input"]["events"]["default"] == ALL_ENDS
    options = FOCUS["blueprint"]["input"]["events"]["selector"]["select"]["options"]
    assert [o["value"] for o in options] == ALL_ENDS


@pytest.mark.parametrize("event", ALL_ENDS)
def test_focus_blueprint_scores_a_finished_block(event):
    assert _scores(_state("2026-11-26T10:00:00"), _state("2026-11-26T10:25:00", event))


@pytest.mark.parametrize("event", ["focus_started", "break_started", "break_over", "paused", "stopped"])
def test_focus_blueprint_skips_other_steps(event):
    assert not _scores(_state("2026-11-26T10:00:00"), _state("2026-11-26T10:25:00", event))


def test_focus_blueprint_scores_only_the_picked_ends():
    before = _state("2026-11-26T10:00:00")
    assert _scores(before, _state("x", "goal_reached"), events=["goal_reached"])
    assert not _scores(before, _state("x", "focus_done"), events=["goal_reached"])


def test_focus_blueprint_scores_the_first_event_ever():
    assert _scores(_state("unknown"), _state("2026-11-26T10:25:00", "focus_done"))


def test_focus_blueprint_skips_a_restore():
    assert not _scores(_state("unavailable"), _state("2026-11-26T10:25:00", "focus_done"))
    assert not _scores(None, _state("2026-11-26T10:25:00", "focus_done"))


def test_focus_blueprint_events_match_the_pomodoro_package():
    pomodoro = _load(ROOT / "packages" / "pomodoro.yaml")
    event = next(e for e in pomodoro["event"] if e.get("id") == "pomo_event")
    assert set(ALL_ENDS) <= set(event["event_types"])


# --- Habits: the device's reply templates -------------------------------------

HABITS = _load(ROOT / "packages" / "app_habits.yaml")


def _habits_template(script_id: str) -> str:
    script = next(s for s in HABITS["script"] if s["id"] == script_id)
    action = script["then"][0]["homeassistant.action"]
    return _substitute(action["response_template"], HABITS["defaults"])


def _render_habits(script_id: str, response) -> list[list[str]]:
    out = _env(datetime.datetime.now()).from_string(_habits_template(script_id)).render(response=response)
    return [line.split("\t") for line in out.split("\n")]


CONTRACT_LIST = {
    "habits": [
        {
            "id": "h1",
            "title": "Drink water",
            "up": True,
            "down": False,
            "value": 4.567,
            "count_up": 3,
            "count_down": 0,
            "period": "daily",
        },
        {
            "id": "h2",
            "title": "Snack\tlate\nat night",
            "up": True,
            "down": True,
            "value": -12,
            "count_up": 1,
            "count_down": 2,
            "period": "weekly",
        },
        {"id": "h3", "title": "x" * 60, "up": False, "down": True, "period": "monthly"},
        "not a habit",
    ],
    "stats": {"hp": 42.5, "hp_max": 50, "mp": None, "level": 12},
}


def test_habits_list_becomes_lines():
    lines = _render_habits("habits_fetch", CONTRACT_LIST)
    assert lines[0] == ["L", "4"]
    assert lines[1] == ["H", "h1", "1", "0", "4.57", "3", "0", "d", "Drink water"]
    # Tabs and new lines in a title become spaces.
    assert lines[2] == ["H", "h2", "1", "1", "-12.0", "1", "2", "w", "Snack late at night"]
    # Missing numbers are 0; a long title is cut.
    assert lines[3][:8] == ["H", "h3", "0", "1", "0", "0", "0", "m"]
    assert lines[3][8] == "x" * 39 + "…"
    # Stats: what is missing is -1.
    assert lines[4] == ["S", "42.5", "50.0", "-1", "-1", "-1", "-1", "-1", "12.0"]
    assert len(lines) == 5


def test_habits_list_without_habits_or_stats():
    assert _render_habits("habits_fetch", {}) == [["L", "0"]]
    assert _render_habits("habits_fetch", None) == [["L", "0"]]
    habit = {"id": 7, "title": "T", "up": True}
    assert _render_habits("habits_fetch", {"habits": [habit]})[1] == ["H", "7", "1", "0", "0", "0", "0", "d", "T"]


def test_habits_list_keeps_max_items():
    many = {"habits": [{"id": f"h{i}", "title": "T", "up": True} for i in range(30)]}
    lines = _render_habits("habits_fetch", many)
    assert lines[0] == ["L", HABITS["defaults"]["max_items"]]
    assert len(lines) == 1 + int(HABITS["defaults"]["max_items"])


def test_habits_score_reply_becomes_lines():
    stats = {"hp": 40, "hp_max": 50, "mp": 21, "mp_max": 45, "xp": 400, "xp_next": 520, "gold": 95.5, "level": 13}
    reply = {"ok": True, "delta": 0.9876, "quest": 3.25, "drop": "You found a Wolf Egg!", "stats": stats}
    lines = _render_habits("habits_score", reply)
    assert lines[0] == ["R", "1", "0.988", "3.25", "You found a Wolf Egg!"]
    assert lines[1] == ["S", "40.0", "50.0", "21.0", "45.0", "400.0", "520.0", "95.5", "13.0"]


def test_habits_score_needs_ok_true():
    assert _render_habits("habits_score", {"ok": True}) == [["R", "1", "0", "0", ""]]
    assert _render_habits("habits_score", {"ok": "yes"})[0][1] == "0"
    assert _render_habits("habits_score", {}) == [["R", "0", "0", "0", ""]]
    assert _render_habits("habits_score", "oops") == [["R", "0", "0", "0", ""]]


# --- Blueprint: Habitica habits -------------------------------------------------

HABITS_BP = _load(ROOT / "blueprints" / "script" / "habitica_habits.yaml")


def _bp_render(template: str, **values):
    # HA turns a rendered dict back into one, as literal_eval does.
    return ast.literal_eval(_env(datetime.datetime.now()).from_string(template).render(**values))


def _bp_list(reply, max_items=20, title_chars=40) -> dict:
    template = HABITS_BP["sequence"][2]["variables"]["result"]
    return _bp_render(template, reply=reply, max_items=max_items, title_chars=title_chars)


def _bp_score(reply) -> dict:
    return _bp_render(HABITS_BP["sequence"][0]["then"][1]["variables"]["result"], reply=reply)


# get_tasks returns full records; these carry fields that must not leave HA.
GET_TASKS = {
    "tasks": [
        {
            "id": "a1",
            "type": "habit",
            "text": "Drink water",
            "notes": "secret notes",
            "up": True,
            "down": False,
            "value": 4.5,
            "counterUp": 3,
            "counterDown": 0,
            "frequency": "daily",
            "history": [{"value": 1}],
            "priority": 1,
        },
        {
            "id": "b2",
            "type": "habit",
            "text": "Snack",
            "up": True,
            "down": True,
            "value": -12.0,
            "counterUp": 1,
            "counterDown": 2,
            "frequency": "weekly",
        },
        {"id": "c3", "type": "daily", "text": "Not a habit"},
    ]
}


def test_blueprint_lists_habits_in_the_contract():
    r = _bp_list(GET_TASKS)
    assert r == {
        "habits": [
            {
                "id": "a1",
                "title": "Drink water",
                "up": True,
                "down": False,
                "value": 4.5,
                "count_up": 3,
                "count_down": 0,
                "period": "daily",
            },
            {
                "id": "b2",
                "title": "Snack",
                "up": True,
                "down": True,
                "value": -12.0,
                "count_up": 1,
                "count_down": 2,
                "period": "weekly",
            },
        ]
    }
    # Notes and history never leave HA.
    assert "secret" not in str(r) and "history" not in str(r)


def test_blueprint_list_takes_a_mapping_too_and_cuts():
    by_id = {"tasks": {t["id"]: t for t in GET_TASKS["tasks"]}}
    assert [h["id"] for h in _bp_list(by_id)["habits"]] == ["a1", "b2"]
    r = _bp_list(GET_TASKS, max_items=1, title_chars=10)
    assert [h["id"] for h in r["habits"]] == ["a1"]
    assert r["habits"][0]["title"] == "Drink wat…"
    assert _bp_list({}) == {"habits": []}
    assert _bp_list(None) == {"habits": []}


def test_blueprint_score_projects_the_reply():
    tmp = {"drop": {"dialog": "You found a Wolf Egg!", "key": "Wolf"}, "quest": {"progressDelta": 3.5}}
    reply = {
        "hp": 40.2,
        "mp": 21,
        "exp": 400,
        "gp": 95.5,
        "lvl": 13,
        "toNextLevel": 520,
        "maxHealth": 50,
        "maxMP": 45,
        "delta": 0.98,
        "_tmp": tmp,
    }
    stats = {"hp": 40.2, "hp_max": 50, "mp": 21, "mp_max": 45, "xp": 400, "xp_next": 520, "gold": 95.5, "level": 13}
    assert _bp_score(reply) == {
        "ok": True,
        "stats": stats,
        "delta": 0.98,
        "drop": "You found a Wolf Egg!",
        "quest": 3.5,
    }
    # The same under "tmp", and a reply with neither.
    reply["tmp"] = reply.pop("_tmp")
    assert _bp_score(reply)["drop"] == "You found a Wolf Egg!"
    bare = _bp_score({"lvl": 2})
    assert bare["ok"] is True and bare["drop"] == "" and bare["quest"] == 0 and bare["delta"] == 0
    assert bare["stats"]["level"] == 2 and bare["stats"]["hp"] is None


def test_blueprint_scores_with_the_device_fields():
    score = HABITS_BP["sequence"][0]["then"][0]
    assert score["action"] == "habitica.score_habit"
    assert score["data"]["task"] == "{{ id }}" and score["data"]["direction"] == "{{ direction }}"
    assert set(HABITS_BP["fields"]) == {"op", "id", "direction"}
    get = HABITS_BP["sequence"][1]
    assert get["action"] == "habitica.get_tasks" and get["data"]["type"] == ["habit"]


# --- A fake HA for the Habitica blueprints -----------------------------------


class FakeHA:
    """States, names and the Habitica device's entities, as HA's template
    functions see them."""

    def __init__(self, states: dict[str, str], names: dict[str, str] | None = None):
        self.states = states
        self.names = names or {}

    def env(self, now: datetime.datetime) -> jinja2.Environment:
        env = _env(now)
        env.globals["states"] = lambda e: self.states.get(e, "unknown")
        env.globals["state_attr"] = lambda e, a: self.names.get(e) if a == "friendly_name" else None
        env.globals["device_entities"] = lambda _device: list(self.states)
        env.globals["as_local"] = lambda t: t
        env.tests["match"] = lambda v, p: re.match(p, v) is not None
        env.tests["search"] = lambda v, p: re.search(p, v) is not None
        return env

    def render(self, template: str, now: datetime.datetime | None = None, **values):
        now = now or datetime.datetime.combine(TODAY, datetime.time(12, 0))
        out = self.env(now).from_string(template).render(**values)
        return ast.literal_eval(out) if out.strip() not in ("", "None") else None


def _hero(cls: str, level: int, mp: float, hp: float = 40, buttons: dict[str, str] | None = None, **more):
    """The Habitica device's entities for a hero (made-up prefix `hero`)."""
    states = {
        "sensor.hero_class": cls,
        "sensor.hero_level": str(level),
        "sensor.hero_next_level": "900",
        "sensor.hero_mana": str(mp),
        "sensor.hero_max_mana": "50",
        "sensor.hero_health": str(hp),
        "switch.hero_rest_in_the_inn": "off",
    }
    states.update({f"button.hero_{k}": v for k, v in (buttons or {}).items()})
    states.update(more)
    return FakeHA(states)


# --- Blueprint: Habitica skills -----------------------------------------------

SKILLS_BP = _load(ROOT / "blueprints" / "script" / "habitica_skills.yaml")
TABLE = SKILLS_BP["variables"]["table"]


def _skills(ha: FakeHA) -> dict:
    hero = ha.render(SKILLS_BP["sequence"][0]["variables"]["hero"], table=TABLE, device="d")
    result = ha.render(SKILLS_BP["sequence"][2]["variables"]["result"], table=TABLE, hero=hero)
    return {s["id"]: (s["ready"], s["why"], s["target"]) for s in result["skills"]} | {"class": result["class"]}


def test_skills_table_matches_habitica_content():
    # Habitica's spells.js: level and MP of each skill.
    want = {
        "fireball": (11, 10),
        "mpheal": (12, 30),
        "earth": (13, 35),
        "frost": (14, 40),
        "smash": (11, 10),
        "defensive_stance": (12, 25),
        "valorous_presence": (13, 20),
        "intimidate": (14, 15),
        "pickpocket": (11, 10),
        "backstab": (12, 15),
        "tools_of_trade": (13, 25),
        "stealth": (14, 45),
        "heal": (11, 15),
        "brightness": (12, 15),
        "protect_aura": (13, 30),
        "heal_all": (14, 25),
    }
    assert {k["id"]: (k["level"], k["mp"]) for k in TABLE} == want
    # Task skills cast; the others have a button.
    assert {k["id"] for k in TABLE if "cast" in k} == {"fireball", "smash", "pickpocket", "backstab"}
    assert all(("cast" in k) != ("button" in k) for k in TABLE)


def test_skills_for_a_mage():
    ha = _hero("wizard", 13, 32, buttons={"ethereal_surge": "unknown", "earthquake": "unavailable"})
    r = _skills(ha)
    assert r["class"] == "wizard"
    assert r["fireball"] == (True, "", "task")
    assert r["mpheal"] == (True, "", "party")  # Its button is there and not unavailable.
    assert r["earth"] == (False, "Needs 35 MP", "party")
    assert r["frost"] == (False, "Needs level 14", "self")  # No button at all.


def test_skills_for_a_warrior():
    ha = _hero("warrior", 14, 18, buttons={"defensive_stance": "unavailable", "intimidating_gaze": "unknown"})
    r = _skills(ha)
    assert r["smash"] == (True, "", "task")
    assert r["defensive_stance"] == (False, "Needs 25 MP", "self")
    assert r["valorous_presence"] == (False, "Needs 20 MP", "party")
    assert r["intimidate"] == (True, "", "party")


def test_skills_for_a_rogue():
    # Stealth: enough level and MP, but HA's own rule keeps its button off.
    ha = _hero("rogue", 14, 50, buttons={"tools_of_the_trade": "unknown", "stealth": "unavailable"})
    r = _skills(ha)
    assert r["pickpocket"] == (True, "", "task") and r["backstab"] == (True, "", "task")
    assert r["tools_of_trade"] == (True, "", "party")
    assert r["stealth"] == (False, "Not now", "self")


def test_skills_for_a_healer_found_by_name():
    # A renamed entity still counts by its name.
    ha = _hero("healer", 11, 20, **{"button.renamed": "2026-11-20T10:00:00"})
    ha.names["button.renamed"] = "Hero Healing Light"
    r = _skills(ha)
    assert r["heal"] == (True, "", "self")
    assert r["brightness"] == (False, "Needs level 12", "self")
    assert set(r) - {"class"} == {"heal", "brightness", "protect_aura", "heal_all"}


def test_skills_of_no_class():
    assert _skills(FakeHA({})) == {"class": ""}


def test_skills_cast_reply_projects_stats():
    then = SKILLS_BP["sequence"][1]["then"]
    template = then[1]["then"][1]["variables"]["result"]
    reply = {"hp": 40, "maxHealth": 50, "mp": 5, "maxMP": 45, "exp": 10, "toNextLevel": 500, "gp": 9, "lvl": 13}
    out = FakeHA({}).render(template, reply=reply)
    assert out == {
        "ok": True,
        "stats": {"hp": 40, "hp_max": 50, "mp": 5, "mp_max": 45, "xp": 10, "xp_next": 500, "gold": 9, "level": 13},
    }
    assert FakeHA({}).render(template, reply=None) == {"ok": True}
    assert then[1]["then"][0]["action"] == "habitica.cast_skill"


# --- The device's skills templates ----------------------------------------------

HABITICA_PKG = _load(ROOT / "packages" / "habitica.yaml")


def _pkg_lines(script_id: str, response) -> list[list[str]]:
    script = next(s for s in HABITICA_PKG["script"] if s["id"] == script_id)
    template = _substitute(script["then"][0]["homeassistant.action"]["response_template"], HABITICA_PKG["defaults"])
    out = _env(datetime.datetime.now()).from_string(template).render(response=response)
    return [line.split("\t") for line in out.split("\n")]


def test_device_skills_lines():
    reply = {
        "class": "rogue",
        "skills": [
            {
                "id": "stealth",
                "name": "Stealth",
                "mp": 45,
                "level": 14,
                "target": "self",
                "ready": False,
                "why": "Not now",
            },
            {"id": "backstab", "name": "Back\tstab", "mp": 15, "level": 12, "target": "task", "ready": True, "why": ""},
            "junk",
        ],
    }
    assert _pkg_lines("habitica_skills_fetch", reply) == [
        ["C", "rogue"],
        ["K", "stealth", "45", "14", "s", "0", "Stealth", "Not now"],
        ["K", "backstab", "15", "12", "t", "1", "Back stab", ""],
    ]
    assert _pkg_lines("habitica_skills_fetch", None) == [["C", ""]]


def test_device_cast_lines():
    stats = {"hp": 40, "hp_max": 50, "mp": 5, "mp_max": 45, "xp": 10, "xp_next": 500, "gold": 9, "level": 13}
    assert _pkg_lines("habitica_cast", {"ok": True, "stats": stats}) == [
        ["R", "1"],
        ["S", "40.0", "50.0", "5.0", "45.0", "10.0", "500.0", "9.0", "13.0"],
    ]
    assert _pkg_lines("habitica_cast", {"ok": True}) == [["R", "1"]]
    assert _pkg_lines("habitica_cast", {}) == [["R", "0"]]


# --- Blueprint: Habitica nudges ---------------------------------------------------

NUDGES = _load(ROOT / "blueprints" / "automation" / "habitica_nudges.yaml")
ALL_ON = dict.fromkeys(["evening_skill", "dailies_left", "heal", "potion", "revive", "full_mana", "allocate"], True)


def _daily(due=True, done=False, streak=0):
    return {"type": "daily", "isDue": due, "completed": done, "streak": streak}


def _nudge(ha: FakeHA, at=(21, 30), dailies=(), seen="", enabled=None, low_hp=20):
    v = NUDGES["variables"]
    facts = ha.render(
        NUDGES["actions"][1]["variables"]["facts"],
        habitica_device="d",
        buttons=v["buttons"],
        dailies={"tasks": list(dailies)},
    )
    now = datetime.datetime.combine(TODAY, datetime.time(*at))
    return ha.render(
        NUDGES["actions"][2]["variables"]["nudge"],
        now=now,
        facts=facts,
        seen=seen,
        enabled=enabled or ALL_ON,
        low_hp=low_hp,
        evening="21:00:00",
        day_start="08:00:00",
        day_end="23:00:00",
        full_mana_skills=v["full_mana_skills"],
    )


OPEN = [_daily(), _daily(streak=4), _daily(done=True), _daily(due=False)]


@pytest.mark.parametrize(
    ("cls", "button", "nudge_id", "option"),
    [
        ("rogue", "stealth", "evening_skill", "Stealth"),
        ("wizard", "chilling_frost", "evening_skill", "Chilling Frost"),
        ("warrior", "defensive_stance", "evening_skill", "Defensive Stance"),
        ("healer", "protective_aura", "evening_skill", "Protective Aura"),
    ],
)
def test_evening_nudge_per_class(cls, button, nudge_id, option):
    n = _nudge(_hero(cls, 14, 10, buttons={button: "unknown"}), dailies=OPEN)
    assert (n["id"], n["option"], n["press"], n["style"]) == (nudge_id, option, f"button.hero_{button}", "info")


def test_evening_stealth_counts_open_due_dailies():
    n = _nudge(_hero("rogue", 14, 10, buttons={"stealth": "unknown"}), dailies=OPEN)
    assert n["body"] == "2 dailies are still open. Hide with Stealth?"


def test_mage_frost_needs_a_streak():
    ha = _hero("wizard", 14, 10, buttons={"chilling_frost": "unknown"})
    n = _nudge(ha, dailies=[_daily()])
    assert n["id"] == "dailies_left" and n["body"] == "1 daily is left today." and n["press"] is None


def test_dailies_left_when_no_skill_is_ready():
    n = _nudge(_hero("rogue", 14, 10, buttons={"stealth": "unavailable"}), dailies=OPEN)
    assert n["id"] == "dailies_left" and n["body"] == "2 dailies are left today." and n["option"] == "OK"


def test_evening_nudges_wait_for_the_evening_and_open_dailies():
    ha = _hero("rogue", 14, 10, buttons={"stealth": "unknown"})
    assert _nudge(ha, at=(20, 59), dailies=OPEN) is None
    assert _nudge(ha, at=(21, 0), dailies=OPEN)["id"] == "evening_skill"
    assert _nudge(ha, dailies=[_daily(done=True)]) is None


def test_low_hp_nudges():
    ha = _hero("healer", 11, 20, hp=12, buttons={"healing_light": "unknown", "buy_a_health_potion": "unknown"})
    assert _nudge(ha, at=(10, 0))["id"] == "heal"
    # Healing Light once today already: the potion is next.
    n = _nudge(ha, at=(10, 0), seen=f"heal={TODAY}")
    assert (n["id"], n["option"], n["press"]) == ("potion", "Buy", "button.hero_buy_a_health_potion")
    # Not low: none. Outside the day window: none.
    assert _nudge(ha, at=(10, 0), low_hp=10) is None
    assert _nudge(ha, at=(7, 59)) is None
    assert _nudge(ha, at=(23, 0)) is None


def test_revive_is_urgent_and_any_time():
    ha = _hero("warrior", 12, 0, hp=0, buttons={"revive_from_death": "unknown"})
    n = _nudge(ha, at=(3, 0))
    assert (n["id"], n["style"], n["option"]) == ("revive", "urgent", "Revive")


def test_full_mana_offers_the_best_ready_skill():
    ha = _hero("wizard", 14, 50, buttons={"earthquake": "unknown", "chilling_frost": "unknown"})
    n = _nudge(ha, at=(12, 0))
    assert (n["id"], n["body"], n["press"]) == ("full_mana", "Cast Earthquake?", "button.hero_earthquake")
    assert _nudge(_hero("wizard", 14, 49, buttons={"earthquake": "unknown"}), at=(12, 0)) is None


def test_allocate():
    n = _nudge(_hero("rogue", 10, 0, buttons={"allocate_all_stat_points": "unknown"}), at=(12, 0))
    assert (n["id"], n["option"]) == ("allocate", "Allocate")


def test_once_a_day_and_switches():
    ha = _hero("rogue", 10, 0, buttons={"allocate_all_stat_points": "unknown"})
    assert _nudge(ha, at=(12, 0), seen=f"x=2026-01-01;allocate={TODAY}") is None
    # Yesterday's does not count.
    assert _nudge(ha, at=(12, 0), seen="allocate=2026-11-25")["id"] == "allocate"
    assert _nudge(ha, at=(12, 0), enabled=ALL_ON | {"allocate": False}) is None


def test_no_nudge_before_the_day_starts_or_in_the_inn():
    buttons = {"allocate_all_stat_points": "unknown", "start_my_day": "unknown"}
    assert _nudge(_hero("rogue", 10, 0, buttons=buttons), at=(12, 0)) is None
    inn = _hero("rogue", 10, 0, buttons={"allocate_all_stat_points": "unknown"})
    inn.states["switch.hero_rest_in_the_inn"] = "on"
    assert _nudge(inn, at=(12, 0)) is None


# --- Blueprint: Habitica morning ---------------------------------------------------

MORNING = _load(ROOT / "blueprints" / "automation" / "habitica_morning.yaml")


def test_morning_lists_yesterdays_open_dailies():
    template = MORNING["actions"][1]["variables"]["yesterday"]
    tasks = [
        {"id": "a", "text": "Stretch", "isDue": True, "yesterDaily": True, "completed": False},
        {"id": "b", "text": "Done", "isDue": True, "yesterDaily": True, "completed": True},
        {"id": "c", "text": "Not due", "isDue": False, "yesterDaily": True, "completed": False},
        {"id": "d", "text": "Not recorded", "isDue": True, "yesterDaily": False, "completed": False},
        {"id": "e", "text": "Read", "isDue": True, "yesterDaily": True},
    ]
    assert FakeHA({}).render(template, reply={"tasks": tasks}) == [
        {"uid": "a", "title": "Stretch"},
        {"uid": "e", "title": "Read"},
    ]
    by_id = {"tasks": {t["id"]: t for t in tasks}}
    assert [t["uid"] for t in FakeHA({}).render(template, reply=by_id)] == ["a", "e"]
    many = [dict(tasks[0], id=str(i)) for i in range(25)]
    assert len(FakeHA({}).render(template, reply={"tasks": many})) == 19
    assert FakeHA({}).render(template, reply=None) == []


def test_morning_shows_once_a_day_while_the_day_has_not_started():
    template = MORNING["conditions"][0]["value_template"]

    def shows(presence="on", start="unknown", last=None):
        ha = FakeHA({"binary_sensor.desk": presence, "button.hero_start_my_day": start})
        this = {"attributes": {"last_triggered": last}}
        out = ha.env(datetime.datetime.combine(TODAY, datetime.time(9, 0))).from_string(template)
        return out.render(presence="binary_sensor.desk", habitica_device="d", this=this).strip() == "True"

    assert shows()
    assert shows(presence="home")
    assert not shows(presence="off")
    assert not shows(start="unavailable")
    assert not shows(last=datetime.datetime.combine(TODAY, datetime.time(7, 0)))
    assert shows(last=datetime.datetime.combine(TODAY - datetime.timedelta(days=1), datetime.time(7, 0)))
