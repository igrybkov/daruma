"""Sprite persona: looping pixel-art animations per mood, scaled up on device.

Frames are stored at native pixel size (small in flash) and drawn at the
largest whole-number scale that fits the stage (`scale` caps it). Each mood
or pose has a list of frames with durations, plus optional single
blink/wink frames. Missing moods and poses fall back like the image persona
(see sprite_persona.cpp).

A layered room fills a stage of another shape from strips taken at its
edges (extend.py): the build finds them, the device repeats them. The room
stands on the bottom of the stage; extra height goes above it.

On gray4 and mono screens (daruma: display_profile: colors) every
picture is reduced to the screen's grays at build time (sprite.py), and the
weekday rug colors are left out.

With a backdrop, the scene is drawn in layers: the window view (drawn on the
device from the hub's sky), the backdrop (the room, see-through where the
glass is), then the frames, which then hold only the persona, placed at
sprite_offset.

Pictures are PNG names in the `art` folder (or paths, without one). They are
stored compressed (daruma/sprite.py); see-through pixels (alpha < 128)
let the layers behind show.

Or the whole persona comes from Python at build time: `pixel_art` names a
persona and the module (by dotted name) or script (by path) that has it.
A module declares its personas with a Spec (daruma_pixel.personas),
or has a build(persona) of its own; either gives the room, frames, plant,
rug colors and animations.

Animations are named freely. A state finds the one named like it (any
case: `focus` finds `Focus`), or the one its `behaviors:` names, or its
fallback's (daruma/persona.py). The plant shows the `progress`
signal, wilting while a source is behind or wellbeing is low.

Param `rug` (choice): `weekday` swaps the rug colors by the day, `plain`
keeps the room's own.

Frames of a layered persona are stored as keyframes and patches on earlier
frames (daruma/sprite_codec.py), so an animation costs little more than
what moves in it. The device keeps the persona in a canvas and, playing
in order, draws only each patch's box.

`during:` (daruma/persona.py) names, per activity, the animation a
reaction plays instead while that activity is on, so its props stay.

`play_once` names animations that play once and hold their last frame,
instead of looping (a one-shot reaction).

A pixel_art persona may look different per stage of today's goal (the `goal`
signal: none, started, done). `pixel_art: goal:` names the script's persona for
`started` and `done`; `persona` is the one for `none`. The personas must share the
room. An animation a stage lacks comes from the nearest stage that has it.

`pixel_art: options:` is a mapping handed to the module as it is: the
module's build(name, options=..., data_dir=...) gets it, with the builder's
data folder for any files it keeps. A module may also have
cache_inputs(name, options=..., data_dir=...): strings its drawing depends
on beyond its code (a look, the hashes of downloaded pictures). They join
the key of the drawn-persona cache. The options themselves never do, and
are never logged, so a secret in them (a token) stays out of both.

`pixel_art: look_sensor:` names a text sensor that shows which look the
persona was drawn with: the module's look_id(name, options=...,
data_dir=...), set once at boot. Home Assistant can compare it with the
look the persona would draw today, and say when a new build is due.
"""

import hashlib
import importlib.util
import json
import pickle
import sys
from functools import cache
from pathlib import Path

import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import text_sensor
from esphome.components.daruma import CONF_DARUMA_ID, Hub, Persona, build_profile, daruma_ns
from esphome.components.daruma.persona import (
    BEHAVIORS_SCHEMA,
    CONF_BEHAVIORS,
    CONF_DURING,
    CONF_PARAMS,
    CONF_RANDOM_EVENTS,
    DURING_SCHEMA,
    RANDOM_EVENTS_SCHEMA,
    Param,
    params_schema,
    persona,
    persona_to_code,
    with_param_entities,
)
from esphome.components.daruma.sounds import CONF_SOUNDS, SOUNDS_SCHEMA, sounds_to_code
from esphome.components.daruma.sprite import (
    art_path,
    bundle_file,
    check_art,
    frame_set,
    resolve_dir,
    resolve_file,
    sprite_expression,
    sprite_from_image,
)
from esphome.components.daruma.theme import CONF_THEME, THEME_SCHEMA, theme_to_code
from esphome.const import CONF_DURATION, CONF_HEIGHT, CONF_ID, CONF_NAME, CONF_WIDTH, CONF_X, CONF_Y
from esphome.core import CORE

DEPENDENCIES = ["daruma"]
MULTI_CONF = True

CONF_IMAGE = "image"
CONF_ART = "art"
CONF_PIXEL_ART = "pixel_art"
CONF_SCRIPT = "script"
CONF_MODULE = "module"
CONF_PERSONA = "persona"
CONF_ANIMATIONS = "animations"
CONF_FRAMES = "frames"
CONF_BLINK = "blink"
CONF_WINK = "wink"
CONF_SCALE = "scale"
CONF_BACKGROUND = "background"
CONF_BACKDROP = "backdrop"
CONF_SPRITE_OFFSET = "sprite_offset"
CONF_WINDOW = "window"
CONF_PLANT = "plant"
CONF_RECOLOR = "recolor"
CONF_COLORS = "colors"
CONF_BY_WEEKDAY = "by_weekday"
CONF_OFFSET = "offset"
CONF_STAGES = "stages"
CONF_WILTED = "wilted"
CONF_GOAL = "goal"
CONF_PLAY_ONCE = "play_once"
CONF_OPTIONS = "options"
CONF_LOOK_SENSOR = "look_sensor"
GOAL_STAGES = ("none", "started", "done")  # signals.h Goal, in order.
_STAGES = "_goal_stages"  # Internal: per stage, the animation keys it uses.

SpritePersona = daruma_ns.class_("SpritePersona", cg.Component, Persona)

PARAMS = {"rug": Param("choice", "weekday", ["weekday", "plain"], icon="mdi:rug")}

FRAME_SCHEMA = cv.Schema(
    {
        cv.Required(CONF_IMAGE): cv.string_strict,
        cv.Optional(CONF_DURATION, default="1s"): cv.positive_time_period_milliseconds,
    }
)

ANIMATION_SCHEMA = cv.Schema(
    {
        cv.Required(CONF_FRAMES): cv.All(cv.ensure_list(FRAME_SCHEMA), cv.Length(min=1)),
        cv.Optional(CONF_BLINK): cv.string_strict,
        cv.Optional(CONF_WINK): cv.string_strict,
    }
)


def _validate_animations(value):
    return cv.Schema({cv.string_strict: ANIMATION_SCHEMA})(value)


def _hex_color(value):
    value = cv.string_strict(value).lstrip("#")
    if len(value) != 6:
        raise cv.Invalid("Use a 6-digit hex color like 000000")
    return int(value, 16)


WINDOW_SCHEMA = cv.Schema(
    {
        cv.Required(CONF_X): cv.int_range(min=0),
        cv.Required(CONF_Y): cv.int_range(min=0),
        cv.Required(CONF_WIDTH): cv.int_range(min=1),
        cv.Required(CONF_HEIGHT): cv.int_range(min=1),
    }
)


def _validate_plant(value):
    if len(value[CONF_STAGES]) != len(value[CONF_WILTED]):
        raise cv.Invalid("plant needs as many wilted images as stages")
    return value


PLANT_SCHEMA = cv.All(
    cv.Schema(
        {
            cv.Optional(CONF_OFFSET, default=[0, 0]): cv.All(cv.ensure_list(cv.int_), cv.Length(min=2, max=2)),
            cv.Required(CONF_STAGES): cv.All(cv.ensure_list(cv.string_strict), cv.Length(min=1)),
            cv.Required(CONF_WILTED): cv.All(cv.ensure_list(cv.string_strict), cv.Length(min=1)),
        }
    ),
    _validate_plant,
)


def _validate_recolor(value):
    for day in value[CONF_BY_WEEKDAY]:
        if len(day) != len(value[CONF_COLORS]):
            raise cv.Invalid("each weekday needs one color per entry in colors")
    return value


RECOLOR_SCHEMA = cv.All(
    cv.Schema(
        {
            cv.Required(CONF_COLORS): cv.All(cv.ensure_list(_hex_color), cv.Length(min=1)),
            cv.Required(CONF_BY_WEEKDAY): cv.All(
                cv.ensure_list(cv.All(cv.ensure_list(_hex_color), cv.Length(min=1))), cv.Length(min=7, max=7)
            ),
        }
    ),
    _validate_recolor,
)


def _pictures(config):
    """Every picture name the config uses."""
    if CONF_PIXEL_ART in config:
        return []
    names = [config[CONF_BACKDROP]] if CONF_BACKDROP in config else []
    if CONF_PLANT in config:
        names += config[CONF_PLANT][CONF_STAGES] + config[CONF_PLANT][CONF_WILTED]
    for anim in config[CONF_ANIMATIONS].values():
        names += [frame[CONF_IMAGE] for frame in anim[CONF_FRAMES]]
        names += [anim[key] for key in (CONF_BLINK, CONF_WINK) if key in anim]
    return names


def _options(value):
    """Any mapping, kept as it is: a !secret in it stays the object ESPHome knows."""
    if not isinstance(value, dict):
        raise cv.Invalid("options must be a mapping")
    return value


PIXEL_ART_SCHEMA = cv.All(
    cv.Schema(
        {
            # A Python file, or a module by dotted name (daruma_personas.corgi).
            cv.Optional(CONF_SCRIPT): cv.string_strict,
            cv.Optional(CONF_MODULE): cv.string_strict,
            cv.Required(CONF_PERSONA): cv.string_strict,
            # The script's persona per goal stage after none (CONF_PERSONA).
            cv.Optional(CONF_GOAL): cv.Schema({cv.Optional(stage): cv.string_strict for stage in GOAL_STAGES[1:]}),
            # Handed to the module's build() and cache_inputs(), never hashed.
            cv.Optional(CONF_OPTIONS): _options,
            # A text sensor for the module's look_id(): the look drawn.
            cv.Optional(CONF_LOOK_SENSOR): cv.use_id(text_sensor.TextSensor),
        }
    ),
    cv.has_exactly_one_key(CONF_SCRIPT, CONF_MODULE),
)

# Keys the pixel_art script fills in; a config sets either them or pixel_art.
_FROM_SCRIPT = (CONF_ART, CONF_ANIMATIONS, CONF_BACKDROP, CONF_WINDOW, CONF_PLANT, CONF_RECOLOR)


def _resolve_pictures(config):
    """Picture paths made absolute (resolve_file: next to the config, or next
    to the package that names them). With an `art` folder, only the folder:
    pictures are names inside it."""
    if CONF_ART in config:
        config[CONF_ART] = resolve_dir(config[CONF_ART])
        return
    if CONF_BACKDROP in config:
        config[CONF_BACKDROP] = resolve_file(config[CONF_BACKDROP])
    if CONF_PLANT in config:
        for key in (CONF_STAGES, CONF_WILTED):
            config[CONF_PLANT][key] = [resolve_file(name) for name in config[CONF_PLANT][key]]
    for anim in config[CONF_ANIMATIONS].values():
        for frame in anim[CONF_FRAMES]:
            frame[CONF_IMAGE] = resolve_file(frame[CONF_IMAGE])
        for key in (CONF_BLINK, CONF_WINK):
            if key in anim:
                anim[key] = resolve_file(anim[key])


def _validate_layers(config):
    if CONF_PIXEL_ART in config:
        for key in _FROM_SCRIPT:
            if key in config:
                raise cv.Invalid(f"{key} comes from the pixel_art script; drop it here")
        script = _pixel_art_file(config[CONF_PIXEL_ART])
        config[CONF_PIXEL_ART][CONF_SCRIPT] = str(script)
        # The script imports the modules next to it and the pixel library, so
        # a bundle needs all of them.
        for module in _script_sources(script):
            bundle_file(module)
        return config
    if CONF_ANIMATIONS not in config:
        raise cv.Invalid("Set animations (with pictures), or pixel_art")
    for key in (CONF_WINDOW, CONF_PLANT, CONF_RECOLOR):
        if key in config and CONF_BACKDROP not in config:
            raise cv.Invalid(f"{key} needs a backdrop to sit in")
    _resolve_pictures(config)
    for name in _pictures(config):
        check_art(config.get(CONF_ART), name)
    return config


CONFIG_SCHEMA = cv.All(
    cv.Schema(
        {
            cv.GenerateID(): cv.declare_id(SpritePersona),
            cv.GenerateID(CONF_DARUMA_ID): cv.use_id(Hub),
            cv.Required(CONF_NAME): cv.string_strict,
            cv.Optional(CONF_THEME): THEME_SCHEMA,
            cv.Optional(CONF_SOUNDS): SOUNDS_SCHEMA,
            cv.Optional(CONF_BEHAVIORS, default={}): BEHAVIORS_SCHEMA,
            cv.Optional(CONF_DURING, default={}): DURING_SCHEMA,
            cv.Optional(CONF_RANDOM_EVENTS, default={}): RANDOM_EVENTS_SCHEMA,
            cv.Optional(CONF_PARAMS, default={}): params_schema(PARAMS),
            # The largest scale to draw at; without it, the largest that fits.
            cv.Optional(CONF_SCALE): cv.int_range(min=1, max=16),
            cv.Optional(CONF_BACKGROUND, default="000000"): _hex_color,
            cv.Optional(CONF_ART): cv.string_strict,
            cv.Optional(CONF_PIXEL_ART): PIXEL_ART_SCHEMA,
            cv.Optional(CONF_ANIMATIONS): _validate_animations,
            cv.Optional(CONF_BACKDROP): cv.string_strict,
            cv.Optional(CONF_SPRITE_OFFSET, default=[0, 0]): cv.All(cv.ensure_list(cv.int_), cv.Length(min=2, max=2)),
            cv.Optional(CONF_WINDOW): WINDOW_SCHEMA,
            cv.Optional(CONF_PLANT): PLANT_SCHEMA,
            cv.Optional(CONF_RECOLOR): RECOLOR_SCHEMA,
            cv.Optional(CONF_PLAY_ONCE, default=[]): cv.ensure_list(cv.string_strict),
        }
    ).extend(cv.COMPONENT_SCHEMA),
    _validate_layers,
    with_param_entities(PARAMS),
)


# The pixel packages, in the same checkout as this component
# (<repo>/src/esphome/components/daruma_sprites/): every <repo>/pixel/*/src.
# They hold daruma_pixel (the drawing layer) and the namespace packages
# daruma_shapes and daruma_personas, one part per folder. The build installs
# nothing: it puts the folders on the import path. A script kept elsewhere,
# such as a persona in another repository, imports them by those names.
PIXEL_ROOT = Path(__file__).resolve().parents[4] / "pixel"


def _pixel_paths() -> list[Path]:
    """The src folder of every pixel package, in name order."""
    return sorted(PIXEL_ROOT.glob("*/src"))


def _use_pixel_paths() -> None:
    """The pixel packages first on the import path, in name order."""
    for folder in reversed(_pixel_paths()):
        if str(folder) not in sys.path:
            sys.path.insert(0, str(folder))


def _pixel_art_file(art) -> Path:
    """The file of a pixel_art script, or of its module: a dotted name found
    with the pixel packages on the import path."""
    if CONF_MODULE not in art:
        try:
            return Path(resolve_file(art[CONF_SCRIPT]))
        except cv.Invalid as err:
            raise cv.Invalid(f"No pixel_art script: {err}") from err
    _use_pixel_paths()
    try:
        spec = importlib.util.find_spec(art[CONF_MODULE])
    except ImportError:
        spec = None
    if spec is None or not spec.origin:
        raise cv.Invalid(f"No pixel_art module {art[CONF_MODULE]}")
    return Path(spec.origin)


def _library_module(script: Path) -> str | None:
    """The module name of a script inside a pixel package (daruma_personas.corgi), or None."""
    path = script.resolve()
    for src in _pixel_paths():
        if path.is_relative_to(src.resolve()):
            parts = path.relative_to(src.resolve()).with_suffix("").parts
            return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)
    return None


def _script_path(script: Path) -> list[Path]:
    """The folders on the import path for a pixel_art script: its own (not
    for a script in a pixel package, whose modules import each other through
    the package), then the pixel packages."""
    folders = [] if _library_module(script) else [script.resolve().parent]
    return folders + _pixel_paths()


def _script_sources(script: Path) -> list[Path]:
    """Every Python file the script can import: the ones next to it and every
    pixel package's. All of them, not only the ones a persona uses: a few
    more files to hash costs less than tracking imports."""
    files = set() if _library_module(script) else set(script.resolve().parent.glob("*.py"))
    for src in _pixel_paths():
        files |= set(src.rglob("*.py"))
    return sorted(files)


def _frozen(options) -> str:
    """pixel_art options as one string, so _build's memo can key on them ("" for none)."""
    return "" if options is None else json.dumps(options, sort_keys=True, default=str)


def _data_dir() -> Path | None:
    """The builder's data folder, where a module may keep its own files."""
    try:
        return Path(CORE.data_dir)
    except Exception:  # No config loaded (a host test): no folder.
        return None


def _extra_inputs(module, name: str, options, data_dir: Path | None) -> list[str]:
    """What the module's cache_inputs() says its drawing depends on; nothing without one."""
    hook = getattr(module, "cache_inputs", None)
    if hook is None:
        return []
    return [str(item) for item in hook(name, options=options or {}, data_dir=data_dir)]


@cache
def _build(script: Path, name: str, options: str = ""):
    """The pixel_art script's persona, built once per build: final validation
    and code generation both need it. `options` comes from _frozen()."""
    for folder in reversed(_script_path(script)):
        if str(folder) not in sys.path:
            sys.path.insert(0, str(folder))
    if (library := _library_module(script)) is not None:
        module = importlib.import_module(library)
    else:
        spec = importlib.util.spec_from_file_location(f"daruma_pixel_art_{script.stem}", script)
        module = importlib.util.module_from_spec(spec)
        # Registered first: dataclasses in the script look their module up here.
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    opts = json.loads(options) if options else None
    data_dir = _data_dir()
    cache = _cache_path(script, name, _extra_inputs(module, name, opts, data_dir))
    if cache is not None and cache.is_file():
        try:
            with cache.open("rb") as f:
                return pickle.load(f)
        except Exception:  # A stale or unreadable cache: draw again.
            pass
    persona = _draw(module, name, opts, data_dir)
    if cache is not None:
        try:
            cache.parent.mkdir(parents=True, exist_ok=True)
            for old in cache.parent.glob(f"{name}-*.pickle"):  # Drawn from older scripts.
                old.unlink(missing_ok=True)
            tmp = cache.with_suffix(".tmp")
            with tmp.open("wb") as f:
                pickle.dump(persona, f, protocol=pickle.HIGHEST_PROTOCOL)
            tmp.replace(cache)
        except Exception:  # Not picklable or not writable: no cache, same result.
            pass
    return persona


def _draw(module, name: str, options=None, data_dir: Path | None = None):
    """The module's own build(name), or personas.build() from its Spec. With
    options, the module's build(name, options=..., data_dir=...)."""
    if options is not None:
        if not hasattr(module, "build"):
            raise cv.Invalid("pixel_art options need a module with build(name, options=..., data_dir=...)")
        return module.build(name, options=options, data_dir=data_dir)
    if hasattr(module, "build"):
        return module.build(name)
    from daruma_pixel import personas

    return personas.build(name, module)


def _cache_path(script: Path, name: str, extra: list[str] = ()) -> Path | None:
    """Where a drawn persona is kept between builds. Drawing some personas takes most
    of a config check, and it only changes when the art scripts do, so the key
    hashes every script it can import (_script_sources), the persona name and
    the Pillow and Python versions. `extra` is what the module's cache_inputs()
    adds; without any, the key is what it always was."""
    try:
        import PIL

        digest = hashlib.sha256()
        for path in _script_sources(script):
            digest.update(path.name.encode())
            digest.update(path.read_bytes())
        for item in extra:
            digest.update(b"\0" + item.encode())
        digest.update(f"{name}|{PIL.__version__}|{sys.version_info[:2]}".encode())
        return Path(CORE.data_dir) / "daruma_pixel_art" / f"{name}-{digest.hexdigest()[:24]}.pickle"
    except Exception:
        return None


def _module(script: Path):
    """The pixel_art module _build() imported."""
    library = _library_module(script)
    return importlib.import_module(library) if library is not None else sys.modules[f"daruma_pixel_art_{script.stem}"]


def _look_id(config) -> str:
    """The module's look_id() for the persona and its options."""
    art = config[CONF_PIXEL_ART]
    script = Path(CORE.relative_config_path(art[CONF_SCRIPT])).resolve()
    hook = getattr(_module(script), "look_id", None)
    if hook is None:
        raise cv.Invalid("look_sensor needs a pixel_art module with look_id(name, options=..., data_dir=...)")
    options = json.loads(_frozen(art.get(CONF_OPTIONS)) or "{}")
    return str(hook(art[CONF_PERSONA], options=options, data_dir=_data_dir()))


async def _look_to_code(config) -> None:
    """Sets the look sensor, if the config names one, to the look drawn."""
    art = config.get(CONF_PIXEL_ART) or {}
    if CONF_LOOK_SENSOR not in art:
        return
    sensor = await cg.get_variable(art[CONF_LOOK_SENSOR])
    cg.add(sensor.publish_state(_look_id(config)))


def _same_room(a, b, label):
    """Personas for the goal stages must share the room, so one view fits all."""

    def pixels(img):
        return img.convert("RGBA").tobytes() if img is not None else None

    checks = {
        "background": (a.background, b.background),
        "backdrop": (pixels(a.backdrop), pixels(b.backdrop)),
        "sprite offset": (tuple(a.sprite_offset), tuple(b.sprite_offset)),
        "window": (a.window, b.window),
        "plant": (
            [pixels(i) for i in a.plant_stages + a.plant_wilted],
            [pixels(i) for i in b.plant_stages + b.plant_wilted],
        ),
        "rug colors": ((a.recolor_from, a.recolor_by_weekday), (b.recolor_from, b.recolor_by_weekday)),
    }
    for what, (x, y) in checks.items():
        if x != y:
            raise cv.Invalid(f"pixel_art goal persona {label}: its {what} differs from the main persona's")


def _from_script(config):
    """The config with every picture key filled in by the pixel_art script.

    With goal stages, the animations of every stage are stored, keyed
    "Name" for none and "Name:stage" for the others; _STAGES lists, per
    stage, the key each animation name uses."""
    script = Path(CORE.relative_config_path(config[CONF_PIXEL_ART][CONF_SCRIPT])).resolve()
    options = _frozen(config[CONF_PIXEL_ART].get(CONF_OPTIONS))
    persona = _build(script, config[CONF_PIXEL_ART][CONF_PERSONA], options)
    stage_personas = [persona]
    for stage in GOAL_STAGES[1:]:
        name = config[CONF_PIXEL_ART].get(CONF_GOAL, {}).get(stage)
        if name is None:
            stage_personas.append(None)
            continue
        other = _build(script, name, options)
        _same_room(persona, other, name)
        stage_personas.append(other)

    out = dict(config)
    out[CONF_BACKGROUND] = persona.background
    out[CONF_BACKDROP] = persona.backdrop
    out[CONF_SPRITE_OFFSET] = list(persona.sprite_offset)
    if persona.window:
        x, y, w, h = persona.window
        out[CONF_WINDOW] = {CONF_X: x, CONF_Y: y, CONF_WIDTH: w, CONF_HEIGHT: h}
    if persona.plant_stages:
        out[CONF_PLANT] = {
            CONF_OFFSET: list(persona.plant_offset),
            CONF_STAGES: persona.plant_stages,
            CONF_WILTED: persona.plant_wilted,
        }
    if persona.recolor_from:
        out[CONF_RECOLOR] = {CONF_COLORS: persona.recolor_from, CONF_BY_WEEKDAY: persona.recolor_by_weekday}
    out[CONF_ANIMATIONS] = {}
    stages = []
    for number, stage_persona in enumerate(stage_personas):
        if stage_persona is None:
            stages.append(None)
            continue
        keys = {}
        for name, anim in stage_persona.animations.items():
            entry = {CONF_FRAMES: [{CONF_IMAGE: img, CONF_DURATION: ms} for img, ms in anim.frames]}
            if anim.blink is not None:
                entry[CONF_BLINK] = anim.blink
            if anim.wink is not None:
                entry[CONF_WINK] = anim.wink
            key = name if number == 0 else f"{name}:{GOAL_STAGES[number]}"
            out[CONF_ANIMATIONS][key] = entry
            keys[name] = key
        stages.append(keys)
    if any(s is not None for s in stages[1:]):
        out[_STAGES] = stages
    return out


def _names(config) -> list[str]:
    """The animation names behaviors see: with goal stages, every stage's
    names once, the main persona's first."""
    if _STAGES not in config:
        return list(config[CONF_ANIMATIONS])
    names = []
    for keys in config[_STAGES]:
        for name in keys or {}:
            if name not in names:
                names.append(name)
    return names


def _goal_maps(config, names: list[str]) -> list[list[int]]:
    """Per goal stage: for each name, the index of the stored animation to
    play. A stage without a persona of its own, or without that animation,
    uses the nearest stage that has it (lower stages first)."""
    stored = list(config[CONF_ANIMATIONS])
    stages = config[_STAGES]
    maps = []
    for number in range(len(stages)):
        order = [number] + [n for d in range(1, len(stages)) for n in (number - d, number + d) if 0 <= n < len(stages)]
        row = []
        for name in names:
            key = next(stages[n][name] for n in order if stages[n] is not None and name in stages[n])
            row.append(stored.index(key))
        maps.append(row)
    return maps


def _ms(duration):
    return duration if isinstance(duration, int) else duration.total_milliseconds


def _strips(backdrop):
    """The backdrop's left, right and top edge strips, as pictures."""
    from PIL import Image

    from . import extend

    if isinstance(backdrop, str):
        with Image.open(CORE.relative_config_path(backdrop)) as img:
            backdrop = img.convert("RGBA")
    backdrop = backdrop.convert("RGBA")
    rows = [[backdrop.getpixel((x, y)) for x in range(backdrop.width)] for y in range(backdrop.height)]

    def picture(grid):
        img = Image.new("RGBA", (len(grid[0]), len(grid)))
        img.putdata([px for row in grid for px in row])
        return img

    return picture(extend.left_strip(rows)), picture(extend.right_strip(rows)), picture(extend.top_strip(rows))


def _animations(config) -> list[str]:
    if CONF_PIXEL_ART in config:
        config = _from_script(config)
    names = _names(config)
    for name in config[CONF_PLAY_ONCE]:
        if name not in names:
            raise cv.Invalid(f"play_once: no animation '{name}' (there are: {', '.join(names)})")
    return names


def daruma_personas(confs):
    """For the hub's final validation: each persona's animations, theme and params."""
    return [(persona(c[CONF_ID].id, _animations(c), c), c.get(CONF_THEME, {}), list(PARAMS)) for c in confs]


def _picture(config, picture):
    """A frame's picture as a PIL image."""
    from PIL import Image

    if isinstance(picture, str):
        with Image.open(CORE.relative_config_path(art_path(config.get(CONF_ART), picture))) as img:
            return img.convert("RGBA")
    return picture.convert("RGBA")


def _frames_to_code(var, config, sprite) -> dict[int, int]:
    """Stores every frame of the persona (add_image) and returns, per picture
    object in the config, its frame index.

    A layered persona whose frames share one size gets them as keyframes and
    patches (sprite.frame_set). Otherwise each picture is a whole sprite."""
    pictures, sequences = [], []

    def add(picture) -> int:
        pictures.append(picture)
        return len(pictures) - 1

    for anim in config[CONF_ANIMATIONS].values():
        seq = [add(frame[CONF_IMAGE]) for frame in anim[CONF_FRAMES]]
        sequences.append(seq)
        for key in (CONF_BLINK, CONF_WINK):
            if key in anim:
                sequences.append([seq[0], add(anim[key])])

    images = [_picture(config, p) for p in pictures]
    out: dict[int, int] = {}
    if CONF_BACKDROP in config and len({img.size for img in images}) == 1:
        stored, index = frame_set(images, sequences, config[CONF_ID].id)
        _image_table(var, config, [(expr, base, x, y) for expr, base, x, y in stored])
        for picture, i in zip(pictures, index, strict=False):
            out[id(picture)] = i
        return out
    stored_at: dict[int, int] = {}  # id(sprite expression) -> frame index
    rows = []
    for picture in pictures:
        expr = sprite(picture)  # The same picture gives the same expression.
        if id(expr) not in stored_at:
            stored_at[id(expr)] = len(stored_at)
            rows.append((expr, -1, 0, 0))
        out[id(picture)] = stored_at[id(expr)]
    _image_table(var, config, rows)
    return out


def _image_table(var, config, rows) -> None:
    name = f"{config[CONF_ID].id}_frame_table"
    body = ", ".join(f"{{{expr}, {base}, {x}, {y}}}" for expr, base, x, y in rows)
    cg.add_global(cg.RawStatement(f"static const Daruma::FrameRef {name}[] = {{{body}}};"))
    cg.add(var.add_image_table(cg.RawExpression(name), len(rows)))


async def to_code(config):
    if CONF_PIXEL_ART in config:
        config = _from_script(config)

    def sprite(picture):
        if isinstance(picture, str):
            return sprite_expression(art_path(config.get(CONF_ART), picture))
        return sprite_from_image(picture)  # Drawn by the pixel_art script.

    var = cg.new_Pvariable(config[CONF_ID], config[CONF_NAME])
    await cg.register_component(var, config)
    if CONF_SCALE in config:
        cg.add(var.set_scale(config[CONF_SCALE]))
    bg = config[CONF_BACKGROUND]
    cg.add(var.set_background((bg >> 16) & 0xFF, (bg >> 8) & 0xFF, bg & 0xFF))

    if CONF_BACKDROP in config:
        backdrop = config[CONF_BACKDROP]
        cg.add(var.set_backdrop(sprite(backdrop)))
        left, right, top = _strips(art_path(config.get(CONF_ART), backdrop) if isinstance(backdrop, str) else backdrop)
        cg.add(var.set_strips(sprite_from_image(left), sprite_from_image(right), sprite_from_image(top)))
        x, y = config[CONF_SPRITE_OFFSET]
        cg.add(var.set_sprite_offset(x, y))
    if CONF_WINDOW in config:
        win = config[CONF_WINDOW]
        cg.add(var.set_window(win[CONF_X], win[CONF_Y], win[CONF_WIDTH], win[CONF_HEIGHT]))

    # Weekday colors mean nothing in gray: the rug keeps the room's own.
    if CONF_RECOLOR in config and build_profile().colors == "full":
        rc = config[CONF_RECOLOR]
        cg.add(var.set_recolor(rc[CONF_COLORS], rc[CONF_BY_WEEKDAY]))
    if CONF_PLANT in config:
        plant = config[CONF_PLANT]
        x, y = plant[CONF_OFFSET]
        cg.add(var.set_plant_offset(x, y))
        for healthy, wilted in zip(plant[CONF_STAGES], plant[CONF_WILTED], strict=False):
            cg.add(var.add_plant_stage(sprite(healthy), sprite(wilted)))

    frame_of = _frames_to_code(var, config, sprite)
    names = _names(config)
    pid = config[CONF_ID].id
    keys = list(config[CONF_ANIMATIONS])
    cg.add_global(
        cg.RawStatement(
            f"static const char *const {pid}_anim_names[] = {{"
            + ", ".join(cg.safe_exp(k).__str__() for k in keys)
            + "};"
        )
    )
    cg.add(var.add_animation_table(cg.RawExpression(f"{pid}_anim_names"), len(keys)))
    steps = [
        f"{{{index}, {frame_of[id(frame[CONF_IMAGE])]}, {_ms(frame[CONF_DURATION])}}}"
        for index, anim in enumerate(config[CONF_ANIMATIONS].values())
        for frame in anim[CONF_FRAMES]
    ]
    cg.add_global(
        cg.RawStatement(
            f"static const Daruma::SpritePersona::FrameStep {pid}_frame_steps[] = {{" + ", ".join(steps) + "};"
        )
    )
    cg.add(var.add_frame_table(cg.RawExpression(f"{pid}_frame_steps"), len(steps)))
    for index, (key, anim) in enumerate(config[CONF_ANIMATIONS].items()):
        if CONF_BLINK in anim:
            cg.add(var.set_blink(index, frame_of[id(anim[CONF_BLINK])]))
        if CONF_WINK in anim:
            cg.add(var.set_wink(index, frame_of[id(anim[CONF_WINK])]))
        if key.split(":")[0] in config[CONF_PLAY_ONCE]:
            cg.add(var.set_play_once(index))
    if _STAGES in config:
        for row in _goal_maps(config, names):
            cg.add(var.add_goal_map(row))

    # A device build reaches to_code; host tests reach _look_to_code itself.
    await _look_to_code(config)  # pragma: no mutate
    await theme_to_code(var, config)
    await sounds_to_code(var, config)
    hub = await cg.get_variable(config[CONF_DARUMA_ID])
    await persona_to_code(var, hub, persona(config[CONF_ID].id, names, config), config, PARAMS)
    cg.add(hub.add_persona(var))
