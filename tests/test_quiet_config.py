"""Host test of the quiet module's options (no ESPHome build needed).

python3 -m unittest tests.test_quiet_config
"""

import unittest
from types import SimpleNamespace

import esphome.config_validation as cv
import esphome_components  # noqa: F401
from esphome.components import daruma_quiet as quiet
from esphome.components.daruma import registry


def state(name: str, kind: str) -> SimpleNamespace:
    return SimpleNamespace(name=name, kind=kind)


class ClockTime(unittest.TestCase):
    def test_reads_hours_and_minutes(self):
        self.assertEqual(quiet._clock_time("22:00"), (22, 0))
        self.assertEqual(quiet._clock_time("07:30"), (7, 30))
        self.assertEqual(quiet._clock_time("0:00"), (0, 0))
        self.assertEqual(quiet._clock_time("23:59"), (23, 59))

    def test_rejects_what_is_not_a_time(self):
        for bad in ("24:00", "12:60", "-1:00", "noon", "7", "7:00:00"):
            with self.subTest(bad=bad), self.assertRaises(cv.Invalid):
                quiet._clock_time(bad)


class DndDuring(unittest.TestCase):
    STATES = [state("focus", registry.ACTIVITY), state("happy", registry.MOOD)]

    def test_keeps_activities_in_order(self):
        config = {quiet.CONF_DND_DURING: ["focus"]}
        self.assertEqual(quiet._dnd_states(config, self.STATES), ["focus"])

    def test_skips_a_state_this_build_lacks(self):
        config = {quiet.CONF_DND_DURING: ["meeting", "focus"]}
        self.assertEqual(quiet._dnd_states(config, self.STATES), ["focus"])

    def test_a_mood_is_an_error(self):
        config = {quiet.CONF_DND_DURING: ["happy"]}
        with self.assertRaisesRegex(cv.Invalid, "not an activity"):
            quiet._dnd_states(config, self.STATES)


class Schema(unittest.TestCase):
    def test_module_declares_its_action_and_color(self):
        self.assertEqual(quiet.DARUMA_MODULE.name, "quiet")
        self.assertIn("quiet.dnd", quiet.DARUMA_MODULE.actions)
        self.assertIn("dnd", quiet.DARUMA_MODULE.colors)


if __name__ == "__main__":
    unittest.main()
