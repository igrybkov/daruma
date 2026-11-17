"""Edge strips that let a pixel-art room fill a screen of any shape.

A room is drawn for one size (106x80 for the BOX-3 at 3x). On a wider or
taller screen the device draws it at the largest whole scale that fits and
fills the rest by repeating strips taken from the room's own edges: the
wall goes on sideways and upward, the floor goes on sideways. No black bars,
and no extra art.

A strip is the smallest band at an edge that repeats outward without a seam.
For each edge, every line across it (a row for the left and right edges, a
column for the top) is tested for a repeat period p: its first pixels from
the edge must repeat every p pixels over a window of max(2p, MIN_WINDOW)
pixels. The period most lines share wins (the smallest on a tie). Lines that
do not repeat with it, such as rows crossing a window frame or a shelf near
the edge, take the strip of the nearest line that does, so the extension
shows plain wall there.

The bottom edge gets no strip: rugs and furniture stand on it, so the device
keeps the room on the bottom of the screen and puts extra height above.

Plain Python with no ESPHome or PIL imports, so it can be tested on its own
(tests/test_registry.py). Pixels are any comparable values, such
as RGBA tuples.
"""

from __future__ import annotations

MAX_PERIOD = 24
MIN_WINDOW = 4


def _period(lines: list[list], max_period: int = MAX_PERIOD) -> tuple[int, list[bool]]:
    """The repeat period most lines share, and which lines repeat with it."""
    longest = max((len(line) for line in lines), default=0)
    best, best_ok = 1, [False] * len(lines)
    best_score = -1
    for p in range(1, max_period + 1):
        window = max(2 * p, MIN_WINDOW)
        if window > longest:
            break
        ok = [len(line) >= window and all(line[i] == line[i + p] for i in range(window - p)) for line in lines]
        score = sum(ok)
        if score > best_score:
            best, best_ok, best_score = p, ok, score
    return best, best_ok


def _repeats(line: list, p: int) -> bool:
    window = max(2 * p, MIN_WINDOW)
    return len(line) >= window and all(line[i] == line[i + p] for i in range(window - p))


def _strip(lines: list[list], max_period: int = MAX_PERIOD) -> list[list]:
    """The first p pixels of every line, from the edge inward. A line that
    does not repeat every p pixels may repeat with a shorter period that
    divides p (a floor row repeats every pixel); else it borrows the nearest
    line that repeats."""
    p, ok = _period(lines, max_period)
    out: list[list | None] = []
    for i, line in enumerate(lines):
        if ok[i]:
            out.append(list(line[:p]))
            continue
        q = next((q for q in range(1, p) if p % q == 0 and _repeats(line, q)), None)
        out.append([line[k % q] for k in range(p)] if q else None)
    good = [i for i, strip in enumerate(out) if strip is not None]
    for i, strip in enumerate(out):
        if strip is None and good:
            # The nearest repeating line that starts with the same pixel, so
            # the edge itself stays continuous (a plank keeps its color).
            same = [g for g in good if lines[g][0] == lines[i][0]] or good
            out[i] = list(out[min(same, key=lambda g: (abs(g - i), g))])
        elif strip is None:
            out[i] = list(lines[i][:p])
    return out


def left_strip(rows: list[list]) -> list[list]:
    """Rows of the strip at the left edge: column c is the room's column c.
    Column x < 0 of the extended room is column x mod p of the strip."""
    return _strip([list(row) for row in rows])


def right_strip(rows: list[list]) -> list[list]:
    """Rows of the strip at the right edge: column c is the room's column
    w - p + c. Column w + k of the extended room is column k mod p."""
    lines = _strip([list(reversed(row)) for row in rows])
    return [list(reversed(line)) for line in lines]


def top_strip(rows: list[list]) -> list[list]:
    """Rows of the strip at the top edge: row r is the room's row r. Row
    y < 0 of the extended room is row y mod p of the strip."""
    width = len(rows[0]) if rows else 0
    columns = [[row[x] for row in rows] for x in range(width)]
    lines = _strip(columns)
    height = len(lines[0]) if lines else 0
    return [[lines[x][y] for x in range(width)] for y in range(height)]


def extended(rows: list[list], left: int, right: int, top: int) -> list[list]:
    """The room with `left`, `right` and `top` more pixels, the way the
    device draws it (for previews and tests)."""
    ls, rs, ts = left_strip(rows), right_strip(rows), top_strip(rows)
    w = len(rows[0])
    pl, pr, pt = len(ls[0]), len(rs[0]), len(ts)

    def pixel(x: int, y: int):
        if y < 0:
            r = y % pt
            if x < 0:
                return ls[r][x % pl]
            if x >= w:
                return rs[r][(x - w) % pr]
            return ts[r][x]
        if x < 0:
            return ls[y][x % pl]
        if x >= w:
            return rs[y][(x - w) % pr]
        return rows[y][x]

    return [[pixel(x, y) for x in range(-left, w + right)] for y in range(-top, len(rows))]
