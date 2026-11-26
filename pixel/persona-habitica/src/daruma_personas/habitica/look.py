"""The look of a Habitica avatar: what decides which sprites it stacks.

A look comes from the user object of Habitica's API (`GET /api/v3/user`),
or from a pin in the device config with the same shape:

    preferences: {skin, shirt, size, chair, background, costume, sleep,
                  hair: {color, base, bangs, beard, mustache, flower}}
    items: {currentPet, currentMount, gear: {equipped: {...}, costume: {...}}}
    stats: {class, buffs: {seafoam, shinySeed, snowball, spookySparkles}}

A missing key takes the default below. Unknown keys are ignored, so the
whole user object works too.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from typing import Any

# Gear slots, in the order habiticalib reads them.
GEAR_SLOTS = ("back", "armor", "body", "eyewear", "head", "headAccessory", "shield", "weapon")
HAIR_PARTS = ("bangs", "base", "mustache", "beard")
BUFFS = ("seafoam", "shinySeed", "snowball", "spookySparkles")


@dataclass(frozen=True)
class Hair:
    color: str = "red"
    base: int = 0
    bangs: int = 0
    mustache: int = 0
    beard: int = 0
    flower: int = 0


@dataclass(frozen=True)
class Look:
    skin: str = "915533"
    shirt: str = "black"
    size: str = "slim"  # slim or broad: the shirt and armor forms.
    chair: str = "none"
    background: str = ""
    costume: bool = False
    sleep: bool = False
    hair: Hair = field(default_factory=Hair)
    equipped: Mapping[str, str] = field(default_factory=dict)
    costume_gear: Mapping[str, str] = field(default_factory=dict)
    pet: str = ""
    mount: str = ""
    klass: str = "warrior"
    buffs: frozenset[str] = frozenset()

    @property
    def gear(self) -> Mapping[str, str]:
        """The gear on show: the costume when it is on, else the equipped set."""
        return self.costume_gear if self.costume else self.equipped

    def canonical(self) -> str:
        """The look as one stable string: equal looks give equal strings."""
        data = asdict(self)
        data["equipped"] = dict(sorted(self.equipped.items()))
        data["costume_gear"] = dict(sorted(self.costume_gear.items()))
        data["buffs"] = sorted(self.buffs)
        return json.dumps(data, separators=(",", ":"))


def _section(data: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = data.get(key)
    return value if isinstance(value, Mapping) else {}


def _text(value: Any, default: str) -> str:
    return default if value is None else str(value)


def _gear(gear: Mapping[str, Any], key: str) -> dict[str, str]:
    return {slot: str(name) for slot, name in _section(gear, key).items() if slot in GEAR_SLOTS and name}


def _hair(prefs: Mapping[str, Any]) -> Hair:
    hair = _section(prefs, "hair")
    parts = {part: int(hair.get(part) or 0) for part in (*HAIR_PARTS, "flower")}
    return Hair(color=_text(hair.get("color"), Hair.color), **parts)


def from_user(data: Mapping[str, Any]) -> Look:
    """The look in a Habitica user object (or a pin of the same shape)."""
    prefs = _section(data, "preferences")
    items = _section(data, "items")
    stats = _section(data, "stats")
    gear = _section(items, "gear")
    buffs = _section(stats, "buffs")
    return Look(
        skin=_text(prefs.get("skin"), Look.skin),
        shirt=_text(prefs.get("shirt"), Look.shirt),
        size=_text(prefs.get("size"), Look.size),
        chair=_text(prefs.get("chair"), Look.chair),
        background=_text(prefs.get("background"), Look.background),
        costume=bool(prefs.get("costume")),
        sleep=bool(prefs.get("sleep")),
        hair=_hair(prefs),
        equipped=_gear(gear, "equipped"),
        costume_gear=_gear(gear, "costume"),
        pet=_text(items.get("currentPet"), ""),
        mount=_text(items.get("currentMount"), ""),
        klass=_text(stats.get("class"), Look.klass),
        buffs=frozenset(name for name in BUFFS if buffs.get(name)),
    )


def look_text(look: Look) -> str:
    """The look as Home Assistant's "Habitica look" sensor writes it
    (docs/habitica-avatar.md): what a new build would draw differently.
    It leaves out sleep, buffs and class, which change at run time.

        skin=..;hair=<color>/<base>/<bangs>/<mustache>/<beard>/<flower>;size=..;
        shirt=..;chair=..;background=..;costume=0|1;gear=<slot>:<name>,...;pet=..;mount=..

    The gear is the gear on show, in GEAR_SLOTS order.
    """
    h = look.hair
    hair = "/".join(str(v) for v in (h.color, h.base, h.bangs, h.mustache, h.beard, h.flower))
    gear = ",".join(f"{slot}:{look.gear[slot]}" for slot in GEAR_SLOTS if slot in look.gear)
    parts = (
        ("skin", look.skin),
        ("hair", hair),
        ("size", look.size),
        ("shirt", look.shirt),
        ("chair", look.chair),
        ("background", look.background),
        ("costume", int(look.costume)),
        ("gear", gear),
        ("pet", look.pet),
        ("mount", look.mount),
    )
    return ";".join(f"{key}={value}" for key, value in parts)


def short_id(text: str) -> str:
    """A short id of a look text: 8 hex digits. Home Assistant's templates
    compute the same (h = h * 31 + ord(c), modulo 2**32), so the device's
    "Avatar look" can be compared with the "Habitica look" sensor."""
    h = 0
    for c in text:
        h = (h * 31 + ord(c)) % 4294967296
    return f"{h:08x}"
