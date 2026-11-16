"""Host test of the Daruma registry's build checks (no ESPHome needed).

    python3 -m unittest discover -s tests
"""

import importlib.util
from pathlib import Path
import sys
import unittest

_PATH = Path(__file__).resolve().parents[1] / "components" / "daruma" / "registry.py"
_SPEC = importlib.util.spec_from_file_location("daruma_registry", _PATH)
registry = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = registry  # Dataclasses look their module up here.
_SPEC.loader.exec_module(registry)

State, ModuleSpec, Persona, RegistryError = registry.State, registry.ModuleSpec, registry.Persona, registry.RegistryError

POMODORO = ModuleSpec(
    name="pomodoro",
    states=[
        State("focus", registry.ACTIVITY, "neutral", sound="start", module="pomodoro"),
        State("goal", registry.REACTION, "celebrate", sound="goal", duration_ms=3000, module="pomodoro"),
    ],
    actions=["pomodoro.toggle", "pomodoro.stop"],
    apps=["stats"],
    progress=["pomodoro"],
    colors={"focus": 0xFF6347},
    bindings={"screen.hold": "pomodoro.toggle", "knob.turn": "pomodoro.toggle"},
)
MENU = ModuleSpec(name="menu", actions=["menu.open"], bindings={"screen.tap": "menu.open"})
HUB = ModuleSpec(name="daruma", actions=["daruma.pet"], bindings={"screen.tap": "daruma.pet"})
MODULES = [HUB, MENU, POMODORO]
CORGI_ANIMS = ["Neutral", "Happy", "Sad", "Loved", "Scared", "Sleepy", "Sleeping", "listening", "thinking",
               "talking", "Focus"]


def inputs():
    return {
        "home": registry.Input("home", registry.BUTTON, ["press", "double", "hold"]),
        "screen": registry.Input("screen", registry.TOUCH,
                                 registry.expand_gestures(registry.TOUCH, ["tap", "hold", "swipe", "stroke"])),
    }


class States(unittest.TestCase):
    def test_module_states_follow_core_ones(self):
        states = registry.collect_states(MODULES)
        names = [s.name for s in states]
        self.assertEqual(names[0], "neutral")
        self.assertEqual(names[-2:], ["focus", "goal"])

    def test_module_state_needs_a_fallback(self):
        bad = ModuleSpec("tasks", states=[State("task_done", registry.REACTION, None, module="tasks")])
        with self.assertRaisesRegex(RegistryError, "needs a fallback"):
            registry.collect_states([bad])

    def test_fallback_must_exist(self):
        bad = ModuleSpec("tasks", states=[State("task_done", registry.REACTION, "celebrat", module="tasks")])
        with self.assertRaisesRegex(RegistryError, "celebrat"):
            registry.collect_states([bad])

    def test_duplicate_state(self):
        bad = ModuleSpec("x", states=[State("happy", registry.MOOD, "neutral", module="x")])
        with self.assertRaisesRegex(RegistryError, "already declares"):
            registry.collect_states([bad])


class Personas(unittest.TestCase):
    def setUp(self):
        self.states = registry.collect_states(MODULES)

    def test_focus_finds_its_animation_by_name(self):
        corgi = Persona("pixel_corgi", CORGI_ANIMS)
        behaviors, log = registry.resolve_persona(corgi, self.states)
        focus = behaviors[[s.name for s in self.states].index("focus")]
        self.assertEqual(CORGI_ANIMS[focus.animation], "Focus")
        self.assertEqual(focus.sound, "start")
        self.assertNotIn("pixel_corgi: focus -> neutral", log)

    def test_missing_state_falls_back_and_says_so(self):
        plain = Persona("plain", ["Neutral", "Happy"])
        behaviors, log = registry.resolve_persona(plain, self.states)
        self.assertIn("plain: focus -> neutral", log)
        self.assertIn("plain: goal -> happy", log)  # goal -> celebrate -> loved -> happy
        goal = behaviors[[s.name for s in self.states].index("goal")]
        self.assertEqual(goal.sound, "goal")  # The state's own sound, not the fallback's.

    def test_no_neutral_is_an_error(self):
        with self.assertRaisesRegex(RegistryError, "no look for 'neutral'"):
            registry.resolve_persona(Persona("broken", ["Happy"]), self.states)

    def test_unknown_state_in_behaviors(self):
        corgi = Persona("pixel_corgi", CORGI_ANIMS, behaviors={"focsu": {"animation": "Focus"}})
        with self.assertRaisesRegex(RegistryError, "unknown state 'focsu'"):
            registry.resolve_persona(corgi, self.states)

    def test_unknown_animation(self):
        corgi = Persona("pixel_corgi", CORGI_ANIMS, behaviors={"focus": {"animation": "Reading"}})
        with self.assertRaisesRegex(RegistryError, "animation 'Reading'"):
            registry.resolve_persona(corgi, self.states)

    def test_unknown_sound(self):
        corgi = Persona("pixel_corgi", CORGI_ANIMS, behaviors={"petted": {"sound": "woof"}})
        with self.assertRaisesRegex(RegistryError, "sound 'woof'"):
            registry.resolve_persona(corgi, self.states)
        corgi.sounds = ["woof"]
        registry.resolve_persona(corgi, self.states)  # Its own sound is fine.


class During(unittest.TestCase):
    """A reaction's look per activity under it (`during:`)."""

    def setUp(self):
        self.states = registry.collect_states(MODULES)
        self.anims = CORGI_ANIMS + ["LovedFocus"]

    def test_swap_names_the_activity_and_both_animations(self):
        char = Persona("daruma", self.anims, during={"focus": {"Loved": "LovedFocus"}})
        (swap,) = registry.resolve_during(char, self.states)
        self.assertEqual(self.states[swap.activity].name, "focus")
        self.assertEqual(self.anims[swap.shown], "Loved")
        self.assertEqual(self.anims[swap.instead], "LovedFocus")

    def test_none_by_default(self):
        self.assertEqual(registry.resolve_during(Persona("plain", self.anims), self.states), [])

    def test_only_an_activity(self):
        char = Persona("daruma", self.anims, during={"petted": {"Loved": "LovedFocus"}})
        with self.assertRaisesRegex(RegistryError, "only an activity"):
            registry.resolve_during(char, self.states)

    def test_unknown_state(self):
        char = Persona("daruma", self.anims, during={"focsu": {"Loved": "LovedFocus"}})
        with self.assertRaisesRegex(RegistryError, "unknown state 'focsu'"):
            registry.resolve_during(char, self.states)

    def test_unknown_animation(self):
        char = Persona("daruma", self.anims, during={"focus": {"Loved": "LovedReading"}})
        with self.assertRaisesRegex(RegistryError, "no animation 'LovedReading'"):
            registry.resolve_during(char, self.states)


class Bindings(unittest.TestCase):
    def setUp(self):
        self.inputs = inputs()
        self.nav = registry.check_navigation(self.inputs, {"back": "home.press", "close": "home.hold"})
        self.actions = registry.collect_actions(MODULES)

    def resolve(self, device):
        return registry.resolve_bindings(self.inputs, self.nav, device, MODULES, self.actions)

    def test_device_bindings_and_module_defaults(self):
        bindings, log = self.resolve({"home.press": {"action": "pomodoro.toggle", "when": "idle"}})
        by_trigger = {f"{b.input}.{b.gesture}": b for b in bindings}
        self.assertEqual(by_trigger["screen.tap"].action, "menu.open")  # Menu wins over the core default.
        self.assertEqual(by_trigger["screen.hold"].action, "pomodoro.toggle")
        self.assertTrue(any("knob.turn" in line and "skipped" in line for line in log))

    def test_missing_action(self):
        with self.assertRaisesRegex(RegistryError, "no included module offers"):
            self.resolve({"home.press": {"action": "pomodoro.togle", "when": "idle"}})

    def test_missing_input_or_gesture(self):
        with self.assertRaisesRegex(RegistryError, "no input 'knob'"):
            self.resolve({"knob.turn": {"action": "pomodoro.toggle"}})
        with self.assertRaisesRegex(RegistryError, "no gesture 'long_hold'"):
            self.resolve({"home.long_hold": {"action": "pomodoro.toggle"}})

    def test_navigation_input_needs_when_idle(self):
        with self.assertRaisesRegex(RegistryError, "when: idle"):
            self.resolve({"home.press": {"action": "pomodoro.toggle"}})

    def test_navigation_needs_back(self):
        with self.assertRaisesRegex(RegistryError, "needs `back`"):
            registry.check_navigation(self.inputs, {"close": "home.hold"})

    def test_buttons_only_board_needs_next_prev_select(self):
        buttons = {"a": registry.Input("a", registry.BUTTON, ["press", "double", "hold"])}
        with self.assertRaisesRegex(RegistryError, "next, prev, select"):
            registry.check_navigation(buttons, {"back": "a.hold"})

    def test_two_modules_bind_one_trigger(self):
        other = ModuleSpec("other", actions=["other.go"], bindings={"screen.tap": "other.go"})
        modules = MODULES + [other]
        with self.assertRaisesRegex(RegistryError, "both bind screen.tap"):
            registry.resolve_bindings(self.inputs, self.nav, {}, modules, registry.collect_actions(modules))
        # The device yaml settles it.
        registry.resolve_bindings(self.inputs, self.nav, {"screen.tap": {"action": "other.go"}}, modules,
                                  registry.collect_actions(modules))


class AppsProgressThemeParams(unittest.TestCase):
    def test_app_order(self):
        order, log = registry.order_apps(["stats"], MODULES + [ModuleSpec("tasks", apps=["tasks"])])
        self.assertEqual(order, ["stats", "tasks"])
        self.assertTrue(log)
        with self.assertRaisesRegex(RegistryError, "no included module offers an app 'calendar'"):
            registry.order_apps(["calendar"], MODULES)

    def test_app_copies(self):
        # Two copies of one app package, each with its own app_id: both on
        # the board, in the apps: order.
        modules = MODULES + [ModuleSpec("tasks", apps=["tasks"]), ModuleSpec("tasks_family", apps=["tasks_family"])]
        order, _ = registry.order_apps(["tasks_family", "stats", "tasks"], modules)
        self.assertEqual(order, ["tasks_family", "stats", "tasks"])

    def test_app_copies_with_one_id(self):
        # The same app_id twice: the module names clash first, and two
        # modules offering one app fail on their own too.
        twice = [ModuleSpec("tasks", apps=["tasks"]), ModuleSpec("tasks", apps=["tasks"])]
        with self.assertRaisesRegex(RegistryError, "own app_id"):
            registry.check_modules(MODULES + twice)
        clash = [ModuleSpec("tasks", apps=["tasks"]), ModuleSpec("tasks_family", apps=["tasks"])]
        with self.assertRaisesRegex(RegistryError, "Two modules offer the app 'tasks'"):
            registry.order_apps([], MODULES + clash)

    def test_progress_sources(self):
        self.assertEqual(registry.check_progress({}, MODULES), ["pomodoro"])
        with self.assertRaisesRegex(RegistryError, "progress: no included module feeds"):
            registry.check_progress({"tasks": 1}, MODULES)

    def test_theme_keys(self):
        registry.check_theme_keys("corgi", {"pomodoro.focus": 1}, {}, MODULES)
        with self.assertRaisesRegex(RegistryError, "not one of pomodoro's"):
            registry.check_theme_keys("corgi", {"pomodoro.fokus": 1}, {}, MODULES)
        with self.assertRaisesRegex(RegistryError, "no included module is named 'calendar'"):
            registry.check_theme_keys("corgi", {}, {"calendar.today": "Heute"}, MODULES)

    def test_param_clash(self):
        registry.check_params([("pixel_corgi", "rug"), ("eyes", "rug")])
        with self.assertRaisesRegex(RegistryError, "pixel_corgi.rug"):
            registry.check_params([("pixel_corgi", "rug"), ("pixel_corgi", "rug")])

    def test_action_names(self):
        with self.assertRaisesRegex(RegistryError, "must start with 'pomodoro.'"):
            registry.collect_actions([ModuleSpec("pomodoro", actions=["menu.open"])])


def menu_modules():
    pomo = ModuleSpec(
        "pomodoro", actions=["pomodoro.toggle", "pomodoro.stop", "pomodoro.break"], apps=["stats"], menu=True,
        buttons={"pomodoro.break": {"label": "Break", "icon": "x", "color": "pomodoro.break"}},
        bindings={"home.press": "menu.open:pomodoro"}, menus={"pomodoro": ["pomodoro", "pomodoro.break"]})
    return [HUB, ModuleSpec("menu", actions=["menu.open"], bindings={"screen.tap": "menu.open"}), pomo,
            ModuleSpec("tasks", apps=["tasks"]), ModuleSpec("tasks_family", apps=["tasks_family"]),
            ModuleSpec("calendar", apps=["calendar"])]


def resolve(device=None, modules=None):
    modules = modules or menu_modules()
    menus, _ = registry.collect_menus(device, modules)
    return registry.resolve_menus(menus, modules, registry.collect_actions(modules))


def kinds(items):
    return [(i.kind, i.id) for i in items]


class Menus(unittest.TestCase):
    def test_default_main(self):
        menus = resolve()
        # Pomodoro has its own menu on a button, so main leaves it out.
        self.assertEqual(kinds(menus["main"]), [("app", "tasks"), ("app", "calendar"), ("more", "")])

    def test_default_main_keeps_modules_without_a_menu(self):
        mods = menu_modules() + [ModuleSpec("lights", menu=True)]
        menus = resolve(modules=mods)
        self.assertEqual(kinds(menus["main"]), [("module", "lights"), ("app", "tasks"), ("app", "calendar"),
                                                ("more", "")])

    def test_module_menu_is_a_default(self):
        menus = resolve()
        self.assertEqual(kinds(menus["pomodoro"]), [("module", "pomodoro"), ("action", "pomodoro.break")])
        self.assertEqual(menus["pomodoro"][1].label, "Break")
        self.assertEqual(menus["pomodoro"][1].color, "pomodoro.break")

    def test_device_wins_per_name(self):
        menus = resolve({"pomodoro": ["pomodoro"], "main": ["calendar", "more"]})
        self.assertEqual(kinds(menus["pomodoro"]), [("module", "pomodoro")])
        self.assertEqual(kinds(menus["main"]), [("app", "calendar"), ("more", "")])

    def test_two_modules_offering_one_menu(self):
        mods = menu_modules() + [ModuleSpec("other", menus={"pomodoro": ["stats"]})]
        with self.assertRaisesRegex(RegistryError, "both offer the menu 'pomodoro'"):
            registry.collect_menus({}, mods)
        menus, log = registry.collect_menus({"pomodoro": ["stats"]}, mods)
        self.assertEqual(menus["pomodoro"], ["stats"])
        self.assertTrue(any("replaces" in line for line in log))

    def test_app_copy_nested_menu_and_event(self):
        menus = resolve({"quick": ["tasks_family", "main", {"label": "Lights", "icon": "y", "event": "lights"}]})
        self.assertEqual(kinds(menus["quick"]), [("app", "tasks_family"), ("menu", "main"), ("event", "lights")])
        self.assertNotIn(("more", ""), kinds(menus["quick"]))  # Only main gets More by itself.

    def test_app_wins_over_module_of_its_name(self):
        mods = menu_modules()
        mods[-1] = ModuleSpec("calendar", apps=["calendar"], menu=True)
        self.assertEqual(kinds(resolve({"main": ["calendar"]}, mods)["main"])[0], ("app", "calendar"))

    def test_unknown_item(self):
        with self.assertRaisesRegex(RegistryError, "'calender' is no app, module with buttons, menu or action"):
            resolve({"main": ["calender"]})

    def test_module_without_buttons(self):
        with self.assertRaisesRegex(RegistryError, "'daruma' is no app"):
            resolve({"main": ["daruma"]})

    def test_action_without_a_look(self):
        with self.assertRaisesRegex(RegistryError, "'pomodoro.stop' has no button look"):
            resolve({"main": ["pomodoro.stop"]})

    def test_unknown_action(self):
        with self.assertRaisesRegex(RegistryError, "no included module offers the action 'pomodoro.snooze'"):
            resolve({"main": ["pomodoro.snooze"]})

    def test_listed_twice(self):
        with self.assertRaisesRegex(RegistryError, "listed twice"):
            resolve({"main": ["tasks", "tasks"]})

    def test_menu_lists_itself(self):
        with self.assertRaisesRegex(RegistryError, "lists itself"):
            resolve({"quick": ["quick"]})

    def test_menu_named_like_its_module(self):
        # `pomodoro` in the menu `pomodoro` is the module's buttons, not the menu itself.
        self.assertEqual(kinds(resolve()["pomodoro"])[0], ("module", "pomodoro"))

    def test_event_button_needs_its_keys(self):
        with self.assertRaisesRegex(RegistryError, "needs icon"):
            resolve({"main": [{"label": "Lights", "event": "lights"}]})

    def test_buttons_must_be_own_actions(self):
        mods = menu_modules() + [ModuleSpec("x", actions=["x.go"], buttons={"pomodoro.stop": {"label": "S", "icon": "s"}})]
        with self.assertRaisesRegex(RegistryError, "not one of its actions"):
            resolve({}, mods)

    def test_menus_need_the_menu(self):
        with self.assertRaisesRegex(RegistryError, "need the menu"):
            registry.check_menus_included({"quick": ["stats"]}, [POMODORO])
        registry.check_menus_included({}, [POMODORO])  # Module defaults alone are fine.


class MenuBindings(unittest.TestCase):
    def setUp(self):
        self.inputs = inputs()
        self.nav = registry.check_navigation(self.inputs, {"back": "home.press", "close": "home.hold"})
        self.mods = menu_modules()
        self.actions = registry.collect_actions(self.mods)
        self.menus, _ = registry.collect_menus({"quick": ["stats"]}, self.mods)

    def bind(self, device):
        return {(b.input, b.gesture): b for b in registry.resolve_bindings(
            self.inputs, self.nav, device, self.mods, self.actions, self.menus)[0]}

    def test_module_default_opens_its_menu(self):
        b = self.bind({})[("home", "press")]
        self.assertEqual((b.action, b.idle, b.source), ("menu.open:pomodoro", True, "pomodoro"))

    def test_device_binding_with_a_menu(self):
        b = self.bind({"home.double": {"action": "menu.open", "menu": "quick"}})[("home", "double")]
        self.assertEqual(b.action, "menu.open:quick")

    def test_device_overrides_the_default(self):
        b = self.bind({"home.press": {"action": "pomodoro.toggle", "when": "idle"}})[("home", "press")]
        self.assertEqual(b.action, "pomodoro.toggle")

    def test_unknown_menu(self):
        with self.assertRaisesRegex(RegistryError, "the menu 'qiuck', which is not defined"):
            self.bind({"home.double": {"action": "menu.open", "menu": "qiuck"}})

    def test_menu_only_with_menu_open(self):
        with self.assertRaisesRegex(RegistryError, "goes only with the action menu.open"):
            self.bind({"home.double": {"action": "pomodoro.stop", "menu": "quick"}})

    def test_default_skipped_without_the_menu(self):
        mods = [m for m in self.mods if m.name != "menu"]
        bindings, log = registry.resolve_bindings(self.inputs, self.nav, {}, mods, registry.collect_actions(mods), {})
        self.assertNotIn(("home", "press"), {(b.input, b.gesture) for b in bindings})
        self.assertTrue(any("no module 'menu' is included" in line for line in log))


# --- Tap areas and device themes ---------------------------------------------------

POMO_AREA = ModuleSpec(name="pomodoro", actions=["pomodoro.toggle"], apps=["stats"], areas=["plaque"],
                       targets={"plaque": {"app": "stats"}}, colors={"done": 1, "pending": 2},
                       words={"ready": "Ready"}, aliases={"tomato": "done"})
CORE_AREA = ModuleSpec(name="daruma", actions=["daruma.pet"], areas=["badge"])
WEATHER = ModuleSpec(name="weather", apps=["weather"], targets={"badge": {"app": "weather"}})
MENU_MOD = ModuleSpec(name="menu", actions=["menu.open", "menu.app"])


class Targets(unittest.TestCase):
    def resolve(self, device=None, modules=None, menus=("main",)):
        modules = modules if modules is not None else [CORE_AREA, MENU_MOD, POMO_AREA, WEATHER]
        return registry.resolve_targets(device or {}, modules, registry.collect_actions(modules), menus)

    def test_module_defaults(self):
        targets, log = self.resolve()
        self.assertEqual(targets, {"plaque": "menu.app:stats", "badge": "menu.app:weather"})
        self.assertTrue(any("a tap on 'badge' runs menu.app:weather" in line for line in log))

    def test_device_wins(self):
        targets, _ = self.resolve({"plaque": {"menu": "main"}, "badge": "none"})
        self.assertEqual(targets, {"plaque": "menu.open:main", "badge": "none"})

    def test_device_action(self):
        targets, _ = self.resolve({"plaque": {"action": "pomodoro.toggle"}})
        self.assertEqual(targets["plaque"], "pomodoro.toggle")

    def test_unknown_area(self):
        with self.assertRaisesRegex(RegistryError, "no included module draws an area 'clock'.*badge, plaque"):
            self.resolve({"clock": {"app": "stats"}})

    def test_unknown_app_menu_or_action(self):
        with self.assertRaisesRegex(RegistryError, "opens the app 'radio'"):
            self.resolve({"plaque": {"app": "radio"}})
        with self.assertRaisesRegex(RegistryError, "opens the menu 'quick'"):
            self.resolve({"plaque": {"menu": "quick"}})
        with self.assertRaisesRegex(RegistryError, "runs 'pomodoro.dance'"):
            self.resolve({"plaque": {"action": "pomodoro.dance"}})

    def test_apps_need_the_menu(self):
        with self.assertRaisesRegex(RegistryError, "needs the menu"):
            self.resolve({"plaque": {"app": "stats"}}, modules=[CORE_AREA, POMO_AREA])
        # A module's default is skipped instead, and logged.
        targets, log = self.resolve(modules=[CORE_AREA, POMO_AREA])
        self.assertEqual(targets, {})
        self.assertTrue(any("default target for 'plaque' skipped" in line for line in log))

    def test_default_for_an_area_nobody_draws(self):
        targets, log = self.resolve(modules=[MENU_MOD, POMO_AREA, WEATHER])
        self.assertNotIn("badge", targets)
        self.assertTrue(any("no included module draws it" in line for line in log))

    def test_first_default_wins(self):
        other = ModuleSpec(name="radio", apps=["radio"], targets={"badge": {"app": "radio"}})
        targets, log = self.resolve(modules=[CORE_AREA, MENU_MOD, WEATHER, other])
        self.assertEqual(targets["badge"], "menu.app:weather")
        self.assertTrue(any("radio: default target for 'badge'" in line and "came first" in line for line in log))


class DeviceThemes(unittest.TestCase):
    def test_keys_and_personas(self):
        registry.check_device_themes({"colors": {"pomodoro.done": 1}, "words": {"pomodoro.ready": "Go"}},
                                     {"eyes": {"colors": {"pomodoro.pending": 2}}}, ["eyes"], [POMO_AREA])

    def test_unknown_persona(self):
        with self.assertRaisesRegex(RegistryError, "no persona has the id 'eye'.*eyes"):
            registry.check_device_themes({}, {"eye": {"colors": {}}}, ["eyes", "daruma"], [POMO_AREA])

    def test_unknown_key(self):
        with self.assertRaisesRegex(RegistryError, "theme color 'pomodoro.ripe' is not one of pomodoro's"):
            registry.check_device_themes({"colors": {"pomodoro.ripe": 1}}, {}, [], [POMO_AREA])
        with self.assertRaisesRegex(RegistryError, "themes: daruma: theme word 'pomodoro.go'"):
            registry.check_device_themes({}, {"daruma": {"words": {"pomodoro.go": "x"}}}, ["daruma"], [POMO_AREA])

    def test_old_keys_still_work(self):
        registry.check_theme_keys("eyes", {"pomodoro.tomato": 1}, {}, [POMO_AREA])
        aliases = registry.theme_aliases([POMO_AREA])
        self.assertEqual(registry.resolve_theme_key("pomodoro.tomato", aliases), "pomodoro.done")
        self.assertEqual(registry.resolve_theme_key("pomodoro.pending", aliases), "pomodoro.pending")

    def test_alias_to_nothing(self):
        bad = ModuleSpec(name="pomodoro", colors={"done": 1}, aliases={"tomato": "ripe"})
        with self.assertRaisesRegex(RegistryError, "alias 'tomato' points at 'ripe'"):
            registry.theme_aliases([bad])

if __name__ == "__main__":
    unittest.main()
