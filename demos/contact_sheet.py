"""Contact sheets of recorded demo GIFs, and side-by-side pictures of failed checks.

    uv run python demos/contact_sheet.py gifs <gif folder> <out folder>
    uv run python demos/contact_sheet.py diffs <results root> <out folder>

`gifs` writes one <scenario>-sheet.png per scenario: a row per persona, with
frames taken at even steps through its GIF. `diffs` finds every
<name>-actual.png under the results root and writes expected | actual | diff
side by side, from the <name>-expected.png and <name>-diff.png next to it.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageDraw, ImageSequence

FRAMES = 6
LABEL = 18
GAP = 4
BACKGROUND = (24, 24, 24)
TEXT = (230, 230, 230)


def _frames(gif: Path, count: int) -> list[Image.Image]:
    with Image.open(gif) as im:
        frames = [f.convert("RGB") for f in ImageSequence.Iterator(im)]
    step = max(1, len(frames) // count)
    return frames[::step][:count]


def _sheet(rows: list[tuple[str, list[Image.Image]]]) -> Image.Image:
    w = max(f.width for _, fs in rows for f in fs)
    h = max(f.height for _, fs in rows for f in fs)
    cols = max(len(fs) for _, fs in rows)
    sheet = Image.new("RGB", (cols * (w + GAP) + GAP, len(rows) * (h + LABEL + GAP) + GAP), BACKGROUND)
    draw = ImageDraw.Draw(sheet)
    for r, (label, frames) in enumerate(rows):
        y = GAP + r * (h + LABEL + GAP)
        draw.text((GAP, y + 2), label, fill=TEXT)
        for c, frame in enumerate(frames):
            sheet.paste(frame, (GAP + c * (w + GAP), y + LABEL))
    return sheet


def gif_sheets(gif_dir: Path, out: Path) -> None:
    """GIFs are named <persona>-<scenario>.gif, as record.py writes them."""
    by_scenario: dict[str, list[Path]] = defaultdict(list)
    for gif in sorted(gif_dir.glob("*.gif")):
        persona, _, scenario = gif.stem.rpartition("-")
        if persona:
            by_scenario[scenario].append(gif)
    out.mkdir(parents=True, exist_ok=True)
    for scenario, gifs in sorted(by_scenario.items()):
        rows = [(gif.stem.rpartition("-")[0], _frames(gif, FRAMES)) for gif in gifs]
        _sheet(rows).save(out / f"{scenario}-sheet.png")
        print(f"{scenario}-sheet.png: {len(rows)} personas")


def diff_pictures(root: Path, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    seen: set[Path] = set()
    for actual in sorted(root.rglob("*-actual.png")):
        # pytest links <name>current to the newest run folder: skip the copy.
        if actual.resolve() in seen:
            continue
        seen.add(actual.resolve())
        name = actual.name.removesuffix("-actual.png")
        cells = [
            ("expected", actual.with_name(f"{name}-expected.png")),
            ("actual", actual),
            ("diff", actual.with_name(f"{name}-diff.png")),
        ]
        row = [(label, [Image.open(p).convert("RGB")]) for label, p in cells if p.exists()]
        frames = [frame for _, fs in row for frame in fs]
        labels = " | ".join(label for label, _ in row)
        target = out / f"{actual.parent.parent.name}-{name}.png"
        _sheet([(labels, frames)]).save(target)
        print(target.name)


def main() -> int:
    if len(sys.argv) != 4 or sys.argv[1] not in ("gifs", "diffs"):
        print(__doc__, file=sys.stderr)
        return 2
    mode, src, out = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    if mode == "gifs":
        gif_sheets(src, out)
    else:
        diff_pictures(src, out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
