"""Host previews of the prompt layouts, drawn the way prompt_controller.cpp
draws them, on the rectangles prompt_layout.h computes from the hub's
Layout. Drawn at 320x240 (the BOX-3) and 480x272 (variant_wide.yaml, with
its larger fonts).

    uvx --python 3.14 --from esphome==2026.11.1 python \
        tests/prompt_preview.py <out dir> <Manrope 700 ttf> <Manrope 800 ttf>

The fonts are the ones ESPHome downloads into .esphome/font/ on a compile.
It builds prompt_geometry.cpp with the host c++ compiler, then writes one
PNG per case and a contact sheet (sheet.png) into <out dir>.
"""

import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
GEOMETRY_SRC = ROOT / "tests" / "prompt_geometry.cpp"

# Themes from persona_pixel_corgi.yaml (wood) and persona_eyes.yaml (outline).
THEMES = {
    "wood": dict(
        style="wood",
        frame="96623A",
        edge="603A22",
        panel="FCF2DE",
        ink="462C1E",
        muted="826046",
        title="FCF2DE",
        accent="D6A032",
        dot="704A2C",
    ),
    "outline": dict(
        style="outline",
        frame="080A0E",
        edge="28323C",
        panel="141A20",
        ink="E1F5FA",
        muted="6E96A0",
        title="00DCF0",
        accent="00C8DC",
        dot="283C46",
    ),
}
# The prompts module's theme color defaults (daruma_prompts/__init__.py).
MODULE = dict(urgent="E53935", game="7E57C2", countdown="F2A33A", selected="F2A33A", correct="2E9E44", wrong="D23C3C")


# Per screen: font sizes (title, text) from the board's substitutions, and
# the device's line heights for them (ESPHome's font metrics in the
# generated main.cpp: 27 and 23 on the BOX-3), not PIL's.
SCREENS = {
    (320, 240): dict(sizes=(20, 17), lines=(27, 23)),
    (480, 272): dict(sizes=(23, 19), lines=(31, 26)),
}


def rgb(hex_):
    return tuple(int(hex_[i : i + 2], 16) for i in (0, 2, 4))


def shade(c, k):
    return tuple(int(min(255.0, max(0.0, v * k))) for v in c)


def ink_on(fill):
    luma = (299 * fill[0] + 587 * fill[1] + 114 * fill[2]) // 1000
    return (28, 28, 32) if luma > 150 else (255, 255, 255)


def drawable(text):
    """Roughly what drawable_text() keeps with GF_Latin_Core + GF_Cyrillic_Core:
    no emoji, U+02BC shown as U+2019, runs of spaces squeezed."""
    text = text.replace("ʼ", "’")
    out = []
    for ch in text:
        cp = ord(ch)
        if cp < 0x20:
            ch = " "
        if cp >= 0x2600 and cp not in (0x2026,):
            continue
        if ch == " " and (not out or out[-1] == " "):
            continue
        out.append(ch)
    return "".join(out).strip()


class Canvas:
    def __init__(self, w, h, theme, title_font, text_font, lines):
        self.w, self.h = w, h
        self.lines = lines
        self.img = Image.new("RGB", (w, h))
        self.d = ImageDraw.Draw(self.img)
        self.t = {k: (rgb(v) if k != "style" else v) for k, v in theme.items()}
        self.m = {k: rgb(v) for k, v in MODULE.items()}
        self.title_font, self.text_font = title_font, text_font

    # --- primitives, as on the device ---------------------------------------
    def rect(self, x, y, w, h, c):
        if w > 0 and h > 0:
            self.d.rectangle([x, y, x + w - 1, y + h - 1], fill=c)

    def rounded(self, x, y, w, h, r, c):
        r = min(r, min(w, h) / 2 - 1)
        self.d.rounded_rectangle([x, y, x + w - 1, y + h - 1], radius=max(0, r), fill=c)

    def ring(self, r, t, c):
        x, y, w, h = r
        self.rect(x, y, w, t, c)
        self.rect(x, y + h - t, w, t, c)
        self.rect(x, y, t, h, c)
        self.rect(x + w - t, y, t, h, c)

    def line_h(self, font):
        return self.lines[0] if font is self.title_font else self.lines[1]

    def width(self, font, s):
        return int(round(font.getlength(s)))

    def fit(self, font, s, max_w):
        if max_w <= 0:
            return ""
        if self.width(font, s) <= max_w:
            return s
        for k in range(len(s) - 1, 0, -1):
            head = s[:k].rstrip()
            if self.width(font, head + "…") <= max_w:
                return head + "…"
        return "…"

    def wrap(self, font, s, max_w):
        lines = []
        for para in s.split("\n"):
            line = ""
            for word in para.split(" "):
                if not word:
                    continue
                cand = word if not line else line + " " + word
                if not line or self.width(font, cand) <= max_w:
                    line = cand
                else:
                    lines.append(line)
                    line = word
            if line:
                lines.append(line)
        return lines

    def print(self, x, y, font, color, s, align="TOP_LEFT"):
        anchor = {"TOP_LEFT": "la", "TOP_CENTER": "ma", "TOP_RIGHT": "ra", "CENTER": "mm"}[align]
        self.d.text((x, y), s, font=font, fill=color, anchor=anchor)

    # --- the painter ----------------------------------------------------------
    def frame(self, unit):
        t = self.t
        if t["style"] == "wood":
            self.rect(0, 0, self.w, self.h, t["edge"])
            self.rect(unit, unit, self.w - 2 * unit, self.h - 2 * unit, t["frame"])
            y = unit
            while y < self.h - unit:
                self.rect(unit, y, self.w - 2 * unit, 1, shade(t["frame"], 0.9))
                y += unit + unit // 2
        elif t["style"] == "paper":
            self.rect(0, 0, self.w, self.h, t["frame"])
            for x in range(0, self.w, 4 * unit):
                self.rect(x, 0, 1, self.h, shade(t["frame"], 0.95))
        else:
            self.rect(0, 0, self.w, self.h, t["frame"])

    def card(self, g, border, bordered):
        x, y, w, h = g["card"]
        b, unit, t = g["border"], g["unit"], self.t
        if t["style"] == "wood":
            self.rect(x, y, w, h, border)
            self.rect(x + b, y + b, w - 2 * b, h - 2 * b, t["panel"])
        elif t["style"] == "paper":
            self.rect(x + unit // 2, y + unit // 2, w, h, shade(t["frame"], 0.75))
            self.rect(x, y, w, h, t["panel"])
            if bordered:
                self.ring((x, y, w, h), b, border)
        else:
            self.rounded(x, y, w, h, 2 * unit, border)
            self.rounded(x + b, y + b, w - 2 * b, h - 2 * b, max(2, 2 * unit - b), t["panel"])

    def button_colors(self, mark):
        t = self.t
        if mark in ("selected", "correct", "wrong"):
            fill = self.m[mark]
            return fill, shade(fill, 0.7), ink_on(fill)
        if t["style"] == "outline":
            return shade(t["panel"], 1.6), t["accent"], t["ink"]
        return t["edge"], shade(t["edge"], 0.7), t["title"]

    def box(self, r, fill, edge, unit):
        x, y, w, h = r
        radius = min(h // 2, unit + unit // 2) if self.t["style"] == "outline" else unit // 2
        self.rounded(x, y, w, h, radius, edge)
        self.rounded(x + 2, y + 2, w - 4, h - 4, max(1, radius - 2), fill)

    def text(self, r, font, s, ink, align):
        x, y, w, h = r
        fitted = self.fit(font, s, w)
        top = y + (h - self.line_h(font)) // 2
        px = x + w // 2 if align == "TOP_CENTER" else x
        self.print(px, top, font, ink, fitted, align)

    def wrapped(self, r, font, s, ink, center, max_lines=99):
        x, y, w, h = r
        if not s or h <= 0:
            return
        lh = self.line_h(font)
        lines = self.wrap(font, s, w)
        fit = min(max_lines, max(1, h // lh))
        if len(lines) > fit:
            lines[fit - 1] = self.fit(font, lines[fit - 1] + " " + lines[fit], w)
            lines = lines[:fit]
        top = y + (h - len(lines) * lh) // 2 if center else y
        for i, line in enumerate(lines):
            line = self.fit(font, line, w)
            self.print(
                x + w // 2 if center else x, top + i * lh, font, ink, line, "TOP_CENTER" if center else "TOP_LEFT"
            )


def geometry(tool, layout, w, h, title_line, text_line, n, urgent, title, bar, body_lines=0, focus=-1, first=0):
    out = subprocess.run(
        [
            str(tool),
            layout,
            str(w),
            str(h),
            str(title_line),
            str(text_line),
            str(n),
            str(int(urgent)),
            str(int(title)),
            str(int(bar)),
            str(body_lines),
            str(focus),
            str(first),
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return json.loads(out)


def inner_width(tool, w, h, urgent):
    out = subprocess.run(
        [str(tool), "width", str(w), str(h), str(int(urgent))], check=True, capture_output=True, text=True
    ).stdout
    return int(out)


def render(tool, case, theme, w, h, fonts, lines):
    title_font, text_font = fonts
    c = Canvas(w, h, THEMES[theme], title_font, text_font, lines)
    t = c.t
    layout, style = case["layout"], case["style"]
    title = drawable(case.get("title", ""))
    body = drawable(case.get("body", ""))
    options = [drawable(o) for o in case["options"]]
    marks = case.get("marks", []) + [""] * len(options)
    focus = case.get("focus", -1)
    answered = case.get("answered", False)
    # 0 is the default of 60 s, -1 none.
    bar = case.get("timeout", 0) >= 0 and not answered
    urgent, game = style == "urgent", style == "game"
    # The body's lines at the card's width, capped as the controller caps them.
    cap = {"message": 6, "choice": 3, "list": 2}[layout]
    body_lines = min(cap, len(c.wrap(text_font, body, inner_width(tool, w, h, urgent)))) if body else 0
    g = geometry(
        tool,
        layout,
        w,
        h,
        c.line_h(title_font),
        c.line_h(text_font),
        len(options),
        urgent,
        bool(title),
        bar,
        body_lines,
        focus,
        0,
    )
    unit = g["unit"]

    normal = t["accent"] if t["style"] == "outline" else t["edge"]
    border = c.m["urgent"] if urgent else c.m["game"] if game else normal
    c.frame(unit)
    c.card(g, border, urgent or game)

    if g["title"][3] > 0:
        ink = c.m["urgent"] if urgent else (t["muted"] if layout == "choice" else t["ink"])
        c.text(g["title"], text_font if layout == "choice" else title_font, title, ink, "TOP_CENTER")

    if layout == "message":
        c.wrapped(g["body"], text_font, body, t["ink"], True)
    elif layout == "choice":
        bw, bh = g["body"][2], g["body"][3]
        font = title_font if len(c.wrap(title_font, body, bw)) * c.line_h(title_font) <= bh else text_font
        c.wrapped(g["body"], font, body, t["ink"], True)
    else:
        c.wrapped(g["body"], text_font, body, t["muted"], False, 2)

    first = g["first"] if layout == "list" else 0
    for r, box in enumerate(g["options"]):
        i = first + r
        mark = marks[i]
        if mark == "hidden":
            continue
        fill, edge, ink = c.button_colors(mark)
        c.box(box, fill, edge, unit)
        x, y, bw, bh = box
        pad = unit
        if layout == "choice" and i < 4:
            radius = max(6, bh // 2 - pad)
            cx, cy = x + pad + radius, y + bh // 2
            badge = t["accent"] if mark == "" else shade(fill, 0.75)
            c.d.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=badge)
            c.print(cx, cy, title_font, ink_on(badge), "ABCD"[i], "CENTER")
            lx = cx + radius + pad
            c.text((lx, y, x + bw - pad - lx, bh), text_font, options[i], ink, "TOP_LEFT")
        elif layout == "list":
            c.text((x + 2 * pad, y, bw - 4 * pad, bh), text_font, options[i], ink, "TOP_LEFT")
        else:
            c.text((x + pad, y, bw - 2 * pad, bh), text_font, options[i], ink, "TOP_CENTER")
        if i == focus:
            # Buttons-only boards: theme.on(panel, focus_color()), the accent here.
            c.ring((x - 3, y - 3, bw + 6, bh + 6), 2, t["accent"])

    sx, sy, sw, sh = g["scroll"]
    if sw > 0:
        n, rows = len(options), max(1, len(g["options"]))
        c.rect(sx, sy, sw, sh, t["dot"])
        thumb_h = max(sw * 2, sh * rows // n)
        thumb_y = sy + (sh - thumb_h) * g["first"] // max(1, n - rows)
        c.rect(sx, thumb_y, sw, thumb_h, t["accent"])

    bx, by, bw, bh = g["bar"]
    if bh > 0:
        k = case.get("left", 1.0)
        c.rect(bx, by, bw, bh, shade(t["panel"], 0.85))
        c.rect(bx, by, int(bw * k), bh, c.m["urgent"] if urgent else c.m["countdown"])
    return c.img, g


CASES = {
    "message_doorbell": dict(
        layout="message",
        style="urgent",
        title="Someone's at the door",
        body="Курʼєр з посилкою 📦 чекає біля входу. Front door camera, 18:42.",
        options=["Unlock", "Talk", "Ignore"],
        left=0.55,
    ),
    "message_doorbell_short": dict(
        layout="message",
        style="urgent",
        title="Someone's at the door",
        body="",
        options=["Unlock", "Talk", "Ignore"],
        left=0.8,
    ),
    "message_info": dict(
        layout="message",
        style="info",
        title="Laundry is done",
        body="The washer finished 5 minutes ago. Hang the shirts before they wrinkle!",
        options=["OK"],
        timeout=-1,
    ),
    "choice_question": dict(
        layout="choice",
        style="game",
        title="Question 3 of 10 · Score 2",
        body="Which planet has the most known moons?",
        options=["Saturn", "Jupiter", "Uranus", "Neptune", "50:50"],
        left=0.4,
        focus=1,
    ),
    "choice_long_question": dict(
        layout="choice",
        style="urgent",
        title="Question 9 of 10 · Score 7",
        body="Which element has the chemical symbol W, from its old German name wolfram?",
        options=["Tungsten", "Tin", "Titanium", "Tellurium", "50:50"],
        left=0.7,
    ),
    "choice_marked": dict(
        layout="choice",
        style="game",
        title="Question 3 of 10 · Score 2",
        body="Яка планета має найбільше відомих супутників? 🪐",
        options=["Saturn", "Jupiter, the largest planet of the Solar System", "Uranus", "Neptune", "50:50"],
        marks=["correct", "hidden", "wrong", "hidden", "hidden"],
        answered=True,
    ),
    "list_dinner": dict(
        layout="list",
        style="info",
        title="Dinner tonight?",
        body="Pick one. The family vote closes at 6 pm.",
        options=[
            "Pizza",
            "Борщ і пампушки",
            "Tacos",
            "Sushi",
            "Pasta carbonara with extra cheese",
            "Salad",
            "Leftovers",
            "Takeout",
        ],
        timeout=-1,
        focus=5,
    ),
}


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    tool = out / "prompt_geometry"
    # The headers include each other as ESPHome builds see them
    # (esphome/components/<name>/...); src/ has that layout.
    subprocess.run(
        ["c++", "-std=c++17", "-Wall", "-Wextra", "-I", str(ROOT / "src"), str(GEOMETRY_SRC), "-o", str(tool)],
        check=True,
    )
    images = []
    for name, case in CASES.items():
        for theme in ("wood", "outline"):
            for (w, h), screen in SCREENS.items():
                title_size, text_size = screen["sizes"]
                fonts = (ImageFont.truetype(sys.argv[3], title_size), ImageFont.truetype(sys.argv[2], text_size))
                img, _ = render(tool, case, theme, w, h, fonts, screen["lines"])
                path = out / f"{name}_{theme}_{w}x{h}.png"
                img.save(path)
                images.append((path.name, img))
                print(path)
    # Contact sheet, 2x, for a quick look.
    cols = 2
    cell_w, cell_h = 480 * 2 // 1, 320 * 2 // 1
    rows = (len(images) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (cell_w + 20), rows * (cell_h + 40)), (40, 40, 40))
    d = ImageDraw.Draw(sheet)
    for k, (name, img) in enumerate(images):
        x, y = (k % cols) * (cell_w + 20), (k // cols) * (cell_h + 40)
        big = img.resize(
            (
                img.width * 2 if img.width < 400 else img.width * 4 // 3,
                img.height * 2 if img.width < 400 else img.height * 4 // 3,
            ),
            Image.NEAREST,
        )
        sheet.paste(big, (x, y + 30))
        d.text((x, y + 6), name, fill=(230, 230, 230))
    sheet.save(out / "sheet.png")
    print(out / "sheet.png")


if __name__ == "__main__":
    main()
