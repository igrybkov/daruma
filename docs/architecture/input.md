# Input and bindings

> Incomplete. Moved from the old ARCHITECTURE.md. Add what you learn
> when a task needs more, and keep it under 300 lines.

Named inputs, bindings to actions, tap areas, and the focus ring on boards without touch.

## Bindings

Nothing in core or in the board package refers to pomodoro. Modules offer
named actions (`pomodoro.toggle`, `pomodoro.stop`, `voice.start`,
`menu.open`). The device yaml binds them to inputs:

```yaml
daruma:
  bindings:
    home.press: { action: pomodoro.toggle, when: idle }
    home.hold: { action: pomodoro.stop, when: idle }
  expose_bindings: true   # also a device setting in HA, starting from these
```

The build fails if a binding names an action that no included module
offers. With `expose_bindings: false`, the yaml choice is fixed.

With `expose_bindings: true`, each binding in the device yaml becomes a
select ("Home press") with "none", every action and `menu.open:<name>` for
every menu. It stores the chosen action by name, so builds with other
modules keep the choice. A stored choice wins over the yaml, so a binding
moved from the device yaml to a module default also drops its select.

Default bindings: a module may declare them. The device yaml wins over
every default, and any module's default wins over the core `daruma`
module's. Two other modules binding one trigger fails the build until the
device yaml picks one. Today's defaults:

- screen.tap and screen.swipe_up: menu.open, the `main` menu (menu);
- screen.hold and screen.long_hold: pomodoro.toggle and pomodoro.stop
  (pomodoro);
- home.press: the `pomodoro` menu (pomodoro). On the BOX-3, home is the
  red circle and also navigation `back`, so the default rests while a
  menu, app or prompt is open. A device that wants one press to start a
  focus binds `home.press: { action: pomodoro.toggle, when: idle }`;
- screen.stroke: daruma.pet;
- screen.swipe_left and screen.swipe_right: change the persona;
- screen.swipe_down: menu.quick, the quick panel (menu). A message bubble
  on screen closes instead. Without menu.yaml, the core's
  daruma.close_message.

A module default whose action belongs to a module the build lacks (the
pomodoro's menu without menu.yaml) is skipped, and the build log says so.

Filters see a gesture before any binding does. A ringing timer takes any
press, tap or hold and stops. A tap closes a message bubble.

## Tap areas: parts of the persona that lead somewhere

A part of the device's own screen can lead somewhere: the pomodoro plaque
opens the Pomodoro page, the temperature badge the Weather app, the next
event line the Calendar.

- **Areas.** The module that draws a part names it in `areas:` and tells
  the hub where it is now: `hub.add_tap_area("plaque", fn)`, where `fn`
  returns the rect, or an empty one while the part is hidden (under a
  message bubble, the badge switched off, no event on the line). Today:
  `badge` (core), `plaque` (pomodoro) and `next_event` (calendar).
- **Targets.** What a tap on an area does. A module offers defaults; the
  device yaml wins per area:

  ```yaml
  daruma:
    targets:
      plaque: { menu: pomodoro }        # or { app: stats }, { action: pomodoro.toggle }
      badge: none                       # a tap there is a tap on the persona again
  ```

  `app` opens one app on its own (the action `menu.app:<id>`; back closes
  it), `menu` opens a menu, `action` runs one.
- **The build checks:** an area no module draws, an app, menu or action
  that is not there, and apps or menus without menu.yaml. A module's
  default that can't work is skipped, and the build log says so, like
  default bindings. When two modules offer different defaults for one
  area, the first in the config wins and the log names both (copies of
  Calendar share `next_event` this way). `registry.resolve_targets`,
  tested in `test_registry.py`.
- **At run time.** A tap on the device's own screen (touch, nothing open)
  goes to the gesture filters first, then to the area under it, then to
  the bindings as before. So a tap elsewhere still opens the main menu.
  Boards without touch have no taps; their areas do nothing.
- **Tests.** The hub lists each visible area on every frame as a UiTree
  part with role `target` and the area's name, so a test taps it:
  `device.get_by_role("target", "plaque").tap()`.

## Inputs are named by the board

Boards differ: two buttons and a touch screen, one knob, five buttons and
no touch. So the board package names its inputs. Each one points at a
binary sensor, a touch zone or an encoder, and lists the gestures it
supports:

```yaml
daruma:
  inputs:
    - name: home                 # bindings use this name
      button: home_button        # a binary_sensor id
      gestures: [press, double, hold]
      hold_time: 1.5s
    - name: top
      button: left_top_button
      gestures: [press, double, hold]
    - name: screen
      touch: s3_box_touch        # a touchscreen id
      gestures: [tap, double, hold, long_hold, swipe, stroke]
  # How the menu, apps and prompts are driven. Touch covers them on the BOX-3.
  navigation:
    back: home.press
    close: home.hold
```

A binding then names an input and a gesture, such as `top.double` or
`screen.swipe_up`. The `screen.*` bindings act only on the device's own
screen. In the menu, apps and prompts, gestures keep their usual meaning.

The build checks:

- A binding to an input or gesture the board doesn't have fails the build.
  This applies only to bindings in the device yaml. A module's default
  binding for a missing input is skipped, and the build log says so.
- **Navigation must be complete.** Every board needs `back`. A board without
  touch also needs `next`, `prev` and `select`, from buttons or a knob
  (`knob.turn` counts as next and prev). Without them, the menu could never
  be left, so the build fails.
- A gesture used by both navigation and a binding fails the build unless
  the binding sets `when: idle`, like the red circle. It goes back in the
  menu, and runs the binding on the device's screen. The check is per
  gesture: `home.double` may be bound while `home.press` navigates.

The source key names the kind: `button:` for a binary sensor and `touch:`
for a touch screen. Touch has a second
hold, `long_hold`, so the screen can keep two holds: 1-2.5 s toggles and
3 s stops. In an open menu or app, screen gestures go to it. Screen
bindings rest there, so a hold on the dock doesn't reach the pomodoro.
A screen hold there fires `Input::HOLD` at hold time, still held. The
Controls app opens a light's or a fan's level with it.

**No delay unless it is needed.** What counts is what is bound in the
current context: idle, or navigation (`when: idle` bindings rest while a
menu, app or prompt is open).

- A press fires at once, on press-down, when that input has neither a
  double nor a hold bound.
- Only a bound double adds the wait for a second press (`double_window`).
- Only a bound hold makes a press fire on release instead of press-down.
  With hold and long hold both bound, HOLD fires on a release between the
  two times, and LONG_HOLD fires the moment it is reached. With only one
  bound, it fires the moment its time is reached.
- Touch follows the same rule. A tap can't fire before lift-off, since a
  swipe starts the same way, but it fires at lift-off unless a double tap
  is bound. Swipes and strokes are unaffected.

Timings are per input, with board defaults. Each is an ESPHome time period
with a checked range: `double_window` (300 ms, 100 ms-1 s), `hold_time`
(1 s, 300 ms-5 s) and `long_hold_time` (3 s, 1-9 s, longer than
`hold_time`). A touch held past `hold_time` is never a tap, even with no
hold bound (an open app). The recognizer is
plain C++ (`gesture.h`). A host test covers the timing
(`tests/test_input.cpp`).

The board keeps safety inputs out of the list, so they can't be bound: the
hardware mute switch, and holding the top button for 10 s to factory reset.
The top button's press fires on press-down, as long as nothing holds it.
So the reset hold also runs the top press action first, which is
voice.start today.

## Focus ring

In `src/esphome/components/daruma/focus.h`, host-tested.

- `device.uses_focus()` is true when the board's navigation has both
  `next` and `prev`. The BOX-3 with touch has neither, so it looks and
  works as before.
- The menu keeps a `FocusRing` for the dock and one for the board:
  - NEXT and PREV move it, with wrap-around, and the board follows it from
    page to page;
  - SELECT opens the focused item;
  - the ring is drawn in `theme.focus_color()`: a ring around the dock
    button, and a rounded frame with a gap around the tile.
- An open app gets NEXT, PREV and SELECT through `App::input`, with x and
  y set to -1. When it returns false for NEXT or PREV, the menu sends
  SWIPE_UP or SWIPE_DOWN instead, so a scrolling app needs no extra code.
  `AppView::focus` tells the app to draw its focus.
- Tasks moves a focus over its rows, keeps it in view, and checks off the
  focused row with SELECT. SELECT retries after a failure.
- Calendar's agenda moves a focus over its rows with NEXT and PREV, and
  SELECT opens the focused row's day. In the day view, NEXT and PREV
  change the day; SELECT pages through the events, wraps to the top, or
  retries after a failure.
- A theme can set `focus:`. Without it, the accent is used.
- The build: a board without touch that includes the menu must bind
  `menu.open` to something. Otherwise the build fails, since the menu's
  own default is a tap.
- `board_box3_buttons.yaml` drives the BOX-3 by its two buttons:
  - next is `top.press` and prev is `top.double`;
  - select is `home.press`, back is `home.double` and close is
    `home.hold`.
- The BOX-3 hardware now lives in `board_box3_hardware.yaml`, which both
  board files include.

Prompts use the layout and the focus ring too (see [prompts.md](prompts.md)).
