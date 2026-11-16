"""Image persona: one picture per state, with optional blink/wink frames.

Pictures are named after states (any case: `Happy` serves `happy`). A
state without one shows its fallback's (daruma/registry.py), so an art
set can start with just a Neutral picture and grow. `behaviors:` can point
a state at another picture (daruma/persona.py). Pictures are PNG names in the
`art` folder (or paths, without one), stored compressed (daruma/sprite.py).
Each picture is drawn 1:1, centered on the stage; a larger screen shows the
picture's corner color around it (or `background`).
"""

import esphome.codegen as cg
from esphome.components.daruma import CONF_DARUMA_ID, Hub, Persona, daruma_ns
from esphome.components.daruma.persona import (
    BEHAVIORS_SCHEMA, CONF_BEHAVIORS, CONF_PARAMS, with_param_entities, persona, persona_to_code, params_schema)
from esphome.components.daruma.theme import CONF_THEME, THEME_SCHEMA, theme_to_code
from esphome.components.daruma.sounds import CONF_SOUNDS, SOUNDS_SCHEMA, sounds_to_code
from esphome.components.daruma.sprite import art_path, check_art, resolve_dir, resolve_file, sprite_expression
import esphome.config_validation as cv
from esphome.const import CONF_ID, CONF_NAME

DEPENDENCIES = ["daruma"]
MULTI_CONF = True

CONF_IMAGE = "image"
CONF_FRAMES = "frames"
CONF_BLINK = "blink"
CONF_WINK = "wink"
CONF_BACKGROUND = "background"
CONF_ART = "art"

ImagePersona = daruma_ns.class_("ImagePersona", cg.Component, Persona)

PARAMS = {}

FRAME_SCHEMA = cv.Any(
    cv.All(cv.string_strict, lambda value: {CONF_IMAGE: value}),
    cv.Schema(
        {
            cv.Required(CONF_IMAGE): cv.string_strict,
            cv.Optional(CONF_BLINK): cv.string_strict,
            cv.Optional(CONF_WINK): cv.string_strict,
        }
    ),
)


def _validate_frames(value):
    return cv.Schema({cv.string_strict: FRAME_SCHEMA})(value)


def _hex_color(value):
    value = cv.string_strict(value).lstrip("#")
    if len(value) != 6:
        raise cv.Invalid("Use a 6-digit hex color like 000000")
    return int(value, 16)


def _check_files(config):
    """Finds the pictures (resolve_file: next to the config, or next to the
    package that names them) and stores their absolute paths."""
    if CONF_ART in config:
        config[CONF_ART] = resolve_dir(config[CONF_ART])
    art = config.get(CONF_ART)
    for frame in config[CONF_FRAMES].values():
        for key in (CONF_IMAGE, CONF_BLINK, CONF_WINK):
            if key in frame:
                if art is None:
                    frame[key] = resolve_file(frame[key])
                check_art(art, frame[key])
    return config


CONFIG_SCHEMA = cv.All(cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(ImagePersona),
        cv.GenerateID(CONF_DARUMA_ID): cv.use_id(Hub),
        cv.Required(CONF_NAME): cv.string_strict,
        cv.Optional(CONF_THEME): THEME_SCHEMA,
        cv.Optional(CONF_SOUNDS): SOUNDS_SCHEMA,
        cv.Optional(CONF_BEHAVIORS, default={}): BEHAVIORS_SCHEMA,
        cv.Optional(CONF_PARAMS, default={}): params_schema(PARAMS),
        # Around the picture when the screen is larger. Default: the
        # picture's own top-left color.
        cv.Optional(CONF_BACKGROUND): _hex_color,
        cv.Optional(CONF_ART): cv.string_strict,
        cv.Required(CONF_FRAMES): _validate_frames,
    }
).extend(cv.COMPONENT_SCHEMA), _check_files, with_param_entities(PARAMS))


def daruma_personas(confs):
    """For the hub's final validation: each persona's pictures, theme and params."""
    return [(persona(c[CONF_ID].id, list(c[CONF_FRAMES]), c), c.get(CONF_THEME, {}), list(PARAMS)) for c in confs]


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID], config[CONF_NAME])
    await cg.register_component(var, config)
    if CONF_BACKGROUND in config:
        bg = config[CONF_BACKGROUND]
        cg.add(var.set_background((bg >> 16) & 0xFF, (bg >> 8) & 0xFF, bg & 0xFF))

    for key, frame in config[CONF_FRAMES].items():
        art = config.get(CONF_ART)
        main = sprite_expression(art_path(art, frame[CONF_IMAGE]))
        blink = sprite_expression(art_path(art, frame[CONF_BLINK])) if CONF_BLINK in frame else cg.nullptr
        wink = sprite_expression(art_path(art, frame[CONF_WINK])) if CONF_WINK in frame else cg.nullptr
        cg.add(var.add_frames(main, blink, wink))

    await theme_to_code(var, config)
    await sounds_to_code(var, config)
    hub = await cg.get_variable(config[CONF_DARUMA_ID])
    await persona_to_code(var, hub, persona(config[CONF_ID].id, list(config[CONF_FRAMES]), config), config,
                            PARAMS)
    cg.add(hub.add_persona(var))
