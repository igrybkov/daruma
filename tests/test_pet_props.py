"""Host test: a reaction over an activity keeps the pet whole (personas on the pet rig, daruma_shapes.pets.rig).

    uv run pytest tests/test_pet_props.py

While a pet holds an activity with props (focus: glasses and a book, or a
ball), a reaction can play over it: petted, startled, celebrate, a task
done. The device then shows the animation the persona's `during:` names for
it, else the reaction's own. For every pet persona, every such activity and
every reaction that can play over it, each frame shown must:

  - keep the activity's props: the glasses' glint, the book, the ball;
  - move the head with the body: sideways, both shift the same (within a
    pixel, which a head tilt takes), so the body never sways under a head
    that stays put.

The personas' animations, behaviors and `during:` are the ones the build
uses: the persona module's ANIMATIONS and the persona YAML, resolved through the
registry with the core's, the pomodoro's and the tasks' states.
tests/test_props.py checks the prop pixels themselves stay put.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

import esphome_components  # noqa: E402, F401
import yaml  # noqa: E402
from esphome.components.daruma import registry  # noqa: E402

from daruma_pixel import personas  # noqa: E402
from daruma_shapes.pets import rig as pet  # noqa: E402

# Props, by a color only that prop has.
PROP_MARKS = {"glasses": pet.LENS_GLINT, "book": pet.BOOK.base, "ball": pet.BALL.base}
NOSE_SHINE = (120, 96, 92)  # dog.py: one pixel on every dog's nose, to find the head.

# Reactions the pomodoro plays when its own focus ends: it switches to a
# break, or stops, in the same turn, so they never show over the focus.
ENDS_THE_FOCUS = {"focus_done", "goal", "focus_stopped", "break_over"}


def _duration_ms(text: str) -> int:
    m = re.fullmatch(r"(\d+)(ms|s)", text)
    return int(m[1]) * (1 if m[2] == "ms" else 1000) if m else 0


def module_states() -> list:
    """The pomodoro's states (pomodoro.yaml) and the tasks' (daruma_tasks)."""
    out = []
    yaml = (ROOT / "packages" / "pomodoro.yaml").read_text()
    for m in re.finditer(r"^\s+(\w+): \{ kind: (\w+), fallback: (\w+)(?:[^}]*duration: (\w+))?", yaml, re.M):
        out.append(registry.State(m[1], m[2], m[3], duration_ms=_duration_ms(m[4] or ""), module="pomodoro"))
    tasks = (ROOT / "src" / "esphome" / "components" / "daruma_tasks" / "__init__.py").read_text()
    for m in re.finditer(r'State\("(\w+)", (\w+), "(\w+)".*?duration_ms=(\d+)', tasks):
        out.append(registry.State(m[1], m[2].lower(), m[3], duration_ms=int(m[4]), module="daruma_tasks"))
    return out


def persona_config(persona: str) -> dict:
    """The daruma_sprites entry of the persona YAML whose pixel_art builds `persona`."""

    class Loader(yaml.SafeLoader):
        pass

    Loader.add_multi_constructor("!", lambda loader, suffix, node: None)
    for path in sorted((ROOT / "packages").glob("persona_*.yaml")):
        conf = ((yaml.load(path.read_text(), Loader=Loader) or {}).get("daruma_sprites") or [{}])[0]
        if conf.get("pixel_art", {}).get("persona") == persona:
            return conf
    raise AssertionError(f"No persona YAML builds pixel_art persona '{persona}'")


def pet_personas() -> list[str]:
    """Personas drawn on the pet rig: their layers module has a pet.Pet."""
    out = []
    for name, spec in personas.discover().items():
        if isinstance(getattr(spec.layers, "_pet", None), pet.Pet):
            out.append(name)
    return out


def has_props(pose) -> bool:
    return bool(pose.prop or pose.glasses)


def marks(img) -> set[str]:
    colors = {px[:3] for px in img.getdata() if px[3]}
    return {name for name, color in PROP_MARKS.items() if color in colors}


def nose(img) -> tuple[int, int]:
    px = img.load()
    for y in range(img.height):
        for x in range(img.width):
            if px[x, y][3] and px[x, y][:3] == NOSE_SHINE:
                return x, y
    raise AssertionError("no nose shine in the frame")


def band_shift(base, frame, rows: range) -> tuple[int, int]:
    """Where the rows of `base` best match `frame`: the (dx, dy) under which
    most of their opaque pixels land on the same color."""
    a, b = base.load(), frame.load()
    w, h = base.size
    pixels = [(x, y, a[x, y]) for y in rows for x in range(w) if a[x, y][3]]
    best, best_score = (0, 0), -1
    for dy in range(-10, 5):
        for dx in range(-4, 5):
            score = sum(1 for x, y, c in pixels if 0 <= x + dx < w and 0 <= y + dy < h and b[x + dx, y + dy] == c)
            # Ties go to the smallest move.
            if score > best_score or (score == best_score and abs(dx) + abs(dy) < abs(best[0]) + abs(best[1])):
                best, best_score = (dx, dy), score
    return best


class RigTest(unittest.TestCase):
    """The checks below catch what they should, on frames drawn here."""

    def test_a_free_butt_wag_moves_the_body_under_a_still_head(self):
        from daruma_personas.corgi import breed as corgi

        base = corgi.render(pet.READING)
        wag = corgi.render(pet.with_(pet.LOVED, wag=1.0))
        _, ny = nose(base)
        head = band_shift(base, wag, range(0, ny + 3))
        body = band_shift(base, wag, range(ny + 12, ny + 21))
        self.assertGreater(abs(head[0] - body[0]), 1)
        self.assertNotIn("book", marks(wag))

    def test_a_wag_with_a_book_moves_head_and_body_together(self):
        from daruma_personas.corgi import breed as corgi

        base = corgi.render(pet.READING)
        wag = corgi.render(pet.with_(pet.READING, wag=1.0))
        _, ny = nose(base)
        head = band_shift(base, wag, range(0, ny + 3))
        body = band_shift(base, wag, range(ny + 12, ny + 21))
        self.assertEqual(head[0], body[0])
        self.assertEqual(head[0], -2)


class ReactionsOverActivities(unittest.TestCase):
    def test_props_stay_and_the_head_moves_with_the_body(self):
        states = registry.collect_states([registry.ModuleSpec("modules", states=module_states())])
        reactions = [
            s for s in states if s.kind == registry.REACTION and s.duration_ms > 0 and s.name not in ENDS_THE_FOCUS
        ]
        activities = [s for s in states if s.kind == registry.ACTIVITY]
        self.assertIn("petted", [s.name for s in reactions])
        self.assertIn("focus", [s.name for s in activities])
        checked = 0
        names = pet_personas()
        self.assertIn("corgi", names)
        self.assertIn("jack_russell", names)
        for name in names:
            spec = personas.spec(name)
            layers, source = spec.layers, spec.animations
            anims = list(source.ANIMATIONS)
            conf = persona_config(name)
            char = registry.Persona(
                name,
                anims,
                {k: dict(v) for k, v in (conf.get("behaviors") or {}).items()},
                during={k: dict(v) for k, v in (conf.get("during") or {}).items()},
            )
            behaviors, _ = registry.resolve_persona(char, states)
            swaps = registry.resolve_during(char, states)
            index = {s.name: i for i, s in enumerate(states)}
            look = {s.name: anims[b.animation] for s, b in zip(states, behaviors, strict=False)}
            for activity in activities:
                held = look[activity.name]
                if not any(has_props(p) for p, _ in source.ANIMATIONS[held]):
                    continue
                held_frames = [layers.foreground(p) for p, _ in source.ANIMATIONS[held]]
                kept = set.intersection(*(marks(img) for img in held_frames))
                self.assertTrue(kept, f"{name} {held}: no prop marks found")
                base = held_frames[0]
                _, ny = nose(base)
                for reaction in reactions:
                    shown = behaviors[index[reaction.name]].animation
                    played = anims[
                        next(
                            (d.instead for d in swaps if d.activity == index[activity.name] and d.shown == shown), shown
                        )
                    ]
                    for i, (pose, _) in enumerate(source.ANIMATIONS[played]):
                        where = f"{name}: {reaction.name} over {activity.name} plays '{played}', frame {i}"
                        img = layers.foreground(pose)
                        self.assertLessEqual(kept, marks(img), f"{where}: props missing")
                        head = band_shift(base, img, range(0, ny + 3))
                        body = band_shift(base, img, range(ny + 12, ny + 21))
                        self.assertLessEqual(
                            abs(head[0] - body[0]), 1, f"{where}: head moves {head[0]}, body {body[0]}"
                        )
                        checked += 1
        self.assertGreater(checked, 0)


if __name__ == "__main__":
    unittest.main()
