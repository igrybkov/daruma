# Themes and words

> Incomplete. Moved from the old ARCHITECTURE.md. Add what you learn
> when a task needs more, and keep it under 300 lines.

How modules, personas and the device yaml set colors and words. How to use it: [customize.md: Themes and words](../customize.md#themes-and-words).

The device yaml, where the parts come together, may set module keys too:

```yaml
daruma:
  theme:                     # every persona
    colors: { pomodoro.done: "D62828" }
    words: { pomodoro.ready: "Bereit" }
  themes:                    # one persona, by its id
    eyes:
      colors: { pomodoro.plaque: "000000" }
```

- For a module key, lowest first: the module's default, the persona's own
  `theme:`, the device's `theme:`, the device's `themes: <persona id>`.
- A persona id is the persona's `id:` (`eyes`, `pixel_corgi`, `daruma`).
  The build stops on an unknown persona id and names the ones there are, and
  on a key no included module declares, as for a persona's theme.
- `theme.py` applies them when it builds each persona's theme, so a persona
  without a `theme:` of its own gets one. Gray and mono screens derive
  from the result at setup, as before.
- A module may keep old key names working: `theme: aliases: {old: new}`.
  The pomodoro's `tomato_unripe`, `tomato` and `tomato_bonus` are now
  `pending`, `done` and `extra`. They color both the tomatoes and the
  timer's dots.
