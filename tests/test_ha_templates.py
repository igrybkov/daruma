"""Jinja templates that HA renders for the device, run here with Jinja2.

The desktop runner answers HA calls in the device's own shape, so it never
runs these templates. These tests render them from the package and the
blueprint files, with a fixed `now()`.
"""

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
