"""Calendar app: Home Assistant calendar events on the app board, as an
agenda of the days ahead and a view of one day.

The C++ side keeps the agenda (which also feeds the board's status line)
and at most one more day, for a day view outside it. The package
(daruma/app_calendar.yaml) registers the app and does the fetching with
`homeassistant.action`; this component decides when to fetch, parses the
replies and draws. One entry per copy of the app, so the package can be
included more than once.
"""

import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import time as time_
from esphome.components.daruma import CONF_DARUMA_ID, Hub, daruma_ns
from esphome.const import CONF_ID, CONF_TIME_ID, CONF_TIMEOUT

DEPENDENCIES = ["api", "daruma", "font", "time"]
# The fetch replies arrive as JSON.
AUTO_LOAD = ["json"]
MULTI_CONF = True

CONF_REFRESH_INTERVAL = "refresh_interval"

CalendarApp = daruma_ns.class_("CalendarApp", cg.Component)

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(CalendarApp),
        cv.GenerateID(CONF_DARUMA_ID): cv.use_id(Hub),
        # "Today" and the clock for the now marker. Use the time synced from HA.
        cv.Required(CONF_TIME_ID): cv.use_id(time_.RealTimeClock),
        # How often the agenda is fetched again, for the status line too.
        cv.Optional(CONF_REFRESH_INTERVAL, default="15min"): cv.positive_time_period_milliseconds,
        # A fetch with no reply after this long counts as failed.
        cv.Optional(CONF_TIMEOUT, default="10s"): cv.positive_time_period_milliseconds,
    }
).extend(cv.COMPONENT_SCHEMA)


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    cg.add(var.set_hub(await cg.get_variable(config[CONF_DARUMA_ID])))
    cg.add(var.set_clock(await cg.get_variable(config[CONF_TIME_ID])))
    cg.add(var.set_refresh_interval(config[CONF_REFRESH_INTERVAL]))
    cg.add(var.set_timeout(config[CONF_TIMEOUT]))
