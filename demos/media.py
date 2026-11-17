"""Frames and sounds of a recording, turned into a GIF or an MP4 (ffmpeg).

A recording (Device.record_start) is a folder of f_<ms>_<n>.bmp frames and
s_<ms>_<name>.wav sounds; <ms> counts from the start. Stretches the runner
skipped are cut out of the timeline.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def frames_of(frames_dir: Path, skipped: list[tuple[int, int]]) -> list[tuple[Path, float]]:
    """The recorded frames with how long each stayed, skipped stretches cut out."""
    shots = sorted(frames_dir.glob("f_*.bmp"))
    times = [int(p.stem.split("_")[1]) for p in shots]

    def shown(ms: int) -> int:
        cut = sum(max(0, min(ms, b) - a) for a, b in skipped)
        return ms - cut

    out = []
    for i, (path, ms) in enumerate(zip(shots, times)):
        if i + 1 == len(shots):
            break  # The last one marks the end.
        d = (shown(times[i + 1]) - shown(ms)) / 1000
        if d > 0:
            out.append((path, d))
    return out


def sounds_of(frames_dir: Path, skipped: list[tuple[int, int]]) -> list[tuple[Path, float]]:
    out = []
    for p in sorted(frames_dir.glob("s_*.wav")):
        ms = int(p.stem.split("_")[1])
        cut = sum(max(0, min(ms, b) - a) for a, b in skipped)
        out.append((p, (ms - cut) / 1000))
    return out


def _concat_list(frames: list[tuple[Path, float]], path: Path) -> None:
    lines = []
    for f, d in frames:
        lines += [f"file '{f}'", f"duration {d:.3f}"]
    lines.append(f"file '{frames[-1][0]}'")  # The concat demuxer needs the last one twice.
    path.write_text("\n".join(lines) + "\n")


def encode_gif(frames: list[tuple[Path, float]], out: Path, max_kb: int, scale: int = 2) -> int:
    """Write a GIF at `scale` (nearest neighbour); drop the frame rate, then the colors, until it fits."""
    listing = frames[0][0].parent / f"{out.stem}.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    _concat_list(frames, listing)
    out.parent.mkdir(parents=True, exist_ok=True)
    for fps, colors in ((None, 256), (12, 128), (8, 96), (6, 64)):
        rate = f"fps={fps}," if fps else ""
        vf = (
            f"{rate}scale=iw*{scale}:ih*{scale}:flags=neighbor,split[a][b];"
            f"[a]palettegen=max_colors={colors}:stats_mode=full[p];[b][p]paletteuse=dither=none"
        )
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(listing),
                "-vf",
                vf,
                "-fps_mode",
                "vfr",
                "-loop",
                "0",
                str(out),
            ],
            check=True,
        )
        size = out.stat().st_size
        if size <= max_kb * 1024:
            break
    listing.unlink()
    return out.stat().st_size


def encode_mp4(frames: list[tuple[Path, float]], sounds: list[tuple[Path, float]], out: Path) -> None:
    listing = frames[0][0].parent / f"{out.stem}.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    _concat_list(frames, listing)
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(listing)]
    for p, _ in sounds:
        cmd += ["-i", str(p)]
    vf = "scale=iw*2:ih*2:flags=neighbor,format=yuv420p"
    if sounds:
        parts = [f"[{i + 1}:a]adelay={int(t * 1000)}:all=1[s{i}]" for i, (_, t) in enumerate(sounds)]
        mix = "".join(f"[s{i}]" for i in range(len(sounds)))
        graph = ";".join(parts) + f";{mix}amix=inputs={len(sounds)}:normalize=0[a]"
        cmd += ["-filter_complex", f"[0:v]{vf}[v];{graph}", "-map", "[v]", "-map", "[a]", "-c:a", "aac"]
    else:
        cmd += ["-vf", vf]
    cmd += ["-fps_mode", "vfr", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)]
    subprocess.run(cmd, check=True)
    listing.unlink()


CAPTION_HEIGHT = 22  # Pixels under the screen, before the GIF's 2x scale.


def with_captions(
    frames: list[tuple[Path, float]], captions: list[tuple[int, str]], out_dir: Path
) -> list[tuple[Path, float]]:
    """The frames with a caption strip under the screen: each frame shows the
    last caption set at or before its time (Device.caption). Writes PNGs to
    out_dir and returns them with the same durations."""
    from PIL import Image, ImageDraw, ImageFont

    out_dir.mkdir(parents=True, exist_ok=True)
    font = ImageFont.load_default(size=14)
    cache: dict[str, Image.Image] = {}
    out = []
    for path, d in frames:
        ms = int(path.stem.split("_")[1])
        text = ""
        for at, caption in captions:
            if at <= ms:
                text = caption
        with Image.open(path) as im:
            screen = im.convert("RGB")
        if text not in cache:
            strip = Image.new("RGB", (screen.width, CAPTION_HEIGHT), (24, 24, 28))
            draw = ImageDraw.Draw(strip)
            draw.text((screen.width / 2, CAPTION_HEIGHT / 2), text, font=font, fill=(230, 230, 230), anchor="mm")
            cache[text] = strip
        frame = Image.new("RGB", (screen.width, screen.height + CAPTION_HEIGHT))
        frame.paste(screen, (0, 0))
        frame.paste(cache[text], (0, screen.height))
        target = out_dir / f"{path.stem}.png"
        frame.save(target)
        out.append((target, d))
    return out
