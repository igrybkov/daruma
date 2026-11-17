"""Tasks app data for Daruma: today's tasks from Home Assistant.

The list itself comes from HA actions that the app package runs
(daruma/app_tasks.yaml); this component keeps it, cleans titles for the
font, tracks check-offs and their timeouts. TaskView (task_view.h) draws it.
The source entity is set at run time (TaskList::set_source).

One entry per copy of the Tasks app, so the package can be included more
than once. The reaction states are declared here, once for all copies.
"""

import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import font
from esphome.components.daruma import daruma_ns
from esphome.components.daruma.registry import REACTION, ModuleSpec, State
from esphome.const import CONF_FONT, CONF_ID, CONF_TIMEOUT

DEPENDENCIES = ["api", "daruma", "font"]
AUTO_LOAD = ["json"]
MULTI_CONF = True

DARUMA_MODULE = ModuleSpec(
    name="daruma_tasks",
    states=[
        # A task checked off, and the last one of the day.
        State("task_done", REACTION, "celebrate", sound="pet", duration_ms=2000, module="daruma_tasks"),
        State("tasks_done", REACTION, "celebrate", sound="goal", duration_ms=3000, module="daruma_tasks"),
    ],
)

TaskList = daruma_ns.class_("TaskList", cg.Component)

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(TaskList),
        # The font task titles are drawn in. Titles lose the glyphs it lacks.
        cv.Required(CONF_FONT): cv.use_id(font.Font),
        # How long to wait for HA before a fetch fails or a check-off is undone.
        cv.Optional(CONF_TIMEOUT, default="10s"): cv.positive_time_period_milliseconds,
    }
).extend(cv.COMPONENT_SCHEMA)


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    cg.add(var.set_font(await cg.get_variable(config[CONF_FONT])))
    cg.add(var.set_timeout(config[CONF_TIMEOUT]))
