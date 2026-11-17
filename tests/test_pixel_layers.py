"""Host test: the pixel packages import each other only downwards.

    uv run pytest tests/test_pixel_layers.py

Three layers, top to bottom:

- daruma_personas.<name>: one persona each. A persona may import shapes and
  the drawing layer, never another persona. Nothing imports a persona:
  daruma_pixel.personas finds them by name.
- daruma_shapes.<family>: pets, rooms, plants, office. A shape may import
  the drawing layer and other shapes, never a persona.
- daruma_pixel: the drawing layer. It imports no shapes and no personas.

grimp reads the import graph from the installed packages (the "pixel" group).
"""

from __future__ import annotations

import unittest

try:
    import grimp
except ImportError:  # pragma: no cover
    grimp = None

DRAWING, SHAPES, PERSONAS = "daruma_pixel", "daruma_shapes", "daruma_personas"


def _top(module: str) -> str:
    return module.split(".")[0]


def _persona(module: str) -> str:
    """daruma_personas.corgi for daruma_personas.corgi.moods."""
    return ".".join(module.split(".")[:2])


def broken_rule(importer: str, imported: str) -> str | None:
    """Why `importer` may not import `imported`, or None when it may."""
    low, high = _top(importer), _top(imported)
    if low == DRAWING and high in (SHAPES, PERSONAS):
        return "the drawing layer imports no shapes and no personas"
    if low == SHAPES and high == PERSONAS:
        return "a shape never imports a persona"
    if low == PERSONAS and high == PERSONAS and _persona(importer) != _persona(imported):
        return "a persona never imports another persona"
    return None


def violations(graph) -> list[str]:
    """One line per import that breaks a rule: file line, the import and the rule."""
    found = []
    for importer in sorted(graph.modules):
        for imported in sorted(graph.find_modules_directly_imported_by(importer)):
            if (rule := broken_rule(importer, imported)) is None:
                continue
            for detail in graph.get_import_details(importer=importer, imported=imported) or [{}]:
                where = f"{importer}:{detail.get('line_number', '?')}"
                found.append(f"{where}: {detail.get('line_contents', imported)!r} ({rule})")
    return found


@unittest.skipIf(grimp is None, "needs grimp (uv sync)")
class Layers(unittest.TestCase):
    def test_imports_go_down(self):
        graph = grimp.build_graph(DRAWING, SHAPES, PERSONAS)
        bad = violations(graph)
        self.assertEqual(bad, [], "Imports that break the pixel layers:\n" + "\n".join(bad))

    def test_every_layer_is_seen(self):
        graph = grimp.build_graph(DRAWING, SHAPES, PERSONAS)
        tops = {_top(m) for m in graph.modules}
        self.assertEqual(tops, {DRAWING, SHAPES, PERSONAS})
        self.assertIn(f"{PERSONAS}.corgi", graph.modules)
        self.assertIn(f"{SHAPES}.pets.rig", graph.modules)


class Rules(unittest.TestCase):
    """The rules on made-up names, so a broken check can't pass by finding nothing."""

    def test_allowed(self):
        for importer, imported in [
            ("daruma_shapes.pets.dog", "daruma_pixel.pixelkit"),
            ("daruma_shapes.rooms.living_room", "daruma_shapes.rooms.couch"),
            ("daruma_shapes.office.boss", "daruma_shapes.pets.rig"),
            ("daruma_personas.corgi", "daruma_shapes.pets.rig"),
            ("daruma_personas.corgi.preview", "daruma_personas.corgi"),
            ("daruma_personas.daruma.moods", "daruma_personas.daruma.doll"),
        ]:
            self.assertIsNone(broken_rule(importer, imported), (importer, imported))

    def test_forbidden(self):
        for importer, imported in [
            ("daruma_pixel.personas", "daruma_personas.corgi"),
            ("daruma_pixel.scene", "daruma_shapes.rooms.couch"),
            ("daruma_shapes.pets.dog", "daruma_personas.corgi.breed"),
            ("daruma_personas.corgi", "daruma_personas.jack_russell"),
            ("daruma_personas.tabby_cat", "daruma_personas.corgi.moods"),
        ]:
            self.assertIsNotNone(broken_rule(importer, imported), (importer, imported))

    def test_message_names_the_import(self):
        class Graph:
            modules = {"daruma_pixel.scene", "daruma_shapes.rooms.couch"}

            def find_modules_directly_imported_by(self, module):
                return {"daruma_shapes.rooms.couch"} if module == "daruma_pixel.scene" else set()

            def get_import_details(self, importer, imported):
                return [{"line_number": 7, "line_contents": "from daruma_shapes.rooms import couch"}]

        (line,) = violations(Graph())
        self.assertIn("daruma_pixel.scene:7", line)
        self.assertIn("from daruma_shapes.rooms import couch", line)


if __name__ == "__main__":
    unittest.main()
