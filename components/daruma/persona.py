"""Options every persona (persona component) shares: behaviors and params.

    behaviors:                    # optional: what the persona does per state
      focus:     { animation: Focus }
      celebrate: { animation: Happy, sound: goal }
      petted:    { animation: Loved, sound: pet, say: "Woof!" }
    params:                       # optional: things only this persona has
      rug: plain                  # or { value: plain, expose: true }
    during:                       # optional: reaction looks per activity
      focus: { Loved: LovedFocus }  # petted during focus keeps the incense

A state left out uses the animation named like it (any case), else its
fallback's (registry.py). `during:` swaps the animation a reaction plays
while an activity is on underneath, so the activity's props stay. The final validation step checks every name. A
param is named with the persona id as a prefix (`pixel_corgi.rug`); with
`expose: true` it is also a device setting in HA ("Pixel corgi rug"), or
with `name:` too, under that name (`{ value: weekday, expose: true, name:
throw }`: "Jack Russell throw").
"""

import esphome.codegen as cg
from esphome.components import select, switch
import esphome.config_validation as cv
from esphome.const import CONF_NAME

from . import registry, states_for_build
from .registry import RegistryError

CONF_BEHAVIORS = "behaviors"
CONF_ANIMATION = "animation"
CONF_SOUND = "sound"
CONF_SAY = "say"
CONF_PARAMS = "params"
CONF_VALUE = "value"
CONF_EXPOSE = "expose"
CONF_DURING = "during"

daruma_ns = cg.esphome_ns.namespace("Daruma")
ParamSelect = daruma_ns.class_("ParamSelect", select.Select, cg.Component)
ParamSwitch = daruma_ns.class_("ParamSwitch", switch.Switch, cg.Component)

BEHAVIOR_SCHEMA = cv.Schema(
    {
        cv.Optional(CONF_ANIMATION): cv.string_strict,
        cv.Optional(CONF_SOUND): cv.string_strict,
        cv.Optional(CONF_SAY): cv.string,
    }
)
BEHAVIORS_SCHEMA = cv.Schema({cv.string_strict: BEHAVIOR_SCHEMA})
# activity state -> {animation a reaction would play: the one to play instead}
DURING_SCHEMA = cv.Schema({cv.string_strict: cv.Schema({cv.string_strict: cv.string_strict})})


class Param:
    """A persona param: `choice` (options, default) or `bool` (default)."""

    def __init__(self, kind: str, default, options=None, icon="mdi:tune"):
        self.kind = kind
        self.default = default
        self.options = options or []
        self.icon = icon

    def validate(self, value):
        if self.kind == "bool":
            return cv.boolean(value)
        return cv.one_of(*self.options, lower=True)(value)

    def as_int(self, value) -> int:
        return int(bool(value)) if self.kind == "bool" else self.options.index(value)


def params_schema(declared: dict[str, Param]):
    """The `params:` option for a persona component that declares these params."""

    def validate(value):
        if not isinstance(value, dict):
            raise cv.Invalid("params: a map of param name to a value, or to {value, expose}")
        out = {}
        for name, conf in value.items():
            if name not in declared:
                raise cv.Invalid(f"No param '{name}' here (params: {', '.join(declared) or 'none'})")
            if not isinstance(conf, dict):
                conf = {CONF_VALUE: conf}
            param = declared[name]
            with cv.prepend_path(name):
                out[name] = cv.Schema(
                    {
                        cv.Optional(CONF_VALUE, default=param.default): param.validate,
                        cv.Optional(CONF_EXPOSE, default=False): cv.boolean,
                        # What the HA entity calls it, if not the param's name:
                        # a persona whose `rug` is a throw says `name: throw`.
                        cv.Optional(CONF_NAME): cv.string_strict,
                    }
                )(conf)
        return out

    return validate


CONF_ENTITY = "entity"


def with_param_entities(declared: dict[str, Param]):
    """A persona config validator: every exposed param gets its HA entity config
    ("<persona name> <param>", or the param's `name:`), so its id is declared like any other."""

    def validate(config):
        for name, conf in config.get(CONF_PARAMS, {}).items():
            if not conf[CONF_EXPOSE]:
                continue
            param = declared[name]
            label = conf.get(CONF_NAME, name.replace("_", " "))
            entity = {CONF_NAME: f"{config[CONF_NAME]} {label}"}
            if param.kind == "bool":
                conf[CONF_ENTITY] = switch.switch_schema(
                    ParamSwitch, entity_category="config", icon=param.icon,
                    default_restore_mode="RESTORE_DEFAULT_ON" if param.default else "RESTORE_DEFAULT_OFF",
                )(entity)
            else:
                conf[CONF_ENTITY] = select.select_schema(ParamSelect, entity_category="config", icon=param.icon)(entity)
        return config

    return validate


def persona(persona_id: str, animations: list[str], config) -> registry.Persona:
    return registry.Persona(
        id=persona_id,
        animations=list(animations),
        behaviors={k: dict(v) for k, v in config.get(CONF_BEHAVIORS, {}).items()},
        sounds=list(config.get("sounds", {})),
        during={k: dict(v) for k, v in config.get(CONF_DURING, {}).items()},
    )


async def persona_to_code(var, hub, char: registry.Persona, config, declared: dict[str, Param]):
    """The persona's behavior table (one per state, in StateId order) and its params."""
    try:
        states = states_for_build()
        behaviors, _ = registry.resolve_persona(char, states)
    except RegistryError as err:  # Final validation already said so; keep codegen honest.
        raise cv.Invalid(str(err)) from err
    items = ", ".join(
        f"Daruma::Behavior{{{b.animation}, {cg.safe_exp(b.sound)}, {cg.safe_exp(b.say)}, "
        f"{'true' if b.shown_as == state.name else 'false'}}}"
        for b, state in zip(behaviors, states)
    )
    cg.add(var.set_behaviors(cg.RawExpression(f"std::vector<Daruma::Behavior>{{{items}}}")))
    try:
        during = registry.resolve_during(char, states)
    except RegistryError as err:
        raise cv.Invalid(str(err)) from err
    for d in during:
        cg.add(var.add_during(cg.RawExpression(f"static_cast<Daruma::StateId>({d.activity})"), d.shown, d.instead))

    params = config.get(CONF_PARAMS, {})
    for name, param in declared.items():
        conf = params.get(name, {CONF_VALUE: param.default, CONF_EXPOSE: False})
        cg.add(var.add_param(name, param.as_int(conf[CONF_VALUE])))
        if not conf[CONF_EXPOSE]:
            continue
        entity = conf[CONF_ENTITY]
        if param.kind == "bool":
            sw = await switch.new_switch(entity, hub, var, name)
            await cg.register_component(sw, entity)
        else:
            sel = await select.new_select(entity, hub, var, name, options=param.options)
            await cg.register_component(sel, entity)
