"""Host test: the small rules of the drawing layer (daruma_pixel).

    uv run pytest tests/test_pixel_parts.py

The persona goldens check what the personas draw. These check the edges
the personas never reach: dots off the canvas, a prop moved to its spot,
the rug check, finding a persona's Spec, and the layer check's defaults.
"""

from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace

import pytest

Image = pytest.importorskip("PIL.Image")

from daruma_pixel import personas, pixelkit  # noqa: E402
from daruma_pixel.scene import PropLayer, Spot  # noqa: E402

RED = (255, 0, 0)


def painted(img: Image.Image) -> set[tuple[int, int]]:
    return {(x, y) for y in range(img.height) for x in range(img.width) if img.getpixel((x, y))[3]}


def test_canvas_dot_draws_inside_and_skips_outside():
    c = pixelkit.Canvas(3, 2)
    for x, y in [(-1, 0), (3, 0), (0, -1), (0, 2), (3, 2), (-1, -1)]:
        c.dot(x, y, RED)
    assert painted(c.img) == set()
    for x, y in [(0, 0), (2, 1)]:
        c.dot(x, y, RED)
    assert painted(c.img) == {(0, 0), (2, 1)}
    assert c.img.getpixel((2, 1)) == (*RED, 255)
    assert c.body.getpixel((2, 1)) == 1
    assert c.body.getpixel((1, 1)) == 0


def test_prop_layer_moves_the_anchor_onto_the_spot():
    layer = PropLayer((10, 20), Spot(13, 18), size=(8, 6))
    assert (layer.dx, layer.dy) == (3, -2)
    layer.dot(1.4, 2.6, RED)  # Rounds to (1, 3), then moves to (4, 1).
    assert painted(layer.img) == {(4, 1)}
    assert layer.img.getpixel((4, 1)) == (*RED, 255)
    assert layer.filled(1, 3)
    assert not layer.filled(1, 2)


def test_prop_layer_skips_dots_off_the_layer():
    layer = PropLayer((0, 0), Spot(0, 0), size=(4, 3))
    for x, y in [(-1, 0), (4, 0), (0, -1), (0, 3)]:
        layer.dot(x, y, RED)
        assert not layer.filled(x, y)
    assert painted(layer.img) == set()
    layer.dot(3, 2, RED)
    assert painted(layer.img) == {(3, 2)}
    assert layer.filled(3, 2)


RUG = (200, 40, 40)


def rug_room(w: int, h: int, spots: set[tuple[int, int]]) -> Image.Image:
    img = Image.new("RGBA", (w, h), (90, 90, 90, 255))
    for xy in spots:
        img.putpixel(xy, (*RUG, 255))
    return img


def test_check_rug_takes_the_bottom_13_rows_by_default():
    layers = SimpleNamespace(RUG_COLORS=[RUG])
    personas.check_rug(layers, rug_room(20, 20, {(0, 7), (19, 19)}))
    with pytest.raises(ValueError, match=r"\(5,6\)"):
        personas.check_rug(layers, rug_room(20, 20, {(5, 6)}))


def test_check_rug_takes_the_layers_box_with_its_ends_outside():
    layers = SimpleNamespace(RUG_COLORS=[RUG], RUG_BOX=(2, 3, 6, 5))
    personas.check_rug(layers, rug_room(10, 10, {(2, 3), (5, 4)}))
    for outside in [(1, 3), (6, 3), (2, 2), (2, 5), (8, 8)]:
        with pytest.raises(ValueError, match="outside the rug"):
            personas.check_rug(layers, rug_room(10, 10, {outside}))


def test_check_rug_compares_colors_at_screen_depth():
    layers = SimpleNamespace(RUG_COLORS=[RUG], RUG_BOX=(0, 0, 1, 1))
    # The same color at RGB565, by each channel's own depth: 5, 6, 5 bits.
    with pytest.raises(ValueError, match="outside the rug"):
        personas.check_rug(layers, _with(4, 4, (2, 2), (207, 43, 47)))
    personas.check_rug(layers, _with(4, 4, (2, 2), (208, 40, 40)))
    personas.check_rug(layers, _with(4, 4, (2, 2), (200, 44, 40)))
    personas.check_rug(layers, _with(4, 4, (2, 2), (200, 40, 48)))
    # A see-through pixel is no rug.
    personas.check_rug(layers, _with(4, 4, (2, 2), RUG, alpha=0))
    clash = SimpleNamespace(RUG_COLORS=[RUG, (201, 41, 41)])
    with pytest.raises(ValueError, match="collide"):
        personas.check_rug(clash, rug_room(4, 4, set()))


def _with(w, h, xy, color, alpha=255):
    img = Image.new("RGBA", (w, h), (90, 90, 90, 255))
    img.putpixel(xy, (*color, alpha))
    return img


def test_union_box_of_nothing_is_one_pixel():
    assert personas.union_box([]) == (0, 0, 1, 1)
    assert personas.union_box([Image.new("RGBA", (4, 4))]) == (0, 0, 1, 1)


def test_union_box_covers_every_picture():
    a, b = Image.new("RGBA", (10, 10)), Image.new("RGBA", (10, 10))
    a.putpixel((2, 7), (1, 1, 1, 255))
    b.putpixel((6, 1), (1, 1, 1, 255))
    assert personas.union_box([a, b]) == (2, 1, 7, 8)


def _module(name: str, **attrs) -> ModuleType:
    module = ModuleType(name)
    module.__dict__.update(attrs)
    return module


def test_specs_takes_one_persona_or_a_list():
    one = personas.Spec("solo", 0)
    module = _module("solo_module", PERSONA=one)
    (found,) = personas.specs(module).values()
    assert (found.name, found.layers, found.animations) == ("solo", module, module)
    two = _module("pair", PERSONAS=[personas.Spec("a", 0), personas.Spec("b", 0, layers="L")])
    assert {n: s.layers for n, s in personas.specs(two).items()} == {"a": two, "b": "L"}
    assert personas.specs(_module("empty")) == {}


def test_spec_finds_a_module_by_its_dotted_name(monkeypatch):
    module = _module("daruma_test_persona", PERSONA=personas.Spec("dotted", 0x102030))
    monkeypatch.setitem(sys.modules, "daruma_test_persona", module)
    assert personas.spec("dotted", "daruma_test_persona").background == 0x102030
    assert personas.spec("dotted", module).background == 0x102030
    with pytest.raises(ValueError, match="No persona 'other'"):
        personas.spec("other", "daruma_test_persona")


def test_spec_without_a_module_finds_every_persona():
    assert personas.spec("corgi").name == "corgi"


class Layers:
    """A tiny scene: the room at the top row, a plant pixel, the persona below."""

    WINDOW = None
    DEFAULT_STAGE = 1

    def __init__(self, scene_extra=None):
        self.scene_extra = scene_extra
        self.plants = []

    def background(self):
        img = Image.new("RGBA", (4, 3))
        img.putpixel((0, 0), (10, 20, 30, 255))
        return img

    def plant(self, stage, wilted):
        self.plants.append((stage, wilted))
        img = Image.new("RGBA", (4, 3))
        img.putpixel((1, 0), (0, 200, 0, 255) if not wilted else (90, 90, 0, 255))
        return img

    def foreground(self, pose):
        img = Image.new("RGBA", (4, 3))
        img.putpixel((pose, 2), (200, 0, 0, 255))
        return img

    def scene(self, pose):
        img = self.background()
        img.alpha_composite(self.plant(self.DEFAULT_STAGE, False))
        img.alpha_composite(self.foreground(pose))
        if self.scene_extra:
            img.putpixel(self.scene_extra, (255, 255, 255, 255))
        return img


def test_under_draws_the_room_and_the_default_plant():
    layers = Layers()
    below = personas.under(layers)
    assert layers.plants == [(1, False)]
    assert painted(below.plant) == {(1, 0)}
    assert personas.under(SimpleNamespace(background=layers.background)).plant is None


def test_check_layers_draws_what_the_caller_did_not_pass():
    personas.check_layers(Layers(), 2)
    personas.check_layers(Layers(), 2, personas.under(Layers()), Layers().foreground(2))
    with pytest.raises(ValueError, match="do not add up"):
        personas.check_layers(Layers(scene_extra=(3, 1)), 2)
    # A foreground passed in is the one checked: the wrong pose fails.
    with pytest.raises(ValueError, match="do not add up"):
        personas.check_layers(Layers(), 2, fg=Layers().foreground(1))
    # So is a room passed in.
    with pytest.raises(ValueError, match="do not add up"):
        personas.check_layers(Layers(), 2, below=personas.Under(Image.new("RGBA", (4, 3)), None))
