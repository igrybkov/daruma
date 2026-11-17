"""Persona picker: one option per registered persona, persisted across reboots.

The options follow the order personas appear in the config (the device yaml's
package order), so the first persona listed is the default for a new device.
The choice is stored by the persona's id, so renaming a persona keeps it too.
`legacy_options` lists the options of a build that stored a position
instead, so an update keeps that choice. `restore_from_name` is the select's
name in a build where it had another one: the stored choice is kept under
that name's key, as ESPHome makes it from the name.
"""

import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import select
from esphome.const import CONF_ID, CONF_NAME
from esphome.core import CORE

from .. import CONF_DARUMA_ID, PERSONA_COMPONENTS, Hub, daruma_ns

DEPENDENCIES = ["daruma"]

CONF_LEGACY_OPTIONS = "legacy_options"
CONF_RESTORE_FROM_NAME = "restore_from_name"

PersonaSelect = daruma_ns.class_("PersonaSelect", select.Select, cg.Component)

CONFIG_SCHEMA = (
    select.select_schema(PersonaSelect, icon="mdi:face-man-shimmer-outline")
    .extend(
        {
            cv.GenerateID(CONF_DARUMA_ID): cv.use_id(Hub),
            cv.Optional(CONF_LEGACY_OPTIONS, default=[]): cv.ensure_list(cv.string_strict),
            cv.Optional(CONF_RESTORE_FROM_NAME): cv.string_strict,
        }
    )
    .extend(cv.COMPONENT_SCHEMA)
)


def _personas():
    """(id, name) of every persona in config order: persona components in the
    order they first appear, each in its list's order."""
    personas = []
    for key in CORE.config:
        if key in PERSONA_COMPONENTS:
            for persona in CORE.config.get(key, []) or []:
                personas.append((persona[CONF_ID].id, persona[CONF_NAME]))
    return personas


async def to_code(config):
    personas = _personas()
    names = [name for _, name in personas]
    if not names:
        raise cv.Invalid("The persona select needs at least one persona (daruma_eyes, daruma_images or daruma_sprites)")
    var = await select.new_select(config, options=names)
    await cg.register_component(var, config)
    hub = await cg.get_variable(config[CONF_DARUMA_ID])
    cg.add(var.set_hub(hub))
    cg.add(var.set_keys([persona_id for persona_id, _ in personas]))
    if config[CONF_LEGACY_OPTIONS]:
        cg.add(var.set_legacy_options(config[CONF_LEGACY_OPTIONS]))
    if CONF_RESTORE_FROM_NAME in config:
        from esphome.helpers import fnv1_hash_object_id

        # make_entity_preference(): the object id's hash, XOR the device id
        # (0 on the main device) and the version (0).
        cg.add(var.set_restore_key(fnv1_hash_object_id(config[CONF_RESTORE_FROM_NAME])))
