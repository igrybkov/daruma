"""Host test of the hub's random events build: its schema, entities, final
checks and the engine tables it writes (daruma/__init__.py).

python3 -m unittest tests.test_random_events_build
"""

import unittest
from types import SimpleNamespace

import esphome.config_validation as cv
import esphome_components  # noqa: F401
from esphome.components import daruma
from esphome.components.daruma import random_events, registry
from esphome.components.daruma.persona import RANDOM_EVENTS_SCHEMA, SAY_ONLY_EVENTS_SCHEMA, event_override
from esphome.core import CORE

STATES = registry.collect_states([])


class HubSchema(unittest.TestCase):
    def test_false_drops_the_engine(self):
        self.assertIs(daruma._random_events_conf(False), False)

    def test_true_is_the_defaults(self):
        rc = daruma._random_events_conf(True)
        self.assertTrue(rc["enabled"])
        self.assertEqual(rc["tick"]["min"].total_milliseconds, 120000)
        self.assertEqual(rc["tick"]["max"].total_milliseconds, 1200000)
        self.assertEqual(rc["min_gap"].total_minutes, 15)
        self.assertEqual(rc["liveliness"], 100)
        self.assertEqual((rc["time_id"].id, rc["event_id"].id), ("daruma_time", "daruma_event"))
        self.assertEqual(rc["personas"], {})

    def test_tick_order(self):
        with self.assertRaisesRegex(cv.Invalid, "tick: min is longer than max"):
            daruma._random_events_conf({"tick": {"min": "10min", "max": "5min"}})

    def test_limits(self):
        for bad in ({"tick": {"min": "10s"}}, {"tick": {"max": "25h"}}, {"min_gap": "241min"}, {"liveliness": 201}):
            with self.subTest(bad=bad), self.assertRaises(cv.Invalid):
                daruma._random_events_conf(bad)

    def test_overrides_keep_only_their_keys(self):
        rc = daruma._random_events_conf({"personas": {"pixel_corgi": {"sneeze": False, "lick_paw": {"frequency": 6}}}})
        self.assertEqual(rc["personas"], {"pixel_corgi": {"sneeze": False, "lick_paw": {"frequency": 6}}})

    def test_override_values(self):
        self.assertIs(event_override(False), False)
        self.assertEqual(event_override({"say": "Hi"}), {"say": ["Hi"]})
        with self.assertRaises(cv.Invalid):
            event_override({"frequency": 11})


class Entities(unittest.TestCase):
    # ESPHome keeps the entity names it has seen in CORE, to catch duplicates.
    def setUp(self):
        CORE.reset()

    def tearDown(self):
        CORE.reset()

    def test_none_with_false(self):
        daruma._random_events_entities(False)  # Nothing to fill in, and no error.

    def test_the_three_settings(self):
        rc = daruma._random_events_conf({"enabled": False})
        daruma._random_events_entities(rc)
        self.assertEqual(rc["switch"]["name"], "Random events")
        self.assertEqual(rc["switch"]["restore_mode"], "RESTORE_DEFAULT_OFF")
        self.assertEqual(rc["liveliness_number"]["unit_of_measurement"], "%")
        self.assertEqual(rc["min_gap_number"]["name"], "Min gap")
        for key in ("switch", "liveliness_number", "min_gap_number"):
            self.assertEqual(str(rc[key]["entity_category"]), "config")

    def test_switch_starts_on_by_default(self):
        rc = daruma._random_events_conf({})
        daruma._random_events_entities(rc)
        self.assertEqual(rc["switch"]["restore_mode"], "RESTORE_DEFAULT_ON")


class PersonaSchema(unittest.TestCase):
    def test_events_get_defaults(self):
        events = RANDOM_EVENTS_SCHEMA({"lick_paw": {"animation": "LickPaw"}})
        self.assertEqual(events, {"lick_paw": {"animation": "LickPaw", "frequency": 8, "when": {}}})

    def test_shape_and_when_errors(self):
        with self.assertRaisesRegex(cv.Invalid, "give it an animation, say or sound"):
            RANDOM_EVENTS_SCHEMA({"x": {"frequency": 3}})
        with self.assertRaisesRegex(cv.Invalid, "unknown key"):
            RANDOM_EVENTS_SCHEMA({"x": {"say": "a", "when": {"nope": 1}}})
        with self.assertRaisesRegex(cv.Invalid, "a map of event name"):
            RANDOM_EVENTS_SCHEMA(["x"])

    def test_say_only(self):
        with self.assertRaisesRegex(cv.Invalid, "say-only"):
            SAY_ONLY_EVENTS_SCHEMA({"x": {"animation": "A"}})


def _images(pid: str, events: dict) -> dict:
    """An images persona config, as daruma_images.daruma_personas reads it."""
    return {"id": SimpleNamespace(id=pid), "frames": {"Neutral": "n.png"}, "random_events": events}


class Final(unittest.TestCase):
    def setUp(self):
        self.full = {"api": {}, "daruma_images": [_images("flat_corgi", {})]}

    def final(self, rc, full=None):
        with self.assertLogs(daruma._LOGGER, "INFO") as logs:
            daruma._random_events_final({"random_events": rc}, self.full if full is None else full, STATES)
        return logs.output

    def test_off_by_false(self):
        self.assertIn("random events: off (random_events: false)", self.final(False)[0])

    def test_off_without_events(self):
        self.assertIn("random events: off (no persona declares any)", self.final({"personas": {}})[0])

    def test_on_with_overrides(self):
        rc = {"personas": {"flat_corgi": {"hi": {"say": ["Hi"]}}}}
        self.assertIn("random events: flat_corgi: 1 (hi)", self.final(rc)[-1])

    def test_merged_pool_is_checked(self):
        rc = {"personas": {"flat_corgi": {"walk": {"animation": "Neutral"}}}}
        with self.assertRaisesRegex(registry.RegistryError, "say-only"):
            daruma._random_events_final({"random_events": rc}, self.full, STATES)

    def test_needs_api(self):
        rc = {"personas": {"flat_corgi": {"hi": {"say": ["Hi"]}}}}
        with self.assertRaisesRegex(registry.RegistryError, "needs `api:`"):
            daruma._random_events_final({"random_events": rc}, {"daruma_images": self.full["daruma_images"]}, STATES)

    def test_event_personas(self):
        ((char, conf, takes),) = daruma.event_personas(self.full)
        self.assertEqual((char.id, takes), ("flat_corgi", True))
        self.assertIs(conf, self.full["daruma_images"][0])
        self.assertEqual(daruma.event_personas({}), [])


class Tables(unittest.TestCase):
    def tearDown(self):
        CORE.reset()

    def test_empty_table_is_nullptr(self):
        self.assertEqual(daruma._cpp_array("none", "uint16_t", []), "nullptr")

    def test_event_row(self):
        CORE.reset()
        event = {
            "animation": "Away",
            "enter": "WalkOff",
            "for": SimpleNamespace(total_milliseconds=60000),
            "say": ["brb"],
            "sound": "pet",
            "frequency": 4,
            "cooldown": SimpleNamespace(total_seconds=600),
            "when": {
                "dates": "12-20..01-05",
                "weekdays": "mon-fri",
                "between": "22:00-06:00",
                "moods": ["sleeping"],
            },
        }
        row = daruma._event_def("p", 0, "nap", event, ["Neutral", "WalkOff", "Away"])
        key = random_events.fnv1a("random_events/p/nap")
        self.assertEqual(
            row,
            f'{{"nap", {key}u, Daruma::RandomEvents::Kind::SPELL, 1, 2, -1, 60000u, 4, 600u, "pet", '
            "p_random_event_0_say, 1, p_random_event_0_dates, 1, 62, p_random_event_0_times, 1, nullptr, 0, "
            "p_random_event_0_moods, 1, true}",
        )
        globals_ = "\n".join(str(s) for s in CORE.global_statements)
        self.assertIn('static const char *const p_random_event_0_say[] = {"brb"};', globals_)
        self.assertIn(
            "static const Daruma::RandomEvents::DateRange p_random_event_0_dates[] = {{1220, 105}};", globals_
        )
        self.assertIn(
            "static const Daruma::RandomEvents::TimeRange p_random_event_0_times[] = {{1320, 360}};", globals_
        )
        self.assertIn("static const Daruma::StateId p_random_event_0_moods[] = {Daruma::StateId::SLEEPING};", globals_)

    def test_scheduled_one_shot(self):
        CORE.reset()
        row = daruma._event_def("p", 3, "pi", {"say": ["Pi"], "frequency": 10, "when": {"at": "15:14"}}, [])
        self.assertIn('Kind::ONE_SHOT, -1, -1, -1, 0u, 10, 0u, ""', row)
        self.assertTrue(row.endswith("nullptr, 0, 0, nullptr, 0, p_random_event_3_at, 1, nullptr, 0, false}"))
        self.assertIn("static const uint16_t p_random_event_3_at[] = {914};", str(CORE.global_statements[-1]))


if __name__ == "__main__":
    unittest.main()
