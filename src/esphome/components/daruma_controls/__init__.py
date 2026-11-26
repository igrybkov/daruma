"""Controls app: a grid of Home Assistant entities with their live state.

Each tile is one entity. Its domain picks what a tap does and what the
tile shows (controls.h). The C++ side subscribes to the entity's state and
one attribute, so HA pushes every change; nothing polls. A tap runs the
package's action script (daruma/app_controls.yaml).

One entry per copy of the app, so the package can be included more than
once. The build checks every tile: a known domain, a known icon name, and
that icon in the icon font.
"""

import esphome.codegen as cg
import esphome.config_validation as cv
import esphome.final_validate as fv
from esphome.components import font
from esphome.components.daruma import CONF_DARUMA_ID, Hub, daruma_ns
from esphome.const import CONF_GLYPHS, CONF_ICON, CONF_ID

DEPENDENCIES = ["api", "daruma", "font"]
MULTI_CONF = True

CONF_LABEL = "label"
CONF_TILES = "tiles"
CONF_ICON_FONT = "icon_font"
CONF_ENTITY = "entity"
CONF_EXTRAS = "extras"

# Material Design Icons by name, the ones a tile may use. Each must also be
# in the icon font (menu.yaml lists them).
ICONS = {
    "air-purifier": 0xF0D44,
    "blinds": 0xF00AC,
    "ceiling-light": 0xF0769,
    "check": 0xF012C,
    "coffee-maker": 0xF109F,
    "curtains": 0xF1846,
    "fan": 0xF0210,
    "flash": 0xF0241,
    "garage": 0xF06D9,
    "gauge": 0xF029A,
    "home": 0xF02DC,
    "lamp": 0xF06B5,
    "leaf": 0xF032A,
    "led-strip-variant": 0xF1051,
    "lightbulb": 0xF0335,
    "lightbulb-group": 0xF1253,
    "molecule-co2": 0xF07E4,
    "movie": 0xF0381,
    "music": 0xF075A,
    "palette": 0xF03D8,
    "power": 0xF0425,
    "power-plug": 0xF06A5,
    "robot-vacuum": 0xF070D,
    "script-text-play": 0xF1727,
    "speaker": 0xF04C3,
    "television": 0xF0502,
    "thermometer": 0xF050F,
    "toggle-switch": 0xF0521,
    "water-percent": 0xF058E,
    "window-shutter": 0xF111C,
}

# The tile kinds by domain, and each domain's icon when a tile names none.
DEFAULT_ICONS = {
    "light": "lightbulb",
    "switch": "power-plug",
    "fan": "fan",
    "input_boolean": "toggle-switch",
    "scene": "palette",
    "script": "script-text-play",
    "media_player": "music",
    "cover": "window-shutter",
    "sensor": "gauge",
}

# The glyph a scene or script tile shows for a moment after a tap.
CHECK_ICON = "check"

ControlsApp = daruma_ns.class_("ControlsApp", cg.Component)


def domain(entity: str) -> str:
    return entity.split(".", 1)[0]


def tile_entity(value):
    value = cv.entity_id(value)
    if domain(value) not in DEFAULT_ICONS:
        kinds = ", ".join(DEFAULT_ICONS)
        raise cv.Invalid(f"'{value}': a tile can't show a {domain(value)} entity; it takes {kinds}")
    return value


def icon_name(value):
    value = cv.string_strict(value)
    name = value.removeprefix("mdi:")
    if name not in ICONS:
        raise cv.Invalid(f"Unknown tile icon '{value}'; known: {', '.join('mdi:' + n for n in sorted(ICONS))}")
    return name


def tile_icon(tile) -> str:
    """The icon name a tile shows: its own, or its domain's."""
    return tile.get(CONF_ICON) or DEFAULT_ICONS[domain(tile[CONF_ENTITY])]


def tile_label(tile) -> str:
    """A tile's label: its own, or the entity's name part ("Desk lamp")."""
    return tile.get(CONF_LABEL) or tile[CONF_ENTITY].split(".", 1)[1].replace("_", " ").capitalize()


def glyph(name: str) -> str:
    return chr(ICONS[name])


TILE_SCHEMA = cv.Schema(
    {
        cv.Required(CONF_ENTITY): tile_entity,
        # Short: it is cut to the tile's width. Default: the entity's name part.
        cv.Optional(CONF_LABEL): cv.string_strict,
        cv.Optional(CONF_ICON): icon_name,
    }
)

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(ControlsApp),
        cv.GenerateID(CONF_DARUMA_ID): cv.use_id(Hub),
        # The Material Design Icons font the tiles' icons come from.
        cv.Required(CONF_ICON_FONT): cv.use_id(font.Font),
        cv.Required(CONF_TILES): cv.All(cv.ensure_list(TILE_SCHEMA), cv.Length(min=1)),
    }
).extend(cv.COMPONENT_SCHEMA)


def font_glyphs(font_conf) -> set[str]:
    """Every glyph a font config lists, its extras' included."""
    strings = list(font_conf.get(CONF_GLYPHS, []))
    for extra in font_conf.get(CONF_EXTRAS, []):
        strings += extra.get(CONF_GLYPHS, [])
    return {ch for s in strings for ch in s}


def check_icons(config, fonts) -> None:
    """Fails when a tile's icon, or the check mark, is not in the icon font."""
    font_id = str(config[CONF_ICON_FONT])
    font_conf = next((f for f in fonts if str(f.get(CONF_ID)) == font_id), None)
    if font_conf is None:
        return
    have = font_glyphs(font_conf)
    names = [tile_icon(t) for t in config[CONF_TILES]] + [CHECK_ICON]
    for name in dict.fromkeys(names):
        if glyph(name) not in have:
            raise cv.Invalid(
                f"Icon 'mdi:{name}' is not in the font '{font_id}'. "
                f'Add it to the font\'s glyphs: - "\\U{ICONS[name]:08X}"  # {name}'
            )


def _final_validate(config):
    fonts = fv.full_config.get().get("font", [])
    for conf in config if isinstance(config, list) else [config]:
        check_icons(conf, fonts)


FINAL_VALIDATE_SCHEMA = _final_validate


async def to_code(config):
    # The tiles subscribe to HA states and call HA actions.
    cg.add_define("USE_API_HOMEASSISTANT_STATES")
    cg.add_define("USE_API_HOMEASSISTANT_SERVICES")
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    cg.add(var.set_hub(await cg.get_variable(config[CONF_DARUMA_ID])))
    cg.add(var.set_check_icon(glyph(CHECK_ICON)))
    for tile in config[CONF_TILES]:
        cg.add(var.add_tile(tile[CONF_ENTITY], tile_label(tile), glyph(tile_icon(tile))))
