"""Host previews of the Calendar app's agenda, using the device's own layout
math and the same row sizes as agenda_view.cpp.

    c++ -std=c++17 -I components/daruma tests/test_layout.cpp -o /tmp/test_layout
    uv run python -I tests/preview_agenda.py /tmp/test_layout OUT_DIR FONT_DIR

FONT_DIR holds Manrope[wght].ttf and mdi.ttf. Writes OUT_DIR/agenda_<theme>_<size>.png
for the wood and outline themes at 320x240 and 480x272: the agenda from the
top, scrolled down, and with the focus ring of a board without touch. The
events are made up; "now" is Sunday 15 Nov, 10:30.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import preview_screens as ps  # noqa: E402

# The default theme (theme.h): flat background, cards with an accent outline.
OUTLINE = {
    "frame": (14, 16, 20),
    "edge": (60, 66, 76),
    "panel": (30, 34, 42),
    "ink": (232, 236, 240),
    "muted": (150, 156, 166),
    "title": (232, 236, 240),
    "accent": (0, 200, 220),
}

# (kind, day, time or "", title): the rows build_agenda() makes from them.
ROWS = [
    ("H", "Today"),
    ("E", "All day", "Grandma's birthday", "allday"),
    ("E", "08:30", "Standup", "past"),
    ("E", "10:00", "Design review: agenda view for the Daruma", "now"),
    ("E", "14:00", "Dentist", ""),
    ("H", "Tomorrow"),
    ("E", "09:00", "Flight to Lisbon", ""),
    ("H", "Wed 18 Nov"),
    ("E", "All day", "Conference", "allday"),
    ("E", "18:30", "Dinner with Ana", ""),
    ("H", "Sat 21 Nov"),
    ("E", "11:00", "Dog to the groomer", ""),
    ("M", "+3 more"),
]


def mix(a, b, k):
    return tuple(int(x + (y - x) * k) for x, y in zip(a, b))


def outline_frame(s, title):
    t = s.theme
    img = Image.new("RGB", (s.w, s.h), t["frame"])
    d = ImageDraw.Draw(img)
    hh = s.l["header"][3]
    d.text((s.w // 2, hh // 2), title, font=s.text, fill=t["title"], anchor="mm")
    d.text((s.px(22), hh // 2), "\U000f0141", font=s.icons, fill=t["title"], anchor="mm")
    return img


def agenda(s, wood: bool, scroll: int, focus: int | None) -> Image.Image:
    t = s.theme
    img = ps.frame(s, "Calendar") if wood else outline_frame(s, "Calendar")
    d = ImageDraw.Draw(img)
    x, y, w, h = s.l["content"]
    if wood:
        d.rectangle(ps.rect(s.l["content"]), fill=t["panel"])
    else:
        d.rounded_rectangle(ps.rect(s.l["content"]), radius=s.px(10), fill=t["panel"], outline=t["accent"], width=2)
    pad, time_w, top0 = s.px(10), s.px(54), s.px(2)
    fit_rows = max(1, (h - 2 * top0) // s.px(26))
    row_h = (h - 2 * top0) // fit_rows
    count = len(ROWS)
    scroll = max(0, min(scroll, count - fit_rows))
    scrolls = count > fit_rows
    right = x + w - pad - (s.px(6) if scrolls else 0)
    left = x + pad
    for i in range(scroll, min(count, scroll + fit_rows)):
        row = ROWS[i]
        top = y + top0 + (i - scroll) * row_h
        mid = top + row_h // 2
        if row[0] == "H":
            d.text(
                (left, top + row_h - s.px(7)),
                ps.fit(d, s.text, row[1], right - left),
                font=s.text,
                fill=t["ink"],
                anchor="ls",
            )
            ly = top + row_h - s.px(3)
            d.line((left, ly, right - 1, ly), fill=mix(t["panel"], t["muted"], 0.35))
        elif row[0] == "E":
            _, when, title, mark = row
            bg = t["panel"]
            if mark == "now":
                bg = mix(t["panel"], t["accent"], 0.2)
                d.rounded_rectangle(
                    (left - s.px(4), top + 1, right + s.px(2), top + row_h - 2), radius=s.px(5), fill=bg
                )
                d.rectangle((left - s.px(4), top + 3, left - s.px(4) + 2, top + row_h - 4), fill=t["accent"])
            tc = t["accent"] if mark == "now" else (t["muted"] if mark in ("past", "allday") else t["ink"])
            d.text((left + 2, mid), ps.fit(d, s.small, when, time_w - s.px(4)), font=s.small, fill=tc, anchor="lm")
            d.text(
                (left + time_w, mid),
                ps.fit(d, s.text, title, right - left - time_w),
                font=s.text,
                fill=t["muted"] if mark == "past" else t["ink"],
                anchor="lm",
            )
        else:
            d.text((left + 2, mid), row[1], font=s.small, fill=t["muted"], anchor="lm")
        if focus == i:
            ring = max(2, s.px(2))
            x0 = left - s.px(5)
            for k in range(ring):
                d.rectangle((x0 + k, top + k, right + s.px(3) - 1 - k, top + row_h - 1 - k), outline=t["accent"])
    if scrolls:
        line = mix(t["panel"], t["muted"], 0.2)
        top = y + top0
        tx, th = x + w - pad - 2, fit_rows * row_h - 4
        thumb = max(10, th * fit_rows // count)
        ty = top + 2 + (th - thumb) * scroll // max(1, count - fit_rows)
        d.rectangle((tx, top + 2, tx + 2, top + 2 + th - 1), fill=line)
        d.rectangle((tx, ty, tx + 2, ty + thumb - 1), fill=mix(t["panel"], t["muted"], 0.7))
    return img


def main() -> None:
    binary, out, font_dir = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    out.mkdir(parents=True, exist_ok=True)
    layouts = json.loads(subprocess.run([binary, "--json"], check=True, capture_output=True, text=True).stdout)
    for theme_name, theme, wood in (("wood", ps.WOOD, True), ("outline", OUTLINE, False)):
        for size in ("320x240", "480x272"):
            s = ps.Screen(layouts[size], ps.FONTS[size], font_dir, theme, focus=False)
            shots = [agenda(s, wood, 0, None), agenda(s, wood, 6, None), agenda(s, wood, 3, 3)]
            path = out / f"agenda_{theme_name}_{size}.png"
            ps.sheet(shots).save(path)
            print(path)


if __name__ == "__main__":
    main()
