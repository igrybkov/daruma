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
