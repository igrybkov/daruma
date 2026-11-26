"""Host tests of the Habits app's build side (daruma_habits/__init__.py).

uv run pytest tests/test_habits_config.py
"""

import asyncio
import unittest

import esphome.config_validation as cv
import esphome_components  # noqa: F401
from esphome.components import daruma_habits as habits
from test_habitica_config import FakeCodegen


class ToCode(unittest.TestCase):
    def test_limits_go_to_the_app(self):
        conf = {
            "id": "habits_app",
            "daruma_id": "hub",
            "max_waiting": 5,
            "per_minute": 12,
            "max_items": 20,
            "timeout": 10000,
        }
        fake = FakeCodegen()
        real = habits.cg
        habits.cg = fake
        try:
            asyncio.run(habits.to_code(conf))
        finally:
            habits.cg = real
        # Other modules look for this define to hook into the app.
        self.assertEqual(fake.defines, ["USE_DARUMA_HABITS"])
        self.assertEqual(fake.registered, [("habits_app", conf)])
        self.assertEqual(
            fake.added,
            [("set_hub", ("var:hub",)), ("set_limits", (5, 12, 10000)), ("set_max_items", (20,))],
        )


class Schema(unittest.TestCase):
    def config(self, **over):
        conf = {"max_waiting": 5, "per_minute": 12, "max_items": 20}
        conf.update(over)
        return conf

    def test_the_defaults_pass(self):
        self.assertEqual(habits.CONFIG_SCHEMA(self.config())["per_minute"], 12)

    def test_caps_stay_in_range(self):
        for key, bad in (("max_waiting", 0), ("max_waiting", 21), ("per_minute", 31), ("max_items", 51)):
            with self.assertRaises(cv.Invalid):
                habits.CONFIG_SCHEMA(self.config(**{key: bad}))


if __name__ == "__main__":
    unittest.main()
