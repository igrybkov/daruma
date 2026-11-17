# Examples

Daruma is an animated companion on a small screen. It runs on an
ESP32-S3-BOX-3, and [Home Assistant](https://www.home-assistant.io/)
controls it. You build its firmware with
[ESPHome](https://esphome.io/) from one YAML file, the **device file**.

This folder holds device files. Copy one to make your own device, or
build them to check a change to Daruma. Each file starts with a comment
that explains its options.

## Make your own device

| File | What it is |
|---|---|
| [box3.yaml](box3.yaml) | A full device for the ESP32-S3-BOX-3: several looks, voice, a pomodoro timer, tasks, a calendar, and cards from Home Assistant. Copy it into your ESPHome config folder, then remove what you don't want. |
| [secrets.example.yaml](secrets.example.yaml) | The private values the device file needs: your Wi-Fi name and password, and a key for the connection to Home Assistant. Copy them into the `secrets.yaml` in your ESPHome config folder and fill them in. ESPHome reads them where the device file says `!secret`. |

[install.md](../docs/install.md) walks you through it, from the first
build to the device on your desk.

## Try it without a device

[desktop.yaml](desktop.yaml) runs the same looks and apps in a window on
your computer. The mouse acts as your finger. It uses the files in your
copy of this repository, so it shows your own changes at once. The
screen tests and demo GIFs use it too.

## Build checks

These files make sure Daruma still builds for setups that the BOX-3
alone doesn't cover. They are only for compiling. Never flash one to a
device: the hardware doesn't match.

| File | What it checks |
|---|---|
| [variant_apps.yaml](variant_apps.yaml) | Two copies of the same app on one device, such as a Family tasks list and a Work calendar next to the usual ones. |
| [variant_mono.yaml](variant_mono.yaml) | A slow black-and-white screen with buttons only, the way an e-ink clock would work. |
| [variant_square.yaml](variant_square.yaml) | A square 240x240 screen. |
| [variant_wide.yaml](variant_wide.yaml) | A wide 480x272 screen, with larger fonts. |

[secrets.ci.yaml](secrets.ci.yaml) has fake secrets for the automatic
builds on GitHub. They are public on purpose. A device built with them
can't join a Wi-Fi network.

## Commands

Run these from the top folder of the repository.

```sh
make secrets              # make examples/secrets.yaml with a random key (only if it isn't there)
make config               # check that every example is valid
make config EXAMPLE=box3  # check one example
make compile              # build the firmware for box3.yaml; EXAMPLE= picks another
make desktop              # open desktop.yaml in a window
```

Commit your changes before `make config` and `make compile`. Those two
take Daruma's files from your last commit, not from the files on disk.
`make desktop` uses the files on disk.

## Adding an example

- Add one when you need to check a setup that no file here covers: a new
  screen size, a new board, or a new mix of features. Name it
  `variant_<what>.yaml`. `make config` picks it up by itself.
- Start the file with a comment. Say what it checks, and that it is only
  for compiling.
- Use made-up names and entities. Never a real person's calendar or
  tasks.
