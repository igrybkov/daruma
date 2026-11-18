"""Record demo GIFs of every persona.

    uv run demos/record.py                     all personas, all scenarios
    uv run demos/record.py --personas Eyes --scenario tour

It builds the desktop firmware once (examples/desktop.yaml, in a scratch
folder), then runs each persona through each scenario (scenarios/*.yaml) on a
clock it controls, so every run draws the same frames.

It writes docs/demos/<persona>-<scenario>.gif (2x, or the scenario's
gif_scale; nearest neighbour; kept under --max-kb), and with --mp4 an MP4
with the sounds. A scenario with `stills: true` writes no GIF: each of its
snapshots becomes docs/demos/screens/<persona>-<name>.png. The same scenarios run as tests in pytest (conftest.py):
their snapshot and expect steps check the screens there.

Needs: uv, a C compiler, SDL2 and ffmpeg (docs/testing.md).
"""

from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import sys
import tempfile
import traceback
from concurrent.futures import ProcessPoolExecutor
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from pathlib import Path

import scenario as scenarios  # noqa: E402
from harness import HERE, Build, Device, build, slug  # noqa: E402
from media import encode_gif, encode_mp4, frames_of, sounds_of, with_captions, with_touches  # noqa: E402

DOCS_DEMOS = HERE.parent / "docs" / "demos"
DEFAULT_WORK = Path(tempfile.gettempdir()) / "daruma-demos"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "--personas", default="all", help="'all' or persona names, comma-separated (as in the Persona select)"
    )
    ap.add_argument("--scenario", default="all", help="'all' or scenario names, comma-separated")
    ap.add_argument(
        "--private-persona",
        action="append",
        default=[],
        metavar="PACKAGE",
        help="an extra persona package (a path); its demos go to --out only",
    )
    ap.add_argument("--variant", default="standard", choices=["standard", "wide", "square"])
    ap.add_argument("--out", type=Path, default=DEFAULT_WORK, help="scratch folder: build, frames, results")
    ap.add_argument("--docs", type=Path, default=DOCS_DEMOS, help="where public GIFs go")
    ap.add_argument("--max-kb", type=int, default=2000)
    ap.add_argument("--mp4", action="store_true", help="also write an MP4 with sound")
    ap.add_argument("--window", action="store_true", help="show the window while it runs")
    ap.add_argument(
        "--port", type=int, default=6053, help="the API port built into the program; runs listen on free ports"
    )
    ap.add_argument(
        "--jobs",
        type=int,
        default=min(4, os.cpu_count() or 1),
        help="runs at a time (default: up to 4)",
    )
    args = ap.parse_args()

    work = args.out
    print(f"Building in {work} ...", flush=True)
    b = build(work / "build", variant=args.variant, private_packages=args.private_persona, port=args.port)

    chosen = scenarios.all_scenarios()
    if args.scenario != "all":
        names = args.scenario.split(",")
        chosen = [scenarios.load(n) for n in names]

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

    jobs = []
    for sc in chosen:
        for persona in personas:
            if sc.runs_on(persona, test=False):
                jobs.append(
                    Job(
                        b,
                        sc,
                        persona,
                        args.variant,
                        work,
                        args.docs,
                        args.max_kb,
                        args.mp4,
                        args.window,
                    )
                )
    failures = 0
    if args.jobs <= 1 or len(jobs) <= 1:
        for job in jobs:
            failures += _run_job(job)
    else:
        # All runs share one build.
        with ProcessPoolExecutor(min(args.jobs, len(jobs))) as pool:
            for failed, text in pool.map(_run_job_captured, jobs):
                print(text, end="", flush=True)
                failures += failed
    if failures:
        print(f"{failures} failed", file=sys.stderr)
    return 1 if failures else 0


@dataclass
class Job:
    """One persona through one scenario."""

    build: Build
    scenario: scenarios.Scenario
    persona: str
    variant: str
    work: Path
    docs: Path
    max_kb: int
    mp4: bool
    window: bool


def _run_job_captured(job: Job) -> tuple[int, str]:
    """Run one job in a pool worker. Returns 1 when it failed, and its output,
    so the output of runs at the same time does not mix."""
    out = io.StringIO()
    with redirect_stdout(out), redirect_stderr(out):
        failed = _run_job(job)
    return failed, out.getvalue()


def _run_job(job: Job) -> int:
    """Run one job. Returns 1 when it failed."""
    b, sc, persona = job.build, job.scenario, job.persona
    # Other screen sizes get their own GIFs.
    size = "" if job.variant == "standard" else f"-{job.variant}"
    label = f"{slug(persona)}-{sc.name}{size}"
    run_dir = job.work / "runs" / label
    shutil.rmtree(run_dir, ignore_errors=True)
    print(f"Demo {persona} / {sc.name} ...", flush=True)
    if sc.stills:
        return _run_stills(job, run_dir)
    device = Device(b, run_dir, persona=persona, window=job.window)
    failed = 0
    try:
        with device:
            scenarios.run_setup(device, sc)
            device.record_start(run_dir / "frames")
            try:
                scenarios.run(device, sc, test=False)
            except AssertionError as e:
                failed = 1
                print(f"  FAIL: {e}", flush=True)
            device.record_stop()
            skipped = device.skipped
            captions = device.captions
            touches = device.touches
    except Exception:  # noqa: BLE001 - report and go on with the next run
        traceback.print_exc()
        return 1
    frames = frames_of(run_dir / "frames", skipped)
    if not frames:
        print("  no frames recorded", flush=True)
        return 1
    private = persona in b.private_personas
    (run_dir / "marks.json").write_text(
        json.dumps({"captions": captions, "touches": touches, "skipped": skipped}, indent=1)
    )
    # Touch marks, and frames split where a caption starts, for the GIF only.
    frames = with_touches(frames, touches, skipped, run_dir / "touched", split_at=[ms for ms, _ in captions])
    if captions:
        frames = with_captions(frames, captions, run_dir / "captioned")
    target = (job.work / "demos" if private else job.docs) / f"{label}.gif"
    nbytes = encode_gif(frames, target, job.max_kb, scale=sc.gif_scale)
    print(f"  {target} ({nbytes // 1024} KB, {sum(d for _, d in frames):.1f} s)", flush=True)
    if job.mp4:
        mp4 = (job.work / "demos") / f"{label}.mp4"
        mp4.parent.mkdir(parents=True, exist_ok=True)
        encode_mp4(frames, sounds_of(run_dir / "frames", skipped), mp4)
        print(f"  {mp4}", flush=True)
    return failed


def _run_stills(job: Job, run_dir: Path) -> int:
    """Run a `stills` scenario: each snapshot becomes a PNG, with no GIF.
    Returns 1 when it failed."""
    sc, persona = job.scenario, job.persona
    private = persona in job.build.private_personas
    shots = run_dir / "stills"
    try:
        with Device(job.build, run_dir, persona=persona, window=job.window) as device:
            scenarios.run_setup(device, sc)
            scenarios.run(device, sc, test=False, stills=shots)
    except AssertionError as e:
        print(f"  FAIL: {e}", flush=True)
        return 1
    except Exception:  # noqa: BLE001 - report and go on with the next run
        traceback.print_exc()
        return 1
    target = (job.work / "demos" if private else job.docs) / "screens"
    target.mkdir(parents=True, exist_ok=True)
    for png in sorted(shots.glob("*.png")):
        out = target / f"{slug(persona)}-{png.name}"
        shutil.copyfile(png, out)
        print(f"  {out}", flush=True)
    return 0


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
