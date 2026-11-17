# Data apps

> Incomplete. Moved from the old ARCHITECTURE.md. Add what you learn
> when a task needs more, and keep it under 300 lines.

Apps that show Home Assistant data: Tasks, Weather, Calendar and the next event line. Read [modules.md](modules.md) first.

- **Tasks sources.** "To-do list" (`todo.get_items`, check-off with
  `todo.update_item`) and "Script": an HA script that returns
  `{open, total, tasks: [{id, title, done, flagged, overdue, due_today}]}`.
  The blueprint `blueprints/script/task_list.yaml` ("Daruma: task
  list from a sensor") makes one from a sensor attribute, with field names
  as inputs. It replaced a `recorder.get_statistics` call that only
  carried a response template. The select keeps its option indexes: the
  old "Task feed" (0) is now "Script". The entity text's `max_length`
  went from 100 to 120, so a stored `sensor.*` entity is dropped for the
  build's default.

- **Weather** (`app_weather.yaml`, component `daruma_weather`). Today's
  report from one HA weather entity, the setting "Weather entity"
  (`weather.home` by default):
  - now: the condition's icon, the temperature big, its name; today's
    high and low; the chance of rain and the wind; a strip of the next
    hours (five on 320x240, eight on wide screens);
  - two `weather.get_forecasts` calls, hourly then daily, through the
    hub's gate; now, the units and the wind come from the entity's state
    in the hourly template. Only while open: on open, then every 30
    minutes. A service without hourly forecasts still shows the rest;
  - units from HA: the temperature as "72°", the wind in its own unit;
  - "Can't reach Home Assistant" without HA, "Can't load the weather"
    when both calls fail; a tap tries again;
  - the conditions' icons and words are plain C++ (`weather.h`, tested in
    `tests/test_weather.cpp`); menu.yaml's icon font lists the glyphs;
  - a tap on the temperature badge opens it.
- **Calendar agenda.** The app opens on an agenda; a day opens the old
  day view.
  - One request covers today and "Days ahead" days (a number setting, 1
    to 31, 14 by default). HA sends at most `agenda_max` (25) events,
    sorted by start, titles cut to `title_chars`, no descriptions. All-day
    events carry HA's local midnights as epochs.
  - Grouping and headings are plain C++ in `src/esphome/components/daruma_calendar/agenda.h`,
    host-tested (`tests/test_agenda.cpp`). An event goes under the day it
    starts; one still running from before today goes under Today. All-day
    events are placed by their middle, so a clock a few hours off HA's
    still finds the right day.
  - The day view takes its day from the agenda when the agenda holds all
    of it: in range, and before the last event's start when HA trimmed
    the list. Otherwise it fetches that day alone (at most 12 events).
  - The tile reads today from the agenda. It refreshes on open (when over
    a minute old), every 15 minutes, at midnight, and when "Days ahead"
    changes.
  - Words are theme words under the app id, with defaults from the
    package's `text_*` values, weekday and month names included.
  - `tests/preview_agenda.py` draws the agenda in the wood and outline
    themes at 320x240 and 480x272.
- **Next event line.** A short line on the device's own screen, at the
  hub's info line: "14:00 Dentist", or "Now: Standup · until 10:30".
  - "Next event within" (hours, 0 = off, 3 by default) is a number
    setting per copy. The package var `next_event` picks the copies that
    show it: `auto` is the first copy only.
  - The pick is plain C++ (`src/esphome/components/daruma_calendar/next_event.h`, tested in
    `test_agenda.cpp`). A running event wins; of several, the one that
    started last. Else the earliest that starts within the hours and
    before midnight: the line is about today. All-day events never show.
    It works on the agenda as loaded, so the minutes after midnight need
    no fetch.
  - Several copies share one line (`next_line.cpp`): running first, then
    the soonest. The words come from the copy the event belongs to.
  - It looks again once a minute and when an agenda arrives. A new text
    redraws only its pill (`request_area`). The pill never gets narrower
    in such a redraw, so it covers the old one. The line going away is a
    full frame. Nothing logs a title.
  - Pill in the dock colors of the persona's theme, text in the menu's small
    font. Templates `line_next`, `line_now` and `line_now_open` are theme
    words with `{start}`, `{end}` and `{title}`; only the title is cut.
  - `tests/preview_line.py` draws it on every persona at 320x240, and the
    corgi at 480x272, 240x240 and mono: idle, a focus, a break and a
    pause, with the plaque and the badge. `--before` draws the old
    layout for comparison.
