"""Host previews of Daruma screens at other sizes, using the device's
own layout math.

    c++ -std=c++17 -I components/daruma tests/test_layout.cpp -o /tmp/test_layout
    uv run --with pillow python -I tests/preview_screens.py /tmp/test_layout OUT_DIR FONT_DIR

The layout (regions, tiles, unit) comes from test_layout --json, which runs
layout.h itself. The pixel corgi's room is extended with the same edge
strips the build makes (daruma_sprites/extend.py) and placed the way
SpritePersona::view_() places it. The dock, the app board and the Tasks app
follow menu_controller.cpp and task_view.cpp with the corgi's wood theme.
FONT_DIR holds Manrope[wght].ttf and mdi.ttf (Material Design Icons).

Writes OUT_DIR/<size>.png per screen size (idle, dock, board, app side by
side) and OUT_DIR/mono.png: 320x240 in black and white with the focus ring
of a board without touch.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pixel"))
sys.path.insert(0, str(ROOT / "components" / "daruma_sprites"))

import extend  # noqa: E402
from daruma_pixel import personas  # noqa: E402

# Font sizes per screen, as the board packages set them.
FONTS = {"320x240": (17, 13, 30), "480x272": (19, 15, 34), "240x240": (17, 13, 30)}

# The corgi's wood theme (persona_pixel_corgi.yaml).
WOOD = {
    "frame": (0x96, 0x62, 0x3A), "edge": (0x60, 0x3A, 0x22), "panel": (0xFC, 0xF2, 0xDE), "ink": (0x46, 0x2C, 0x1E),
    "muted": (0x82, 0x60, 0x46), "title": (0xFC, 0xF2, 0xDE), "accent": (0xD6, 0xA0, 0x32), "dot": (0x70, 0x4A, 0x2C),
    "dock": (0xFA, 0xF6, 0xEE), "dock_ink": (0x3C, 0x2C, 0x24), "dock_muted": (0x78, 0x64, 0x58),
}
DONE = (46, 160, 87)


def luminance(c):
    return (c[0] * 299 + c[1] * 587 + c[2] * 114) // 1000


def mono(c):
    v = 255 if luminance(c) >= 128 else 0
    return (v, v, v)


def mono_theme(t):
    """Theme::for_mode(MONO): every color by luminance, readable pairs kept apart."""
    out = {k: mono(v) for k, v in t.items()}

    def on(bg, fg):
        return fg if fg != out[bg] else ((0, 0, 0) if out[bg][0] >= 128 else (255, 255, 255))

    for fg, bg in (("ink", "panel"), ("muted", "panel"), ("title", "frame"), ("dock_ink", "dock"),
                   ("dock_muted", "dock"), ("dot", "frame")):
        out[fg] = on(bg, out[fg])
    out["focus"] = on("frame", out["accent"])
    return out


class Screen:
    def __init__(self, layout: dict, fonts: tuple[int, int, int], font_dir: Path, theme: dict, focus: bool):
        self.l = layout
        self.w, self.h = layout["stage"][2], layout["stage"][3]
        self.unit = layout["unit"]
        self.theme = theme
        self.focus = focus

        def font(name, size, weight=None):
            f = ImageFont.truetype(str(font_dir / name), size)
            if weight:
                try:
                    f.set_variation_by_axes([weight])
                except OSError:
                    pass  # A static bold file (ESPHome's own download) has no axes.
            return f

        self.text = font("Manrope[wght].ttf", fonts[0], 700)
        self.small = font("Manrope[wght].ttf", fonts[1], 700)
        self.icons = font("mdi.ttf", fonts[2])

    def px(self, v):
        return int(round(v * self.unit))

    def new(self):
        return Image.new("RGB", (self.w, self.h), (0, 0, 0))


def rect(r):
    x, y, w, h = r
    return (x, y, x + w - 1, y + h - 1)


def corgi_idle(s: Screen) -> Image.Image:
    """SpritePersona: the extended room at the largest whole scale, on the bottom."""
    _, layers, source = personas._persona("corgi")
    persona = personas.build("corgi")
    pose = source.ANIMATIONS["Neutral"][0][0]
    scene = layers.scene(pose).convert("RGBA")
    room = persona.backdrop.convert("RGBA")
    # The glass the device paints: the full scene's own pixels there.
    full = scene.copy()
    rows = [[room.getpixel((x, y)) for x in range(room.width)] for y in range(room.height)]
    rows = [[scene.getpixel((x, y)) if px[3] < 128 else px for x, px in enumerate(row)] for y, row in enumerate(rows)]
    full_rows = [[full.getpixel((x, y)) for x in range(full.width)] for y in range(full.height)]
    bw, bh = room.size
    stage = s.l["stage"]
    sc = max(1, min(stage[2] // bw, stage[3] // bh))
    core_x = stage[0] + (stage[2] - bw * sc) // 2
    core_y = stage[1] + stage[3] - bh * sc

    def cells(margin):
        return (margin + sc - 1) // sc if margin >= sc else 0

    left, right = cells(core_x - stage[0]), cells(stage[0] + stage[2] - (core_x + bw * sc))
    top = cells(core_y - stage[1])
    # Strips from the room (as the build does), drawn around the full scene.
    ls, rs, ts = extend.left_strip(rows), extend.right_strip(rows), extend.top_strip(rows)
    pl, pr, pt = len(ls[0]), len(rs[0]), len(ts)
    vw, vh = left + bw + right, top + bh
    view = Image.new("RGB", (vw, vh))
    for y in range(vh):
        by = y - top
        sy = by if by >= 0 else by % pt
        for x in range(vw):
            bx = x - left
            if by >= 0 and 0 <= bx < bw:
                px = full_rows[by][bx]
            elif bx < 0:
                px = ls[sy][bx % pl]
            elif bx >= bw:
                px = rs[sy][(bx - bw) % pr]
            else:
                px = ts[sy][bx]
            view.putpixel((x, y), px[:3])
    img = Image.new("RGB", (s.w, s.h), (0x4A, 0x2A, 0x1A))  # The persona's background.
    big = view.resize((vw * sc, vh * sc), Image.NEAREST)
    img.paste(big, (core_x - left * sc, core_y - top * sc))
    return img


def badge(s: Screen, img: Image.Image) -> None:
    """The temperature badge in the layout's bottom-right corner."""
    d = ImageDraw.Draw(img)
    x, y, w, h = s.l["badge"]
    r = w // 2
    cx, cy = x + w // 2, y + h // 2
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(255, 255, 255))
    r2 = r - s.px(2)
    d.ellipse((cx - r2, cy - r2, cx + r2, cy + r2), fill=(52, 150, 74))
    d.text((cx + 1, cy + 1), "64°", font=s.text, fill=(255, 255, 255), anchor="mm")


FOCUS = ("Focus", "\U000F051B", (0xFF, 0x63, 0x47), (255, 255, 255))
PAUSE = ("Pause", "\U000F03E4", (0xFF, 0x63, 0x47), (255, 255, 255))
STOP = ("Stop", "\U000F04DB", (0x80, 0x80, 0x80), (255, 255, 255))
BREAK = ("Break", "\U000F0176", (0x26, 0xED, 0x3A), (0, 0, 0))
TASKS = ("Tasks", "\U000F0756", (0x4A, 0x7F, 0xE0), (255, 255, 255))
CALENDAR = ("Calendar", "\U000F00ED", (0xEF, 0x5B, 0x3F), (255, 255, 255))


def more(t):
    return ("More", "\U000F15FC", t["edge"], (255, 255, 255))


def dock(s: Screen, idle: Image.Image, items=None) -> Image.Image:
    """The dock as menu_controller.cpp draws it. Default: the main menu
    while idle (Focus, Tasks, Calendar, More)."""
    t = s.theme
    img = idle.copy()
    d = ImageDraw.Draw(img)
    x, y, w, h = s.l["dock"]
    d.rounded_rectangle(rect(s.l["dock"]), radius=s.px(18), fill=t["dock"])
    d.text((x + w // 2, y + s.px(14)), "1 of 3 today", font=s.small, fill=t["dock_muted"], anchor="mm")
    items = items or [FOCUS, TASKS, CALENDAR, more(t)]
    n = len(items)
    span = w // n
    r = min(s.px(26) if n <= 4 else s.px(23), span // 2 - s.px(3))
    # Labels borrow room their neighbours' shorter labels leave (draw_dock_).
    slot = span - s.px(2)
    widths = [d.textlength(item[0], font=s.small) for item in items]

    def spare(i):
        return 0 if i < 0 or i >= n else max(0, int(slot - widths[i]) // 2)

    for i, (label, icon, bg, fg) in enumerate(items):
        room = slot + 2 * min(spare(i - 1), spare(i + 1))
        cx, cy = x + span * i + span // 2, y + s.px(52)
        if s.focus and i == 0:
            ring = t["focus"] if t["focus"] != t["dock"] else t["dock_ink"]
            for k in range(s.px(3), s.px(5) + 1):
                d.ellipse((cx - r - k, cy - r - k, cx + r + k, cy + r + k), outline=ring)
        if "focus" in t:  # Mono: buttons by luminance, icons readable on them.
            bg = mono(bg)
            fg = mono(fg)
            if fg == bg:
                fg = (0, 0, 0) if bg[0] >= 128 else (255, 255, 255)
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=bg)
        if "focus" in t and bg == t["dock"]:
            d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=t["dock_ink"])
        d.text((cx, cy), icon, font=s.icons, fill=fg, anchor="mm")
        d.text((cx, cy + r + s.px(13)), fit(d, s.small, label, room), font=s.small, fill=t["dock_ink"],
               anchor="mm")
    return img


def frame(s: Screen, title: str) -> Image.Image:
    t = s.theme
    img = Image.new("RGB", (s.w, s.h), t["edge"])
    d = ImageDraw.Draw(img)
    rim = s.px(5)
    d.rectangle((rim, rim, s.w - rim - 1, s.h - rim - 1), fill=t["frame"])
    shade = tuple(int(c * 0.9) for c in t["frame"]) if "focus" not in t else t["frame"]
    for y in range(rim, s.h - rim, s.px(9)):
        d.line((rim, y, s.w - rim - 1, y), fill=shade)
    hh = s.l["header"][3]
    d.text((s.w // 2, hh // 2), title, font=s.text, fill=t["title"], anchor="mm")
    d.text((s.px(22), hh // 2), "\U000F0141", font=s.icons, fill=t["title"], anchor="mm")
    return img


def card(s: Screen, d: ImageDraw.ImageDraw, r) -> None:
    t = s.theme
    x, y, w, h = r
    rim = s.px(3)
    d.rectangle(rect(r), fill=t["edge"])
    d.rectangle(rect((x + rim, y + rim, w - 2 * rim, h - 2 * rim)), fill=t["panel"])
    low = tuple(int(c * 0.88) for c in t["panel"]) if "focus" not in t else t["panel"]
    d.rectangle(rect((x + rim, y + h - s.px(7), w - 2 * rim, s.px(4))), fill=low)


def fit(d, font, text, room):
    if d.textlength(text, font=font) <= room:
        return text
    while text and d.textlength(text + "…", font=font) > room:
        text = text[:-1]
    return text + "…"


def board(s: Screen) -> Image.Image:
    t = s.theme
    img = frame(s, "Apps")
    d = ImageDraw.Draw(img)
    apps = [("Tasks", "\U000F0756", (0x4A, 0x7F, 0xE0), "3 left"), ("Calendar", "\U000F00ED", (0x2E, 0x9E, 0x8A), "Next 14:30"),
            ("Stats", "\U000F0128", (0xFF, 0x63, 0x47), "Streak 5")]
    for i, (name, icon, color, status) in enumerate(apps):
        tile = s.l["tiles"][i]
        x, y, w, h = tile
        if s.focus and i == 0:
            out, gap = s.px(6), s.px(3)
            d.rounded_rectangle(rect((x - out, y - out, w + 2 * out, h + 2 * out)), radius=s.px(14) + out, fill=t["focus"])
            d.rounded_rectangle(rect((x - gap, y - gap, w + 2 * gap, h + 2 * gap)), radius=s.px(14) + gap, fill=t["frame"])
        card(s, d, tile)
        ic = mono(color) if "focus" in t else color
        if ic == t["panel"]:
            ic = t["ink"]
        if w >= s.px(130):
            tx = x + s.px(54)
            room = x + w - tx - s.px(4)
            d.text((x + s.px(30), y + h // 2 - s.px(2)), icon, font=s.icons, fill=ic, anchor="mm")
            d.text((tx, y + s.px(30)), fit(d, s.text, name, room), font=s.text, fill=t["ink"], anchor="lm")
            d.text((tx, y + s.px(54)), fit(d, s.small, status, room), font=s.small, fill=t["muted"], anchor="lm")
        else:
            room = w - s.px(10)
            cx = x + w // 2
            d.text((cx, y + h * 33 // 100), icon, font=s.icons, fill=ic, anchor="mm")
            d.text((cx, y + h * 66 // 100), fit(d, s.text, name, room), font=s.text, fill=t["ink"], anchor="mm")
            d.text((cx, y + h * 86 // 100), fit(d, s.small, status, room), font=s.small, fill=t["muted"], anchor="mm")
    return img


def tasks(s: Screen) -> Image.Image:
    """TaskView: rows with checks inside the content area; the focus on row 1."""
    t = s.theme
    img = frame(s, "Tasks")
    d = ImageDraw.Draw(img)
    cx_, cy_, cw, ch = s.l["content"]
    d.rectangle(rect(s.l["content"]), fill=t["panel"])
    text_h = s.text.getbbox("Ag")[3] - s.text.getbbox("Ag")[1]
    pad = max(4, cw // 48)
    left, top, width, height = cx_ + pad, cy_ + pad, cw - 2 * pad - 8, ch - 2 * pad
    rows = max(1, height // (text_h + 14))
    row_h = height // rows
    items = [("Water the plants", True), ("Reply to the landlord", False), ("Book the dentist", False),
             ("Plan the weekend trip to the mountains", False), ("Pay the internet bill", False), ("Call mom", False)]
    for k in range(min(rows, len(items))):
        title, done = items[k]
        y = top + k * row_h
        cy = y + row_h // 2
        row_ring = t.get("focus", t["accent"])
        row_ring = row_ring if row_ring != t["panel"] else t["ink"]
        if s.focus and k == 1:
            ring = max(2, s.px(2))
            r = min(row_h // 2 - 1, s.px(8))
            d.rounded_rectangle(rect((left, y + 1, width, row_h - 2)), radius=r, fill=row_ring)
            d.rounded_rectangle(rect((left + ring, y + 1 + ring, width - 2 * ring, row_h - 2 - 2 * ring)), radius=max(1, r - ring), fill=t["panel"])
        r = max(7, min(row_h * 27 // 100, 12))
        ccx = left + r + 4
        if done:
            d.ellipse((ccx - r, cy - r, ccx + r, cy + r), fill=mono(DONE) if "focus" in t else DONE)
        else:
            d.ellipse((ccx - r, cy - r, ccx + r, cy + r), outline=t["ink"], width=2)
        tx = ccx + r + 10
        d.text((tx, cy), fit(d, s.text, title, left + width - tx - 4), font=s.text,
               fill=t["muted"] if done else t["ink"], anchor="lm")
        if k + 1 < rows:
            d.line((left + 4, y + row_h - 1, left + width - 5, y + row_h - 1), fill=t["muted"] if "focus" in t else
                   tuple(int(c * 0.88) for c in t["panel"]))
    return img


def sheet(images: list[Image.Image], scale: int = 2) -> Image.Image:
    w, h = images[0].size
    gap = 12
    out = Image.new("RGB", (len(images) * (w * scale + gap) + gap, h * scale + 2 * gap), (60, 60, 60))
    for i, img in enumerate(images):
        out.paste(img.resize((w * scale, h * scale), Image.NEAREST), (gap + i * (w * scale + gap), gap))
    return out


def to_mono(img: Image.Image) -> Image.Image:
    """What a black-and-white panel shows."""
    return img.convert("L").point(lambda v: 255 if v >= 128 else 0).convert("RGB")


def main() -> None:
    binary, out, font_dir = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    out.mkdir(parents=True, exist_ok=True)
    layouts = json.loads(subprocess.run([binary, "--json"], check=True, capture_output=True, text=True).stdout)
    for size, fonts in FONTS.items():
        s = Screen(layouts[size], fonts, font_dir, WOOD, focus=False)
        idle = corgi_idle(s)
        badge(s, idle)
        shots = [idle, dock(s, idle), board(s), tasks(s)]
        sheet(shots).save(out / f"{size}.png")
        for name, img in zip(("idle", "dock", "board", "tasks"), shots):
            img.save(out / f"{size}_{name}.png")
        print(f"{size}: {s.l['size_class']}, unit {s.unit:.2f}, scale {min(s.w // 106, s.h // 80)} -> {out / size}.png")

    # The menus at 320x240: main idle and in a focus session (five buttons),
    # then the pomodoro menu (the red circle) idle and in a session.
    s = Screen(layouts["320x240"], FONTS["320x240"], font_dir, WOOD, focus=False)
    idle = corgi_idle(s)
    menus = [dock(s, idle), dock(s, idle, [PAUSE, STOP, TASKS, CALENDAR, more(WOOD)]),
             dock(s, idle, [FOCUS, BREAK]), dock(s, idle, [PAUSE, STOP, BREAK])]
    sheet(menus).save(out / "menus.png")
    print(f"menus -> {out / 'menus.png'}")

    # Mono, buttons only: every pixel to black or white by luminance (as the
    # build and the device do), the UI in the derived mono theme with the
    # focus ring of a board without touch.
    s = Screen(layouts["320x240"], FONTS["320x240"], font_dir, mono_theme(WOOD), focus=True)
    idle = to_mono(corgi_idle(s))
    shots = [idle, to_mono(dock(s, idle)), to_mono(board(s)), to_mono(tasks(s))]
    sheet(shots).save(out / "mono.png")
    print(f"mono -> {out / 'mono.png'}")


if __name__ == "__main__":
    main()
