"""Frame sets for test_frames.cpp: encoded by sprite_codec.py, with the
pixels each frame must decode to.

    uv run --with pillow python tests/frames_fixture.py OUT [--personas]

Without --personas, only small made-up sets. With it, every pixel persona too
(corgi, The Boss, Jack Russell, the tabby cat and the daruma's three eye states), in full
color, gray4 and mono. Building the personas takes a minute or two.

The file is plain text, one record per line:

    set LABEL WIDTH HEIGHT FRAMES
    frame BASE X Y W H BITS CLEAR COLORS DATA  palette... data...
    expect FRAME  pixels...           (RGB565, -1 for see-through)
    seq N  frames...                  (an order the frames play in)
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parents[1]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


codec = _load("daruma_sprite_codec", _ROOT / "components" / "daruma" / "sprite_codec.py")


def persona_pictures(personas) -> tuple[list, list[list[int]]]:
    """Every frame picture of personas.Persona objects, and the orders they play
    in, the way daruma_sprites passes them to the encoder."""
    images, sequences = [], []

    def add(img) -> int:
        images.append(img)
        return len(images) - 1

    for persona in personas:
        for anim in persona.animations.values():
            seq = [add(img) for img, _ in anim.frames]
            sequences.append(seq)
            for extra in (anim.blink, anim.wink):
                if extra is not None:
                    sequences.append([seq[0], add(extra)])
    return images, sequences


def synthetic():
    """Small sets that hit the edge cases: see-through pixels appearing and
    going, a frame that only differs in one corner, long runs, many colors."""
    from PIL import Image

    def picture(w, h, fn):
        img = Image.new("RGBA", (w, h))
        img.putdata([fn(x, y) for y in range(h) for x in range(w)])
        return img

    sets = []
    # A dot that walks across a see-through field and back.
    walk = [picture(20, 6, lambda x, y, i=i: (255, 0, 0, 255) if (x == i and y == 2) else (0, 0, 0, 0))
            for i in range(12)]
    sets.append(("walk", walk, [list(range(12)), list(range(11, -1, -1))]))
    # A body that grows and shrinks over a background, with see-through edges.
    blob = [picture(30, 30, lambda x, y, r=r: (40 + x // 3 * 18, 200 - y // 3 * 15, 90, 255)
                    if (x - 15) ** 2 + (y - 15) ** 2 < r * r else (0, 0, 0, 0)) for r in (4, 7, 10, 13, 10, 7)]
    sets.append(("blob", blob, [[0, 1, 2, 3, 4, 5]]))
    # 250 colors, long rows (two-byte runs at 8 bits).
    def shade(v):
        return v // 32 * 8, v % 32 * 8, 0, 255  # 250 values, all different at RGB565.

    many = [picture(300, 3, lambda x, y, k=k: shade((x + y + k) % 250)) for k in range(3)]
    sets.append(("many", many, [[0, 1, 2]]))
    return sets


def personas_sets():
    sys.path.insert(0, str(_ROOT / "pixel"))
    from daruma_pixel import daruma_persona, personas

    out = []
    for label, build in (("corgi", lambda: [personas.build("corgi")]),
                         ("the_boss", lambda: [personas.build("the_boss")]),
                         ("jack_russell", lambda: [personas.build("jack_russell")]),
                         ("tabby_cat", lambda: [personas.build("tabby_cat")]),
                         ("daruma", lambda: [daruma_persona.build(n) for n in (0, 1, 2)])):
        try:
            built = build()
        except ImportError as err:  # A persona whose art lives elsewhere.
            print(f"frames_fixture: {label} skipped ({err})")
            continue
        images, sequences = persona_pictures(built)
        out.append((label, images, sequences))
    return out


def write(path: Path, sets, modes=("full",)) -> None:
    lines = []
    for label, images, sequences in sets:
        for mode in modes:
            fs = codec.encode_set(images, sequences, mode, label)
            lines.append(f"set {label}:{mode} {fs.width} {fs.height} {len(fs.frames)}")
            for f in fs.frames:
                lines.append(" ".join(map(str, ["frame", f.base, f.x, f.y, f.w, f.h, f.bits, f.clear,
                                                 len(f.palette), len(f.data), *f.palette, *f.data])))
            expected: dict[int, list[int]] = {}
            for i, img in enumerate(images):
                expected.setdefault(fs.index[i], codec.screen_pixels(img, mode))
            for frame in sorted(expected):
                lines.append(" ".join(map(str, ["expect", frame, *expected[frame]])))
            for seq in sequences:
                lines.append(" ".join(map(str, ["seq", len(seq), *(fs.index[i] for i in seq)])))
    path.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    sets = synthetic()
    modes = ("full",)
    if "--personas" in sys.argv:
        sets += personas_sets()
        modes = ("full", "gray4", "mono")
    write(Path(sys.argv[1]), sets, modes)
