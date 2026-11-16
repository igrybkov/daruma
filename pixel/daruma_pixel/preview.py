"""Preview the pixel corgi: mood grid, UI mock, and a wag GIF.

    cd pixel && uv run --with pillow python -m daruma_pixel.preview OUT_DIR [PIXEL_FONT.ttf]
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


from .corgi import CORGI, H, W
from .pet import Pet
from .room import Room
from .moods import ANIMATIONS, wag_cycle, HAPPY
from .pixelkit import upscale

SCALE = 3

# --- Layers for the device ----------------------------------------------------
# The corgi in its cozy room (room.py): warm plank walls, a window, a shelf
# with the plant, floor boards and a red rug that changes color by weekday.

_pet = Pet(CORGI, Room())
globals().update(_pet.layers())  # background, foreground, scene, WINDOW, plant, the rug colors
room = _pet.stage.image
# Where focus's props stand (tests/test_props.py): the book in the lap. The
# glasses move with the head (tests/test_pet_props.py checks they stay on).
PROPS = {"focus": [(40, 55, 67, 75)]}


# --- Pixel UI ---------------------------------------------------------------

WOOD_DARK = (74, 42, 26)
WOOD = (150, 94, 52)
WOOD_LIGHT = (196, 136, 78)
PAPER = (250, 232, 192)


def wood_panel(d: ImageDraw.ImageDraw, x0: int, y0: int, x1: int, y1: int) -> None:
    """Chunky wooden frame with a parchment inside (drawn at screen scale)."""
    s = SCALE
    d.rectangle((x0, y0, x1, y1), fill=WOOD_DARK)
    d.rectangle((x0 + s, y0 + s, x1 - s, y1 - s), fill=WOOD)
    d.rectangle((x0 + s, y0 + s, x1 - s, y0 + 2 * s - 1), fill=WOOD_LIGHT)
    d.rectangle((x0 + 3 * s, y0 + 3 * s, x1 - 3 * s, y1 - 3 * s), fill=WOOD_DARK)
    d.rectangle((x0 + 4 * s, y0 + 4 * s, x1 - 4 * s, y1 - 4 * s), fill=PAPER)
    for cx, cy in ((x0 + s * 2, y0 + s * 2), (x1 - s * 2, y0 + s * 2), (x0 + s * 2, y1 - s * 2), (x1 - s * 2, y1 - s * 2)):
        d.rectangle((cx - 1, cy - 1, cx + 1, cy + 1), fill=(230, 200, 120))  # Brass nails.


def tomato(d: ImageDraw.ImageDraw, x: int, y: int, body, star=False) -> None:
    """9x9 logical tomato at screen scale."""
    s = SCALE
    sprite = [
        "...LL....",
        "..LLLL...",
        ".BBLLBB..",
        "BBBBBBBB.",
        "BHBBBBBB.",
        "BBBBBBBB.",
        "BBBBBBBB.",
        ".BBBBBB..",
        "..BBBB...",
    ]
    if star:
        star_px = [
            "....Y....",
            "...YYY...",
            "YYYYYYYYY",
            ".YYYYYYY.",
            "..YYYYY..",
            ".YYY.YYY.",
            "YY.....YY",
        ]
        for r, row in enumerate(star_px):
            for col, ch in enumerate(row):
                if ch == "Y":
                    d.rectangle((x + (col - 4) * s, y + (r - 1) * s, x + (col - 3) * s - 1, y + (r) * s - 1), fill=(255, 210, 60))
    for r, row in enumerate(sprite):
        for col, ch in enumerate(row):
            color = {"L": (60, 130, 50), "B": body, "H": (255, 220, 210)}.get(ch)
            if color and not (ch == "H" and body[1] > 150):
                d.rectangle((x + col * s, y + r * s, x + (col + 1) * s - 1, y + (r + 1) * s - 1), fill=color)
            elif ch == "H":
                d.rectangle((x + col * s, y + r * s, x + (col + 1) * s - 1, y + (r + 1) * s - 1), fill=body)


def ui_idle(base: Image.Image, font) -> Image.Image:
    img = Image.new("RGB", (320, 240), (0, 0, 0))
    img.paste(upscale(base, SCALE).convert("RGB"), (1, 0))
    d = ImageDraw.Draw(img)
    # Timer plaque.
    wood_panel(d, 232, 4, 316, 36)
    d.text((274, 21), "18:42", font=font, fill=(150, 40, 30), anchor="mm")
    # Tomatoes: 3 done, 1 bonus, 1 to go... (goal 3 + bonus shown for the mock)
    colors = [(214, 50, 40)] * 3 + [(130, 70, 170)]
    x0 = 160 - (len(colors) * 30) // 2
    for i, col in enumerate(colors):
        tomato(d, x0 + i * 30, 208, col, star=i >= 3)
    return img


def ui_message(base: Image.Image, font) -> Image.Image:
    img = ui_idle(base, font)
    d = ImageDraw.Draw(img)
    wood_panel(d, 6, 160, 314, 236)
    d.text((24, 182), "Nice work! 3 of 3.", font=font, fill=(60, 34, 24))
    d.text((24, 202), "Treat time? Woof!", font=font, fill=(60, 34, 24))
    return img


def ui_menu(font) -> Image.Image:
    img = upscale(room(), SCALE).convert("RGB")
    full = Image.new("RGB", (320, 240))
    full.paste(img, (1, 0))
    d = ImageDraw.Draw(full)
    d.rectangle((0, 0, 320, 240), fill=None)
    wood_panel(d, 4, 4, 316, 236)
    d.text((160, 26), "3 of 3 today", font=font, fill=(110, 70, 40), anchor="mm")
    labels = [("Focus", (196, 70, 50)), ("Break", (70, 140, 60)), ("Pet me", (196, 90, 140)), ("Mute", (110, 96, 86))]
    for i, (label, col) in enumerate(labels):
        bx = 22 + (i % 2) * 142
        by = 44 + (i // 2) * 92
        d.rectangle((bx, by, bx + 134, by + 82), fill=WOOD_DARK)
        d.rectangle((bx + 3, by + 3, bx + 131, by + 79), fill=col)
        d.rectangle((bx + 3, by + 3, bx + 131, by + 8), fill=tuple(min(255, v + 40) for v in col))
        d.rectangle((bx + 3, by + 74, bx + 131, by + 79), fill=tuple(max(0, v - 50) for v in col))
        d.text((bx + 67, by + 42), label, font=font, fill=(255, 248, 230), anchor="mm")
    return full


def main(out: Path, font_path: str | None) -> None:
    out.mkdir(parents=True, exist_ok=True)
    font = ImageFont.truetype(font_path, 8 * 2) if font_path else ImageFont.load_default()
    small = ImageFont.truetype(font_path, 8) if font_path else ImageFont.load_default()

    names = ["Neutral", "Happy", "Loved", "Sad", "Scared", "Sleepy", "Sleeping", "listening", "thinking", "talking"]
    tiles = []
    for n in names:
        tile = upscale(scene(ANIMATIONS[n][0][0]), 2).convert("RGB")
        ImageDraw.Draw(tile).text((4, 4), n, font=small, fill=(255, 255, 255))
        tiles.append(tile)
    tw, th = tiles[0].size
    grid = Image.new("RGB", (tw * 5, th * 2))
    for i, t in enumerate(tiles):
        grid.paste(t, ((i % 5) * tw, (i // 5) * th))
    grid.save(out / "moods.png")

    # Butt wag strip: one wag cycle, side by side.
    cyc = wag_cycle(HAPPY, frames=8)
    strip = Image.new("RGB", (W * 3 * 4, H * 3 * 2))
    for i, (pose, _) in enumerate(cyc):
        strip.paste(upscale(scene(pose), 3).convert("RGB"), ((i % 4) * W * 3, (i // 4) * H * 3))
    strip.save(out / "wag_frames.png")
    frames = [upscale(scene(p), SCALE).convert("RGB") for p, _ in cyc * 3]
    frames[0].save(out / "wag.gif", save_all=True, append_images=frames[1:], duration=70, loop=0)
    neutral = [upscale(scene(p), SCALE).convert("RGB") for p, _ in ANIMATIONS["Neutral"]]
    neutral[0].save(out / "neutral.gif", save_all=True, append_images=neutral[1:],
                    duration=[ms for _, ms in ANIMATIONS["Neutral"]], loop=0)

    ui = Image.new("RGB", (320 * 3 + 20, 240), (255, 255, 255))
    ui.paste(ui_idle(scene(ANIMATIONS["Happy"][2][0]), font), (0, 0))
    ui.paste(ui_message(scene(ANIMATIONS["Loved"][2][0]), font), (330, 0))
    ui.paste(ui_menu(font), (660, 0))
    ui.save(out / "ui.png")


if __name__ == "__main__":
    main(Path(sys.argv[1]), sys.argv[2] if len(sys.argv) > 2 else None)
