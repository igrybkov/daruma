"""Touch menu: a dock over the persona, an app board, and full-screen apps.

Buttons come from the hub's named menus (`daruma: menus:`), apps from
Hub::add_app; the
current persona's theme sets the look (daruma/theme.py). As a module it
offers menu.open, menu.app (`menu.app:<id>` opens one app), menu.back and
menu.close, and binds a tap and an upward
swipe on the screen to menu.open unless the device yaml binds them.
"""

import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import font
from esphome.components.daruma import CONF_DARUMA_ID, Hub, daruma_ns
from esphome.components.daruma.registry import ModuleSpec
from esphome.const import CONF_ID, CONF_TIMEOUT

DEPENDENCIES = ["daruma", "font"]

CONF_TEXT_FONT = "text_font"
CONF_SMALL_FONT = "small_font"
CONF_ICON_FONT = "icon_font"
CONF_APP_TIMEOUT = "app_timeout"
CONF_NEXT_LABEL = "next_label"

MenuController = daruma_ns.class_("MenuController", cg.Component)

DARUMA_MODULE = ModuleSpec(
    name="menu",
    actions=["menu.open", "menu.app", "menu.back", "menu.close"],
    bindings={"screen.tap": "menu.open", "screen.swipe_up": "menu.open"},
)

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(MenuController),
        cv.GenerateID(CONF_DARUMA_ID): cv.use_id(Hub),
        cv.Required(CONF_TEXT_FONT): cv.use_id(font.Font),
        cv.Required(CONF_SMALL_FONT): cv.use_id(font.Font),
        cv.Required(CONF_ICON_FONT): cv.use_id(font.Font),
        # The dock closes after this long without a touch; the board and apps after app_timeout.
        cv.Optional(CONF_TIMEOUT, default="10s"): cv.positive_time_period_milliseconds,
        cv.Optional(CONF_APP_TIMEOUT, default="60s"): cv.positive_time_period_milliseconds,
        # The button that pages to the rest of a menu with more than five items.
        cv.Optional(CONF_NEXT_LABEL, default="Next"): cv.string_strict,
    }
).extend(cv.COMPONENT_SCHEMA)


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    cg.add(
        var.set_fonts(
            await cg.get_variable(config[CONF_TEXT_FONT]),
            await cg.get_variable(config[CONF_SMALL_FONT]),
            await cg.get_variable(config[CONF_ICON_FONT]),
        )
    )
    cg.add(var.set_timeout(config[CONF_TIMEOUT]))
    cg.add(var.set_app_timeout(config[CONF_APP_TIMEOUT]))
    cg.add(var.set_next_label(config[CONF_NEXT_LABEL]))
    # The hub sets its modules up before the first draw.
    cg.add((await cg.get_variable(config[CONF_DARUMA_ID])).add_module(var))
