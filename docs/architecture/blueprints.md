# Blueprints

> Incomplete. Moved from the old ARCHITECTURE.md. Add what you learn
> when a task needs more, and keep it under 300 lines.

Home Assistant blueprints that ship with the framework.

`blueprints/` holds examples of what Home Assistant can do with a device.
Each one started as a real automation and was made generic: every entity
is an input. Four are built: `prompt_demos`, `doorbell_prompt`, `quiz`
and `task_list`. The others in the table are ideas.

| Blueprint | Kind | What it does |
|---|---|---|
| `joke_after_focus` | automation | After a focus session or the daily goal, asks an AI task for a short joke and shows it on the device. |
| `window_weather` | automation | Sets the persona's window sky from a weather entity, and the temperature badge from a sensor. |
| `quiet_during_calls` | automation | While a call is on, mutes the device's sounds, speaker and mic, and restores them after. |
| `prompt_demos` | script | Shows every kind of card (yes/no with `ask`, an urgent alert, a card that stays, a list, two stacked alerts) and the answer it sent back. |
| `doorbell_prompt` | automation | Shows an urgent prompt when someone rings: Unlock, Talk or Ignore. |
| `quiz` | script | A multiple-choice quiz with scores and a 50:50 lifeline. |
| `task_list` | script | Returns a sensor attribute's task list, trimmed, for the Tasks app's "Script" source. |
| `goal_nudge` | automation | Late in the day, if the daily goal is still far off, the device looks sad and offers to start a focus session. |
| `calendar_heads_up` | automation | A few minutes before a meeting, shows an info prompt with the title and a "Start focus after" option. |

New blueprints land here when an automation in a real house proves
useful. Blueprints use only what the
framework offers (API actions, events, entities), so they keep working on any
board and persona.
