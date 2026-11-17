#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["aioesphomeapi==46.30.0", "pillow>=10", "pyyaml>=6"]
# ///
"""Record demo GIFs of every persona, or check the screens against golden pictures.

    uv run demos/record.py                     all personas, all scenarios
    uv run demos/record.py --personas Eyes --scenario tour
    uv run demos/record.py --test              check, exit 1 on a difference
    uv run demos/record.py --update-golden     write new golden pictures

It builds the desktop firmware once (examples/desktop.yaml, in a scratch
folder), then runs each persona through each scenario (scenarios/*.yaml) on a
clock it controls, so every run draws the same frames.

Demo mode writes docs/demos/<persona>-<scenario>.gif (2x, or the scenario's
gif_scale; nearest neighbour; kept under --max-kb), and with --mp4 an MP4
with the sounds. Test mode runs the scenarios' snapshot and expect steps; on a failure it writes the actual
picture, a diff and a GIF of the run to --out.

Needs: uv, a C compiler, SDL2 (brew install sdl2) and ffmpeg.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import scenario as scenarios  # noqa: E402
from harness import GOLDEN_DIR, HERE, Device, build, slug  # noqa: E402
from media import encode_gif, encode_mp4, frames_of, sounds_of, with_captions, with_touches  # noqa: E402

DOCS_DEMOS = HERE.parent / "docs" / "demos"
DEFAULT_WORK = Path(tempfile.gettempdir()) / "daruma-demos"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--personas", default="all", help="'all' or persona names, comma-separated (as in the Persona select)")
    ap.add_argument("--scenario", default="all", help="'all' or scenario names, comma-separated")
    ap.add_argument("--private-persona", action="append", default=[], metavar="PACKAGE",
                    help="an extra persona package (a path); its demos go to --out only")
    ap.add_argument("--variant", default="standard", choices=["standard", "wide", "square"])
    ap.add_argument("--out", type=Path, default=DEFAULT_WORK, help="scratch folder: build, frames, results")
    ap.add_argument("--docs", type=Path, default=DOCS_DEMOS, help="where public GIFs go")
    ap.add_argument("--max-kb", type=int, default=2000)
    ap.add_argument("--mp4", action="store_true", help="also write an MP4 with sound")
    ap.add_argument("--window", action="store_true", help="show the window while it runs")
    ap.add_argument("--test", action="store_true", help="check snapshots and expects; no GIFs")
    ap.add_argument("--update-golden", action="store_true", help="write golden pictures from this run")
    ap.add_argument("--port", type=int, default=6053, help="the API port (another runner may hold 6053)")
    args = ap.parse_args()
    test = args.test or args.update_golden

    work = args.out
    print(f"Building in {work} ...", flush=True)
    b = build(work / "build", variant=args.variant, private_packages=args.private_persona, port=args.port)

    chosen = scenarios.all_scenarios()
    if args.scenario != "all":
        names = args.scenario.split(",")
        chosen = [scenarios.load(n) for n in names]

    failures = 0
    with _probe(b, work) as personas_all:
        pass
    if args.personas == "all":
        personas = [f for f in personas_all if f not in b.private_personas]
    else:
        personas = [f.strip() for f in args.personas.split(",")]
        unknown = [f for f in personas if f not in personas_all]
        if unknown:
            print(f"No persona named {unknown}; personas: {personas_all}", file=sys.stderr)
            return 2

    for sc in chosen:
        for persona in personas:
            if not sc.runs_on(persona, test):
                continue
            # Other screen sizes get their own GIFs and golden pictures.
            size = "" if args.variant == "standard" else f"-{args.variant}"
            label = f"{slug(persona)}-{sc.name}{size}"
            run_dir = work / "runs" / label
            shutil.rmtree(run_dir, ignore_errors=True)
            # A private persona's pictures stay in the scratch folder.
            golden = (work / "golden" if persona in b.private_personas else GOLDEN_DIR) / slug(persona) / f"{sc.name}{size}"
            print(f"{'Test' if test else 'Demo'} {persona} / {sc.name} ...", flush=True)
            device = Device(b, run_dir, persona=persona, window=args.window, golden=golden,
                          update_golden=args.update_golden)
            try:
                with device:
                    scenarios.run_setup(device, sc)
                    device.record_start(run_dir / "frames")
                    ok = True
                    try:
                        scenarios.run(device, sc, test=test)
                    except AssertionError as e:
                        ok = False
                        failures += 1
                        print(f"  FAIL: {e}", flush=True)
                    device.record_stop()
                    skipped = device.skipped
                    captions = device.captions
                    touches = device.touches
            except Exception:  # noqa: BLE001 - report and go on with the next run
                failures += 1
                traceback.print_exc()
                continue
            frames = frames_of(run_dir / "frames", skipped)
            if not frames:
                print("  no frames recorded", flush=True)
                failures += 1
                continue
            private = persona in b.private_personas
            if test:
                if not ok:
                    size = encode_gif(frames, run_dir / "results" / "trace.gif", args.max_kb)
                    print(f"  trace: {run_dir / 'results'} ({size // 1024} KB GIF)", flush=True)
                else:
                    print("  ok", flush=True)
                continue
            (run_dir / "marks.json").write_text(json.dumps({"captions": captions, "touches": touches,
                                                            "skipped": skipped}, indent=1))
            # Touch marks, and frames split where a caption starts, for the GIF only.
            frames = with_touches(frames, touches, skipped, run_dir / "touched", split_at=[ms for ms, _ in captions])
            if captions:
                frames = with_captions(frames, captions, run_dir / "captioned")
            target = (work / "demos" if private else args.docs) / f"{label}.gif"
            size = encode_gif(frames, target, args.max_kb, scale=sc.gif_scale)
            print(f"  {target} ({size // 1024} KB, {sum(d for _, d in frames):.1f} s)", flush=True)
            if args.mp4:
                mp4 = (work / "demos") / f"{label}.mp4"
                mp4.parent.mkdir(parents=True, exist_ok=True)
                encode_mp4(frames, sounds_of(run_dir / "frames", skipped), mp4)
                print(f"  {mp4}", flush=True)
    if failures:
        print(f"{failures} failed", file=sys.stderr)
    return 1 if failures else 0


class _probe:
    """Start the build once to read the Persona select's options."""

    def __init__(self, b, work: Path):
        self.device = Device(b, work / "runs" / "_probe")

    def __enter__(self) -> list[str]:
        self.device.start()
        return self.device.personas()

    def __exit__(self, *exc) -> None:
        self.device.close()


if __name__ == "__main__":
    sys.exit(main())
