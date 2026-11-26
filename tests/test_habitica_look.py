"""Host test: Home Assistant's "Habitica look" sensor and the "Habitica look
changed" blueprint agree with the persona's look.

    uv run pytest tests/test_habitica_look.py

The template file and the sensors come from docs/habitica-avatar.md, the
condition from blueprints/automation/habitica_look_changed.yaml. Each is
rendered with Jinja2 and the few Home Assistant functions it uses, on
made-up users, and compared with daruma_personas.habitica.look.
"""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import jinja2
import pytest
import yaml
from jinja2.sandbox import ImmutableSandboxedEnvironment

from daruma_personas import habitica
from daruma_personas.habitica import fixture
from daruma_personas.habitica.look import from_user, look_text, short_id

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "habitica-avatar.md"
BLUEPRINT = ROOT / "blueprints" / "automation" / "habitica_look_changed.yaml"


def block(kind: str) -> str:
    """The first fenced block of `kind` in the docs page after the look heading."""
    text = DOCS.read_text()
    text = text[text.index("## When your look changes") :]
    return re.search(rf"```{kind}\n(.*?)```", text, re.S).group(1)


class Loader(yaml.SafeLoader):
    """Home Assistant's YAML tags as plain values: !secret NAME, !input NAME."""


Loader.add_constructor("!secret", lambda loader, node: f"<secret {loader.construct_scalar(node)}>")
Loader.add_constructor("!input", lambda loader, node: f"<input {loader.construct_scalar(node)}>")


def env(**globals_) -> jinja2.Environment:
    """Home Assistant's template flavor, as far as these templates need it."""
    e = ImmutableSandboxedEnvironment(loader=jinja2.DictLoader({"habitica.jinja": block("jinja")}))
    e.filters["ord"] = ord
    e.globals.update(globals_)
    return e


def sensors() -> dict:
    return yaml.load(block("yaml"), Loader=Loader)


def rendered(user: dict) -> tuple[str, str]:
    """The "Habitica look" sensor's state and its `look` attribute, for `user`."""
    attrs = {key: user.get(key) for key in ("preferences", "items")}
    e = env(state_attr=lambda entity, name: attrs[name] if entity == "sensor.habitica_user" else None)
    sensor = sensors()["template"][0]["sensor"][0]
    state = e.from_string(sensor["state"]).render().strip()
    look = e.from_string(sensor["attributes"]["look"]).render().strip()
    return state, look


USERS = {
    "fixture": fixture.USER,
    "full": {
        "preferences": {
            "skin": "c06534",
            "shirt": "pink",
            "size": "broad",
            "chair": "red",
            "background": "a_beach",
            "costume": False,
            "sleep": True,
            "hair": {"color": "blond", "base": 3, "bangs": "2", "mustache": 0, "beard": 1, "flower": 4},
        },
        "items": {
            "currentPet": "Fox-Red",
            "currentMount": "Owl-Base",
            "gear": {
                "equipped": {
                    "weapon": "weapon_x_1",
                    "armor": "armor_x_2",
                    "headAccessory": "headAccessory_x",
                    "head": "head_x_3",
                    "eyewear": "",
                    "cape": "not a slot",
                },
                "costume": {"armor": "armor_c"},
            },
        },
        "stats": {"class": "healer", "buffs": {"seafoam": True}},
    },
    "costume": {
        "preferences": {"costume": True},
        "items": {"gear": {"equipped": {"armor": "armor_e"}, "costume": {"head": "head_c", "armor": "armor_c"}}},
    },
    "empty": {},
    "nones": {
        "preferences": {"skin": None, "hair": {"color": None, "bangs": None}, "background": None},
        "items": {"currentPet": None, "gear": None},
    },
    "odd sections": {"preferences": "x", "items": ["y"]},
}


@pytest.mark.parametrize("user", USERS.values(), ids=USERS.keys())
def test_the_sensor_writes_the_look_as_the_persona_does(user):
    state, look = rendered(user)
    want = look_text(from_user(user))
    assert look == want
    assert state == short_id(want)


def test_the_device_and_the_sensor_show_the_same_id():
    user = USERS["full"]
    state, _look = rendered(user)
    assert habitica.look_id("habitica", {"look": user}, None) == state


def test_the_look_leaves_out_what_changes_at_run_time():
    user = USERS["full"]
    calm = {**user, "preferences": {**user["preferences"], "sleep": False}, "stats": {"class": "rogue"}}
    assert rendered(calm) == rendered(user)
    assert look_text(from_user(calm)) == look_text(from_user(user))


def test_look_text():
    look = from_user(USERS["costume"])
    assert look_text(look) == (
        "skin=915533;hair=red/0/0/0/0/0;size=slim;shirt=black;chair=none;background=;costume=1;"
        "gear=armor:armor_c,head:head_c;pet=;mount="
    )


def test_short_id():
    assert short_id("") == "00000000"
    assert short_id("a") == "00000061"
    assert short_id("ab") == f"{97 * 31 + 98:08x}"
    # Past 32 bits it wraps, as Home Assistant's template does.
    assert len(short_id("z" * 300)) == 8
    assert short_id("z" * 7) == f"{sum(122 * 31**k for k in range(7)) % 2**32:08x}"


def test_the_sensor_reads_habitica_every_30_minutes_with_the_secrets():
    (rest,) = sensors()["rest"]
    assert rest["scan_interval"] == 1800
    assert rest["resource"].startswith("https://habitica.com/api/v3/user?userFields=")
    assert rest["headers"] == {
        "x-api-user": "<secret habitica_user_id>",
        "x-api-key": "<secret habitica_api_token>",
        "x-client": "<secret habitica_x_client>",
    }
    assert rest["sensor"][0]["json_attributes"] == ["preferences", "items"]


# --- the blueprint ----------------------------------------------------------------


def blueprint() -> dict:
    return yaml.load(BLUEPRINT.read_text(), Loader=Loader)


def state(value: str, look: str | None) -> SimpleNamespace:
    return SimpleNamespace(state=value, attributes={} if look is None else {"look": look})


A, B = "skin=a;gear=armor:x", "skin=a;gear=armor:y"
ID_A, ID_B = short_id(A), short_id(B)


def notifies(before, after, device: str = "") -> bool:
    condition = blueprint()["conditions"][0]["value_template"]
    trigger = SimpleNamespace(from_state=before, to_state=after)
    return env().from_string(condition).render(trigger=trigger, device_look_id=device).strip() == "True"


def test_a_gear_change_notifies():
    assert notifies(state(ID_A, A), state(ID_B, B))


@pytest.mark.parametrize(
    ("before", "after"),
    [
        (state(ID_A, A), state(ID_A, A)),  # The inn, a buff: the look stays.
        (None, state(ID_A, A)),  # Home Assistant started.
        (state("unknown", None), state(ID_A, A)),
        (state("unavailable", None), state(ID_B, B)),
        (state(ID_A, A), state("unavailable", None)),
        (state(ID_A, A), state("unknown", B)),
        (state(ID_A, ""), state(ID_B, B)),
        (state(ID_A, A), None),
    ],
    ids=[
        "same look",
        "restart",
        "from unknown",
        "from unavailable",
        "to unavailable",
        "to unknown",
        "from empty",
        "removed",
    ],
)
def test_no_notification(before, after):
    assert not notifies(before, after)


def test_the_device_already_shows_the_look():
    assert not notifies(state(ID_A, A), state(ID_B, B), device=ID_B)
    assert notifies(state(ID_A, A), state(ID_B, B), device=ID_A)
    for gone in ("unknown", "unavailable", ""):
        assert notifies(state(ID_A, A), state(ID_B, B), device=gone)


def test_the_device_id_comes_from_the_picked_sensor():
    variables = blueprint()["variables"]
    template = env(states=lambda entity: {"sensor.daruma_avatar_look": ID_B}[entity]).from_string(
        variables["device_look_id"]
    )
    assert template.render(device_look="sensor.daruma_avatar_look") == ID_B
    assert template.render(device_look="") == ""


def test_the_blueprint_notifies_once_and_triggers_on_the_look():
    bp = blueprint()
    (trigger,) = bp["triggers"]
    assert trigger == {"trigger": "state", "entity_id": "<input look_sensor>", "attribute": "look"}
    note = bp["actions"][0]
    assert note["action"] == "persistent_notification.create"
    assert note["data"]["message"] == "Your Habitica look changed. Rebuild Daruma."
    assert bp["mode"] == "single"
