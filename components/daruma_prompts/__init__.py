"""Prompts: full-screen cards that Home Assistant shows, updates and closes.

    daruma_prompts:
      id: prompts
      title_font: font_prompt_title
      text_font: font_small
      hold_back_during: [focus]    # info prompts wait while one of these activities runs
      on_answer:                   # prompt_id, choice, index, reason
        - homeassistant.event: ...
      on_shown:                    # prompt_id, style, sound ("" for none); the sound plays by itself
        - light.turn_on: ...

The API actions and the answer event are wired in daruma/prompts.yaml.
As a module it offers prompts.dismiss and the theme colors prompts.*.
"""

import logging

import esphome.automation as automation
import esphome.codegen as cg
from esphome.components import font
from esphome.components.daruma import CONF_DARUMA_ID, Hub, collect_modules, daruma_ns, state_id
from esphome.components.daruma import registry
from esphome.components.daruma.registry import ModuleSpec
import esphome.config_validation as cv
from esphome.const import CONF_ID
from esphome.core import CORE
import esphome.final_validate as fv

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ["daruma", "font"]

CONF_TITLE_FONT = "title_font"
CONF_TEXT_FONT = "text_font"
CONF_HOLD_BACK_DURING = "hold_back_during"
CONF_ON_ANSWER = "on_answer"
CONF_ON_SHOWN = "on_shown"

PromptController = daruma_ns.class_("PromptController", cg.Component)

DARUMA_MODULE = ModuleSpec(
    name="prompts",
    actions=["prompts.dismiss"],
    colors={
        "urgent": 0xE53935,     # Border, title and countdown of urgent prompts.
        "game": 0x7E57C2,       # Border of game prompts.
        "countdown": 0xF2A33A,  # The countdown bar.
        "selected": 0xF2A33A,   # The answer just chosen.
        "correct": 0x2E9E44,
        "wrong": 0xD23C3C,
    },
)

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(PromptController),
        cv.GenerateID(CONF_DARUMA_ID): cv.use_id(Hub),
        cv.Required(CONF_TITLE_FONT): cv.use_id(font.Font),
        cv.Required(CONF_TEXT_FONT): cv.use_id(font.Font),
        cv.Optional(CONF_HOLD_BACK_DURING, default=["focus"]): cv.ensure_list(cv.string_strict),
        cv.Optional(CONF_ON_ANSWER): automation.validate_automation({}),
        cv.Optional(CONF_ON_SHOWN): automation.validate_automation({}),
    }
).extend(cv.COMPONENT_SCHEMA)


def _hold_back_states(config, states) -> list[str]:
    """The hold_back_during states in this build. A name no included module
    declares is skipped (the build log says so); one that is not an activity
    is an error."""
    by_name = {s.name: s for s in states}
    out = []
    for name in config[CONF_HOLD_BACK_DURING]:
        state = by_name.get(name)
        if state is None:
            _LOGGER.info("prompts: hold_back_during: no state '%s' in this build; skipped", name)
            continue
        if state.kind != registry.ACTIVITY:
            raise cv.Invalid(f"hold_back_during: '{name}' is a {state.kind}, not an activity")
        out.append(name)
    return out


def _final_validate(config):
    full = fv.full_config.get()
    try:
        states = registry.collect_states(collect_modules(full))
    except registry.RegistryError as err:
        raise cv.Invalid(str(err)) from err
    _hold_back_states(config, states)


FINAL_VALIDATE_SCHEMA = _final_validate


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    cg.add(var.set_fonts(await cg.get_variable(config[CONF_TITLE_FONT]),
                         await cg.get_variable(config[CONF_TEXT_FONT])))
    states = registry.collect_states(collect_modules(CORE.config))
    for name in _hold_back_states(config, states):
        cg.add(var.add_hold_back(state_id(name)))
    for conf in config.get(CONF_ON_ANSWER, []):
        await automation.build_callback_automation(
            var, "add_on_answer_callback",
            [(cg.std_string, "prompt_id"), (cg.std_string, "choice"), (cg.int_, "index"), (cg.std_string, "reason")],
            conf)
    for conf in config.get(CONF_ON_SHOWN, []):
        await automation.build_callback_automation(
            var, "add_on_shown_callback",
            [(cg.std_string, "prompt_id"), (cg.std_string, "style"), (cg.std_string, "sound")],
            conf)
    # The hub sets its modules up before the first draw.
    cg.add((await cg.get_variable(config[CONF_DARUMA_ID])).add_module(var))
