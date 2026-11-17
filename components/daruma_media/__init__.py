"""Media app: a remote for the Home Assistant media players in the device's room.

The C++ side keeps the players, decides when to fetch, parses the replies,
draws and sends the buttons' commands. The package (daruma/app_media.yaml)
registers the app and does the fetching and the commands with
`homeassistant.action`, and loads the cover into an online_image. One entry
per copy of the app, so the package can be included more than once.
"""

import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components.daruma import CONF_DARUMA_ID, Hub, daruma_ns
from esphome.const import CONF_ID, CONF_TIMEOUT

DEPENDENCIES = ["api", "daruma", "font"]
# The fetch replies arrive as JSON.
AUTO_LOAD = ["json"]
MULTI_CONF = True

CONF_REFRESH_INTERVAL = "refresh_interval"
CONF_IDLE_REFRESH = "idle_refresh"
CONF_COMMAND_REFRESH = "command_refresh"
CONF_HOLD = "hold"
CONF_VOLUME_STEP = "volume_step"
CONF_COVER_SIZE = "cover_size"
CONF_HA_PORT = "ha_port"

MediaApp = daruma_ns.class_("MediaApp", cg.Component)

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(MediaApp),
        cv.GenerateID(CONF_DARUMA_ID): cv.use_id(Hub),
        # How often the players are fetched again while the app is open.
        cv.Optional(CONF_REFRESH_INTERVAL, default="5s"): cv.All(
            cv.positive_time_period_milliseconds, cv.Range(min=cv.TimePeriod(seconds=1))
        ),
        # How often while it is closed, for the board's tile and the
        # buttons in menus; 0s fetches only while open.
        cv.Optional(CONF_IDLE_REFRESH, default="60s"): cv.positive_time_period_milliseconds,
        # A fetch this long after a button, to show what HA made of it.
        cv.Optional(CONF_COMMAND_REFRESH, default="1s"): cv.positive_time_period_milliseconds,
        # How long the screen keeps what a button expects while HA catches up.
        cv.Optional(CONF_HOLD, default="3s"): cv.positive_time_period_milliseconds,
        # A fetch with no reply after this long counts as failed.
        cv.Optional(CONF_TIMEOUT, default="10s"): cv.positive_time_period_milliseconds,
        # One press of louder or quieter, on HA's volume scale of 0 to 1.
        cv.Optional(CONF_VOLUME_STEP, default=0.05): cv.float_range(min=0.01, max=0.5),
        # The cover's box, in screen pixels: the online_image's resize.
        cv.Optional(CONF_COVER_SIZE, default=96): cv.int_range(min=32, max=320),
        # HA's port, for its address when the HA URL setting is empty.
        cv.Optional(CONF_HA_PORT, default=8123): cv.port,
    }
).extend(cv.COMPONENT_SCHEMA)


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    cg.add(var.set_hub(await cg.get_variable(config[CONF_DARUMA_ID])))
    cg.add(var.set_refresh_interval(config[CONF_REFRESH_INTERVAL]))
    cg.add(var.set_idle_refresh(config[CONF_IDLE_REFRESH]))
    cg.add(var.set_command_refresh(config[CONF_COMMAND_REFRESH]))
    cg.add(var.set_hold(config[CONF_HOLD]))
    cg.add(var.set_timeout(config[CONF_TIMEOUT]))
    cg.add(var.set_volume_step(config[CONF_VOLUME_STEP]))
    cg.add(var.set_cover_size(config[CONF_COVER_SIZE]))
    cg.add(var.set_ha_port(config[CONF_HA_PORT]))
