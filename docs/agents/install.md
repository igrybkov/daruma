# Agent playbook: install Daruma for a person

You are a coding agent. A person asked you to install Daruma on their
ESP32-S3-BOX-3 and connect it to their Home Assistant. This file tells
you how. People are welcome to read it too.

The repository: <https://github.com/igrybkov/daruma>. If you have no
checkout, clone it: you need the example files. For the words Daruma
uses (persona, state, module), see [AGENTS.md](../../AGENTS.md).

Follow [docs/install.md](../install.md). It has every step a person
does. Where you have access, do the step yourself. Otherwise tell the
person exactly what to click.

## Steps

1. **Ask first.** The device name, and which parts they want: personas,
   apps, the voice assistant. Default: everything in `examples/box3.yaml`.
2. **Device file.** Copy `examples/box3.yaml` into their ESPHome config
   folder under the device name. Set `name` and `friendly_name`. Pin
   `daruma_ref` to the latest release tag if there is one, else `main`.
   Drop the `files:` entries they don't want.
3. **Secrets.** Add the four keys of `examples/secrets.example.yaml` to
   their `secrets.yaml`. Generate `daruma_api_key` with
   `openssl rand -base64 32`. Ask for the Wi-Fi name and password; never
   invent them. Never print secrets back.
4. **Compile.** `esphome compile <file>`. Fix config errors from the
   message: Daruma's build checks name the bad key and the choices.
5. **Flash.** The first flash needs USB. The person plugs the device in
   and installs from the ESPHome Device Builder, or you run
   `esphome run <file>` on the machine it is plugged into. Never flash a
   build made with placeholder secrets: the device loses its Wi-Fi.
6. **Add to Home Assistant.** The ESPHome integration discovers it. The
   API key is `daruma_api_key`.
7. **Allow actions.** In the integration's options for this device, turn
   on "Allow the device to perform Home Assistant actions". The Calendar,
   Tasks and Weather apps need it. This is an options flow on the ESPHome
   config entry. If you can't run it, ask the person to.
8. **Pick the data.** List the person's `todo.*`, `calendar.*` and
   `weather.*` entities, ask which to use, and set them on the device:
   the text entities "Tasks entity", "Calendars" (comma-separated) and
   "Weather entity", and the select "Tasks source". The device keeps them.
9. **Check.** The device shows a persona, no "No Home Assistant" line,
   and the apps load. Open the device's logs if not.

## Extras to offer

- The blueprints in `blueprints/`: the prompt demos, a doorbell card, a
  quiz, a task list script. The README links each with an import button.
- An automation that sets the "Window" select from the weather.
- `set_wellbeing`, or a custom progress source (see
  [customize.md](../customize.md#signals-progress-wellbeing-sky-goal)).
