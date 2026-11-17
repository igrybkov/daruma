"""Effects around a persona: hearts, zzz, sweat, a tear, thinking dots, sparkle.

Every actor draws them the same way, at its own place: pet.py's rig, the
cat, the Jack Russell curled up, the boss at the desk. A Pose names them in
its `extras`.
"""

from __future__ import annotations

from .pixelkit import Canvas

HEART = (226, 52, 72)
HEART_SHINE = (255, 160, 170)
DOT_RING = (40, 30, 36)  # Thinking dots: a dark ring around white.


def extras(c: Canvas, extras: tuple[str, ...], cx: int, floor: int, tear: tuple[int, int] | None = None) -> None:
    """Effects around the persona: hearts, zzz, sweat, tear, dots, sparkle.

    `tear` is where a tear starts (under the left eye); by default, under
    the corgi's eye.
    """
    top = floor - 64
    for e in extras:
        if e == "hearts":
            for hx, hy in ((cx - 26, top + 10), (cx + 24, top + 4), (cx + 30, top + 18)):
                for row, line in enumerate([".X.X.", "XXXXX", ".XXX.", "..X.."]):
                    for col, ch in enumerate(line):
                        if ch == "X":
                            c.dot(hx + col, hy + row, HEART)
                c.dot(hx + 1, hy + 1, HEART_SHINE)
        elif e == "zzz":
            for _i, (zx, zy, s) in enumerate(((cx + 20, top + 18, 3), (cx + 26, top + 10, 4), (cx + 33, top + 1, 5))):
                col = (200, 210, 255)
                for k in range(s):
                    c.dot(zx + k, zy, col)
                    c.dot(zx + s - 1 - k, zy + k, col)
                    c.dot(zx + k, zy + s - 1, col)
        elif e == "sweat":
            for dx, dy in ((0, 0), (-1, 1), (0, 1), (-1, 2), (0, 2), (1, 2), (0, 3)):
                c.dot(cx + 18 + dx, top + 20 + dy, (120, 190, 255))
        elif e == "tear":
            tx, ty = tear or (cx - 9, floor - 36)
            for dy in range(3):
                c.dot(tx, ty + dy, (120, 190, 255))
        elif e == "dots":
            # White dots in a dark ring, so they read on light and dark walls.
            for i in range(3):
                x, y = cx + 22 + i * 5, top + 13 - i * 4
                for dx, dy in ((0, -1), (1, -1), (-1, 0), (2, 0), (-1, 1), (2, 1), (0, 2), (1, 2)):
                    c.dot(x + dx, y + dy, DOT_RING)
                for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1)):
                    c.dot(x + dx, y + dy, (255, 255, 255))
        elif e == "sparkle":
            for sx, sy in ((cx - 24, top + 16), (cx + 25, top + 12)):
                for dx, dy in ((0, -2), (0, -1), (0, 0), (0, 1), (0, 2), (-2, 0), (-1, 0), (1, 0), (2, 0)):
                    c.dot(sx + dx, sy + dy, (255, 236, 140))
