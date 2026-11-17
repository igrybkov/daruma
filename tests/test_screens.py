"""Host tests of the screen checks: the display profile, the menu on boards
without touch, and the edge strips that extend a pixel-art room (no ESPHome
or PIL needed).

    python3 -m unittest discover -s tests
"""

import unittest

import esphome_components  # noqa: F401
from esphome.components.daruma import registry
from esphome.components.daruma_sprites import extend

RegistryError, ModuleSpec = registry.RegistryError, registry.ModuleSpec


def buttons():
    return {
        "home": registry.Input("home", registry.BUTTON, ["press", "double", "hold"]),
        "top": registry.Input("top", registry.BUTTON, ["press", "double", "hold"]),
    }


NAVIGATION = {"next": "top.press", "prev": "top.double", "select": "home.press", "back": "home.double"}
MENU = ModuleSpec(name="menu", actions=["menu.open"], bindings={"screen.tap": "menu.open"})
HUB = ModuleSpec(name="daruma", actions=["daruma.pet"], bindings={"screen.stroke": "daruma.pet"})


class Profile(unittest.TestCase):
    def test_default_is_a_fast_color_lcd(self):
        p = registry.Profile()
        registry.check_profile(p)
        self.assertFalse(p.slow)

    def test_animation_needs_fast_frames(self):
        with self.assertRaisesRegex(RegistryError, "animate: false"):
            registry.check_profile(registry.Profile(animate=True, min_frame_ms=5000))
        # The limit is one second: 999 ms still animates, 1000 ms doesn't.
        registry.check_profile(registry.Profile(animate=True, min_frame_ms=999))
        with self.assertRaisesRegex(RegistryError, "animate: false"):
            registry.check_profile(registry.Profile(animate=True, min_frame_ms=1000))

    def test_eink_profile(self):
        p = registry.Profile("mono", False, 5000, True, 20)
        registry.check_profile(p)
        self.assertTrue(p.slow)

    def test_full_refresh_needs_partial(self):
        with self.assertRaisesRegex(RegistryError, "partial_refresh"):
            registry.check_profile(registry.Profile(partial_refresh=False, full_refresh_every=10))

    def test_unknown_colors(self):
        with self.assertRaisesRegex(RegistryError, "colors"):
            registry.check_profile(registry.Profile(colors="sepia"))


class ButtonOnlyMenu(unittest.TestCase):
    def resolve(self, device):
        inputs = buttons()
        nav = registry.check_navigation(inputs, NAVIGATION)
        actions = registry.collect_actions([HUB, MENU])
        bindings, log = registry.resolve_bindings(inputs, nav, device, [HUB, MENU], actions)
        return inputs, bindings, log

    def test_menu_needs_a_button(self):
        inputs, bindings, log = self.resolve({})
        # The menu's tap default is skipped on this board.
        self.assertTrue(any("screen.tap" in line and "skipped" in line for line in log))
        with self.assertRaisesRegex(RegistryError, "nothing opens the menu"):
            registry.check_menu_reachable(inputs, bindings, [HUB, MENU])

    def test_menu_on_a_button(self):
        inputs, bindings, _ = self.resolve({"home.press": {"action": "menu.open", "when": "idle"}})
        registry.check_menu_reachable(inputs, bindings, [HUB, MENU])

    def test_a_named_menu_on_a_button(self):
        binding = registry.Binding("home", "press", "menu.open:main", True, "device")
        registry.check_menu_reachable(buttons(), [binding], [HUB, MENU])

    def test_navigation_gesture_needs_when_idle(self):
        with self.assertRaisesRegex(RegistryError, "when: idle"):
            self.resolve({"home.press": {"action": "menu.open"}})

    def test_no_menu_module_no_rule(self):
        inputs = buttons()
        registry.check_menu_reachable(inputs, [], [HUB])


# A tiny room: wall planks with a period of 3 (a b c), a window frame (W)
# near the left edge in rows 1-2, and a floor (F, with a line L) that a rug
# (R) crosses in the middle.
ROOM = [
    "abcabcabcabcabcabc",
    "abWWWWabcabcabcabc",
    "abWWWWabcabcabcabc",
    "abcabcabcabcabcabc",
    "abcabcabcabcabcabc",
    "LLLLLLLLRRRRLLLLLL",
    "FFFFFFFFRRRRFFFFFF",
]
GRID = [list(row) for row in ROOM]


class EdgeStrips(unittest.TestCase):
    def test_wall_repeats_and_window_rows_borrow_plain_wall(self):
        strip = extend.left_strip(GRID)
        self.assertEqual(len(strip[0]), 3)
        self.assertEqual(strip[0], list("abc"))
        # Rows through the window frame show the nearest plain wall row.
        self.assertEqual(strip[1], list("abc"))
        # Floor rows repeat every pixel, up to the rug.
        self.assertEqual(strip[5], list("LLL"))
        self.assertEqual(strip[6], list("FFF"))

    def test_right_strip_continues_the_pattern(self):
        strip = extend.right_strip(GRID)
        self.assertEqual(len(strip[0]), 3)
        # The row ends "...abc"; going on to the right it is "abc" again.
        self.assertEqual(strip[0], list("abc"))

    def test_top_strip_repeats_the_top_row(self):
        strip = extend.top_strip(GRID)
        self.assertEqual(len(strip), 1)
        self.assertEqual(strip[0], GRID[0])

    def test_extended_room_has_no_seams(self):
        big = extend.extended(GRID, 4, 5, 2)
        self.assertEqual(len(big), len(GRID) + 2)
        self.assertEqual(len(big[0]), len(GRID[0]) + 9)
        # The wall goes on with the same period on both sides and above.
        self.assertEqual("".join(big[0]), "cabc" + "abcabcabcabcabcabc" + "abcab")
        self.assertEqual("".join(big[2])[:4], "cabc")
        # The floor goes on sideways, the rug does not.
        self.assertEqual("".join(big[-1]), "FFFF" + ROOM[-1] + "FFFFF")

    def test_nothing_repeats(self):
        noise = [list("abcdefghijkl"), list("mnopqrstuvwx")]
        strip = extend.left_strip(noise)
        self.assertEqual(len(strip), 2)
        self.assertTrue(all(len(row) == len(strip[0]) for row in strip))


if __name__ == "__main__":
    unittest.main()
