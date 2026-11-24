"""Options every persona (persona component) shares: behaviors and params.

    behaviors:                    # optional: what the persona does per state
      focus:     { animation: Focus }
      celebrate: { animation: Happy, sound: goal }
      petted:    { animation: Loved, sound: pet, say: "Woof!" }
    params:                       # optional: things only this persona has
      rug: plain                  # or { value: plain, expose: true }
    during:                       # optional: reaction looks per activity
      focus: { Loved: LovedFocus }  # petted during focus keeps the incense
    random_events:                # optional: quirks now and then (random_events.py)
      lick_paw: { animation: LickPaw, frequency: 9 }

A state left out uses the animation named like it (any case), else its
fallback's (registry.py). `during:` swaps the animation a reaction plays
while an activity is on underneath, so the activity's props stay. The final validation step checks every name. A
param is named with the persona id as a prefix (`pixel_corgi.rug`); with
`expose: true` it is also a device setting in HA ("Pixel corgi rug"), or
with `name:` too, under that name (`{ value: weekday, expose: true, name:
throw }`: "Jack Russell throw").
"""

import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import select, switch
from esphome.const import CONF_NAME

from . import random_events, registry, states_for_build
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

CONF_RANDOM_EVENTS = "random_events"


def _when(value):
    """Checks the conditions and keeps them as written; codegen parses them again."""
    try:
        random_events.parse_when(value)
    except RegistryError as err:
        raise cv.Invalid(str(err)) from err
    return value


EVENT_SCHEMA = cv.Schema(
    {
        cv.Optional(random_events.CONF_ANIMATION): cv.string_strict,
        cv.Optional(random_events.CONF_ENTER): cv.string_strict,
        cv.Optional(random_events.CONF_EXIT): cv.string_strict,
        cv.Optional(random_events.CONF_FOR): cv.All(
            cv.positive_time_period_milliseconds,
            cv.Range(min=cv.TimePeriod(seconds=5), max=cv.TimePeriod(hours=2)),
        ),
        cv.Optional(random_events.CONF_SAY): cv.All(cv.ensure_list(cv.string), cv.Length(min=1, max=8)),
        cv.Optional(random_events.CONF_SOUND): cv.string_strict,
        cv.Optional(random_events.CONF_FREQUENCY, default=random_events.DEFAULT_FREQUENCY): cv.int_range(min=1, max=10),
        cv.Optional(random_events.CONF_COOLDOWN): cv.All(
            cv.positive_time_period_seconds,
            cv.Range(min=cv.TimePeriod(minutes=1), max=cv.TimePeriod(days=366)),
        ),
        cv.Optional(random_events.CONF_WHEN, default={}): _when,
    }
)


def _events_schema(say_only: bool):
    """name -> event, each with its shape checked."""

    def validate(value):
        if not isinstance(value, dict):
            raise cv.Invalid("random_events: a map of event name to event")
        out = {}
        for name, conf in value.items():
            with cv.prepend_path(name):
                event = EVENT_SCHEMA(conf)
                try:
                    if say_only:
                        registry.check_say_only(f"random_events: {name}", event)
                    random_events.check_shape(name, event)
                except RegistryError as err:
                    raise cv.Invalid(str(err)) from err
                out[name] = event
        return out

    return validate


# The device's change to one event (`daruma: random_events: personas:`):
# only the keys it names, so no defaults; random_events.merge_pool fills
# them in for a new event.
_EVENT_OVERRIDE_SCHEMA = cv.Schema({cv.Optional(str(key)): value for key, value in EVENT_SCHEMA.schema.items()})


def event_override(value):
    """`false` drops the event; a map changes or adds one."""
    return False if value is False else _EVENT_OVERRIDE_SCHEMA(value)


RANDOM_EVENTS_SCHEMA = _events_schema(say_only=False)
# The images persona has one picture per state, so its events only say and sound.
SAY_ONLY_EVENTS_SCHEMA = _events_schema(say_only=True)


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
                    ParamSwitch,
                    entity_category="config",
                    icon=param.icon,
                    default_restore_mode="RESTORE_DEFAULT_ON" if param.default else "RESTORE_DEFAULT_OFF",
                )(entity)
            else:
                conf[CONF_ENTITY] = select.select_schema(ParamSelect, entity_category="config", icon=param.icon)(entity)
        return config

    return validate


def persona(persona_id: str, animations: list[str], config, event_animations: bool = True) -> registry.Persona:
    return registry.Persona(
        id=persona_id,
        animations=list(animations),
        behaviors={k: dict(v) for k, v in config.get(CONF_BEHAVIORS, {}).items()},
        sounds=list(config.get("sounds", {})),
        during={k: dict(v) for k, v in config.get(CONF_DURING, {}).items()},
        random_events={k: dict(v) for k, v in config.get(CONF_RANDOM_EVENTS, {}).items()},
        event_animations=event_animations,
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
        for b, state in zip(behaviors, states, strict=False)
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
