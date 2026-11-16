"""The living room: a Scene (pet.py) with a comfy couch for a pet to sit on.

Linen-striped wallpaper, an arched window with curtains (the device draws
the sky in its glass), a spider plant hanging from the ceiling (the
progress prop, spider_plant.py), honey oak floor boards, and a bottle-green
velvet couch with a dusty blue cushion and a knitted throw over its left arm.
The throw changes color by weekday (THROW_BY_WEEKDAY: the day colors of
the corgi's rug). The pet sits on the seat: the scene's `pet_floor` is the
seat's top, where pet.render() puts its feet.

Nothing touches the left and right edges (8 px of plain wallpaper and
floor each side), so a wide screen extends the room by its own wall.
"""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image, ImageDraw

from . import room as _room
from . import spider_plant as _plant
from .pixelkit import Canvas, Color, Ramp, ellipse, mask, poly

W, H = 106, 80
WINDOW = (74, 7, 20, 23)  # Glass: x, y, width, height. The arch corners and bars stay in the room.
FLOOR_Y = 73  # The wall meets the floor here.
SEAT = 66  # The seat cushion's top edge at the front: the pet's floor (pet.render).
THROW_BOX = (6, 40, 33, 77)  # Where the weekday colors may be: the throw on the left arm.

FRAME = Ramp(base=(108, 74, 50), shadow=(80, 54, 36), light=(136, 96, 66))
CURTAIN = Ramp(base=(184, 102, 78), shadow=(150, 78, 58), light=(208, 132, 104), line=(122, 60, 44))
COUCH = Ramp(base=(50, 100, 76), shadow=(34, 72, 54), light=(76, 132, 100), line=(26, 54, 40))
COUCH_DARK = Ramp(base=(40, 82, 62), shadow=(28, 60, 44), light=(56, 106, 80), line=(22, 46, 34))
CUSHION = Ramp(base=(92, 118, 158), shadow=(70, 92, 130), light=(124, 150, 186), line=(52, 68, 100))  # Dusty blue.
TIE = Ramp(base=(220, 166, 58), shadow=(184, 130, 40))  # The curtains' mustard tie-backs.

GLASS = (255, 0, 255)  # A placeholder for the glass while drawing; never left in a picture.


@dataclass(frozen=True)
class LivingRoom:
    """A living room with a couch. The defaults are the Jack Russell's."""

    wall: Color = (228, 214, 188)  # Linen wallpaper ...
    wall_stripe: Color = (216, 200, 170)  # ... with a fine stripe every 4 px.
    wall_line: Color = (170, 146, 112)  # Skirting board's top edge.
    skirting: Color = (240, 232, 214)
    floor: Color = (180, 128, 80)
    floor_line: Color = (152, 104, 64)
    rod: Color = (70, 48, 34)
    couch_outline: Color = (24, 40, 32)
    legs: Color = (92, 60, 40)
    # The throw: fringe and stripes, the knit, its folds. Swapped by weekday.
    throw_edge: Color = (236, 210, 164)
    throw: Color = (178, 72, 86)
    throw_shadow: Color = (140, 52, 66)
    sky: tuple[Color, ...] = ((122, 190, 236), (150, 206, 240), (184, 224, 246))

    # The Scene protocol (pet.py).
    window = WINDOW
    pet_floor = SEAT  # Not a field: the couch is always where it is. See pet.Pet.

    def image(self) -> Image.Image:
        img = living_room(self)
        _fill_glass(img, self.sky)
        return img

    def background(self) -> Image.Image:
        img = living_room(self)
        px = img.load()
        for y in range(H):
            for x in range(W):
                if px[x, y][:3] == GLASS:
                    px[x, y] = (0, 0, 0, 0)
        return img

    def layers(self) -> dict:
        return {"plant": _plant.plant, "PLANT_STAGES": _plant.STAGES, "DEFAULT_STAGE": _plant.DEFAULT_STAGE,
                "RUG_COLORS": (self.throw_edge, self.throw, self.throw_shadow),
                "RUG_BY_WEEKDAY": THROW_BY_WEEKDAY, "RUG_BOX": THROW_BOX}


# The throw's colors by weekday, Sunday first: the corgi's rug days
# (room.py), with Wednesday's green lighter, so it stands out on the couch.
THROW_BY_WEEKDAY = (
    *_room.RUG_BY_WEEKDAY[:3],
    ((236, 222, 170), (150, 196, 108), (114, 158, 80)),  # Wednesday: spring green
    *_room.RUG_BY_WEEKDAY[4:],
)


def _fill_glass(img: Image.Image, sky: tuple[Color, ...]) -> None:
    """Sky bands and a cloud in the glass, for pictures without the device."""
    px = img.load()
    x0, y0, w, h = WINDOW
    for y in range(y0, y0 + h):
        for x in range(x0, x0 + w):
            if px[x, y][:3] == GLASS:
                band = min(len(sky) - 1, (y - y0) * len(sky) // h)
                px[x, y] = (*sky[band], 255)
    for x, y in ((78, 20), (79, 20), (80, 20), (81, 20), (79, 19), (80, 19)):
        px[x, y] = (255, 255, 255, 255)


def _in_arch(x: int, y: int) -> bool:
    """Inside the window's opening: a rectangle with a round top."""
    x0, y0, w, h = WINDOW
    cx, r = x0 + (w - 1) / 2, w / 2
    if not (x0 <= x < x0 + w and y0 <= y < y0 + h):
        return False
    top = y0 + r
    return y >= top or (x - cx) ** 2 + (y - top) ** 2 <= r * r


def _wall(img: Image.Image, r: LivingRoom) -> None:
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, W, FLOOR_Y), fill=r.wall)
    for x in range(1, W, 4):
        d.line((x, 0, x, FLOOR_Y - 4), fill=r.wall_stripe)
    # Skirting board.
    d.rectangle((0, FLOOR_Y - 3, W, FLOOR_Y - 1), fill=r.skirting)
    d.line((0, FLOOR_Y - 4, W, FLOOR_Y - 4), fill=r.wall_line)
    # Floor boards, long planks across.
    d.rectangle((0, FLOOR_Y, W, H), fill=r.floor)
    d.line((0, FLOOR_Y, W, FLOOR_Y), fill=r.floor_line)
    for y in range(FLOOR_Y + 3, H, 3):
        d.line((0, y, W, y), fill=r.floor_line)


def _window(img: Image.Image, r: LivingRoom) -> None:
    px = img.load()
    x0, y0, w, h = WINDOW
    frame = Canvas(W, H)
    # The frame: the opening grown by two pixels, then the glass cut out.
    m, _ = mask((W, H))
    mp = m.load()
    for y in range(y0 - 2, y0 + h + 2):
        for x in range(x0 - 2, x0 + w + 2):
            if any(_in_arch(x + dx, y + dy) for dx in (-2, 0, 2) for dy in (-2, 0, 2)):
                mp[x, y] = 1
    frame.paint(m, FRAME)
    img.alpha_composite(frame.img)
    for y in range(y0, y0 + h):
        for x in range(x0, x0 + w):
            if _in_arch(x, y):
                px[x, y] = (*GLASS, 255)
    # Glazing bars: a mullion, and a transom where the arch begins.
    mid = x0 + w // 2
    for y in range(y0, y0 + h):
        if _in_arch(mid, y):
            px[mid, y] = (*FRAME.base, 255)
    for x in range(x0, x0 + w):
        px[x, y0 + w // 2] = (*FRAME.base, 255)
    # The sill, a little wider than the frame.
    d = ImageDraw.Draw(img)
    d.rectangle((x0 - 4, y0 + h + 1, x0 + w + 3, y0 + h + 2), fill=FRAME.light)
    d.line((x0 - 4, y0 + h + 3, x0 + w + 3, y0 + h + 3), fill=FRAME.shadow)


def _curtains(img: Image.Image, r: LivingRoom) -> None:
    """Two curtains on a rod, gathered by a tie-back each side of the window."""
    x0, y0, w, h = WINDOW
    d = ImageDraw.Draw(img)
    d.line((x0 - 8, y0 - 3, x0 + w + 7, y0 - 3), fill=r.rod)  # The rod, with knobs.
    d.point([(x0 - 9, y0 - 4), (x0 + w + 8, y0 - 4), (x0 - 9, y0 - 2), (x0 + w + 8, y0 - 2)], fill=r.rod)
    c = Canvas(W, H)
    tie_y, bottom = y0 + 14, y0 + h + 5
    for side in (-1, 1):
        # Measured from the window outward: 0 at its edge, out to 7.
        edge = x0 + 1 if side < 0 else x0 + w - 2
        at = lambda k: edge + side * k  # noqa: E731
        m, dm = mask((W, H))
        poly(dm, [(at(7), y0 - 2), (at(0), y0 - 2), (at(1), y0 + 5), (at(4), tie_y - 1), (at(4), tie_y + 1),
                  (at(1), bottom - 3), (at(0), bottom), (at(7), bottom)])
        c.paint(m, CURTAIN)
        # Folds: shadows a third and two thirds across each row.
        mp = m.load()
        for y in range(y0 - 1, bottom):
            row = [x for x in range(W) if mp[x, y]]
            if len(row) >= 4:
                for f in (1 / 3, 2 / 3):
                    c.dot(row[0] + round((len(row) - 1) * f), y, CURTAIN.shadow)
        for k in range(4, 8):  # The tie-back.
            c.dot(at(k), tie_y, TIE.base)
            c.dot(at(k), tie_y + 1, TIE.shadow)
    c.outline(CURTAIN.line)
    img.alpha_composite(c.img)


def _couch(img: Image.Image, r: LivingRoom) -> None:
    c = Canvas(W, H)
    left, right = 9, 96  # Outside of the arms.
    # Back: two plump back cushions, rounded at the top corners.
    m, dm = mask((W, H))
    dm.rounded_rectangle((left + 5, 37, right - 5, SEAT - 2), radius=5, fill=1)
    c.paint(m, COUCH_DARK)
    for x in (W // 2,):  # The seam between the back cushions, hidden behind the pet.
        for y in range(39, SEAT - 4):
            c.dot(x, y, COUCH_DARK.shadow)
    # Seat: the top of the cushions, lit, and their front face.
    m, dm = mask((W, H))
    dm.rectangle((left + 8, SEAT - 4, right - 8, SEAT), fill=1)
    c.paint(m, COUCH, shade=False)
    for x in range(left + 8, right - 7):
        c.dot(x, SEAT - 4, COUCH.light)
    m, dm = mask((W, H))
    dm.rectangle((left + 8, SEAT + 1, right - 8, FLOOR_Y - 1), fill=1)
    c.paint(m, COUCH)
    for y in range(SEAT + 1, FLOOR_Y - 1):  # Seam between the seat cushions.
        c.dot(53, y, COUCH.line)
    for x in range(left + 8, right - 7):  # Piping along the front edge.
        c.dot(x, SEAT + 1, COUCH.shadow)
    # Arms: rolled tops over upright sides.
    for side in (-1, 1):
        outer = left if side < 0 else right
        inner = left + 10 if side < 0 else right - 10
        m, dm = mask((W, H))
        x_lo, x_hi = min(outer, inner), max(outer, inner)
        dm.rectangle((x_lo, 49, x_hi, FLOOR_Y - 1), fill=1)
        ellipse(dm, (x_lo + x_hi) / 2, 49, (x_hi - x_lo) / 2 + 1, 4)
        c.paint(m, COUCH)
        # The roll's curl on the front, a dark crescent.
        cx = (x_lo + x_hi) / 2
        for dx, dy in ((-2, 0), (-1, 1), (0, 1), (1, 1), (2, 0), (-3, -1), (3, -1)):
            c.dot(round(cx + dx), 50 + dy, COUCH.shadow)
    # Base and short wooden legs.
    c.outline(r.couch_outline)
    for x in (left + 2, left + 13, right - 13, right - 2):
        for y in (FLOOR_Y + 1, FLOOR_Y + 2):
            c.dot(x, y, r.legs)
            c.dot(x + 1, y, r.legs)
    img.alpha_composite(c.img)
    # A soft shadow on the floor under the couch.
    px = img.load()
    for x in range(left + 1, right):
        y = FLOOR_Y + 1
        if px[x, y][:3] == r.floor:
            px[x, y] = (*r.floor_line, 255)


def _cushion(img: Image.Image, r: LivingRoom) -> None:
    """A plump dusty blue cushion propped in the right corner, leaning on the arm."""
    c = Canvas(W, H)
    m, dm = mask((W, H))
    dm.rounded_rectangle((76, 44, 89, 58), radius=4, fill=1)
    for x, y in ((76, 44), (89, 44), (76, 58), (89, 58)):  # Corners poke out.
        dm.point([(x, y)], fill=1)
    c.paint(m, CUSHION)
    c.dot(82, 50, CUSHION.line)  # A tufted button.
    c.dot(83, 51, CUSHION.shadow)
    c.outline(CUSHION.line)
    img.alpha_composite(c.img)


def _throw(img: Image.Image, r: LivingRoom) -> None:
    """A knitted throw over the left arm: it lies over the roll, hangs down
    the front of the arm to a fringe, and one corner spills onto the seat.
    Drawn in its three colors only (outline included), so the device can
    swap them by weekday."""
    c = Canvas(W, H)
    m, dm = mask((W, H))
    poly(dm, [(7, 49), (9, 45), (14, 43), (19, 44), (22, 47), (24, 54), (31, 61), (27, 64), (21, 61),
              (20, 65), (8, 65), (7, 58)])
    c.paint(m, Ramp(base=r.throw, shadow=r.throw_shadow), shade=True)
    px = c.img.load()
    for y in (58, 61):  # Two woven stripes across the hanging end.
        for x in range(6, 22):
            if px[x, y][3]:
                px[x, y] = (*r.throw_edge, 255)
    for x, y0, y1 in ((11, 48, 65), (16, 46, 65)):  # Folds down the front.
        for y in range(y0, y1):
            if px[x, y][3] and px[x, y][:3] == r.throw:
                px[x, y] = (*r.throw_shadow, 255)
    # The edge: the shadow color all round.
    edge = []
    for y in range(H):
        for x in range(W):
            if not px[x, y][3] and any(0 <= x + dx < W and 0 <= y + dy < H and px[x + dx, y + dy][3]
                                       for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                edge.append((x, y))
    for x, y in edge:
        px[x, y] = (*r.throw_shadow, 255)
    for x in range(9, 21, 2):  # Tassels below the hem.
        for y in (67, 68):
            px[x, y] = (*r.throw_edge, 255)
    img.alpha_composite(c.img)


def living_room(r: LivingRoom) -> Image.Image:
    img = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    _wall(img, r)
    _window(img, r)
    _curtains(img, r)
    _couch(img, r)
    _cushion(img, r)
    _throw(img, r)
    return img
