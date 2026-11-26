"""Host tests of the Settings page's build side: rows from the modules'
`settings:` (daruma/__init__.py) and the app component (daruma_settings).

    python3 -m unittest discover -s tests
"""

import asyncio
import unittest

import esphome.config_validation as cv
import esphome.final_validate as fv
import esphome_components  # noqa: F401
from esphome.components import daruma
from esphome.components import daruma_settings as settings_app


class FakeVar:
    """A C++ variable: each method call comes back as (name, args)."""

    def __init__(self, name):
        self.name = name

    def __str__(self):
        return self.name

    def __getattr__(self, method):
        return lambda *args: (self.name, method, args)


class FakeCodegen:
    """The parts of esphome.codegen that to_code calls, recorded."""

    bool_ = "bool"

    def __init__(self):
        self.added, self.registered, self.lambdas = [], [], []

    def new_Pvariable(self, id_):  # noqa: N802 - ESPHome's name
        return FakeVar(id_)

    async def register_component(self, var, conf):
        self.registered.append((var.name, conf))

    async def get_variable(self, id_):
        return FakeVar(id_)

    async def process_lambda(self, value, args, return_type):
        self.lambdas.append((value, args, return_type))
        return f"lambda:{value}"

    @staticmethod
    def RawExpression(text):  # noqa: N802 - ESPHome's name
        return text

    def add(self, expression):
        self.added.append(expression)


def run_with(module, fake, coro_fn, *args):
    real = module.cg
    module.cg = fake
    try:
        asyncio.run(coro_fn(*args))
    finally:
        module.cg = real


def module_conf(name, rows):
    return {
        "name": name,
        "states": {},
        "actions": {},
        "apps": [],
        "progress": [],
        "theme": {"colors": {}, "words": {}, "aliases": {}},
        "bindings": {},
        "menu": False,
        "buttons": {},
        "menus": {},
        "areas": [],
        "targets": {},
        "settings": rows,
    }


SOUNDS = {"id": "sounds", "label": "Sounds", "icon": "S", "switch": "sounds_enabled", "held": "held()"}
DND = {"id": "dnd", "label": "Do not disturb", "icon": "D", "switch": "dnd_switch"}


class ModuleFromYaml(unittest.TestCase):
    def test_settings_are_the_row_ids_in_order(self):
        spec = daruma._module_from_yaml(module_conf("daruma", [SOUNDS, DND]))
        self.assertEqual(spec.settings, ["sounds", "dnd"])
        self.assertEqual(daruma._module_from_yaml(module_conf("x", [])).settings, [])


class SettingsToCode(unittest.TestCase):
    def emit(self, order):
        config = {"modules": [module_conf("daruma", [SOUNDS]), module_conf("dnd", [DND])], "settings": order}
        modules = [daruma._module_from_yaml(m) for m in config["modules"]]
        fake = FakeCodegen()
        run_with(daruma, fake, daruma._settings_to_code, FakeVar("hub"), config, modules)
        return fake

    def test_rows_in_page_order(self):
        fake = self.emit(["dnd"])
        on_dnd = "[]() { return dnd_switch->state; }"
        set_dnd = "[](bool on) { if (on) { dnd_switch->turn_on(); } else { dnd_switch->turn_off(); } }"
        on_sounds = "[]() { return sounds_enabled->state; }"
        set_sounds = "[](bool on) { if (on) { sounds_enabled->turn_on(); } else { sounds_enabled->turn_off(); } }"
        redraw = "[](bool) { hub->request_redraw(); }"
        self.assertEqual(
            fake.added,
            [
                ("hub", "add_setting", ("dnd", "Do not disturb", "D", on_dnd, set_dnd, "nullptr")),
                ("dnd_switch", "add_on_state_callback", (redraw,)),
                ("hub", "add_setting", ("sounds", "Sounds", "S", on_sounds, set_sounds, "lambda:held()")),
                ("sounds_enabled", "add_on_state_callback", (redraw,)),
            ],
        )
        # Only a row with `held` has a lambda, and it returns a bool.
        self.assertEqual(fake.lambdas, [("held()", [], "bool")])

    def test_module_order_without_a_list(self):
        fake = self.emit([])
        self.assertEqual([a[2][0] for a in fake.added if a[1] == "add_setting"], ["sounds", "dnd"])


class FinalValidate(unittest.TestCase):
    def test_unknown_setting_fails_the_build(self):
        conf = {"modules": [module_conf("daruma", [SOUNDS])], "settings": ["mute"]}
        token = fv.full_config.set({"daruma": conf})
        try:
            with self.assertRaisesRegex(cv.Invalid, "no included module offers a setting 'mute'"):
                daruma._final_validate(
                    {
                        **conf,
                        "theme": {},
                        "themes": {},
                        "menus": {},
                        "targets": {},
                        "navigation": {},
                        "bindings": {},
                        "inputs": [],
                        "apps": [],
                        "progress": {},
                        "random_events": False,
                    }
                )
        finally:
            fv.full_config.reset(token)


class SettingsApp(unittest.TestCase):
    def test_to_code_hands_the_hub_to_the_app(self):
        fake = FakeCodegen()
        conf = {"id": "settings_app", "daruma_id": "daruma_hub"}
        run_with(settings_app, fake, settings_app.to_code, conf)
        self.assertEqual(fake.registered, [("settings_app", conf)])
        self.assertEqual(len(fake.added), 1)
        name, method, args = fake.added[0]
        self.assertEqual((name, method), ("settings_app", "set_hub"))
        self.assertEqual(str(args[0]), "daruma_hub")


if __name__ == "__main__":
    unittest.main()
