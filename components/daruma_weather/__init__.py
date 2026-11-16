"""Weather app: today's report from a Home Assistant weather entity.

The C++ side keeps the report, decides when to fetch, parses the replies
and draws. The package (daruma/app_weather.yaml) registers the app and
does the fetching with `homeassistant.action` (weather.get_forecasts, hourly
and daily). One entry per copy of the app, so the package can be included
more than once.
"""

import esphome.codegen as cg
from esphome.components import time as time_
from esphome.components.daruma import CONF_DARUMA_ID, Hub, daruma_ns
import esphome.config_validation as cv
from esphome.const import CONF_ID, CONF_TIME_ID, CONF_TIMEOUT

DEPENDENCIES = ["api", "daruma", "font", "time"]
# The fetch replies arrive as JSON.
AUTO_LOAD = ["json"]
MULTI_CONF = True

CONF_REFRESH_INTERVAL = "refresh_interval"

WeatherApp = daruma_ns.class_("WeatherApp", cg.Component)

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(WeatherApp),
        cv.GenerateID(CONF_DARUMA_ID): cv.use_id(Hub),
        # The clock for "now" and the hours. Use the time synced from HA.
        cv.Required(CONF_TIME_ID): cv.use_id(time_.RealTimeClock),
        # How often the report is fetched again while the app stays open.
        cv.Optional(CONF_REFRESH_INTERVAL, default="30min"): cv.positive_time_period_milliseconds,
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
