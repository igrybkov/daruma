# Menus

> Incomplete. Moved from the old ARCHITECTURE.md. Add what you learn
> when a task needs more, and keep it under 300 lines.

Named menus of dock buttons, what an item can be, and the rules that hide buttons.

A menu is a named list of dock buttons. Modules offer default menus; the
device yaml's `menus:` replaces one by name or adds more:

```yaml
daruma:
  menus:
    main: [tasks, calendar]                    # a tap on the persona opens main
    quick: [pomodoro.skip, pomodoro.stop, stats, more]
  bindings:
    top.double: { action: menu.open, menu: quick }
```

An item is one of these. The build checks each and names the choices when
one is wrong:

| Item | Button |
|---|---|
| an app id (`tasks`, `tasks_family`) | opens the app; hidden while its switch is off |
| a module name (`pomodoro`) | the module's buttons for the moment: Focus, or Pause and Stop |
| an action (`pomodoro.break`) | runs it; label, icon and color from the module's `buttons:` |
| another menu's name | opens that menu; back returns |
| `more` | the app board |
| `{ label, icon, event }` | fires the HA event `esphome.daruma_menu` with `event` in its data |

- A name is looked up as an app id first, then a module, then a menu. So
  the menu `pomodoro` can list the module `pomodoro`.
- A module that adds buttons declares `menu: true` and calls
  `add_menu_provider()` in its setup. The hub tags each provider with the
  module whose setup added it.
- A module gives its actions a button look under `buttons:`, `{label,
  icon, color}`. The color is a module theme key (`pomodoro.break`) or
  hex. An action without a look can be bound but not listed.
- Two modules offering one menu name fail the build, unless the device
  yaml defines it.
- `main` ends with More unless it lists `more`, so the app board stays in
  reach. Without `main` in any yaml, it is every `menu: true` module that
  has no menu of its own, then Tasks and Calendar when the build has them.
  So pomodoro stays out of `main`: its buttons are in its own menu, one
  press away on the board's main button.
- The pomodoro offers `pomodoro: [pomodoro]` and opens it with home.press.
- **No buttons that contradict the moment.** A module may give an action's
  button a hook (`Device::set_action_button(name, fn)`). The hub calls it
  for that action in every menu that lists it. The hook can change the
  label or icon, give the button a submenu, or hide it (return false).
  Bindings are not affected. The pomodoro's rules are plain C++
  (`pomodoro_rules.h`, host-tested in `tests/test_pomodoro_rules.cpp`),
  and the module's own buttons, the listed actions and the Pomodoro page
  all ask them:

  | Now | Buttons |
  |---|---|
  | focus, running or paused | Pause or Resume, Stop, Skip |
  | break | Resume (when paused), Focus (ends the break), End |
  | idle, in the break window | Focus, Custom, Break, Long break |
  | idle otherwise | Focus, Custom |

  The break window: the last focus ended less than the break it earned
  ago (long after every Nth pomodoro, else short). A focus starts its
  break by itself, so the window shows after End or Stop on that break.
  The time is kept in `millis()`, cleared at midnight and lost on a
  reboot, which only hides the Break buttons.
- Focus (`pomodoro.start`) starts the "Pomodoro focus" length at once.
  Custom (`pomodoro.custom`) shows the lengths: in a menu as its submenu,
  bound to an input as the Pomodoro page's row. `pomodoro.long_break` is
  new.
- The dock lays out five buttons at most. A longer menu shows four and
  Next (`text_menu_next`), which pages to the rest. A label may use the
  room its neighbours' shorter labels leave, so "Calendar" fits between
  "Tasks" and "More" on five buttons.
- Back: an app opened from a dock button returns to that dock, and a
  nested menu to the one that opened it.
- The menu title is the pomodoro's "N of goal today" on every menu.
- **The quick panel** (`menu.quick`, on a swipe down from the top edge) is a menu level
  that hangs from the top over the persona. It shows `Hub::settings()`
  as round tiles, no named menu. A tap flips a tile and keeps the panel
  open. The grid, the label room and the label wrap are plain C++
  (`quick_grid.h`, host-tested in `tests/test_quick_grid.cpp`). Two rows
  at most; more tiles page sideways. It uses the dock's colors and
  timeout.
- `menu.open` with a menu runs as `menu.open:<name>`, an action with an
  argument (`Device::add_arg_action`). HA opens one with
  `esphome.<device>_menu_open(name)`.
- The build checks: unknown items, an item listed twice, a menu that lists
  itself, an event button without label, icon or event, `buttons:` for an
  action of another module, `menu:` on any action but menu.open, a
  binding to a menu that does not exist, and `menus:` without menu.yaml.
