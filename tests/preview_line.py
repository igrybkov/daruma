"""Host previews of the bottom corners and the next event line on every
persona: the tomato plaque or the pomodoro timer bottom left, the
temperature badge bottom right, and the info line under both.

    c++ -std=c++17 -I components/daruma tests/test_layout.cpp -o /tmp/test_layout
    uv run python -I tests/preview_line.py /tmp/test_layout OUT_DIR FONT_DIR [--before]

FONT_DIR as for preview_screens.py. The regions come from layout.h
(test_layout --json), and both plaques from plaque.h (test_layout
--plaque), with the digit width and height measured from the timer font
here, as the device measures its own. The pill follows next_line.cpp:
the dock colors of the persona's theme, the menu's small font, 6 px
padding, the title cut to fit. Pixel personas are their room and Neutral
frame, scaled as the device does without edge strips (the corgi with
them, from preview_screens). The eyes persona is its Neutral eyes glanced
40 to the left (as far as they go), and looking down and narrowed during
a focus, where eye_reach.h puts them (test_layout --eyes).

Each sheet shows four screens: idle with the "Now" line, a focus running
with the "Next" line, a break running, and a focus paused. A goal of 8,
5 done. Writes OUT_DIR/line_<persona>.png, and line_corgi_<size>.png for
the wide, square and mono screens. With --before it draws the old layout
instead (timer top right, countdown bar, plaque lifted over the line),
for side-by-side checks.

Also writes OUT_DIR/eyes_worst_<size>.png at 320x240 and 240x240: the
eyes' lowest looks (Neutral, thinking, Sad, Sleepy, focus) glanced fully
left over three rows of tomatoes (goal 9), the timer under focus. With
--before they all sit at layout.upper's center, as they used to.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[0]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "pixel"))

import preview_screens as ps  # noqa: E402

# Made-up events only.
NOW = ("Now: ", "Quarterly planning with the whole team", " · until 10:30")
NEXT = ("14:00 ", "Dentist", "")

# The dock colors of each persona's theme (persona_*.yaml); flat corgi has none
# and uses the default theme.
DOCKS = {
    "daruma": ("FAF2E2", "232A4E", "6C6880"),
    "pixel_corgi": ("FAF6EE", "3C2C24", "786458"),
    "the_boss": ("F4EEE2", "1C2C2E", "5E6E6C"),
    "eyes": ("141A20", "E1F5FA", "6E96A0"),
    "flat_corgi": ("1E222A", "E8ECF0", "969CA6"),
}
# pomodoro.yaml's theme defaults (no persona overrides them).
TOMATO, UNRIPE, BONUS, LEAF, PLAQUE = (0xE8, 0x32, 0x2B), (0x9C, 0xCC, 0x3C), (0x8E, 0x44, 0xAD), (0x2E, 0x7D, 0x32), (0x3A, 0x22, 0x16)
FOCUS, BREAK, PAUSED = (0xFF, 0x63, 0x47), (0x26, 0xED, 0x3A), (0x80, 0x80, 0x80)
GOAL, DONE = 8, 5

# name, phase color, seconds left, paused, line
STATES = (
    ("idle", None, 0, False, NOW),
    ("focus", FOCUS, 12 * 60 + 34, False, NEXT),
    ("break", BREAK, 4 * 60 + 12, False, NEXT),
    ("paused", PAUSED, 12 * 60 + 34, True, NOW),
)


def rgb(h: str):
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def on(bg, fg, mono: bool):
    """Theme::on() in mono: a foreground that comes out as its background flips."""
    if not mono:
        return fg
    m_bg, m_fg = ps.mono(bg), ps.mono(fg)
    if m_fg == m_bg:
        return (0, 0, 0) if m_bg[0] >= 128 else (255, 255, 255)
    return m_fg


def pixel_room(s: ps.Screen, persona) -> Image.Image:
    """A sprite persona: backdrop with the Neutral frame, largest whole scale,
    centered on the bottom, the rest in the persona's background."""
    room = persona.backdrop.convert("RGBA")
    sky = Image.new("RGBA", room.size, (150, 200, 240, 255))
    room = Image.alpha_composite(sky, room)
    frame = persona.animations["Neutral"].frames[0][0].convert("RGBA")
    room.alpha_composite(frame, tuple(persona.sprite_offset))
    bw, bh = room.size
    sc = max(1, min(s.w // bw, s.h // bh))
    bg = persona.background
    img = Image.new("RGB", (s.w, s.h), ((bg >> 16) & 255, (bg >> 8) & 255, bg & 255))
    img.paste(room.convert("RGB").resize((bw * sc, bh * sc), Image.NEAREST), ((s.w - bw * sc) // 2, s.h - bh * sc))
    return img


def flat_corgi(s: ps.Screen) -> Image.Image:
    art = Image.open(ROOT / "art" / "flat_corgi" / "neutral.png").convert("RGB")
    img = Image.new("RGB", (s.w, s.h), art.getpixel((0, 0)))
    img.paste(art, ((s.w - art.width) // 2, (s.h - art.height) // 2))
    return img


EYE_BG, EYE = (8, 10, 14), (0, 220, 240)
NEUTRAL, HAPPY, SAD, LOVED, SCARED, SLEEPY, SLEEPING = range(7)
LOOK_THINKING, LOOK_FOCUS = 8, 9


def draw_look(s: ps.Screen, img: Image.Image, look: dict, glance: int = 0) -> None:
    """One look's eyes in their box from test_layout --eyes (glance 0: fully
    left). Shapes as the moods draw them, near enough for overlap checks."""
    d = ImageDraw.Draw(img)
    x, y, w, h = look["glances"][glance]
    mood = look["mood"]
    ew = (w - s.px(40)) // 2 if mood != SCARED else s.px(20)
    for i, ex in enumerate((x, x + w - ew)):
        box = (ex, y, ex + ew - 1, y + h - 1)
        if mood == SCARED:
            d.ellipse((ex, y + h // 2 - ew // 2, ex + ew, y + h // 2 + ew // 2), fill=EYE)
        elif mood == SLEEPING:
            d.rectangle(box, fill=EYE)
        else:
            d.rounded_rectangle(box, radius=min(s.px(15), h // 2), fill=EYE)
            if mood == SAD:
                # The outer top corner cut away, so the eyes droop outward.
                cy = y + h // 2
                tri = ((ex, y), (ex + ew, y), (ex, cy)) if i == 0 else ((ex, y), (ex + ew, y), (ex + ew, cy))
                d.polygon(tri, fill=EYE_BG)


def eyes(s: ps.Screen, looks: list, focus: bool) -> Image.Image:
    """Neutral eyes glanced fully left; focus looks down (dy 30), half shut."""
    img = Image.new("RGB", (s.w, s.h), EYE_BG)
    draw_look(s, img, looks[LOOK_FOCUS if focus else NEUTRAL])
    return img


def tomato(d: ImageDraw.ImageDraw, x, y, r, body, mono):
    d.ellipse((x - r, y - r, x + r, y + r), fill=on(PLAQUE, body, mono))
    d.rectangle((x - 2, y - r - 2, x + 2, y - r + 1), fill=on(PLAQUE, LEAF, mono))


def line(s: ps.Screen, d: ImageDraw.ImageDraw, info, dock, text) -> None:
    """The pill as next_line.cpp draws it."""
    bg, ink, muted = (rgb(c) for c in dock)
    before, title, after = text
    f = s.small
    lpad = s.px(6)
    wb, wa = d.textlength(before, font=f), d.textlength(after, font=f)
    room = info[2] - 2 * lpad - wb - wa
    title = ps.fit(d, f, title, room) if room > 0 else ""
    w = min(int(2 * lpad + wb + wa + d.textlength(title, font=f)), info[2])
    x, y, h = info[0], info[1], info[3]
    d.rounded_rectangle((x, y, x + w - 1, y + h - 1), radius=s.px(6), fill=bg)
    cx, cy = x + lpad, y + h // 2
    for part, color in ((before, muted), (title, ink), (after, muted)):
        if part:
            d.text((cx, cy), part, font=f, fill=color, anchor="lm")
            cx += d.textlength(part, font=f)


def after(s: ps.Screen, img, state, dock, font, plaque, mono=False) -> None:
    """The new layout: plaque.h's plaques, the badge, the line under both."""
    name, color, left, paused, text = state
    d = ImageDraw.Draw(img)
    r6 = s.px(6)
    if color is None:
        t = plaque["tomatoes"]
        x, y, w, h = t["rect"]
        d.rounded_rectangle((x, y, x + w - 1, y + h - 1), radius=r6, fill=PLAQUE)
        r = t["r"]
        for i, (cx, cy) in enumerate(t["centers"]):
            if i >= DONE and on(PLAQUE, UNRIPE, mono) == on(PLAQUE, TOMATO, mono):
                d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=on(PLAQUE, UNRIPE, mono))
            else:
                tomato(d, cx, cy, r, TOMATO if i < DONE else UNRIPE, mono)
    else:
        t = plaque["timer"]
        x, y, w, h = t["rect"]
        d.rounded_rectangle((x, y, x + w - 1, y + h - 1), radius=r6, fill=(0, 0, 0) if mono else PLAQUE)
        c = on(PLAQUE, color, mono)
        base = t["baseline"]
        dx, dy, dw, cap = t["digits"]
        sx = t["sep_cx"]
        def bars(cx, top, bh, bw, gap, fill):
            x0 = cx - gap // 2 - bw
            for bx in (x0, x0 + bw + gap):
                d.rectangle((bx, top, bx + bw - 1, top + bh - 1), fill=fill)

        if mono:
            # The mono board is a slow screen: whole minutes, the pause
            # sign before them.
            mins = "%dm" % ((left + 59) // 60)
            shift = s.px(5) if paused else 0
            d.text((dx + dw // 2 + shift, base), mins, font=font, fill=c, anchor="ms")
            if paused:
                bh = cap * 3 // 4
                bars(dx + dw // 2 + shift - int(d.textlength(mins, font=font)) // 2 - s.px(6),
                     dy + (cap - bh) // 2, bh, max(s.px(3), 2), max(s.px(2), 1), c)
        else:
            if paused:
                # The tab on the top edge, the plaque's color in its sign.
                tx, ty, tw, th = t["pause_tab"]
                b = t["tab_bar"]
                d.rounded_rectangle((tx, ty, tx + tw - 1, ty + th - 1), radius=th // 2, fill=c)
                bars(tx + tw // 2, ty + b, th - 2 * b, b, b, PLAQUE)
            digits = (left // 600, left // 60 % 10, left % 60 // 10, left % 10)
            for i, v in enumerate(digits):
                d.text((t["digit_cx"][i], base), str(v), font=font, fill=c, anchor="ms")
            # The colon blinks while running and stays while paused.
            if paused or left % 2 == 0:
                q = max(s.px(3), 2)
                for k in (3, 8):
                    yy = dy + cap * k // 10 - q // 2
                    d.rectangle((sx - q // 2, yy, sx - q // 2 + q - 1, yy + q - 1), fill=c)
        r = t["dot_r"]
        for i, (cx, cy) in enumerate(t["dots"]):
            if i < DONE:
                d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=on(PLAQUE, TOMATO, mono))
            else:
                d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=on(PLAQUE, UNRIPE, mono))
    ps.badge(s, img)
    line(s, d, s.l["info"], dock, text)


def before(s: ps.Screen, img, state, dock, font) -> None:
    """The old layout: countdown bar and mm:ss top right, the plaque lifted
    over the line, the badge where it was."""
    name, color, left, paused, text = state
    d = ImageDraw.Draw(img)
    W, H = s.w, s.h
    if color is not None:
        d.rectangle((0, H - s.px(6), W * 2 // 3, H - 1), fill=color)
        d.text((W - s.px(6), s.px(6)), "%02d:%02d" % (left // 60, left % 60), font=font, fill=color, anchor="ra")
    info = (s.px(4), H - s.px(10) - s.px(18), W - s.px(60), s.px(18))
    slots, per_row, step, row_h, r, pad = GOAL, 3, s.px(24), s.px(24), s.px(8), s.px(6)
    rows, cols = (slots + per_row - 1) // per_row, min(slots, per_row)
    pw, ph = cols * step + pad, rows * row_h + pad
    px, py = s.px(4), info[1] - s.px(4) - ph
    d.rounded_rectangle((px, py, px + pw - 1, py + ph - 1), radius=s.px(6), fill=PLAQUE)
    for i in range(slots):
        x = px + pad // 2 + step // 2 + (i % per_row) * step
        y = py + ph - pad // 2 - row_h // 2 - (i // per_row) * row_h + s.px(2)
        tomato(d, x, y, r, TOMATO if i < DONE else UNRIPE, False)
    rr = s.px(21)
    cx, cy = W - rr - s.px(10), H - rr - s.px(12)
    d.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), fill=(255, 255, 255))
    r2 = rr - s.px(2)
    d.ellipse((cx - r2, cy - r2, cx + r2, cy + r2), fill=(52, 150, 74))
    d.text((cx + 1, cy + 1), "64°", font=s.text, fill=(255, 255, 255), anchor="mm")
    line(s, d, info, dock, text)


def main() -> None:
    binary, out, font_dir = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    old = "--before" in sys.argv[4:]
    out.mkdir(parents=True, exist_ok=True)
    layouts = json.loads(subprocess.run([binary, "--json"], check=True, capture_output=True, text=True).stdout)

    from daruma_pixel import daruma_persona, personas

    def timer_font(size):
        f = ImageFont.truetype(str(font_dir / "Manrope[wght].ttf"), size)
        try:
            f.set_variation_by_axes([700])
        except OSError:
            pass
        return f

    def plaque_for(s: ps.Screen, font):
        # As the device: the widest digit's advance, and the cap height.
        digit_w = max(int(round(font.getlength(str(v)))) for v in range(10))
        box = font.getbbox("X", anchor="ls")
        cap = -box[1]
        res = subprocess.run([binary, "--plaque", str(s.w), str(s.h), str(GOAL), str(digit_w), str(cap)],
                             check=True, capture_output=True, text=True)
        return json.loads(res.stdout)

    def shots(s, base_for, dock, font, mono=False):
        plaque = plaque_for(s, font)
        imgs = []
        for state in STATES:
            img = base_for(state).copy()
            if old:
                before(s, img, state, dock, font)
            else:
                after(s, img, state, dock, font, plaque, mono)
            imgs.append(ps.to_mono(img) if mono else img)
        return imgs

    suffix = "_before" if old else ""
    s = ps.Screen(layouts["320x240"], ps.FONTS["320x240"], font_dir, ps.WOOD, focus=False)
    rooms = {
        "daruma": lambda: pixel_room(s, daruma_persona.build(0)),
        "pixel_corgi": lambda: ps.corgi_idle(s),
        "the_boss": lambda: pixel_room(s, personas.build("the_boss")),
        "flat_corgi": lambda: flat_corgi(s),
    }
    for name, room in rooms.items():
        base = room()
        ps.sheet(shots(s, lambda _st: base, DOCKS[name], timer_font(22))).save(out / f"line_{name}{suffix}.png")
        print(f"{name} -> {out / f'line_{name}{suffix}.png'}")
    def eye_looks(size):
        w, h = size.split("x")
        args = [binary, "--eyes", w, h] + (["--before"] if old else [])
        return json.loads(subprocess.run(args, check=True, capture_output=True, text=True).stdout)["looks"]

    looks = eye_looks("320x240")
    eyes_for = lambda st: eyes(s, looks, st[0] in ("focus",))  # noqa: E731
    ps.sheet(shots(s, eyes_for, DOCKS["eyes"], timer_font(22))).save(out / f"line_eyes{suffix}.png")
    print(f"eyes -> {out / f'line_eyes{suffix}.png'}")

    # The eyes' lowest looks over the tallest plaques they keep clear of.
    for size in ("320x240", "240x240"):
        s2 = ps.Screen(layouts[size], ps.FONTS[size], font_dir, ps.WOOD, focus=False)
        font = timer_font(22)
        digit_w = max(int(round(font.getlength(str(v)))) for v in range(10))
        cap = -font.getbbox("X", anchor="ls")[1]
        w, h = size.split("x")
        res = subprocess.run([binary, "--plaque", w, h, "9", str(digit_w), str(cap)],
                             check=True, capture_output=True, text=True)
        plaque = json.loads(res.stdout)
        looks2 = eye_looks(size)
        imgs = []
        for idx, state in ((NEUTRAL, STATES[0]), (LOOK_THINKING, STATES[0]), (SAD, STATES[0]),
                           (SLEEPY, STATES[0]), (LOOK_FOCUS, STATES[1])):
            img = Image.new("RGB", (s2.w, s2.h), EYE_BG)
            draw_look(s2, img, looks2[idx])
            after(s2, img, state, DOCKS["eyes"], font, plaque)
            imgs.append(img)
        ps.sheet(imgs).save(out / f"eyes_worst_{size}{suffix}.png")
        print(f"eyes worst {size} -> {out / f'eyes_worst_{size}{suffix}.png'}")

    for size, fonts, timer in (("480x272", ps.FONTS["480x272"], 25), ("240x240", ps.FONTS["240x240"], 22)):
        s2 = ps.Screen(layouts[size], fonts, font_dir, ps.WOOD, focus=False)
        base = ps.corgi_idle(s2)
        ps.sheet(shots(s2, lambda _st: base, DOCKS["pixel_corgi"], timer_font(timer))).save(
            out / f"line_corgi_{size}{suffix}.png")
        print(f"corgi {size} -> {out / f'line_corgi_{size}{suffix}.png'}")

    # Mono: the derived theme's dock colors, the frame to black and white.
    mono = ps.mono_theme(ps.WOOD)
    hexes = tuple("%02X%02X%02X" % mono[k] for k in ("dock", "dock_ink", "dock_muted"))
    base = ps.corgi_idle(s)
    ps.sheet(shots(s, lambda _st: base, hexes, timer_font(22), mono=True)).save(out / f"line_corgi_mono{suffix}.png")
    print(f"corgi mono -> {out / f'line_corgi_mono{suffix}.png'}")


if __name__ == "__main__":
    main()
