"""Settings app: a page of switches the modules offer.

A module adds a row with `settings:` in its `daruma: modules:` entry (see
daruma/__init__.py); the hub keeps them in page order. This component only
draws them and flips them. The package (daruma/app_settings.yaml) registers
the app.
"""

import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components.daruma import CONF_DARUMA_ID, Hub, daruma_ns
from esphome.const import CONF_ID

DEPENDENCIES = ["daruma", "font"]

SettingsApp = daruma_ns.class_("SettingsApp", cg.Component)

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(SettingsApp),
        cv.GenerateID(CONF_DARUMA_ID): cv.use_id(Hub),
    }
).extend(cv.COMPONENT_SCHEMA)


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    cg.add(var.set_hub(await cg.get_variable(config[CONF_DARUMA_ID])))
