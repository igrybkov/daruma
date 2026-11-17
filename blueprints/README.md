# Blueprints

Home Assistant blueprints that use the device. Each one started as a real
automation and was made generic: every entity is an input.

| Blueprint | Kind | What it does |
|---|---|---|
| [prompt_demos](script/prompt_demos.yaml) | script | Shows every kind of card (yes/no with `ask`, an urgent alert, a card that stays, a list, two stacked alerts) and the answer it sent back. |
| [doorbell_prompt](automation/doorbell_prompt.yaml) | automation | Shows an urgent prompt when someone rings: Unlock, Talk or Ignore. |
| [quiz](script/quiz.yaml) | script | A multiple-choice quiz with scores and a 50:50 lifeline. |
| [task_list](script/task_list.yaml) | script | Returns a sensor attribute's task list, trimmed, for the Tasks app's "Script" source. |

Import buttons are in [prompts.md](../docs/prompts.md).

## Writing a blueprint

- Use only what the framework offers: API actions, events and entities.
  Then the blueprint works on any board and any persona.
- Make every entity an input. Don't name a real device or a real house.
- Add a blueprint when an automation in a real house proves useful.
- How the device talks to Home Assistant:
  [Talking to Home Assistant](../docs/architecture/home-assistant.md) and
  [Prompts](../docs/architecture/prompts.md).

## Ideas

Not built yet.

| Blueprint | Kind | What it would do |
|---|---|---|
| `joke_after_focus` | automation | After a focus session or the daily goal, asks an AI task for a short joke and shows it on the device. |
| `window_weather` | automation | Sets the persona's window sky from a weather entity, and the temperature badge from a sensor. |
| `quiet_during_calls` | automation | While a call is on, mutes the device's sounds, speaker and mic, and restores them after. |
| `goal_nudge` | automation | Late in the day, if the daily goal is still far off, the device looks sad and offers to start a focus session. |
| `calendar_heads_up` | automation | A few minutes before a meeting, shows an info prompt with the title and a "Start focus after" option. |
