"""Golden pictures of every pixel persona: each picture the device gets.

    uv run python tests/persona_frames.py check [PERSONA ...]
    uv run python tests/persona_frames.py update [PERSONA ...]

test_persona_frames.py runs the check, one test per persona. `update`
writes the goldens. It keeps a golden whose pixels did not change, so a
PNG written by another zlib does not show up as a change.

The goldens live in tests/golden/frames/<persona>/:

    persona.json               background, offsets, window, recolors, frame times
    backdrop.png               the room
    <animation>/<nn>.png       every frame, in play order
    <animation>/blink.png      and wink.png, when the animation has them
    plant/<stage>.png          and <stage>-wilted.png

A persona is a name from frames_fixture.persona_builds(). A build that
gives more than one persona (the daruma's eye states) gets one folder per
persona: daruma0, daruma1, daruma2.

A failed check writes the actual and the expected pictures to
$DARUMA_WORK/frames (or a temp folder) and names every file that differs.
"""

from __future__ import annotations

import dataclasses
import json
import os
import sys
import tempfile
from pathlib import Path

import frames_fixture
from PIL import Image

GOLDEN = Path(__file__).resolve().parent / "golden" / "frames"

# Every field of personas.Persona that the goldens cover. A new field fails
# the check until the goldens cover it too.
FIELDS = {
    "background",
    "backdrop",
    "sprite_offset",
    "animations",
    "window",
    "plant_offset",
    "plant_stages",
    "plant_wilted",
    "recolor_from",
    "recolor_by_weekday",
}


def builds() -> dict[str, object]:
    """label -> a function that builds the personas of that label."""
    return dict(frames_fixture.persona_builds())


def personas_of(label: str, build) -> dict[str, object]:
    """folder name -> personas.Persona for one entry of builds()."""
    built = build()
    if len(built) == 1:
        return {label: built[0]}
    return {f"{label}{i}": persona for i, persona in enumerate(built)}


def pictures(persona) -> dict[str, Image.Image]:
    """Relative path -> picture, for every picture of a persona."""
    out = {"backdrop.png": persona.backdrop}
    for key, anim in persona.animations.items():
        for i, (img, _ms) in enumerate(anim.frames):
            out[f"{key}/{i:02d}.png"] = img
        if anim.blink is not None:
            out[f"{key}/blink.png"] = anim.blink
        if anim.wink is not None:
            out[f"{key}/wink.png"] = anim.wink
    for stage, img in enumerate(persona.plant_stages):
        out[f"plant/{stage}.png"] = img
    for stage, img in enumerate(persona.plant_wilted):
        out[f"plant/{stage}-wilted.png"] = img
    return out


def _hex(color: int) -> str:
    return f"{color:06X}"


def numbers(persona) -> dict:
    """The parts of a persona that are not pictures, as JSON."""
    fields = {f.name for f in dataclasses.fields(persona)}
    if fields != FIELDS:
        raise AssertionError(f"personas.Persona changed: {sorted(fields ^ FIELDS)}. Cover it in {__file__}.")
    return {
        "background": _hex(persona.background),
        "sprite_offset": list(persona.sprite_offset),
        "window": list(persona.window) if persona.window is not None else None,
        "plant_offset": list(persona.plant_offset),
        "recolor_from": [_hex(c) for c in persona.recolor_from],
        "recolor_by_weekday": [[_hex(c) for c in day] for day in persona.recolor_by_weekday],
        "animations": {key: [ms for _img, ms in anim.frames] for key, anim in persona.animations.items()},
    }


def _json_text(data: dict) -> str:
    """One line per key, and one per animation: short diffs in review."""
    lines = []
    for key, value in data.items():
        if isinstance(value, dict):
            inner = ",\n".join(f"  {json.dumps(k)}: {json.dumps(v)}" for k, v in value.items())
            lines.append(f" {json.dumps(key)}: {{\n{inner}\n }}")
        else:
            lines.append(f" {json.dumps(key)}: {json.dumps(value)}")
    return "{\n" + ",\n".join(lines) + "\n}\n"


def same_pixels(a: Image.Image, b: Image.Image) -> bool:
    if a.size != b.size:
        return False
    return a.convert("RGBA").tobytes() == b.convert("RGBA").tobytes()


def _golden_files(folder: Path) -> set[str]:
    if not folder.is_dir():
        return set()
    return {p.relative_to(folder).as_posix() for p in folder.rglob("*.png")}


def _differs(path: Path, img: Image.Image) -> bool:
    if not path.is_file():
        return True
    with Image.open(path) as golden:
        return not same_pixels(golden, img)


def _save(path: Path, img: Image.Image) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, optimize=True)


def check(name: str, persona, out: Path) -> list[str]:
    """What differs between a persona and its goldens; writes the actual and
    the expected pictures of each difference under out/name."""
    folder = GOLDEN / name
    problems = []
    meta = folder / "persona.json"
    if not meta.is_file() or meta.read_text() != _json_text(numbers(persona)):
        problems.append("persona.json")
        _save_text(out / name / "persona.json", _json_text(numbers(persona)))
    pics = pictures(persona)
    for rel, img in sorted(pics.items()):
        if _differs(folder / rel, img):
            problems.append(rel)
            _save(out / name / "actual" / rel, img)
            if (folder / rel).is_file():
                with Image.open(folder / rel) as golden:
                    _save(out / name / "expected" / rel, golden)
    problems += [f"{rel} (no longer drawn)" for rel in sorted(_golden_files(folder) - pics.keys())]
    return problems


def _save_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def update(name: str, persona) -> list[str]:
    """Write the goldens of a persona; returns the files it changed."""
    folder = GOLDEN / name
    changed = []
    text = _json_text(numbers(persona))
    meta = folder / "persona.json"
    if not meta.is_file() or meta.read_text() != text:
        _save_text(meta, text)
        changed.append("persona.json")
    pics = pictures(persona)
    for rel, img in sorted(pics.items()):
        if _differs(folder / rel, img):
            _save(folder / rel, img)
            changed.append(rel)
    for rel in sorted(_golden_files(folder) - pics.keys()):
        (folder / rel).unlink()
        changed.append(f"{rel} (removed)")
    return changed


def results_folder() -> Path:
    base = os.environ.get("DARUMA_WORK") or tempfile.gettempdir()
    return Path(base) / "frames"


def selected(wanted: set[str]):
    """(name, persona) for every persona, or only the ones named in wanted
    (by folder name or by label)."""
    for label, build in builds().items():
        if wanted and label not in wanted and not any(w.startswith(label) for w in wanted):
            continue
        for name, persona in personas_of(label, build).items():
            if not wanted or name in wanted or label in wanted:
                yield name, persona


def _run(command: str, name: str, persona) -> bool:
    """Runs one command on one persona; True when its goldens differ."""
    if command == "update":
        changed = update(name, persona)
        print(f"{name}: {len(changed)} files written" if changed else f"{name}: unchanged", flush=True)
        return False
    problems = check(name, persona, results_folder())
    print(f"{name}: {len(problems)} differ" if problems else f"{name}: ok", flush=True)
    return bool(problems)


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in ("check", "update"):
        raise SystemExit(__doc__)
    failed = [_run(argv[0], name, persona) for name, persona in selected(set(argv[1:]))]
    return int(any(failed))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
