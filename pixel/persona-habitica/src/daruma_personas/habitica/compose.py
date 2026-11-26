"""Stack a Habitica avatar from its sprites, the way habiticalib does.

The avatar is a 141x147 canvas. Each sprite is pasted at its offset, at
whatever size it is (most body layers are 90x90, some shields 103 wide,
some mount bodies 105). Back to front:

1. the background, at (0, 0);
2. the mount body, at (24, 18);
3. the rider, at (24, 24), or (24, 0) on a mount:
   - with a visual buff (seafoam, shiny seed, snowball, spooky sparkles):
     the buff sprites, then the hair flower;
   - otherwise: chair, back, skin (`_sleep` when asleep), shirt,
     `head_0`, armor, hair (bangs, base, mustache, beard), body, eyewear,
     head, head accessory, hair flower, shield, weapon;
4. `zzz` when asleep, at the rider's offset;
5. the mount head, at (24, 18);
6. the pet, at (0, 48).

Gear named `<slot>_base_0` is "nothing worn" and is skipped. With the
costume on, the costume set replaces the equipped one. Armor comes in a
slim and a broad form, picked by the look's size.

plan() says what goes where, with no pictures. compose() loads each
sprite, places it on a canvas of its own, takes it down to one pixel per
art pixel (downscale.py) and stacks it into its group. A missing sprite is
skipped with a warning: one piece of gear never stops the build.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from PIL import Image

from . import downscale
from .look import Look
from .sources import Source, load

log = logging.getLogger(__name__)

CANVAS = (141, 147)
ART = (CANVAS[0] // downscale.BLOCK, CANVAS[1] // downscale.BLOCK)  # 47x49 art pixels.
BACKGROUND_AT = (0, 0)
MOUNT_AT = (24, 18)
PET_AT = (0, 48)
RIDER_X = 24
RIDER_Y = 24  # Without a mount.
RIDER_Y_MOUNTED = 0

# Groups, back to front. Each can move on its own in an animation.
BACKGROUND, MOUNT_BODY, RIDER, ZZZ, MOUNT_HEAD, PET = "background", "mount_body", "rider", "zzz", "mount_head", "pet"
GROUPS = (BACKGROUND, MOUNT_BODY, RIDER, ZZZ, MOUNT_HEAD, PET)


@dataclass(frozen=True)
class Layer:
    sprite: str  # Habitica's name for it, without the extension.
    at: tuple[int, int]  # Top left on the 141x147 canvas.
    group: str


def rider_offset(look: Look) -> tuple[int, int]:
    return (RIDER_X, RIDER_Y_MOUNTED if look.mount else RIDER_Y)


def gear_sprite(look: Look, slot: str) -> str | None:
    """The sprite of the gear in `slot`, or None when nothing is worn there."""
    name = look.gear.get(slot)
    if not name or name == f"{slot}_base_0":
        return None
    return f"{look.size}_{name}" if slot == "armor" else name


def _hair_flower(look: Look) -> list[str]:
    return [f"hair_flower_{look.hair.flower}"] if look.hair.flower else []


def buff_sprites(look: Look) -> list[str]:
    """The rider while a visual buff is on: the buffs, then the hair flower."""
    names = []
    if "spookySparkles" in look.buffs:
        names.append("ghost")
    if "snowball" in look.buffs:
        names.append(f"avatar_snowball_{look.klass}")
    if "shinySeed" in look.buffs:
        names.append(f"avatar_floral_{look.klass}")
    if "seafoam" in look.buffs:
        names.append("seafoam_star")
    return names + _hair_flower(look)


def _gear(look: Look, *slots: str) -> list[str]:
    return [name for slot in slots if (name := gear_sprite(look, slot))]


def rider_sprites(look: Look) -> list[str]:
    """The rider without a buff, back to front."""
    names = [f"chair_{look.chair}"] if look.chair and look.chair != "none" else []
    names += _gear(look, "back")
    names.append(f"skin_{look.skin}_sleep" if look.sleep else f"skin_{look.skin}")
    names += [f"{look.size}_shirt_{look.shirt}", "head_0"]
    names += _gear(look, "armor")
    hair = look.hair
    styles = ((part, getattr(hair, part)) for part in ("bangs", "base", "mustache", "beard"))
    names += [f"hair_{part}_{style}_{hair.color}" for part, style in styles if style]
    names += _gear(look, "body", "eyewear", "head", "headAccessory")
    names += _hair_flower(look)
    names += _gear(look, "shield", "weapon")
    return names


def plan(look: Look) -> list[Layer]:
    """Every sprite of the avatar, back to front, with where it goes."""
    rider_at = rider_offset(look)
    layers = []
    if look.background:
        layers.append(Layer(f"background_{look.background}", BACKGROUND_AT, BACKGROUND))
    if look.mount:
        layers.append(Layer(f"Mount_Body_{look.mount}", MOUNT_AT, MOUNT_BODY))
    rider = buff_sprites(look) if look.buffs else rider_sprites(look)
    layers += [Layer(name, rider_at, RIDER) for name in rider]
    if look.sleep:
        layers.append(Layer("zzz", rider_at, ZZZ))
    if look.mount:
        layers.append(Layer(f"Mount_Head_{look.mount}", MOUNT_AT, MOUNT_HEAD))
    if look.pet:
        layers.append(Layer(f"Pet-{look.pet}", PET_AT, PET))
    return layers


def placed(sprite: Image.Image, at: tuple[int, int]) -> Image.Image:
    """`sprite` on a see-through canvas of the avatar's size, at `at`; what falls outside is cut."""
    canvas = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    canvas.paste(sprite, at)  # No mask: the canvas is empty, so alpha is kept as it is.
    return canvas


@dataclass
class Avatar:
    """The avatar at one pixel per art pixel (47x49), one picture per group."""

    groups: dict[str, Image.Image]
    missing: list[str] = field(default_factory=list)
    non_uniform: dict[str, int] = field(default_factory=dict)  # Per sprite, blocks off the grid.

    def flat(self, *groups: str) -> Image.Image:
        """The named groups stacked (all of them by default)."""
        out = Image.new("RGBA", ART, (0, 0, 0, 0))
        for name in groups or GROUPS:
            out.alpha_composite(self.groups[name])
        return out


def compose(look: Look, source: Source) -> Avatar:
    """The avatar of `look`, from the sprites in `source`."""
    avatar = Avatar(groups={name: Image.new("RGBA", ART, (0, 0, 0, 0)) for name in GROUPS})
    for layer in plan(look):
        sprite = load(source, layer.sprite)
        if sprite is None:
            log.warning("habitica: no sprite %s; the avatar is drawn without it", layer.sprite)
            avatar.missing.append(layer.sprite)
            continue
        reduced = downscale.reduce(placed(sprite, layer.at))
        avatar.non_uniform[layer.sprite] = reduced.non_uniform
        if reduced.non_uniform:
            log.info("habitica: %s has %d blocks off the 3x grid", layer.sprite, reduced.non_uniform)
        avatar.groups[layer.group].alpha_composite(reduced.image)
    return avatar
