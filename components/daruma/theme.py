"""The `theme:` option that personas share: how the menu and apps look for them.

    theme:
      style: wood          # wood, paper or outline
      frame: "96623A"      # colors as 6-digit hex; any left out keep defaults
      ...
      icon_color: "00DCF0" # optional: one color for every app icon
      focus: "FFFFFF"      # optional: the focus ring on boards without touch (default: accent)
      info_line: bottom    # the info line (next calendar event): bottom, top or off
      mono:                # optional: colors for gray4 and mono screens, by the
        frame: "000000"    # keys above; the rest is derived from luminance
      apps:                # optional: an app under another name or icon
        care: { name: Coffee, icon: "\\U000F0176" }
      words:               # optional: other text for a module, by key
        calendar.today: "Heute"
      colors:              # optional: a module's colors, by key
        pomodoro.focus: "FF6347"

Module keys are declared by the module (`daruma: modules: theme:`) with
a default; the build stops on a key no included module declares. Old keys a
module keeps as `aliases:` still work (`pomodoro.tomato` sets
`pomodoro.done`).

The device yaml may set module colors and words too, for every persona
(`daruma: theme:`) or for one persona by its id (`daruma: themes:`).
For a module key, lowest first: the module's default, the persona's `theme:`,
the device's `theme:`, then the device's `themes: <persona id>`.

App icons are Material Design Icons code points; menu.yaml's icon font must
include every one used.
"""

import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.const import CONF_ID
from esphome.core import CORE, ID

from . import registry

daruma_ns = cg.esphome_ns.namespace("Daruma")
Theme = daruma_ns.class_("Theme")

CONF_THEME = "theme"
STYLES = {"outline": 0, "wood": 1, "paper": 2}
INFO_PLACES = {"bottom": 0, "top": 1, "off": 2}
COLORS = ("frame", "edge", "panel", "ink", "muted", "title", "accent", "dot", "dock", "dock_ink",
          "dock_muted", "icon_color", "focus")
CONF_MONO = "mono"


def _hex_color(value):
    value = cv.string_strict(value).lstrip("#")
    if len(value) != 6:
        raise cv.Invalid("Use a 6-digit hex color like 000000")
    return int(value, 16)


THEME_SCHEMA = cv.Schema(
    {
        cv.Optional("style", default="outline"): cv.one_of(*STYLES, lower=True),
        cv.Optional("info_line", default="bottom"): cv.one_of(*INFO_PLACES, lower=True),
        **{cv.Optional(key): _hex_color for key in COLORS},
        cv.Optional("apps", default={}): cv.Schema(
            {
                cv.string_strict: cv.Schema(
                    {
                        cv.Optional("name"): cv.string_strict,
                        cv.Optional("icon"): cv.string_strict,
                    }
                )
            }
        ),
        cv.Optional("words", default={}): cv.Schema({cv.string_strict: cv.string_strict}),
        cv.Optional("colors", default={}): cv.Schema({cv.string_strict: _hex_color}),
        cv.Optional(CONF_MONO, default={}): cv.Schema({cv.Optional(key): _hex_color for key in COLORS}),
    }
)

_count = [0]


def _device_overrides(persona_id: str) -> tuple[dict, dict]:
    """Module colors and words the device yaml sets for this persona: its
    `theme:` for every persona, then its `themes:` entry for this one."""
    hub = (CORE.config or {}).get("daruma") or {}
    colors, words = {}, {}
    for conf in (hub.get("theme") or {}, (hub.get("themes") or {}).get(persona_id) or {}):
        colors.update(conf.get("colors", {}))
        words.update(conf.get("words", {}))
    return colors, words


def _aliases() -> dict:
    # Imported here: the package's __init__ loads this file's users first.
    from . import collect_modules

    return registry.theme_aliases(collect_modules(CORE.config))


async def theme_to_code(persona, config):
    """Builds the persona's theme from its `theme:` option and the device's
    overrides, if there are any."""
    persona_id = config[CONF_ID].id
    dev_colors, dev_words = _device_overrides(persona_id)
    if CONF_THEME not in config and not dev_colors and not dev_words:
        return
    conf = THEME_SCHEMA(config.get(CONF_THEME) or {}) if CONF_THEME not in config else config[CONF_THEME]
    aliases = _aliases()
    # Lowest first: the persona's own, then the device's (theme:, then themes:).
    module_colors = {registry.resolve_theme_key(k, aliases): v for k, v in conf["colors"].items()}
    module_colors.update({registry.resolve_theme_key(k, aliases): v for k, v in dev_colors.items()})
    module_words = {registry.resolve_theme_key(k, aliases): v for k, v in conf["words"].items()}
    module_words.update({registry.resolve_theme_key(k, aliases): v for k, v in dev_words.items()})
    _count[0] += 1
    theme = cg.new_Pvariable(ID(f"daruma_theme_{_count[0]}", is_declaration=True, type=Theme))
    cg.add(theme.set_style(STYLES[conf["style"]]))
    if conf["info_line"] != "bottom":
        cg.add(theme.set_info_line(INFO_PLACES[conf["info_line"]]))
    for key in COLORS:
        if key in conf:
            cg.add(theme.set_color(key, conf[key]))
    for app_id, look in conf["apps"].items():
        cg.add(theme.set_app(app_id, look.get("name", ""), look.get("icon", "")))
    for key, text in module_words.items():
        cg.add(theme.set_word(key, text))
    for key, rgb in module_colors.items():
        cg.add(theme.set_module_color(key, rgb))
    for key, rgb in conf[CONF_MONO].items():
        cg.add(theme.set_mono_color(key, rgb))
    cg.add(persona.set_theme(theme))
