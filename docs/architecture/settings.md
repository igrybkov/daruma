# Settings in Home Assistant

> Incomplete. Moved from the old ARCHITECTURE.md. Add what you learn
> when a task needs more, and keep it under 300 lines.

What becomes a device setting in HA, and what stays in YAML.

Settings that may change after flashing appear in HA under the device's
"Configuration" section. They are ESPHome entities with
`entity_category: config`. They keep their values across reboots. The device
yaml sets their first value.

- Apps: one switch per app ("App: Calendar").
- App settings: for example "Calendars", a text entity holding a list of
  entity IDs, "Days ahead", and "Tasks source".
- Persona params with `expose: true`.
- Bindings, with `expose_bindings: true`.
- The home button action, the jokes switch and the theme options already
  work like this, or will.

Things that change the build stay in YAML: which modules, which personas,
fonts and the board.
