"""Host test: an activity's props stay in the picture while a reaction plays.

    uv run --with pillow --with pyyaml python -m unittest discover -s tests -p test_props.py

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

Personas without PROPS are not checked; adding PROPS to a persona's layers
module is enough to bring it in. It builds the personas (about a minute); set
DARUMA_SKIP_PERSONAS=1 to skip it, as test_frames.py does.
"""

import importlib.util
import os
from pathlib import Path
import re
import sys
import unittest

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_PACKAGES = _ROOT / "packages"
_LIBRARY = _ROOT / "pixel"
sys.path.insert(0, str(_LIBRARY))

try:
    from PIL import Image  # noqa: F401
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

_REGISTRY = _ROOT / "components" / "daruma" / "registry.py"
_SPEC = importlib.util.spec_from_file_location("daruma_registry_props", _REGISTRY)
registry = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = registry
_SPEC.loader.exec_module(registry)

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
    out = []
    for path in sorted(_PACKAGES.glob("persona_*.yaml")):
        conf = load_persona_config(path)
        if "pixel_art" in conf:
            out.append((path.name, conf))
    return out


def _script(conf: dict):
    # Scripts are named relative to their package file. A library script is
    # imported as a module of daruma_pixel, so its relative imports work.
    path = (_PACKAGES / conf["pixel_art"]["script"]).resolve()
    library = _LIBRARY.resolve()
    if path.is_relative_to(library):
        return importlib.import_module(".".join(path.relative_to(library).with_suffix("").parts))
    spec = importlib.util.spec_from_file_location(f"daruma_props_{path.stem}", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


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


class Props(unittest.TestCase):
    @unittest.skipIf(yaml is None, "needs Pillow and PyYAML")
    @unittest.skipIf(os.environ.get("DARUMA_SKIP_PERSONAS"), "DARUMA_SKIP_PERSONAS is set")
    def test_reactions_keep_the_activity_props(self):
        states = registry.collect_states([registry.ModuleSpec("pomodoro", states=module_states())])
        names = [s.name for s in states]
        reactions = [s.name for s in states if s.kind == registry.REACTION and s.module == "core"]
        checked = 0
        for file, conf in pixel_personas():
            script = _script(conf)
            from daruma_pixel import personas  # The script registers its personas with it.

            stage_names = [conf["pixel_art"]["persona"]] + [conf["pixel_art"].get("goal", {}).get(k) for k in GOAL_KEYS]
            built = [script.build(n) if n else None for n in stage_names]
            layers = personas._persona(stage_names[0])[1]
            props = getattr(layers, "PROPS", None)
            if not props:
                continue
            anims = []
            for persona in built:
                for name in persona.animations if persona else ():
                    if name not in anims:
                        anims.append(name)
            char = registry.Persona(
                file, anims,
                behaviors={k: dict(v) for k, v in (conf.get("behaviors") or {}).items()},
                during={k: dict(v) for k, v in (conf.get("during") or {}).items()})
            behaviors, _ = registry.resolve_persona(char, states)
            swaps = registry.resolve_during(char, states)
            for activity, boxes in props.items():
                act = names.index(activity)
                own = anims[behaviors[act].animation]
                for reaction in reactions:
                    shown = behaviors[names.index(reaction)].animation
                    usual = anims[shown]
                    shown = next((d.instead for d in swaps if d.activity == act and d.shown == shown), shown)
                    played = anims[shown]
                    for stage, persona in zip(stage_names, built):
                        if persona is None or played not in persona.animations or own not in persona.animations:
                            continue
                        for box in boxes:
                            want = prop_pixels(persona, own, box)
                            self.assertTrue(want, f"{file} {stage}: no prop pixels in {box} of {own}")
                            for i, (img, _) in enumerate(persona.animations[played].frames):
                                img = img.convert("RGBA")
                                kept = sum(1 for xy, v in want.items() if img.getpixel(xy) == v)
                                with self.subTest(persona=stage, activity=activity, reaction=reaction, frame=i):
                                    self.assertGreaterEqual(
                                        kept / len(want), KEEP,
                                        f"{file} {stage}: {reaction} during {activity} plays {played}; frame {i} "
                                        f"keeps {kept} of {len(want)} prop pixels in {box}. Give the persona a "
                                        f"`during: {{{activity}: {{{usual}: ...}}}}` "
                                        "animation with the props")
                            checked += 1
        self.assertGreater(checked, 0, "no persona declares PROPS")


if __name__ == "__main__":
    unittest.main()
