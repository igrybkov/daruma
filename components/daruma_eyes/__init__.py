"""Eyes persona: animated eyes drawn from shapes (blink, glance, wink).

Its looks, which states find by name (daruma/persona.py): the moods
Neutral, Happy, Sad, Loved, Scared, Sleepy and Sleeping, plus listening
(eyes up), thinking (a glance aside) and focus (eyes down, as if reading).
Other states show their fallback's look.

Param `color` (choice): the eye color.
"""

import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components.daruma import CONF_DARUMA_ID, Hub, Persona, daruma_ns
from esphome.components.daruma.persona import (
    BEHAVIORS_SCHEMA, CONF_BEHAVIORS, CONF_PARAMS, with_param_entities, Param, persona, persona_to_code, params_schema)
from esphome.components.daruma.theme import CONF_THEME, THEME_SCHEMA, theme_to_code
from esphome.components.daruma.sounds import CONF_SOUNDS, SOUNDS_SCHEMA, sounds_to_code
from esphome.const import CONF_ID, CONF_NAME

DEPENDENCIES = ["daruma"]
MULTI_CONF = True

EyesPersona = daruma_ns.class_("EyesPersona", cg.Component, Persona)

# In the order of the eyes persona's look table (eye_reach.h).
LOOKS = ["Neutral", "Happy", "Sad", "Loved", "Scared", "Sleepy", "Sleeping", "listening", "thinking", "focus"]
# In the order of EyesPersona's color table.
PARAMS = {"color": Param("choice", "cyan", ["cyan", "green", "amber", "pink", "white"], icon="mdi:eye")}

CONFIG_SCHEMA = cv.All(cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(EyesPersona),
        cv.GenerateID(CONF_DARUMA_ID): cv.use_id(Hub),
        cv.Optional(CONF_NAME, default="Eyes"): cv.string_strict,
        cv.Optional(CONF_THEME): THEME_SCHEMA,
        cv.Optional(CONF_SOUNDS): SOUNDS_SCHEMA,
        cv.Optional(CONF_BEHAVIORS, default={}): BEHAVIORS_SCHEMA,
        cv.Optional(CONF_PARAMS, default={}): params_schema(PARAMS),
    }
).extend(cv.COMPONENT_SCHEMA), with_param_entities(PARAMS))


def daruma_personas(confs):
    """For the hub's final validation: each persona's looks, theme and params."""
    return [(persona(c[CONF_ID].id, LOOKS, c), c.get(CONF_THEME, {}), list(PARAMS)) for c in confs]


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID], config[CONF_NAME])
    await cg.register_component(var, config)
    await theme_to_code(var, config)
    await sounds_to_code(var, config)
    hub = await cg.get_variable(config[CONF_DARUMA_ID])
    await persona_to_code(var, hub, persona(config[CONF_ID].id, LOOKS, config), config, PARAMS)
    cg.add(hub.add_persona(var))
