# Packages

Daruma is an animated companion on a small screen. It runs on an
ESP32-S3-BOX-3, and [Home Assistant](https://www.home-assistant.io/)
controls it. You build its firmware with [ESPHome](https://esphome.io/)
from one YAML file, the **device file**.

Daruma comes in parts, and each file in this folder is one part: the
hardware, the core, a look, or a feature. You pick the parts you want.
Your device file only lists them, so it stays short. ESPHome downloads
the parts from this repository when it builds.

A [package](https://esphome.io/components/packages/) is ESPHome's word
for such a part. It's a YAML file that ESPHome merges into your device
file. Here is a small device file:

```yaml
packages:
  daruma:
    url: https://github.com/igrybkov/daruma
    ref: main            # which version of Daruma to use
    files:
      - packages/board_box3.yaml
      - packages/core.yaml
      - packages/persona_daruma.yaml
      - packages/menu.yaml
      - packages/pomodoro.yaml
```

To add a feature, add its line. To remove one, delete its line. Nothing
else needs to change. To update Daruma, change `ref` to a newer version.

Each file starts with a comment. It lists the file's options, and what
it lets Home Assistant do. For a full device file, see
[examples/box3.yaml](../examples/box3.yaml).

## The hardware: pick one

A **board** package tells Daruma what hardware it runs on: the screen,
the buttons, the touch screen, the speaker.

| Package | What it is |
|---|---|
| [board_box3.yaml](board_box3.yaml) | The ESP32-S3-BOX-3, with touch and both buttons. |
| [board_box3_buttons.yaml](board_box3_buttons.yaml) | The same BOX-3, used with its two buttons only. |
| [board_desktop.yaml](board_desktop.yaml) | A window on a computer, for trying things out and for tests. |

You don't list [board_box3_hardware.yaml](board_box3_hardware.yaml) or
[core_voice.yaml](core_voice.yaml) yourself. Both BOX-3 boards bring
them in. They hold the screen setup, the audio and the voice assistant.

## The core: always

| Package | What it is |
|---|---|
| [core.yaml](core.yaml) | The part every device needs. It decides what the device shows, handles taps and buttons, plays sounds and draws the screen. |

## Looks: one or more

A **persona** is one look of the device: a character with its own
animations. List as many as you like. The first one is the default. You
switch between them with the "Persona" setting in Home Assistant, or by
swiping left or right on the screen.

| Package | What it is |
|---|---|
| [persona_daruma.yaml](persona_daruma.yaml) | A pixel-art daruma doll. It paints in its eyes as you reach today's goal. |
| [persona_pixel_corgi.yaml](persona_pixel_corgi.yaml) | A pixel-art corgi in a cozy room. |
| [persona_jack_russell.yaml](persona_jack_russell.yaml) | A pixel-art Jack Russell terrier. |
| [persona_tabby_cat.yaml](persona_tabby_cat.yaml) | A pixel-art tabby cat. |
| [persona_the_boss.yaml](persona_the_boss.yaml) | A pixel-art executive at her desk. |
| [persona_eyes.yaml](persona_eyes.yaml) | A pair of eyes drawn from simple shapes. |
| [persona_images.yaml](persona_images.yaml) | Your own pictures, one PNG for each mood or activity. List it once for each set of pictures. |

## Features: any you want

Each of these adds something the device can do. Some need another
package too. The last column says which.

| Package | What it adds | Also needs |
|---|---|---|
| [menu.yaml](menu.yaml) | A menu that opens when you tap the screen. Without it, a tap pets the character. | |
| [pomodoro.yaml](pomodoro.yaml) | A focus timer ([pomodoro](https://en.wikipedia.org/wiki/Pomodoro_Technique)). You set a daily goal in sessions, and the screen shows a tomato for each one. | |
| [prompts.yaml](prompts.yaml) | Cards: full-screen messages from Home Assistant, with buttons to answer. See [prompts.md](../docs/prompts.md). | |
| [quiet.yaml](quiet.yaml) | Quiet hours, Do not disturb and dimming when idle. See [customize.md](../docs/customize.md#quiet-hours-and-do-not-disturb). | |
| [app_tasks.yaml](app_tasks.yaml) | An app with today's tasks, from a Home Assistant to-do list. You can check tasks off. List it once for each to-do list. | menu |
| [app_calendar.yaml](app_calendar.yaml) | An app with your coming calendar events. List it once for each group of calendars. | menu |
| [app_weather.yaml](app_weather.yaml) | An app with today's weather. | menu |

## More

- Change a part's options, or list one twice:
  [customize.md](../docs/customize.md).
- Keep your own parts in your own repository:
  [private-packages.md](../docs/private-packages.md).
- Write a new part: [docs/architecture/](../docs/architecture/README.md).
