"""Habitica module: the hero's stats from Home Assistant, reactions to them,
and the Character app.

The C++ side subscribes to the Habitica integration's entities, so HA
pushes every change; nothing polls. The stats model (habitica.h) turns the
numbers into reactions. A button on the sheet runs the package's press
script (packages/habitica.yaml). The package builds the entity ids from its
`user` var; this component only takes full ids.
"""

import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components.daruma import CONF_DARUMA_ID, Hub, daruma_ns
from esphome.const import CONF_ID

DEPENDENCIES = ["api", "daruma", "font"]

CONF_STATS = "stats"
CONF_BUTTONS = "buttons"
CONF_HP_MAX = "hp_max"
CONF_HURT_THRESHOLD = "hurt_threshold"
CONF_MESSAGE_SECONDS = "message_seconds"

# The entities the sheet follows, by the field name habitica.h knows.
STATS = ["health", "max_health", "experience", "next_level", "mana", "max_mana", "level", "class", "gold", "inn"]
# The HA buttons the sheet offers, in the order it shows them. Each shows
# only while its entity is available.
BUTTONS = ["potion", "start_day", "revive", "allocate"]

HabiticaApp = daruma_ns.class_("HabiticaApp", cg.Component)

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(HabiticaApp),
        cv.GenerateID(CONF_DARUMA_ID): cv.use_id(Hub),
        cv.Required(CONF_STATS): cv.Schema({cv.Optional(name): cv.entity_id for name in STATS}),
        cv.Required(CONF_BUTTONS): cv.Schema({cv.Optional(name): cv.entity_id for name in BUTTONS}),
        # Habitica's max HP, until a score reply says otherwise. HA has no sensor for it.
        cv.Required(CONF_HP_MAX): cv.positive_float,
        # HP lost in one change that plays `hurt`.
        cv.Required(CONF_HURT_THRESHOLD): cv.positive_float,
        # How long a drop's or a quest's words stay in the bubble.
        cv.Required(CONF_MESSAGE_SECONDS): cv.int_range(min=1, max=60),
    }
).extend(cv.COMPONENT_SCHEMA)


async def to_code(config):
    # The sheet follows HA states and presses HA buttons.
    cg.add_define("USE_API_HOMEASSISTANT_STATES")
    cg.add_define("USE_API_HOMEASSISTANT_SERVICES")
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    cg.add(var.set_hub(await cg.get_variable(config[CONF_DARUMA_ID])))
    cg.add(var.set_hp_max(config[CONF_HP_MAX]))
    cg.add(var.set_hurt_threshold(config[CONF_HURT_THRESHOLD]))
    cg.add(var.set_message_seconds(config[CONF_MESSAGE_SECONDS]))
    for field in STATS:
        if field in config[CONF_STATS]:
            cg.add(var.follow(field, config[CONF_STATS][field]))
    for key in BUTTONS:
        if key in config[CONF_BUTTONS]:
            cg.add(var.add_button(key, config[CONF_BUTTONS][key]))
