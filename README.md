# Daruma
[![CI](https://github.com/igrybkov/daruma/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/igrybkov/daruma/actions/workflows/ci.yml)

Daruma turns a small screen on your desk into a companion for your home.
It is a framework built on [ESPHome](https://esphome.io) and
[Home Assistant](https://www.home-assistant.io).

You choose who lives on the screen. A daruma doll, a pixel pet, a pair of
eyes, or your own pictures. You choose the apps: focus
sessions, tasks, calendar, weather, a voice assistant. Home Assistant
sends the device messages and questions, and gets your answers back.

It is ready for the [ESP32-S3-BOX-3](https://github.com/espressif/esp-box),
but is designed to run on any screen. Wide, square and black-and-white
screens build on every change. A new screen needs a short board file. A
desktop build runs Daruma in a window on your computer.

Where to go next:

- **Put it on your desk**: [Install](#install).
- **Drive it from your home**: [Home Assistant talks to it](#home-assistant-talks-to-it).
- **Make it your own**: [Make it yours](#make-it-yours) and
  [docs/customize.md](docs/customize.md).

| | | |
|:-:|:-:|:-:|
| [![Daruma](docs/demos/daruma-highlight.gif)](docs/gallery.md#daruma) | [![Pixel corgi](docs/demos/pixel-corgi-highlight.gif)](docs/gallery.md#pixel-corgi) | [![Jack Russell](docs/demos/jack-russell-highlight.gif)](docs/gallery.md#jack-russell) |
| **Daruma** | **Pixel corgi** | **Jack Russell** |
| [![Tabby cat](docs/demos/tabby-cat-highlight.gif)](docs/gallery.md#tabby-cat) | [![The Boss](docs/demos/the-boss-highlight.gif)](docs/gallery.md#the-boss) | [![Eyes](docs/demos/eyes-highlight.gif)](docs/gallery.md#eyes) |
| **Tabby cat** | **The Boss** | **Eyes** |
|  | [![Flat corgi](docs/demos/flat-corgi-highlight.gif)](docs/gallery.md#flat-corgi) |  |
|  | **Flat corgi** (pictures) |  |

Every persona shows every mood, reaction and activity the device knows:
the voice assistant, a focus block, the menu and apps in its own theme, a
message and a doorbell card. See them all in the
[gallery](docs/gallery.md).

## What comes with it

Each part is a package. Include it to turn it on. Leave it out to drop it.

- **Pomodoro**: one tap starts a focus block. A daily goal, breaks,
  tomatoes for the day, this week's bars and a streak.
- **Tasks**: today's tasks from a Home Assistant to-do list, or from a
  script that returns any task list. Tap one to check it off.
- **Calendar**: the Agenda of your coming events, and the next event on
  the persona's screen.
- **Weather**: now, today's high and low, rain, wind and the next hours.
- **Prompts**: Home Assistant puts a card on the screen and gets the
  answer back: a doorbell with Unlock and Talk, a quiz with a countdown,
  a yes/no question.
- **Voice assistant**: a wake word, or the top button, and Home
  Assistant's Assist.
- **Sounds**: chimes on the device's speaker for focus, breaks, messages
  and alerts. Each persona can bring its own, written as short synth
  tunes. The "Sounds" switch in Home Assistant mutes them.
- **Menus** you lay out yourself: apps, device actions, other menus, and
  buttons that fire Home Assistant events.

| | | |
|:-:|:-:|:-:|
| ![The focus menu: Focus and Custom, 2 of 4 today](docs/demos/screens/daruma-focus-menu.png) | ![A focus block: the timer on the persona's screen](docs/demos/screens/daruma-focus.png) | ![The Pomodoro page: the timer, today's tomatoes and this week](docs/demos/screens/daruma-pomodoro.png) |
| **Start a focus block** | **Focus, on the persona's screen** | **The Pomodoro page** |
| ![The app board: Tasks, Calendar, Weather and Pomodoro](docs/demos/screens/daruma-apps.png) | ![Tasks: one task checked off](docs/demos/screens/daruma-tasks.png) | ![Weather: now, the high and low, and the next hours](docs/demos/screens/daruma-weather.png) |
| **Apps** | **Tasks** | **Weather** |
| ![Calendar: the Agenda of today's events](docs/demos/screens/daruma-calendar.png) | ![Calendar: today's day view with start and end times](docs/demos/screens/daruma-calendar-day.png) | ![The voice assistant: "Will it rain tomorrow?"](docs/demos/screens/daruma-voice.png) |
| **Calendar: the Agenda** | **Calendar: one day** | **Voice assistant** |
| ![A yes/no question: turn the lights off?](docs/demos/screens/daruma-question.png) | ![A doorbell card: Unlock, Talk, Ignore](docs/demos/screens/daruma-doorbell.png) | ![A quiz question with four answers and a countdown](docs/demos/screens/daruma-quiz.png) |
| **A question from Home Assistant** | **The doorbell** | **A quiz** |

![Daruma at work: a focus block reaches the day's goal, a task is checked off, the Calendar's Agenda, the weather, and a question from Home Assistant](docs/demos/daruma-work.gif)

## The name

A [daruma](https://en.wikipedia.org/wiki/Daruma_doll) is a round Japanese
doll that holds a goal. It comes with blank eyes. You paint one eye when
you set the goal, and the other when you reach it. It is weighted at the
bottom, so it stands back up when you knock it over. The saying that goes
with it is *nanakorobi yaoki*: "fall down seven times, get up eight".

Daruma started as a focus companion, and the default persona still plays
the doll. Its first eye fills in after the day's first focus block. The
second fills in when you reach the day's goal. At midnight both are blank
again.

The framework has no opinion on what you do with it. Pick a pet that
cheers on your focus blocks. Build a character that keeps score in a game
of your own, and make it as playful as you like. Or drop the companions and
every app, show a photo of your family, and still get the doorbell cards
and messages from your home.

## Install

You need an ESP32-S3-BOX-3, Home Assistant, and
ESPHome 2026.10.2 or later.

1. Copy [examples/box3.yaml](examples/box3.yaml) into your ESPHome config
   folder. It has every public persona and every app.
2. Set the device name (`name` and `friendly_name`). Nothing else is
   required.
3. Add the keys from [examples/secrets.example.yaml](examples/secrets.example.yaml)
   to your `secrets.yaml`.
4. Compile and flash it over USB the first time.
5. Add the device in Home Assistant, and turn on "Allow the device to
   perform Home Assistant actions" in its options.
6. On the device's page in Home Assistant, pick your to-do list,
   calendars and weather entity.

[docs/install.md](docs/install.md) has every step in detail, with links to
the ESPHome and Home Assistant docs.

The device file is short. It pulls the parts you list from this
repository. A smaller one, with two personas, looks like this:

```yaml
substitutions:
  name: daruma
  friendly_name: Daruma

packages:
  daruma:
    url: https://github.com/igrybkov/daruma
    ref: main            # pin a release tag or a full commit for a device you rely on
    files:
      - packages/board_box3.yaml
      - packages/core.yaml
      - packages/persona_daruma.yaml       # the first persona is the default
      - packages/persona_pixel_corgi.yaml
      - packages/menu.yaml
      - packages/pomodoro.yaml
      - path: packages/app_calendar.yaml
        vars: { calendars: calendar.home }
      - packages/prompts.yaml
```

Every persona you include shows up in the "Persona" select on the
device's page in Home Assistant. The first one in the list is the
default on a new device, and the device keeps your choice across reboots
and updates. On the device, swipe left or right on the screen to change
the persona. Those swipes run `daruma.next_persona` and
`daruma.previous_persona`, which you can bind to a button too. Drop a
line from `files:` to drop that part.

**Or let your agent do it.** Copy this prompt to your coding agent with
access to Home Assistant:

```text
Install Daruma (https://github.com/igrybkov/daruma) on my ESP32-S3-BOX-3
and connect it to my Home Assistant. Follow
https://github.com/igrybkov/daruma/blob/main/docs/agents/install.md and the
install guide it links. Before you start, ask me for the device name, my
Wi-Fi details, and which personas and apps I want. Tell me when I need to
plug in the device or click something.
```

## Home Assistant talks to it

**Try the prompt demos first.** Import the
[prompt demos blueprint](blueprints/script/prompt_demos.yaml), make a
script from it, and run it. In two minutes you see every kind of card the
device can show, and each answer coming back to Home Assistant.

| Blueprint | What it does | Import |
|---|---|---|
| [Prompt demos](blueprints/script/prompt_demos.yaml) (script) | Try every kind of card in two minutes: a yes/no question, an urgent alert, a card that stays, a scrolling list, two stacked alerts. The device shows the answer it sent back. | <a href="https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fraw.githubusercontent.com%2Figrybkov%2Fdaruma%2Fmain%2Fblueprints%2Fscript%2Fprompt_demos.yaml"><img src="https://my.home-assistant.io/badges/blueprint_import.svg" alt="Import blueprint" width="296"></a> |
| [Doorbell prompt](blueprints/automation/doorbell_prompt.yaml) (automation) | When the doorbell rings, an urgent card offers Unlock, Talk and Ignore. | <a href="https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fraw.githubusercontent.com%2Figrybkov%2Fdaruma%2Fmain%2Fblueprints%2Fautomation%2Fdoorbell_prompt.yaml"><img src="https://my.home-assistant.io/badges/blueprint_import.svg" alt="Import blueprint" width="296"></a> |
| [Quiz](blueprints/script/quiz.yaml) (script) | A quiz from your list of questions, with a score and a 50:50 button. | <a href="https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fraw.githubusercontent.com%2Figrybkov%2Fdaruma%2Fmain%2Fblueprints%2Fscript%2Fquiz.yaml"><img src="https://my.home-assistant.io/badges/blueprint_import.svg" alt="Import blueprint" width="296"></a> |
| [Task list from a sensor](blueprints/script/task_list.yaml) (script) | Turns a list of tasks in a sensor attribute into a source for the Tasks app. | <a href="https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fraw.githubusercontent.com%2Figrybkov%2Fdaruma%2Fmain%2Fblueprints%2Fscript%2Ftask_list.yaml"><img src="https://my.home-assistant.io/badges/blueprint_import.svg" alt="Import blueprint" width="296"></a> |

Your own automations call the device's actions. Each is
`esphome.<node>_<action>`, for example `esphome.daruma_show_message`:

| Action | What it does |
|---|---|
| `show_message(message, seconds)` | a speech bubble, with a chime |
| `prompt_show`, `prompt_update`, `prompt_close` | a card with buttons; the answer comes back as the event `esphome.daruma_prompt` |
| `ask` | a card that waits for the answer and returns it, for quick questions |
| `pomodoro_start(minutes)` | starts a focus block; `0` takes the focus setting |
| `menu_open(name)` | opens a menu |
| `wink()`, `add_happiness(change_by)`, `set_wellbeing(value)` | a wink, the mood, the plant's health |

The device tells Home Assistant what happens on it: the "Event" entity
fires `petted`, `scared` and `timer_finished`, menu buttons can fire
`esphome.daruma_menu`, and every setting is an entity. Cards, layouts and
examples: [docs/prompts.md](docs/prompts.md).

## Make it yours

Everything is a part you can swap, change or add to. The manual,
[docs/customize.md](docs/customize.md), covers each:

| Part | What you can do |
|---|---|
| [Personas](docs/customize.md#personas) | pixel art, pictures or eyes; behaviors, words and params per state |
| [Pets, rooms and props](docs/customize.md#pixel-art-pets-rooms-and-props) | a new breed in a few shapes and colors, a room of its own, a prop for focus |
| [States and reactions](docs/customize.md#states-what-the-device-can-show) | moods, activities and reactions with fallbacks, so a new persona works from one picture. Reactions [blend with the activity under them](docs/customize.md#reactions-during-an-activity-during), so its props and decorations stay in the picture |
| [Sounds](docs/customize.md#sounds) | each persona's own chimes and yips from a small synth, or silence |
| [Themes and words](docs/customize.md#themes-and-words) | the menu's style and colors per persona, every word in your language |
| [Apps](docs/customize.md#apps) | order, switches, copies for a second list or calendar, apps of your own |
| [Menus](docs/customize.md#menus), [bindings](docs/customize.md#buttons-and-gestures-bindings), [targets](docs/customize.md#parts-of-the-screen-that-lead-somewhere-targets) | which buttons, gestures and taps do what |
| [Signals](docs/customize.md#signals-progress-wellbeing-sky-goal) | grow the plant from anything Home Assistant knows |
| [Modules](docs/customize.md#your-own-module) | new states, actions and buttons in a few lines of YAML |
| [Prompts](docs/prompts.md) and [blueprints](#home-assistant-talks-to-it) | cards and questions from Home Assistant, ready to import |
| [Screens and boards](docs/customize.md#other-screens-and-boards) | wide, square, black and white, buttons only |
| [Your own repository](docs/private-packages.md) | keep personas and apps in a repository of your own, private or public |

How it fits together: [docs/architecture/](docs/architecture/README.md).

**Make a persona with your agent.** Ask your coding agent to create a
persona of your favorite character, animal, flower, bird or imaginary
friend:

```text
Create a Daruma persona of <your favorite character, animal, flower, bird
or imaginary friend>. Follow
https://github.com/igrybkov/daruma/blob/main/docs/agents/new-persona.md.
Show me the preview sheet before you build it, and record the showcase
GIFs when it is done.
```

## Why pick Daruma

**It speaks Home Assistant.** Every setting on the device is an entity.
Its actions are Home Assistant actions, and taps and answers come
back as events. Your automations drive it like any other device. It
talks to Home Assistant over your own network, with no cloud.

**It is built for a small chip.** The device does as little work as it
can. Pixel personas are drawn on your computer at build time. Each
animation frame is stored as a small patch on the frame before it: the
daruma's 119 frames take 17 KB instead of 80 KB. The screen redraws only
the box that changed, and only when something changed. When nothing
moves, nothing is drawn. Seven personas, the voice assistant and every
app fit in a quarter of the firmware space, with the rest left for your
own parts. [docs/architecture/rendering.md](docs/architecture/rendering.md)
has the details.

**You change it without forking it.** Personas, apps, sounds and whole
modules come from your own files or your own repository. Updates to
Daruma still reach you.

**Mistakes show up on your computer, not on your desk.** The build checks
every part against every other, so a typo fails at compile time. The
desktop build runs the same screens in a window, with a fake clock: a
25-minute focus block takes a second. Golden pictures and a pytest
harness check every screen. See [docs/testing.md](docs/testing.md).

## Contributing

This repository is a starting point. Diverge from it as far as you like,
and send back what others could use: a persona, a room, an app, a board,
a fix. [CONTRIBUTING.md](CONTRIBUTING.md) has the setup, the checks and
the pull request checklist.

## License

MIT, see [LICENSE](LICENSE).

The hub and the eyes persona (`src/esphome/components/daruma`,
`src/esphome/components/daruma_eyes`) started from code by
[Rudy Gnodde](https://github.com/FamousWolf): an ESPHome component that
puts animated eyes on the ESP32-S3-BOX-3. See
[his original repository](https://github.com/FamousWolf/deskbuddy). His
code is under the MIT license. His notice is kept in those folders and in
[LICENSE](LICENSE). Thank you, Rudy.
