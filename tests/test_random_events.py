"""Host test of the random events' build rules (no ESPHome needed).

python3 -m unittest tests.test_random_events
"""

import unittest

import esphome_components  # noqa: F401
from esphome.components.daruma import random_events
from esphome.components.daruma.random_events import When, check_shape, merge_pool, parse_when
from esphome.components.daruma.registry import RegistryError


class Tables(unittest.TestCase):
    def test_mean_intervals_match_the_issue(self):
        minute, hour, day = 60, 3600, 86400
        expected = {
            10: 10 * minute,
            9: 30 * minute,
            8: 2 * hour,
            7: 6 * hour,
            6: day,
            5: 3 * day,
            4: 7 * day,
            3: 14 * day,
            2: 30 * day,
            1: 90 * day,
        }
        self.assertEqual({f: random_events.MEAN_S[f] for f in range(1, 11)}, expected)
        self.assertEqual(len(random_events.MEAN_S), 11)

    def test_scheduled_chances_match_the_design(self):
        expected = {10: 100, 9: 95, 8: 85, 7: 70, 6: 55, 5: 40, 4: 25, 3: 15, 2: 5, 1: 1}
        self.assertEqual({f: random_events.AT_CHANCE[f] for f in range(1, 11)}, expected)
        self.assertEqual(len(random_events.AT_CHANCE), 11)

    def test_default_frequency(self):
        self.assertEqual(random_events.DEFAULT_FREQUENCY, 8)


class Dates(unittest.TestCase):
    def test_one_day_a_range_and_a_list(self):
        self.assertEqual(parse_when({"dates": "12-25"}).dates, ((1225, 1225),))
        self.assertEqual(parse_when({"dates": "04-01..05-31"}).dates, ((401, 531),))
        self.assertEqual(parse_when({"dates": ["12-20..01-05", "07-04"]}).dates, ((1220, 105), (704, 704)))

    def test_leap_day_and_month_ends(self):
        self.assertEqual(parse_when({"dates": "02-29"}).dates, ((229, 229),))
        self.assertEqual(parse_when({"dates": "01-01..12-31"}).dates, ((101, 1231),))

    def test_bad_dates(self):
        for bad in ("02-30", "04-31", "13-01", "00-10", "01-00", "4-1", "04-01..", "12-25x"):
            with self.subTest(bad), self.assertRaisesRegex(RegistryError, "is no date"):
                parse_when({"dates": bad})

    def test_empty_list(self):
        with self.assertRaisesRegex(RegistryError, "dates: an empty list"):
            parse_when({"dates": []})


class Weekdays(unittest.TestCase):
    def test_sunday_is_bit_zero(self):
        days = {"sun": 1, "mon": 2, "tue": 4, "wed": 8, "thu": 16, "fri": 32, "sat": 64}
        for day, mask in days.items():
            with self.subTest(day):
                self.assertEqual(parse_when({"weekdays": day}).weekdays, mask)

    def test_ranges_wrap_and_lists_add(self):
        self.assertEqual(parse_when({"weekdays": "mon-fri"}).weekdays, 0b0111110)
        self.assertEqual(parse_when({"weekdays": "fri-mon"}).weekdays, 0b1100011)
        self.assertEqual(parse_when({"weekdays": "sun-sat"}).weekdays, 0b1111111)
        self.assertEqual(parse_when({"weekdays": ["sat", "sun"]}).weekdays, 0b1000001)
        self.assertEqual(parse_when({"weekdays": "wed-wed"}).weekdays, 0b0001000)

    def test_bad_days(self):
        for bad in ("monday", "Mon", "mon-funday", "xyz"):
            with self.subTest(bad), self.assertRaisesRegex(RegistryError, "is no day"):
                parse_when({"weekdays": bad})
        with self.assertRaisesRegex(RegistryError, "weekdays: an empty list"):
            parse_when({"weekdays": []})


class Between(unittest.TestCase):
    def test_spans(self):
        self.assertEqual(parse_when({"between": "16:00-18:00"}).between, ((960, 1080),))
        self.assertEqual(parse_when({"between": "22:00-06:00"}).between, ((1320, 360),))
        self.assertEqual(parse_when({"between": "15:14-15:15"}).between, ((914, 915),))
        self.assertEqual(parse_when({"between": ["00:00-01:00", "23:00-24:00"]}).between, ((0, 60), (1380, 1440)))

    def test_bad_spans(self):
        cases = {
            "16:00-16:00": "starts where it ends",
            "00:00-24:00": "starts where it ends",
            "24:00-01:00": "is no time",
            "25:00-26:00": "is no time",
            "9:00-10:00": "is no time",
            "10:60-11:00": "is no time",
            "23:00-24:01": "is no time",
            "16:00": "needs a start and an end",
        }
        for bad, message in cases.items():
            with self.subTest(bad), self.assertRaisesRegex(RegistryError, message):
                parse_when({"between": bad})

    def test_messages_name_the_key_and_the_bad_part(self):
        cases = {
            "25:00-10:00": "when: between: '25:00' is no time; write HH:MM, like 09:00",
            "10:00-25:00": "when: between: '25:00' is no time; write HH:MM, like 09:00",
            "16:00-18:00-20:00": "when: between: '18:00-20:00' is no time; write HH:MM, like 09:00",
        }
        for bad, message in cases.items():
            with self.subTest(bad), self.assertRaises(RegistryError) as caught:
                parse_when({"between": bad})
            self.assertEqual(str(caught.exception), message)
        with self.assertRaises(RegistryError) as caught:
            parse_when({"between": []})
        self.assertEqual(str(caught.exception), "when: between: an empty list; leave the key out instead")


class At(unittest.TestCase):
    def test_one_time_or_a_list(self):
        self.assertEqual(parse_when({"at": "09:00"}).at, (540,))
        self.assertEqual(parse_when({"at": ["00:00", "23:59", "15:14"]}).at, (0, 1439, 914))

    def test_bad_times(self):
        for bad in ("24:00", "9:00", "12:60", "noon"):
            with self.subTest(bad), self.assertRaises(RegistryError) as caught:
                parse_when({"at": bad})
            self.assertEqual(str(caught.exception), f"when: at: '{bad}' is no time; write HH:MM, like 09:00")
        with self.assertRaises(RegistryError) as caught:
            parse_when({"at": []})
        self.assertEqual(str(caught.exception), "when: at: an empty list; leave the key out instead")

    def test_unquoted_times_ask_for_quotes(self):
        # YAML reads 16:00 as 960 and 9:00 as 540.
        cases = {960: r'16:00 needs quotes: "16:00"', 540: r'9:00 needs quotes: "09:00"', 1440: "24:00"}
        for number, message in cases.items():
            with self.subTest(number), self.assertRaisesRegex(RegistryError, message):
                parse_when({"at": number})
        with self.assertRaisesRegex(RegistryError, "needs quotes"):
            parse_when({"at": ["09:00", 960]})
        with self.assertRaisesRegex(RegistryError, "is no time"):
            parse_when({"at": True})

    def test_not_with_between(self):
        with self.assertRaisesRegex(RegistryError, "drop `between:`"):
            parse_when({"at": "09:00", "between": "08:00-10:00"})

    def test_with_the_other_keys(self):
        when = parse_when({"at": "15:14", "dates": "03-14", "weekdays": "mon", "moods": ["happy"]})
        self.assertEqual(when, When(dates=((314, 314),), weekdays=2, at=(914,), moods=("happy",)))


class WhenKeys(unittest.TestCase):
    def test_empty_always_holds(self):
        self.assertEqual(parse_when({}), When())
        self.assertEqual(When(), When((), 0, (), (), ()))

    def test_moods_are_a_list(self):
        self.assertEqual(parse_when({"moods": ["sleeping", "sleepy"]}).moods, ("sleeping", "sleepy"))
        for bad in ("sleeping", []):
            with self.subTest(bad), self.assertRaisesRegex(RegistryError, "a list of moods"):
                parse_when({"moods": bad})

    def test_unknown_key(self):
        with self.assertRaisesRegex(
            RegistryError, r"unknown key 'weekday' \(keys: dates, weekdays, between, at, moods\)"
        ):
            parse_when({"weekday": "mon"})

    def test_not_a_map(self):
        with self.assertRaisesRegex(RegistryError, "a map of conditions"):
            parse_when(["mon"])


class Shape(unittest.TestCase):
    def test_one_shots(self):
        for event in ({"animation": "LickPaw"}, {"say": ["Hi"]}, {"sound": "pet"}):
            with self.subTest(event):
                check_shape("quirk", event)

    def test_one_shot_needs_something_to_show(self):
        with self.assertRaisesRegex(RegistryError, "give it an animation, say or sound"):
            check_shape("quirk", {"frequency": 8, "when": {}})

    def test_spell(self):
        check_shape("bathroom", {"enter": "WalkOff", "animation": "Away", "exit": "WalkBack", "for": 180000})
        check_shape("nap", {"animation": "Away", "for": 180000})

    def test_spell_needs_its_loop(self):
        with self.assertRaisesRegex(RegistryError, "needs the `animation:` it loops"):
            check_shape("bathroom", {"enter": "WalkOff", "for": 180000, "say": ["brb"]})

    def test_enter_or_exit_needs_for(self):
        for key in ("enter", "exit"):
            with self.subTest(key), self.assertRaisesRegex(RegistryError, f"`{key}:` belongs to a spell"):
                check_shape("bathroom", {key: "WalkOff", "animation": "Away"})

    def test_name(self):
        with self.assertRaisesRegex(RegistryError, "Random event 'LickPaw': use lowercase"):
            check_shape("LickPaw", {"animation": "LickPaw"})


class Merge(unittest.TestCase):
    POOL = {
        "lick_paw": {"animation": "LickPaw", "frequency": 9, "when": {}},
        "sneeze": {"animation": "Sneeze", "frequency": 10, "when": {"dates": "04-01..05-31"}},
        "walk_q": {"say": ["Walk?"], "frequency": 8, "when": {"between": "16:00-18:00", "weekdays": ["mon-fri"]}},
    }

    def test_no_overrides(self):
        self.assertEqual(merge_pool(self.POOL, {}), self.POOL)

    def test_false_removes(self):
        self.assertEqual(list(merge_pool(self.POOL, {"sneeze": False})), ["lick_paw", "walk_q"])
        # The overrides after a removal still apply.
        pool = merge_pool(self.POOL, {"sneeze": False, "lick_paw": {"frequency": 6}})
        self.assertEqual(pool["lick_paw"]["frequency"], 6)

    def test_false_on_a_missing_name(self):
        with self.assertRaisesRegex(RegistryError, "random event 'sneez': false removes an event"):
            merge_pool(self.POOL, {"sneez": False})

    def test_partial_merges_key_by_key(self):
        pool = merge_pool(self.POOL, {"lick_paw": {"frequency": 6}})
        self.assertEqual(pool["lick_paw"], {"animation": "LickPaw", "frequency": 6, "when": {}})

    def test_when_is_replaced_whole(self):
        pool = merge_pool(self.POOL, {"walk_q": {"when": {"weekdays": "sat"}}})
        self.assertEqual(pool["walk_q"]["when"], {"weekdays": "sat"})

    def test_new_name_with_defaults_goes_last(self):
        pool = merge_pool(self.POOL, {"pi_time": {"say": ["π"]}, "lick_paw": {"frequency": 6}})
        self.assertEqual(list(pool), ["lick_paw", "sneeze", "walk_q", "pi_time"])
        self.assertEqual(pool["pi_time"], {"say": ["π"], "frequency": 8, "when": {}})

    def test_new_name_needs_a_full_shape(self):
        with self.assertRaisesRegex(RegistryError, "random event 'snack_q': give it"):
            merge_pool(self.POOL, {"snack_q": {"frequency": 6}})
        with self.assertRaisesRegex(RegistryError, "Random event 'Snack': use lowercase"):
            merge_pool(self.POOL, {"Snack": {"say": ["Snack?"]}})

    def test_a_partial_override_is_checked_again(self):
        with self.assertRaisesRegex(RegistryError, "walk_q': a spell"):
            merge_pool(self.POOL, {"walk_q": {"for": 180000}})

    def test_the_persona_pool_is_left_alone(self):
        merge_pool(self.POOL, {"lick_paw": {"frequency": 6}, "sneeze": False})
        self.assertEqual(self.POOL["lick_paw"]["frequency"], 9)
        self.assertIn("sneeze", self.POOL)


if __name__ == "__main__":
    unittest.main()
