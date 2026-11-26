"""Host tests of the Habitica module's build side (daruma_habitica/__init__.py):
what to_code hands the C++ app, and the config it accepts.

    uv run pytest tests/test_habitica_config.py
"""

import asyncio
import unittest

import esphome.config_validation as cv
import esphome_components  # noqa: F401
from esphome.components import daruma_habitica as habitica


class FakeVar:
    """The app's C++ variable: each method call comes back as (name, args)."""

    def __init__(self, id_):
        self.id = id_

    def __getattr__(self, name):
        return lambda *args: (name, args)


class FakeCodegen:
    """The parts of esphome.codegen that to_code calls, recorded."""

    def __init__(self):
        self.defines, self.added, self.registered = [], [], []

    def add_define(self, name):
        self.defines.append(name)

    def new_Pvariable(self, id_):  # noqa: N802 - ESPHome's name
        return FakeVar(id_)

    async def register_component(self, var, conf):
        self.registered.append((var.id, conf))

    async def get_variable(self, id_):
        return f"var:{id_}"

    def add(self, expression):
        self.added.append(expression)


def run_to_code(conf):
    fake = FakeCodegen()
    real = habitica.cg
    habitica.cg = fake
    try:
        asyncio.run(habitica.to_code(conf))
    finally:
        habitica.cg = real
    return fake


class ToCode(unittest.TestCase):
    def test_stats_and_buttons_go_to_the_app_in_order(self):
        conf = {
            "id": "habitica_app",
            "daruma_id": "hub",
            "hp_max": 50.0,
            "hurt_threshold": 1.5,
            "message_seconds": 6,
            # Out of order, and a stat and a button left out.
            "stats": {"level": "sensor.hero_level", "health": "sensor.hero_health", "inn": "switch.hero_inn"},
            "buttons": {"revive": "button.hero_revive", "potion": "button.hero_potion"},
        }
        fake = run_to_code(conf)
        self.assertEqual(fake.defines, ["USE_API_HOMEASSISTANT_STATES", "USE_API_HOMEASSISTANT_SERVICES"])
        self.assertEqual(fake.registered, [("habitica_app", conf)])
        self.assertEqual(
            fake.added,
            [
                ("set_hub", ("var:hub",)),
                ("set_hp_max", (50.0,)),
                ("set_hurt_threshold", (1.5,)),
                ("set_message_seconds", (6,)),
                ("follow", ("health", "sensor.hero_health")),
                ("follow", ("level", "sensor.hero_level")),
                ("follow", ("inn", "switch.hero_inn")),
                ("add_button", ("potion", "button.hero_potion")),
                ("add_button", ("revive", "button.hero_revive")),
            ],
        )


class Schema(unittest.TestCase):
    def config(self, **over):
        conf = {
            "stats": {"health": "sensor.hero_health"},
            "buttons": {"potion": "button.hero_potion"},
            "hp_max": 50,
            "hurt_threshold": 1,
            "message_seconds": 6,
        }
        conf.update(over)
        return conf

    def test_a_stat_name_it_does_not_know_fails(self):
        with self.assertRaises(cv.Invalid):
            habitica.CONFIG_SCHEMA(self.config(stats={"strength": "sensor.hero_strength"}))

    def test_an_entity_id_is_checked(self):
        with self.assertRaises(cv.Invalid):
            habitica.CONFIG_SCHEMA(self.config(buttons={"potion": "not an entity"}))

    def test_every_stat_and_button_name_is_known(self):
        stats = {name: f"sensor.hero_{name}" for name in habitica.STATS}
        buttons = {name: f"button.hero_{name}" for name in habitica.BUTTONS}
        self.assertEqual(len(stats), 10)
        self.assertEqual(len(buttons), 4)
        for name in ["health", "class", "inn", "max_health"]:
            self.assertIn(name, habitica.STATS)


if __name__ == "__main__":
    unittest.main()
