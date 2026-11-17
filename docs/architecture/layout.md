# Layout and screens

> Incomplete. Moved from the old ARCHITECTURE.md. Add what you learn
> when a task needs more, and keep it under 300 lines.

How the screen splits into regions, how personas fill other screen sizes, and the display profile for still, gray and mono screens.

## Regions

**Layout** (`components/daruma/layout.h`). Plain C++, host-tested.

- The hub computes it in `setup()`, before any module, from the display
  the board names (`daruma: display: s3_box_lcd`). `render()` checks
  the size again on every frame.
- `device.layout()` gives:
  - `width`, `height`, `size_class` (standard, wide, square, tall);
  - `unit` = min(w, h) / 240, and `px(v)`, which turns a 320x240 design
    size into screen pixels;
  - regions as `Rect`: `stage`, `dock`, `header`, `back` (the back
    arrow's tap zone), `content` (the app area) and `board` (the tiles);
  - `grid_cols` x `grid_rows`, `gap`, `tile(i)`, `tile_at(x, y)` and
    `dots_y`.
- Size classes by aspect: wide from 1.6, standard from 1.2, square from
  0.84, tall below. The grid is 2x2, 3x2 on wide screens, 2x3 on tall
  ones.
- `Rect` has `inset`, `contains`, `cell(i, cols, rows, gap)` and
  `cell_at`. A prompt card starts as `layout.content.inset(px(8))`, and
  its 2x2 answers are cells of a grid in it (see [prompts.md](prompts.md)).
- Regions sit on the screen's edges and their sizes scale by `unit`. So
  320x240 gives back every old number: the dock at y 128, the header 40
  high, tiles of 140x82 at x 16/164 and y 48/138, the app area at
  (14, 42, 292, 184), and the badge, bubbles and captions where they were.
  `test_layout.cpp` checks that table.
- `AppView` carries `layout` and `px()`. Calendar, the Pomodoro page and the pomodoro
  layers scale their sizes with it. Tasks already sized itself from the
  app area.
- Font sizes are board substitutions: `font_size_text`, `font_size_small`,
  `font_size_badge`, `font_size_icon` and `font_size_timer`.
- The menu adapts to narrow screens:
  - tiles narrower than 130 design pixels put the icon above the name;
  - names and statuses are cut to fit (`fit_text`);
  - dock buttons shrink so they never touch.

## Personas in the stage

- **Pixel art** takes the largest whole-number scale that fits the stage.
  `scale:` now only caps it.
- A layered room fills the rest from **edge strips** that the build takes
  from the room itself (`components/daruma_sprites/extend.py`, plain
  Python, host-tested). The strips work like this:
  - For each edge, every line across it gets tested for a repeat period.
    The period most lines share wins: the corgi's planks repeat every
    21 px. Rows that repeat with a shorter period that divides it (floor
    rows) keep their own pattern.
  - Rows that don't repeat (the window frame, the shelf) borrow the nearest
    row that does and that starts with the same pixel. So the wall goes on
    plain, and no plank changes color.
  - The left and right strips are as tall as the room, and the top strip is
    as wide as it. The bottom gets no strip: the rug and the furniture
    stand there. The room sits on the bottom of the stage, centered, and
    extra height goes above it onto the wall.
- On the device, `SpritePersona::view_()` works out how many whole scene
  pixels each side needs. `compose_under_()` maps each pixel of that view
  to the room, a strip, or a top-strip row (also for the corners). The
  recolor, the window, the plant and the persona are shifted by the
  extension. `present_()` clips to the stage.
- A margin narrower than one scene pixel stays in the background color.
  That keeps 320x240 the same as before.
- The extension costs the strips in flash, under 1 KB per persona, and larger
  frame buffers in PSRAM: 160x91 on 480x272.

- **The bottom band.** One fixed layout, with or without the info line:
  - The info line (`layout.info`) is a strip 18 high, 6 up from the
    bottom, between 6 px side margins (`layout.edge`). 320x240:
    (6, 216, 308, 18).
  - The two bottom corners stand on one line 4 above it
    (`corner_bottom`, 212 on 320x240), each 6 from its side.
    `corner_left(w, h)` holds the tomato plaque, `badge()` (42 across, in
    `corner_right`) the temperature badge.
  - Nothing moves when an event comes or goes, or when the line is off.
  - `layout.upper` is the stage above that line. The eyes persona centers
    there, so its eyes stay clear of the corners at rest.
  - A persona's theme sets `info_line: bottom`, `top` (`info_top`, right of
    the voice timer) or `off`. A module that draws there calls
    `set_info_line_used(true)`, and `Device::info_line()` then gives the
    rect for the current persona.

- **Picture personas** are drawn 1:1, centered, on the art's top-left color,
  unless `background:` is set. A screen smaller than the art crops it.

## Display profile

A real e-ink panel still needs a driver package and a device test.

The board declares the profile under `daruma:`:

```yaml
daruma:
  display: s3_box_lcd
  display_profile:
    colors: full           # full, gray4 or mono
    animate: true
    min_frame: 100ms       # 10 ms to 60 s
    partial_refresh: true
    full_refresh_every: 0  # 0 = never; needs partial_refresh
```

The build fails on `animate: true` with `min_frame` of 1 s or more. It also
fails on `full_refresh_every` without `partial_refresh`
(`registry.check_profile`).

## Still screens and slow screens

- `animate: false` changes the hub, not the personas:
  - `draw_idle()` and `draw_persona()` ask the persona for `draw_still()`;
  - `needs_redraw()` asks only whether the state changed;
  - `blink`, `wink` and `look_around` do nothing.
  So the sprite cycles, the window's rain, the eye moods and the
  celebrate winks all stop.
- `profile().slow()` is true when `min_frame` is 1 s or more. The pomodoro
  then shows "12m" and the voice timer "12 min". Both redraw only when a
  minute turns over.

## Gray and mono

- `Theme::for_mode()` derives the theme from luminance: mono is a
  threshold at 128, and gray4 rounds to 0, 85, 170 or 255. The hub swaps
  each persona's theme for it at setup.
- Readable pairs are kept apart: ink on the panel, titles on the frame,
  dock text on the dock, and the focus on the frame. Where both sides come
  out the same gray, the foreground flips to black or white.
- A theme's `mono:` colors override the derived ones.
- `theme.fit(c)` and `theme.on(bg, fg)` let the menu and the badge adapt
  their own colors.
- Module colors from `theme.color()` come out in grays too.
- At build time, `sprite.py` reduces every picture to the screen's grays
  by the same rule (`reduce_colors`). The edge strips are reduced as well.
  On the device, `SpritePersona` reduces the composed room the same way,
  which covers the painted sky. The persona's frames come reduced from
  the build, patches included.
- The weekday rug colors are left out in gray, so the rug keeps the room's
  own color.
- Don't dither. A 4x4 ordered dither turned the corgi's
  mid-tone wall and fur into noise at 106x80. A plain threshold reads as
  a clear silhouette.

## Proof without hardware

- `examples/` holds three build checks. Each one compiles next to
  `box3.yaml`:
  - `variant_wide.yaml`: 480x272, with larger fonts;
  - `variant_square.yaml`: 240x240;
  - `variant_mono.yaml`: two buttons, mono, stills, a 5 s `min_frame`,
    and a full refresh every 20 frames.
  The wide and square checks are the BOX-3 with the display's
  `dimensions` overridden. They compile and pass the registry checks, but
  that panel can't show them.
- `tests/preview_screens.py` draws the idle corgi, the dock, the app
  board and Tasks at 320x240, 480x272, 240x240 and in mono. It takes its
  regions from `test_layout --json`, which runs `layout.h` itself.
