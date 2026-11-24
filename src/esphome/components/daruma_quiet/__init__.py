"""Quiet hours, Do not disturb and the idle screen.

    daruma_quiet:
      id: quiet
      quiet_hours: { start: "22:00", end: "07:00" }  # first values of the time entities
      quiet_brightness: 0%     # the screen in quiet hours (0: off)
      wake_for: 30s            # a tap or a button wakes it this long
      idle_brightness: 30%     # the screen after "Dim after" with nothing on it
      dnd_during: [focus]      # HA messages also wait during these activities
      dnd_keep: 12h            # a card that waited longer drops
      dnd_release: 5           # at most this many wait; the oldest go first

The entities and their ids are wired in packages/quiet.yaml. The first
value of "Dim after" is that package's `quiet_dim_after` (minutes). As a module it
offers quiet.dnd and the theme color quiet.dnd.
"""

import logging

import esphome.codegen as cg
import esphome.config_validation as cv
import esphome.final_validate as fv
from esphome.components import datetime, light, number, switch, time
from esphome.components.daruma import CONF_DARUMA_ID, Hub, collect_modules, daruma_ns, registry, state_id
from esphome.components.daruma.registry import ModuleSpec
from esphome.const import CONF_ID
from esphome.core import CORE

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ["daruma", "light", "switch", "time", "datetime", "number"]

CONF_SCREEN = "screen"
CONF_SOUNDS = "sounds"
CONF_CLOCK = "clock"
CONF_DND_SWITCH = "dnd_switch"
CONF_START_TIME = "start_time"
CONF_END_TIME = "end_time"
CONF_DIM_AFTER_NUMBER = "dim_after_number"
CONF_QUIET_HOURS = "quiet_hours"
CONF_START = "start"
CONF_END = "end"
CONF_QUIET_BRIGHTNESS = "quiet_brightness"
CONF_IDLE_BRIGHTNESS = "idle_brightness"
CONF_WAKE_FOR = "wake_for"
CONF_DND_DURING = "dnd_during"
CONF_DND_KEEP = "dnd_keep"
CONF_DND_RELEASE = "dnd_release"

QuietComponent = daruma_ns.class_("QuietComponent", cg.Component)

DARUMA_MODULE = ModuleSpec(
    name="quiet",
    actions=["quiet.dnd"],
    colors={
        "dnd": 0x7E57C2,  # The Do not disturb mark on the info line.
    },
)


def _clock_time(value):
    """ "HH:MM" as (hour, minute)."""
    value = cv.string_strict(value)
    try:
        hour, minute = (int(p) for p in value.split(":"))
    except ValueError:
        raise cv.Invalid(f"'{value}': give a time as HH:MM") from None
    if not (0 <= hour < 24 and 0 <= minute < 60):
        raise cv.Invalid(f"'{value}': give a time as HH:MM, 00:00 to 23:59")
    return (hour, minute)


CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(QuietComponent),
        cv.GenerateID(CONF_DARUMA_ID): cv.use_id(Hub),
        cv.Required(CONF_SCREEN): cv.use_id(light.LightState),
        cv.Required(CONF_SOUNDS): cv.use_id(switch.Switch),
        cv.Required(CONF_CLOCK): cv.use_id(time.RealTimeClock),
        cv.Required(CONF_DND_SWITCH): cv.use_id(switch.Switch),
        cv.Required(CONF_START_TIME): cv.use_id(datetime.TimeEntity),
        cv.Required(CONF_END_TIME): cv.use_id(datetime.TimeEntity),
        cv.Required(CONF_DIM_AFTER_NUMBER): cv.use_id(number.Number),
        cv.Optional(CONF_QUIET_HOURS, default={}): cv.Schema(
            {
                cv.Optional(CONF_START, default="22:00"): _clock_time,
                cv.Optional(CONF_END, default="07:00"): _clock_time,
            }
        ),
        cv.Optional(CONF_QUIET_BRIGHTNESS, default="0%"): cv.percentage,
        cv.Optional(CONF_IDLE_BRIGHTNESS, default="30%"): cv.percentage,
        cv.Optional(CONF_WAKE_FOR, default="30s"): cv.positive_time_period_milliseconds,
        cv.Optional(CONF_DND_DURING, default=["focus"]): cv.ensure_list(cv.string_strict),
        cv.Optional(CONF_DND_KEEP, default="12h"): cv.positive_time_period_milliseconds,
        cv.Optional(CONF_DND_RELEASE, default=5): cv.int_range(min=0, max=8),
    }
).extend(cv.COMPONENT_SCHEMA)


def _dnd_states(config, states) -> list[str]:
    """The dnd_during states in this build. A name no included module
    declares is skipped (the build log says so); one that is not an activity
    is an error."""
    by_name = {s.name: s for s in states}
    out = []
    for name in config[CONF_DND_DURING]:
        state = by_name.get(name)
        if state is None:
            _LOGGER.info("quiet: dnd_during: no state '%s' in this build; skipped", name)
            continue
        if state.kind != registry.ACTIVITY:
            raise cv.Invalid(f"dnd_during: '{name}' is a {state.kind}, not an activity")
        out.append(name)
    return out


def _final_validate(config):
    full = fv.full_config.get()
    try:
        states = registry.collect_states(collect_modules(full))
    except registry.RegistryError as err:
        raise cv.Invalid(str(err)) from err
    _dnd_states(config, states)


FINAL_VALIDATE_SCHEMA = _final_validate


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    cg.add(var.set_screen(await cg.get_variable(config[CONF_SCREEN])))
    cg.add(var.set_sounds(await cg.get_variable(config[CONF_SOUNDS])))
    cg.add(var.set_clock(await cg.get_variable(config[CONF_CLOCK])))
    cg.add(var.set_dnd_switch(await cg.get_variable(config[CONF_DND_SWITCH])))
    start = await cg.get_variable(config[CONF_START_TIME])
    end = await cg.get_variable(config[CONF_END_TIME])
    cg.add(var.set_quiet_times(start, end))
    # The options are the entities' first values; HA changes them later.
    for entity, (hour, minute) in (
        (start, config[CONF_QUIET_HOURS][CONF_START]),
        (end, config[CONF_QUIET_HOURS][CONF_END]),
    ):
        cg.add(
            entity.set_initial_value(
                cg.StructInitializer(cg.ESPTime, ("second", 0), ("minute", minute), ("hour", hour))
            )
        )
    cg.add(var.set_dim_after(await cg.get_variable(config[CONF_DIM_AFTER_NUMBER])))
    cg.add(var.set_quiet_brightness(config[CONF_QUIET_BRIGHTNESS]))
    cg.add(var.set_idle_brightness(config[CONF_IDLE_BRIGHTNESS]))
    cg.add(var.set_wake_for(config[CONF_WAKE_FOR].total_milliseconds))
    cg.add(var.set_limits(config[CONF_DND_RELEASE], config[CONF_DND_KEEP].total_milliseconds))
    states = registry.collect_states(collect_modules(CORE.config))
    for name in _dnd_states(config, states):
        cg.add(var.add_dnd_during(state_id(name)))
    # The hub sets its modules up before the first draw.
    cg.add((await cg.get_variable(config[CONF_DARUMA_ID])).add_module(var))
