"""Host tests of the Controls app's build checks: tile domains, icon names,
and icons missing from the icon font (daruma_controls/__init__.py).

    python3 -m unittest discover -s tests
"""

import re
import unittest
from pathlib import Path

import esphome.config_validation as cv
import esphome.final_validate as fv
import esphome_components  # noqa: F401
from esphome.components import daruma_controls as controls

ROOT = Path(__file__).resolve().parents[1]

ICON_FONT = "font_icons"


def font(*names, extra=()):
    """A font config with these icons' glyphs, and an extra with more."""
    conf = {"id": ICON_FONT, "file": "mdi.ttf", "glyphs": [controls.glyph(n) for n in names]}
    if extra:
        conf["extras"] = [{"glyphs": [controls.glyph(n) for n in extra]}]
    return conf


def config(*tiles):
    return {"icon_font": ICON_FONT, "tiles": list(tiles)}


class TileEntity(unittest.TestCase):
    def test_known_domains(self):
        for entity in ["light.desk", "switch.kettle", "fan.desk", "input_boolean.guests", "scene.movie"]:
            self.assertEqual(controls.tile_entity(entity), entity)
        for entity in ["script.night", "media_player.office", "cover.blinds", "sensor.co2"]:
            self.assertEqual(controls.tile_entity(entity), entity)

    def test_unknown_domain_names_the_kinds(self):
        with self.assertRaisesRegex(cv.Invalid, r"can't show a climate entity; it takes light, switch"):
            controls.tile_entity("climate.office")

    def test_not_an_entity_id(self):
        with self.assertRaises(cv.Invalid):
            controls.tile_entity("desk lamp")

    def test_every_domain_has_a_known_icon(self):
        for name in controls.DEFAULT_ICONS.values():
            self.assertIn(name, controls.ICONS)


class IconName(unittest.TestCase):
    def test_with_and_without_prefix(self):
        self.assertEqual(controls.icon_name("mdi:movie"), "movie")
        self.assertEqual(controls.icon_name("movie"), "movie")

    def test_unknown_icon_lists_the_known(self):
        with self.assertRaisesRegex(cv.Invalid, r"Unknown tile icon 'mdi:rocket'; known: mdi:air-purifier, "):
            controls.icon_name("mdi:rocket")

    def test_tile_icon_falls_back_to_the_domain(self):
        self.assertEqual(controls.tile_icon({"entity": "light.desk"}), "lightbulb")
        self.assertEqual(controls.tile_icon({"entity": "light.desk", "icon": "lamp"}), "lamp")
        self.assertEqual(controls.tile_icon({"entity": "cover.blinds"}), "window-shutter")

    def test_label_falls_back_to_the_entity_name(self):
        self.assertEqual(controls.tile_label({"entity": "light.desk_lamp"}), "Desk lamp")
        self.assertEqual(controls.tile_label({"entity": "light.desk_lamp", "label": "Desk"}), "Desk")

    def test_glyph(self):
        self.assertEqual(controls.glyph("check"), "\U000f012c")


class IconsInTheFont(unittest.TestCase):
    def test_all_there(self):
        conf = config({"entity": "light.desk"}, {"entity": "scene.movie", "icon": "movie"})
        controls.check_icons(conf, [font("lightbulb", "movie", "check")])

    def test_glyphs_in_one_string_and_extras_count(self):
        fonts = [{"id": ICON_FONT, "glyphs": [controls.glyph("lightbulb") + controls.glyph("check")]}]
        controls.check_icons(config({"entity": "light.desk"}), fonts)
        controls.check_icons(config({"entity": "fan.desk"}), [font("check", extra=["fan"])])

    def test_missing_icon_names_the_line_to_add(self):
        with self.assertRaisesRegex(cv.Invalid, r'Icon \'mdi:fan\' is not in the font .*"\\U000F0210"  # fan'):
            controls.check_icons(config({"entity": "fan.desk"}), [font("check")])

    def test_the_check_mark_is_needed_too(self):
        with self.assertRaisesRegex(cv.Invalid, "mdi:check"):
            controls.check_icons(config({"entity": "light.desk"}), [font("lightbulb")])

    def test_another_font_is_not_checked(self):
        other = {"id": "font_other", "glyphs": []}
        controls.check_icons(config({"entity": "fan.desk"}), [other])

    def test_final_validate_reads_the_fonts_of_the_whole_config(self):
        token = fv.full_config.set({"font": [font("palette", "check")]})
        try:
            with self.assertRaisesRegex(cv.Invalid, "mdi:fan"):
                controls._final_validate(config({"entity": "fan.desk"}))
            with self.assertRaisesRegex(cv.Invalid, "mdi:fan"):
                controls._final_validate(
                    [config({"entity": "scene.movie", "icon": "palette"}), config({"entity": "fan.desk"})]
                )
        finally:
            fv.full_config.reset(token)
        token = fv.full_config.set({"font": [font("fan", "check")]})
        try:
            controls._final_validate([config({"entity": "fan.desk"})])
        finally:
            fv.full_config.reset(token)

    def test_menu_font_has_every_icon(self):
        # menu.yaml's icon font lists every icon a tile may name.
        text = (ROOT / "packages" / "menu.yaml").read_text()
        have = {int(h, 16) for h in re.findall(r'"\\U000(F[0-9A-F]{4})"', text)}
        missing = [n for n, code in controls.ICONS.items() if code not in have]
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
