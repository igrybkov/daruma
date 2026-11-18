"""Host test: an activity's props stay in the picture while a reaction plays.

    uv run pytest tests/test_props.py

A reaction (petted, startled, ...) shows over the activity under it, which
stays on. The daruma's incense belongs to focus, so a reaction during a
focus session must keep it, or the incense vanishes while you pet the doll.
A persona keeps props with `during:` (registry.py).

For every pixel_art persona whose layers module declares PROPS, a map of
activity state -> boxes (x0, y0, x1, y1, scene pixels, end exclusive)
where its props stand: the prop pixels are the ones in a box that are the
same in every frame of the activity's own animation. Then, for each core
reaction, the animation the device would play over that activity (its
behavior, its fallbacks, then `during:`) must keep them, in every frame
and every goal stage. Module reactions (focus_done, goal, ...) are left
out: the module ends its activity as it plays them.

DARUMA_PERSONA_PATH adds the personas of folders outside this repository
(demos/persona_path.py).

Personas without PROPS are not checked; adding PROPS to a persona's layers
module is enough to bring it in. It builds the personas (about a minute); set
DARUMA_SKIP_PERSONAS=1 to skip it, as test_frames.py does.
"""

import importlib.util
import os
import re
import sys
import unittest
from dataclasses import dataclass
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_PACKAGES = _ROOT / "packages"
_LIBRARIES = [src.resolve() for src in (_ROOT / "pixel").glob("*/src")]

try:
    import yaml
    from PIL import Image  # noqa: F401
except ImportError:  # pragma: no cover
    yaml = None

import esphome_components  # noqa: E402, F401
from esphome.components.daruma import registry  # noqa: E402

sys.path.insert(0, str(_ROOT / "demos"))
import persona_path  # noqa: E402 - from demos/, put on the path above

GOAL_KEYS = ("started", "done")
KEEP = 0.95  # Share of the prop pixels a reaction frame must show unchanged.


def module_states() -> list:
    """The pomodoro module's states, read from its package (focus, break, ...)."""
    text = (_PACKAGES / "pomodoro.yaml").read_text()
    states = []
    for name, body in re.findall(r"^\s+(\w+): \{ kind: (\w+.*?) \}$", text, re.M):
        fields = dict(part.split(": ", 1) for part in ("kind: " + body).split(", "))
        states.append(registry.State(name, fields["kind"], fields.get("fallback"), module="pomodoro"))
    return states


def load_persona_config(path: Path) -> dict:
    """The persona entry of a persona package (its first daruma_sprites item)."""

    class Loader(yaml.SafeLoader):
        pass

    Loader.add_multi_constructor("!", lambda loader, suffix, node: None)
    doc = yaml.load(path.read_text(), Loader=Loader)
    return (doc or {}).get("daruma_sprites", [{}])[0]


def pixel_personas() -> list[tuple[str, dict]]:
    """(file name, persona entry) of every pixel_art package: Daruma's own and
    the ones of DARUMA_PERSONA_PATH. `_dir` holds the package's folder, for
    its script path."""
    paths = sorted(_PACKAGES.glob("persona_*.yaml"))
    paths += [pkg for folder in persona_path.folders() for pkg in folder.packages]
    out = []
    for path in paths:
        conf = load_persona_config(path)
        if "pixel_art" in conf:
            out.append((path.name, {**conf, "_dir": path.parent}))
    return out


def _script(conf: dict):
    # A `module:` is imported by name. Scripts are named relative to their
    # package file; a script inside a pixel package is imported by its module
    # name, so its relative imports work.
    if "module" in conf["pixel_art"]:
        return importlib.import_module(conf["pixel_art"]["module"])
    path = (conf.get("_dir", _PACKAGES) / conf["pixel_art"]["script"]).resolve()
    for library in _LIBRARIES:
        if path.is_relative_to(library):
            parts = path.relative_to(library).with_suffix("").parts
            return importlib.import_module(".".join(parts[:-1] if parts[-1] == "__init__" else parts))
    return persona_path.load_script(path)


def prop_pixels(persona, anim: str, box) -> dict:
    """Pixels in `box` (scene coordinates) that every frame of `anim` shows the same."""
    ox, oy = persona.sprite_offset
    frames = [img.convert("RGBA") for img, _ in persona.animations[anim].frames]
    out = {}
    x0, y0, x1, y1 = box
    for y in range(y0, y1):
        for x in range(x0, x1):
            fx, fy = x - ox, y - oy
            if not (0 <= fx < frames[0].width and 0 <= fy < frames[0].height):
                continue
            values = {f.getpixel((fx, fy)) for f in frames}
            if len(values) == 1:
                (v,) = values
                if v[3] >= 128:
                    out[(fx, fy)] = v
    return out


def _stage_names(conf: dict) -> list:
    """The persona's name, then its goal stages' ("started", "done"), None where unset."""
    return [conf["pixel_art"]["persona"]] + [conf["pixel_art"].get("goal", {}).get(k) for k in GOAL_KEYS]


def _build(script, name: str):
    """The persona `name` of a pixel_art module, as daruma_sprites builds it."""
    if hasattr(script, "build"):
        return script.build(name)
    from daruma_pixel import personas

    return personas.build(name, script)


def _props(conf: dict):
    """PROPS of the main persona's layers, from its Spec: no drawing needed."""
    from daruma_pixel import personas

    script = _script(conf)
    spec = personas.spec(_stage_names(conf)[0], None if hasattr(script, "build") else script)
    return getattr(spec.layers, "PROPS", None)


class Props(unittest.TestCase):
    """One test per pixel persona, so pytest-xdist can spread them."""

    @unittest.skipIf(yaml is None, "needs Pillow and PyYAML")
    def test_some_persona_declares_props(self):
        from daruma_pixel import personas

        layers = [spec.layers for spec in personas.discover().values()]
        self.assertTrue(any(getattr(m, "PROPS", None) for m in layers), "no persona declares PROPS")

    def check(self, file: str, conf: dict):
        props = _props(conf)
        if not props:
            self.skipTest(f"{file} declares no PROPS")
        states = registry.collect_states([registry.ModuleSpec("pomodoro", states=module_states())])
        names = [s.name for s in states]
        reactions = [s.name for s in states if s.kind == registry.REACTION and s.module == "core"]
        script = _script(conf)
        stage_names = _stage_names(conf)
        built = [_build(script, n) if n else None for n in stage_names]
        anims = _animation_names(built)
        char = registry.Persona(
            file,
            anims,
            behaviors={k: dict(v) for k, v in (conf.get("behaviors") or {}).items()},
            during={k: dict(v) for k, v in (conf.get("during") or {}).items()},
        )
        behaviors, _ = registry.resolve_persona(char, states)
        swaps = registry.resolve_during(char, states)
        for activity, boxes in props.items():
            act = names.index(activity)
            own = anims[behaviors[act].animation]
            for reaction in reactions:
                shown = behaviors[names.index(reaction)].animation
                usual = anims[shown]
                shown = next((d.instead for d in swaps if d.activity == act and d.shown == shown), shown)
                case = _Case(file, activity, reaction, own, anims[shown], usual)
                for stage, persona in zip(stage_names, built, strict=True):
                    self.check_stage(case, stage, persona, boxes)

    def check_stage(self, case: "_Case", stage: str, persona, boxes) -> None:
        """The reaction's animation keeps the prop pixels of every box, in every frame."""
        if persona is None or case.played not in persona.animations or case.own not in persona.animations:
            return
        for box in boxes:
            want = prop_pixels(persona, case.own, box)
            self.assertTrue(want, f"{case.file} {stage}: no prop pixels in {box} of {case.own}")
            for i, (img, _) in enumerate(persona.animations[case.played].frames):
                img = img.convert("RGBA")
                kept = sum(1 for xy, v in want.items() if img.getpixel(xy) == v)
                with self.subTest(persona=stage, activity=case.activity, reaction=case.reaction, frame=i):
                    self.assertGreaterEqual(
                        kept / len(want),
                        KEEP,
                        f"{case.file} {stage}: {case.reaction} during {case.activity} plays {case.played}; "
                        f"frame {i} keeps {kept} of {len(want)} prop pixels in {box}. Give the persona a "
                        f"`during: {{{case.activity}: {{{case.usual}: ...}}}}` "
                        "animation with the props",
                    )


@dataclass
class _Case:
    """A reaction over an activity: the animations it involves."""

    file: str
    activity: str
    reaction: str
    own: str  # The activity's own animation.
    played: str  # What plays over it.
    usual: str  # What the reaction plays without `during:`.


def _animation_names(built: list) -> list[str]:
    """Every animation name of the stages' personas, in first-seen order."""
    anims = []
    for persona in built:
        for name in persona.animations if persona else ():
            if name not in anims:
                anims.append(name)
    return anims


def _props_test(file: str, conf: dict):
    @unittest.skipIf(os.environ.get("DARUMA_SKIP_PERSONAS"), "DARUMA_SKIP_PERSONAS is set")
    def test(self):
        self.check(file, conf)

    return test


if yaml is not None:
    for _file, _conf in pixel_personas():
        _name = Path(_file).stem.removeprefix("persona_")
        setattr(Props, f"test_reactions_keep_the_activity_props_{_name}", _props_test(_file, _conf))


if __name__ == "__main__":
    unittest.main()
