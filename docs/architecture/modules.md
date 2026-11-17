# Modules

> Incomplete. Moved from the old ARCHITECTURE.md. Add what you learn
> when a task needs more, and keep it under 300 lines.

How a module plugs into the core: what it declares, what it may add, and how an app runs twice.

- A module is a C++ `Module` with one `setup(Device &)`. It registers apps,
  menu items, layers, input handlers, states and prompt layouts there. The
  package yaml only wires HA entities and options.
- Apps get `on_open` and `on_close`, so they fetch data only while shown.
  The Calendar and Tasks apps are built this way.
- **On and off.** An app is in the build when its package is included. At
  run time, core adds one switch per app ("App: Calendar"). A switched-off
  app leaves the board and stops fetching.
- The board order comes from one `apps:` list in the device yaml, not
  from the package order.

## Declaring a module

- A module is declared where the build can see it. A package adds a
  `daruma: modules:` entry with `name`, `states`, `actions` (each a
  list of ESPHome steps), `apps`, `progress`, `theme: {colors, words}`,
  `bindings` (defaults) and `setup:`, a lambda over `hub` (the Device). A
  C++ component can declare the same as `DARUMA_MODULE` in its Python file
  (the menu does). `Device::setup()` runs each module's `setup()` before
  the on_boot automations and the first draw. Final validation reads every
  declaration.
- Core's own actions belong to the module `daruma`: daruma.pet,
  daruma.next_persona, daruma.previous_persona and daruma.close_message. The module
  `voice` offers voice.start.
- An app missing from `apps:` goes last on the board, and the build log
  says so. Every app a `daruma: modules:` entry declares gets a
  switch. An app that only a C++ `DARUMA_MODULE` declares gets one only if
  it is in `apps:`. A name in `apps:` that no module offers fails the
  build.
- An open app gets every swipe, so Calendar pages days with left and
  right. Board paging lives one level up, on the board, so the two never
  meet.
- A switched-off app gets `on_enable(false)` and stops fetching. Calendar
  fetches only while open or for its status line. Tasks fetches for its
  tile.
- The text helpers that Calendar and Tasks shared (`fit_text`,
  `drawable_text`, `text_width`) now live in `components/daruma/text.h`.
- **Copies of an app.** `app_tasks.yaml` and `app_calendar.yaml` take
  `!include` vars (`app_id`, `app_name`, and `source`/`entity` or
  `calendars`), with defaults in the package's top-level `defaults:`
  block. Without vars they build the single app as before.
  - Every id, script, setting and the module name come from `app_id`. The
    module name is also the theme key prefix (`calendar_work.today`), and
    a theme renames or re-icons a copy by its app id.
  - A module's `apps:` entry may be `{id, name}`; the switch then reads
    "App: <name>" ("App: Family").
  - The components are `MULTI_CONF`, written as lists in the packages, so
    two includes add two entries instead of merging into one.
  - States shared by every copy (`task_done`, `tasks_done`) are declared
    once, by `daruma_tasks`'s `DARUMA_MODULE`.
  - The default copies keep their entity names: "Tasks source", "Tasks
    entity", "Calendars". A second calendar copy gets "Work calendars" and
    "Work days ahead".
  - Two copies with one `app_id` fail the build. ESPHome reports the
    clashing ids first; the registry also fails on two modules with one
    name or one app id.
  - `examples/variant_apps.yaml` builds two of each.
- **Back into an app.** `App::back` runs before the menu closes an open
  app (header arrow or the board's back input). Calendar uses it to leave
  its day view.

## What a module may contribute

Pomodoro is the model: it already has its own screens and settings, and they
look right on every persona. Every module, pomodoro included, may
contribute:

- **States**, each with a fallback: pomodoro adds the `focus` and `break`
  activities and the `focus_done` and `goal` reactions.
- **Signal sources**: pomodoro feeds `progress` from today's goal, and Tasks
  can feed it from tasks done.
- **Screens and layers**: the timer plaque, the dock buttons, the Pomodoro
  page.
- **Settings**: device settings in HA, such as the focus length and the
  daily goal.
- **Looks per persona**: theme keys under the module's name, such as
  `pomodoro.ring` or `pomodoro.done_word`. A persona may set them, and a
  default covers any it leaves out. The build checks the keys the same way
  as states.

Theme keys as built: a module declares `theme: colors:` and `words:` with
defaults. A persona's theme sets `colors: {pomodoro.focus: ...}` or
`words: {calendar.today: ...}`. C++ reads `theme.color("pomodoro.focus")`.
