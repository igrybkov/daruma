# Rendering

> Incomplete. Moved from the old ARCHITECTURE.md. Add what you learn
> when a task needs more, and keep it under 300 lines.

How a frame reaches the screen with as few pixels as possible: deltas, patches, layer areas and the frame scheduler.

## Deltas: send only what changed

- **The eyes persona** centers on the stage and scales every size and offset
  by `unit`. Each mood renderer takes `setGeometry(cx, cy, unit)`.
  Blinks, glances, winks and moving moods repaint only the union of the
  old and new eye boxes (`draw_delta`), clipped, so the screen sends that
  box instead of the whole frame. Each mood has a box in design pixels.
  Loved draws hearts and always redraws in full.
- **Layers over a delta.** A persona whose `draw_delta()` repaints a box with
  its background reports it in `delta_area()`. The hub then draws the
  layers again, clipped to that box, so a timer or badge under it stays.
  Pixel-art personas report the box they sent too.
- **A layer's own area.** `request_area(rect)` says a layer changed only
  inside `rect` and paints all of it. The next idle frame draws the layers
  clipped to it and leaves the persona alone, on still screens too. A persona
  can't repaint just a part of itself without spoiling its next delta (it
  keeps what it last sent), so a layer that shrinks or goes away calls
  `request_redraw()` instead.

## Animation frames as patches

In `sprite_codec.py` and `frame_chain.h`, host-tested by
`tests/test_frames.py`.

- Most animation frames differ from the one before by a few pixels. So a
  layered pixel persona stores its frames as one set: each frame is a
  keyframe (a whole picture), or a patch on an earlier frame. A patch is a
  small sprite of the box where the two differ. In it, one code means
  "keep the frame below", and the see-through index means the persona
  no longer covers that pixel.
- Each frame has its own palette, so a patch with three colors uses two
  bits per run code. Same palettes are stored once.
- The encoder picks each frame's base at build time:
  - an animation's first frame comes first, and stays at most 2 patches
    from a keyframe, since it is shown out of order;
  - any other frame prefers the frame before it, which is what the screen
    already shows; else the cheapest of the animation's first frame and
    the three closest frames;
  - no frame is more than 4 patches from its keyframe;
  - a frame whose best patch costs more than a whole picture is a keyframe.
  - Frames with the same pixels are one frame, across animations and the
    daruma's eye states.
- The art scripts are unchanged. They still draw whole frames, and the
  build checks that every patch chain gives back exactly that picture.
- On the device, `FrameCanvas` holds the persona's pixels and which
  frame they are. To show a frame, it applies the patches from the frame
  it holds, when that frame is on the chain. Otherwise it starts from the
  keyframe. It returns the box that changed.
- `SpritePersona` keeps the room behind the persona in a buffer
  (`under_`), composed again only when the window step, sky, plant stage,
  wilting or rug day changes. When only the persona moved,
  `draw_delta()` sends just the patch box: the canvas over the room,
  where it differs from the screen. A blink, a wink or a new animation
  rebuilds the canvas from its keyframe and sends what differs in it.
- Flat personas (no backdrop) and picture personas keep whole pictures.
- Sizes for the frames, at full color (gray4, mono):

  | Persona        | Frames | Whole pictures | Keyframes and patches |
  |-------------|--------|----------------|-----------------------|
  | Pixel corgi | 41     | 37.9 KB        | 13.0 KB (9.3, 7.8)    |
  | The Boss    | 31     | 37.4 KB        | 11.0 KB (7.8, 5.8)    |
  | Daruma, 3 eye states | 119 | 79.8 KB  | 16.9 KB (13.7, 11.1)  |

- The canvas and the room buffer cost RAM, both in PSRAM: 3 bytes per
  persona pixel, and one more view-sized frame buffer.

## The frame scheduler

`FrameScheduler` in `profile.h`, host-tested.

- `Device::loop()` draws when something asked for a frame, no sooner than
  `min_frame` after the last one. It replaces core's 100 ms polling
  interval. On the BOX-3, `min_frame` is 100 ms, so the pace is the same.
- `request_frame()` draws soon, even in a voice phase. The `draw_display`
  script calls it, so voice phases still get one still frame each.
- `request_redraw()` and the persona's own motion are drawn only while core's
  frame gate allows: no voice phase up, and not still booting.
- Requests inside one `min_frame` make a single frame.
- `full_frame()` is true for the first frame, for every frame without
  partial refresh, and for every `full_refresh_every`-th frame. On those,
  `draw_idle_delta()` gives way to a full draw.
- An e-ink driver with its own full-update setting
  (`full_update_every`) should get the same number.
