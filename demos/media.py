"""Frames and sounds of a recording, turned into a GIF or an MP4 (ffmpeg).

A recording (Device.record_start) is a folder of f_<ms>_<n>.bmp frames and
s_<ms>_<name>.wav sounds; <ms> counts from the start. Stretches the runner
skipped are cut out of the timeline.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


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
        vf = (f"{rate}scale=iw*{scale}:ih*{scale}:flags=neighbor,split[a][b];"
              f"[a]palettegen=max_colors={colors}:stats_mode=full[p];[b][p]paletteuse=dither=none")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
                        "-vf", vf, "-fps_mode", "vfr", "-loop", "0", str(out)], check=True)
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


def with_captions(frames: list[tuple[Path, float]], captions: list[tuple[int, str]],
                  out_dir: Path) -> list[tuple[Path, float]]:
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


# Touch marks: a ring where a finger lands, shown on the GIF frames only.
TOUCH_LEAD_MS = 300  # The ring shows this long before the finger lands.
TOUCH_FADE_MS = 450  # ...and fades out over this, after the finger lifts.
TOUCH_STEP_MS = 50   # Frames of the fade, as a GIF frame rate.
_RING = (255, 255, 255)
_EDGE = (20, 20, 24)
_FILL = (60, 130, 255)  # Blue reads on the light cards and on the red app frame.
_BUTTON = {"home": "Red circle", "top": "Top button"}  # Labels for the board's buttons.
BUTTON_MIN_MS = 900  # A button's label stays at least this long, so it can be read.
SCREEN_CHANGE = 0.2  # A frame with this share of pixels changed is a new screen.


def _shown(ms: int, skipped: list[tuple[int, int]]) -> int:
    return ms - sum(max(0, min(ms, b) - a) for a, b in skipped)


def _touch_window(t: dict[str, Any], skipped: list[tuple[int, int]]) -> tuple[int, int, int]:
    """(start, contact, end) of a touch's mark, in shown ms."""
    at = _shown(t["ms"], skipped)
    long = max(t["ms_long"], BUTTON_MIN_MS) if t["kind"].startswith("press:") else t["ms_long"]
    return at - TOUCH_LEAD_MS, at, at + long + TOUCH_FADE_MS


def _thumb(path: Path):
    from PIL import Image

    with Image.open(path) as im:
        return im.convert("L").resize((80, 60))


def _changed(a, b) -> float:
    """The share of pixels that differ between two thumbnails."""
    pa, pb = a.tobytes(), b.tobytes()
    return sum(abs(x - y) > 24 for x, y in zip(pa, pb)) / len(pa)


def _touch_fade(now: int, at: int, lifted: int) -> tuple[float, float, float]:
    """(alpha, grow, fill) of a finger's mark at `now`."""
    if now < at:  # Coming in: a ring that firms up.
        return (now - (at - TOUCH_LEAD_MS)) / TOUCH_LEAD_MS, 0.0, 0.0
    if now < lifted:  # Down: a filled dot.
        return 1.0, 0.0, 1.0
    f = (now - lifted) / TOUCH_FADE_MS  # Lifted: the ring widens and fades.
    return 1.0 - f, f, 1.0 - f


def _draw_button(draw, font, t: dict[str, Any], now: int, a: float, at: int, end: int) -> None:
    """A pill at the bottom of the screen: a red dot and the button's name."""
    name = t["kind"].split(":", 1)[1]
    lifted = at + t["ms_long"]
    label = _BUTTON.get(name, name) + (": hold" if t["ms_long"] >= 1000 else "")
    w = int(font.getlength(label)) + 34
    x0, y0, x1, y1 = 160 - w // 2, 196, 160 + w // 2, 220
    if now < at:
        a = max(a, 0.0)
    else:
        a = 1.0 if now < end - TOUCH_FADE_MS else (end - now) / TOUCH_FADE_MS
    draw.rounded_rectangle((x0, y0, x1, y1), 12, fill=(*_EDGE, int(215 * a)),
                           outline=(*_RING, int(200 * a)), width=1)
    r = 6 + 2 * (1.0 if at <= now < lifted else 0.0)
    draw.ellipse((x0 + 14 - r, 208 - r, x0 + 14 + r, 208 + r), fill=(220, 40, 40, int(255 * a)),
                 outline=(*_RING, int(255 * a)), width=1)
    draw.text((x0 + 26, 208), label, font=font, anchor="lm", fill=(*_RING, int(255 * a)))


def _finger_at(draw, t: dict[str, Any], now: int, a: float, at: int) -> tuple[float, float]:
    """Where the finger is at `now`; a swipe or a stroke also draws its trail."""
    kind, points = t["kind"], t["points"]
    if kind == "swipe" and now >= at:
        (x1, y1), (x2, y2) = points
        k = min(1.0, (now - at) / max(1, t["ms_long"]))
        x, y = x1 + (x2 - x1) * k, y1 + (y2 - y1) * k
        draw.line((x1, y1, x, y), fill=(*_FILL, int(170 * a)), width=5)
        return x, y
    if kind == "stroke" and now >= at:
        x0, y0 = points[0]
        leg = min(5.0, (now - at) / 200)  # desktop.cpp: 5 legs of 200 ms, 60 px wide.
        k = leg % 1 if int(leg) % 2 == 0 else 1 - leg % 1
        draw.line((x0 - 30, y0, x0 + 30, y0), fill=(*_FILL, int(120 * a)), width=5)
        return x0 - 30 + 60 * k, y0
    return points[0]


def _draw_touch(draw, font, t: dict[str, Any], now: int, start: int, at: int, end: int) -> None:
    """One touch's mark at `now` (shown ms), onto an RGBA overlay."""
    a, grow, fill = _touch_fade(now, at, at + t["ms_long"])
    if t["kind"].startswith("press:"):
        _draw_button(draw, font, t, now, a, at, end)
        return
    x, y = _finger_at(draw, t, now, a, at)
    r = 11 + 7 * grow
    draw.ellipse((x - r - 2, y - r - 2, x + r + 2, y + r + 2), outline=(*_EDGE, int(170 * a)), width=2)
    draw.ellipse((x - r, y - r, x + r, y + r), fill=(*_FILL, int(150 * fill * a)),
                 outline=(*_RING, int(255 * a)), width=2)


def _end_on_screen_change(windows: list, frames: list[tuple[Path, float]], starts: list[int]) -> None:
    """End each finger's mark where the screen changes (a menu opens, an app
    shows), so it never lands on the new screen. A button's label stays."""
    thumbs: dict[int, Any] = {}

    def thumb(i: int):
        if i not in thumbs:
            thumbs[i] = _thumb(frames[i][0])
        return thumbs[i]

    for n, (t, start, at, end) in enumerate(windows):
        shown = [i for i, s in enumerate(starts) if s <= at]
        if t["kind"].startswith("press:") or not shown:
            continue
        lifted = at + t["ms_long"]
        base = shown[-1]
        for i in range(base + 1, len(frames)):
            if starts[i] >= end:
                break
            if starts[i] > lifted and _changed(thumb(base), thumb(i)) > SCREEN_CHANGE:
                windows[n] = (t, start, at, starts[i])
                break


def _marked_frame(path: Path, now: int, windows: list, font):
    """The frame at `path` with every mark live at `now` drawn on it, as RGB."""
    from PIL import Image, ImageDraw

    with Image.open(path) as im:
        frame = im.convert("RGBA")
    live = [w for w in windows if w[1] <= now < w[3]]
    if live:
        layer = Image.new("RGBA", frame.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        for t, start, at, end in live:
            _draw_touch(draw, font, t, now, start, at, end)
        frame = Image.alpha_composite(frame, layer)
    return frame.convert("RGB")


def with_touches(frames: list[tuple[Path, float]], touches: list[dict[str, Any]],
                 skipped: list[tuple[int, int]], out_dir: Path,
                 split_at: list[int] = ()) -> list[tuple[Path, float]]:
    """The frames, all as PNG (ffmpeg's concat reads every file with the
    first one's decoder), with a mark wherever the runner touched (Device.touches):
    a ring that shows just before the finger lands, a dot while it is down,
    a trail for a swipe, and a fade after. For the GIF only: golden pictures
    come from screenshots and never see it. Frames are split where a mark
    changes, and at `split_at` (recording ms, such as caption times), so each
    piece is named after the recording time it starts at."""
    from PIL import ImageFont

    if not touches and not split_at:
        return frames
    out_dir.mkdir(parents=True, exist_ok=True)
    font = ImageFont.load_default(size=14)
    windows = [(t, *_touch_window(t, skipped)) for t in touches]
    starts = [_shown(int(p.stem.split("_")[1]), skipped) for p, _ in frames]
    _end_on_screen_change(windows, frames, starts)
    cuts = {_shown(ms, skipped) for ms in split_at}
    for _, start, _, end in windows:
        cuts.update(range(start, end + 1, TOUCH_STEP_MS))
    cuts = sorted(cuts)
    out = []
    for i, (path, d) in enumerate(frames):
        raw0 = int(path.stem.split("_")[1])
        a = starts[i]
        b = a + round(d * 1000)
        edges = [a] + [c for c in cuts if a < c < b] + [b]
        for k, (p0, p1) in enumerate(zip(edges, edges[1:])):
            target = out_dir / f"f_{raw0 + (p0 - a)}_{i}_{k}.png"
            _marked_frame(path, p0, windows, font).save(target)
            out.append((target, (p1 - p0) / 1000))
    return out
