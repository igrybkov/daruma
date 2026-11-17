# Examples

Device configs to copy or to build from this checkout. Each file's header
comment explains its options.

## Start from one

| File | What it is |
|---|---|
| [box3.yaml](box3.yaml) | A real device on the ESP32-S3-BOX-3: personas, voice, pomodoro, tasks, calendar and prompts. Copy it to start your own. |
| [desktop.yaml](desktop.yaml) | The same personas and apps in a window on a computer. It uses this checkout, so it shows your changes. Never flashed. |
| [secrets.example.yaml](secrets.example.yaml) | The keys the examples read with `!secret`. Copy them into your `secrets.yaml`. |

To set up a device from `box3.yaml`, follow [install.md](../docs/install.md).

## Build checks

Compile-only. Each one proves the framework still builds for a case the
BOX-3 doesn't cover. Never flash them.

| File | What it checks |
|---|---|
| [variant_apps.yaml](variant_apps.yaml) | Two copies each of the Tasks and Calendar apps, each with its own `app_id`. |
| [variant_mono.yaml](variant_mono.yaml) | A slow black-and-white screen with buttons only, like an e-ink clock. |
| [variant_square.yaml](variant_square.yaml) | A square 240x240 screen. |
| [variant_wide.yaml](variant_wide.yaml) | A 16:9 480x272 screen, with larger fonts. |

[secrets.ci.yaml](secrets.ci.yaml) holds public placeholder secrets for
CI. A build made with them can't join Wi-Fi.

## Commands

Run them from the repository root. Commit before `make config` and
`make compile`: they fetch the packages from this checkout's last commit.
`make desktop` uses the files as they are.

```sh
make secrets              # write examples/secrets.yaml once, with a random API key
make config               # check the config of every example
make config EXAMPLE=box3  # check one
make compile              # compile box3; EXAMPLE= picks another
make desktop              # run desktop.yaml in a window
```

## Adding an example

- A new screen size, board or module mix that the others don't cover
  goes here as a `variant_*.yaml`. `make config` picks up every file in
  this folder except the secrets.
- Start the file with a comment: what it checks, and whether it is
  compile-only.
- Use made-up names and entities. Never a real person's calendar or
  tasks.
