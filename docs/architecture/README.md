# Architecture by kind of work

Start here before you change the code. Find your task in the tables
below and read that topic first. Follow its links when the task reaches
further. You don't need to read the whole folder.

Each topic covers one kind of work, not one layer. A tail for the corgi
and a new cat share a topic. A music remote and an NFC reader share
another.

## The layers

```
 device yaml   examples/box3.yaml: name, board, personas, apps, HA entities
 modules       pomodoro, calendar, tasks, weather, prompts, menus, ...
 personas      daruma, pixel corgi, Jack Russell, tabby cat, The Boss, eyes, images
 core          state, behaviors, render loop, layout, input, sounds, themes
 board         ESP32-S3-BOX-3 or the desktop: display, touch, buttons, audio
```

- The **core** owns the state and picks what is on screen. It never
  names a persona or a module.
- A **persona** answers to states and reads shared signals. It never
  reads a module directly.
- A **module** adds states, signal sources, screens, settings and theme
  keys. Including its package turns it on.
- `src/esphome/components/daruma/registry.py` checks all of it at build time.

## Find your topic

Every topic is incomplete. Each one holds what the old ARCHITECTURE.md
knew. Topics marked TBD have no file yet; the name in brackets is the
file to create.

### Looks

| You want to | Topic |
|---|---|
| Draw a new character, fix a pose, add a tail, keep limbs attached, build an animal on a shared body | [Characters](characters.md) |
| Change what is around the character: a room, a window, a plant, a rug, a forest | Scenes and props: TBD (`scenes.md`). For now: [customize.md: Rooms](../customize.md#rooms) |
| Understand how a frame reaches the screen: deltas, patches, memory, flash size, speed | [Rendering](rendering.md) |
| Make a look follow data: progress, weather, time of day, a goal | [Looks that follow the world](signals.md) |
| Add a mood, an activity or a reaction, or change what wins on screen | [States and reactions](states.md) |
| Give a persona quirks it plays now and then: a paw lick, a line in a bubble, a trip away | [Random events](random-events.md) |
| Change colors, words or a look per persona, or translate the device | [Themes and words](themes.md) |
| Show text in another language, a new font, long or wrapped text | Text and fonts: TBD (`text.md`) |

### Apps and screens

| You want to | Topic |
|---|---|
| Write a module: what it declares, what it may add, two copies of one app | [Modules](modules.md) |
| Show Home Assistant data: calendar, tasks, game stats, stocks, feed titles | [Data apps](data-apps.md) |
| Show long text the person scrolls or pages through: an article, a book | Reading apps: TBD (`reading-apps.md`) |
| Add something that keeps its own state on the device, like pomodoro | [Device-side modules](device-modules.md) |
| Place things on the screen: regions, the bottom band, other screen sizes, gray, mono and e-ink | [Layout and screens](layout.md) |
| Add a menu, a page, or more items than fit on one screen | [Menus](menus.md) |

### Input and output

| You want to | Topic |
|---|---|
| Bind a button, a gesture, a double or long press, or a tap on part of the picture | [Input and bindings](input.md) |
| Make the device control something else: a music player, a tag scan, keys on a computer | The device as a controller: TBD (`controller.md`) |
| Add or change a sound, or mute sounds | [Sounds](sounds.md) |
| Change the voice assistant, the wake word or the microphone | Voice: TBD (`voice.md`) |

### Home Assistant

| You want to | Topic |
|---|---|
| Send events to HA, call an HA action, or get a reply from one | [Talking to Home Assistant](home-assistant.md) |
| Let HA show a card, an alert or a question, and get the answer | [Prompts](prompts.md) |
| Make something a setting in HA | [Settings in Home Assistant](settings.md) |
| Read HA's own configuration: language, time zone, first day of the week | HA configuration: TBD (`ha-config.md`) |
| Share an automation that uses the device | [blueprints/README.md](../../blueprints/README.md) |

### The device

| You want to | Topic |
|---|---|
| Keep state across a reboot: a running timer, today's count, the chosen persona | [Preserving state](state-preservation.md) |
| Support a new board, a USB device or a sensor | Hardware: TBD (`hardware.md`). For now: [Input and bindings](input.md#inputs-are-named-by-the-board) |
| Install, flash, or find out why a device is offline | Install and debug: TBD (`install.md`). For now: [install.md](../install.md) |

### The project

| You want to | Topic |
|---|---|
| Test a change, write a screen test, record a GIF, accept golden pictures | Tests and demos: TBD (`testing.md`). For now: [testing.md](../testing.md) |
| Change the build, CI, lint, the Python setup or releases | Build and CI: TBD (`build.md`). For now: [CONTRIBUTING.md](../../CONTRIBUTING.md) |
| Ship parts from another repository, public or private | [Packages](packages.md) |

A task can touch two topics. A new app with a mood of its own touches
"Data apps" and "States and reactions". Read both.

## How this folder grows

Topics grow when a real task needs more, not before.

1. Do the task. Note each place where you searched, guessed wrong or had
   to ask.
2. Add those notes to the topic. For a TBD topic, create the file with
   the name in the table, from the template below, and link it.
3. Keep each fact in one place. If another topic or doc says the same,
   link to it instead.

Rules for every topic file:

- **One kind of work.** Follow the task through every layer it touches.
  A file named after a layer is fine only if it covers the whole task,
  not that layer's internals.
- **At most 300 lines.** If it grows past that, split it into two kinds
  of work. Don't trim the useful parts.
- **As built only.** No history, no plans, no "before".
- **Few names.** Name a file or a symbol only when it is the place to
  start or the example to copy. Grep finds the rest.
- **Links that work.** Every path in the file must exist.
  `tests/test_docs.py` checks the links, the paths and the line count.

## How to write a topic

The reader is in the middle of a task. They want the next fact, not a
tour. Write for that reader.

- **Short sentences.** One idea per sentence. Plain verbs: "the hub
  picks", not "selection is performed by the hub".
- **Say what is true now.** Not what it used to be, and not what it
  will be.
- **Lead with the rule, then the reason.** One reason is enough. Skip it
  if the rule is obvious.
- **Name the trap.** If something compiles, passes the tests and is
  still wrong, it goes under Traps. Say what goes wrong and how to see it.
- **Show, don't list.** One small example beats five bullets of options.
  Link to the full option list in a use guide such as
  [customize.md](../customize.md) instead of copying it.
- **Link, don't repeat.** If a fact is in another topic, link to the
  heading.
- **No filler.** No "simply", "just", "note that", "it is important".
  No em dashes. No summary at the end.

A paragraph that is hard to act on:

> The frame scheduling subsystem has been designed with voice
> interactions in mind. It is important to note that there are two
> mechanisms for requesting frames, and care should generally be taken
> to select the appropriate one depending on the use case.

The same facts, easy to act on:

> `request_redraw()` waits while a voice phase is up. `request_frame()`
> draws anyway.
>
> Trap: motion that calls `request_frame()` keeps drawing while the voice
> assistant talks. It looks fine on the desktop. Use `request_redraw()`
> for motion.

## Topic template

```markdown
# <Kind of work>

What this kind of work covers, in two sentences. Two or three example
tasks.

## How it works
The mechanism: where the data comes from, which layer owns what, how it
reaches the screen. A small diagram if it helps.

## Conventions
The rules that hold for every task of this kind.

## Traps
What compiles and passes the tests but is still wrong.

## Example to copy
One part of the code that does this well, and why it is the one.

## Check it
The command that shows the result, and what to look at.
```
