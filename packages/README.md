# Packages

Daruma is built from parts, and each package is one part: a board, the
core, a persona or a feature. Your device file stays short. It names the
parts you want, and ESPHome fetches them from this repository. To get a
new version, change the `ref`.

A package is an
[ESPHome package](https://esphome.io/components/packages/): a YAML file
that ESPHome merges into your device's config. List it under
`packages:` to turn the part on. Leave it out and the part is gone, with
nothing else to remove. Each file's header comment has its options and
the Home Assistant actions it adds.

For a full device file, see [examples/box3.yaml](../examples/box3.yaml).

## Board: pick one

| Package | What it is |
|---|---|
| [board_box3.yaml](board_box3.yaml) | The ESP32-S3-BOX-3 with touch and both buttons. |
| [board_box3_buttons.yaml](board_box3_buttons.yaml) | The same BOX-3, driven by its two buttons only. |
| [board_desktop.yaml](board_desktop.yaml) | A window on a computer, for demos and tests. |

The two BOX-3 boards share
[board_box3_hardware.yaml](board_box3_hardware.yaml): the screen, audio,
buttons and touch. It pulls in
[core_voice.yaml](core_voice.yaml): the voice assistant, wake word,
speaker and Wi-Fi. You don't list either of them yourself.

## Core: always

| Package | What it is |
|---|---|
| [core.yaml](core.yaml) | The hub: state, mood, signals, input, sounds and drawing. |

## Personas: one or more

The first one listed is the default. The "Persona" select in Home
Assistant switches between them.

| Package | What it is |
|---|---|
| [persona_daruma.yaml](persona_daruma.yaml) | A pixel-art daruma doll that paints its eyes as you reach today's goal. |
| [persona_pixel_corgi.yaml](persona_pixel_corgi.yaml) | A pixel-art corgi in a cozy room. |
| [persona_jack_russell.yaml](persona_jack_russell.yaml) | A pixel-art Jack Russell terrier. |
| [persona_tabby_cat.yaml](persona_tabby_cat.yaml) | A pixel-art tabby cat. |
| [persona_the_boss.yaml](persona_the_boss.yaml) | A pixel-art executive at her desk. |
| [persona_eyes.yaml](persona_eyes.yaml) | Eyes drawn from shapes. |
| [persona_images.yaml](persona_images.yaml) | A persona from PNG pictures. Include it once per picture set. |

## Modules: any you want

| Package | What it adds | Needs |
|---|---|---|
| [menu.yaml](menu.yaml) | The tap menu. Without it, a tap pets the persona. | core |
| [pomodoro.yaml](pomodoro.yaml) | A pomodoro timer, a daily goal and tomatoes. | core |
| [prompts.yaml](prompts.yaml) | Cards that Home Assistant shows, and the answers sent back. | core |
| [app_tasks.yaml](app_tasks.yaml) | Today's tasks from a to-do list or a script. Include it once per list. | core, menu |
| [app_calendar.yaml](app_calendar.yaml) | The coming events of one or more calendars. Include it once per set. | core, menu |
| [app_weather.yaml](app_weather.yaml) | Today's weather from a weather entity. | core, menu |

## More

- How to set options and include a package twice:
  [customize.md](../docs/customize.md).
- Packages from your own repository:
  [private-packages.md](../docs/private-packages.md).
- How to write a module or a persona:
  [docs/architecture/](../docs/architecture/README.md).
