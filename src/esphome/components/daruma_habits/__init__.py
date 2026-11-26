"""Habits app: habits with plus and minus from a Home Assistant script.

The C++ side keeps the list and the scores on the way (habits.h) and draws
them. The package (packages/app_habits.yaml) calls the script through the
hub's gate. The script contract is generic; the blueprint "Daruma:
Habitica habits" makes one for Habitica.

The define USE_DARUMA_HABITS lets other modules hook into the app when it
is in the build: the habitica module adds its stats row and hears replies.
"""

import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components.daruma import CONF_DARUMA_ID, Hub, daruma_ns
from esphome.const import CONF_ID, CONF_TIMEOUT

DEPENDENCIES = ["api", "daruma", "font"]
# The script's replies arrive as JSON.
AUTO_LOAD = ["json"]

CONF_MAX_WAITING = "max_waiting"
CONF_PER_MINUTE = "per_minute"
CONF_MAX_ITEMS = "max_items"

HabitsApp = daruma_ns.class_("HabitsApp", cg.Component)

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(HabitsApp),
        cv.GenerateID(CONF_DARUMA_ID): cv.use_id(Hub),
        # Taps that may wait for HA; one more is dropped with a notice.
        cv.Required(CONF_MAX_WAITING): cv.int_range(min=1, max=20),
        # Scores the device sends in a minute at most.
        cv.Required(CONF_PER_MINUTE): cv.int_range(min=1, max=30),
        # Habits the device keeps.
        cv.Required(CONF_MAX_ITEMS): cv.int_range(min=1, max=50),
        # A score or fetch with no answer after this long fails.
        cv.Optional(CONF_TIMEOUT, default="10s"): cv.positive_time_period_milliseconds,
    }
).extend(cv.COMPONENT_SCHEMA)


async def to_code(config):
    cg.add_define("USE_DARUMA_HABITS")
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    cg.add(var.set_hub(await cg.get_variable(config[CONF_DARUMA_ID])))
    cg.add(var.set_limits(config[CONF_MAX_WAITING], config[CONF_PER_MINUTE], config[CONF_TIMEOUT]))
    cg.add(var.set_max_items(config[CONF_MAX_ITEMS]))
