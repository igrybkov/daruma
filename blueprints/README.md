# Blueprints

Daruma is an animated companion on a small screen. It runs on an
ESP32-S3-BOX-3, and [Home Assistant](https://www.home-assistant.io/)
controls it. This folder holds blueprints that make Home Assistant use
the device.

A [blueprint](https://www.home-assistant.io/docs/blueprint/) is a
reusable automation or script for Home Assistant. You import it once.
Then you make an automation or a script from it, and fill in your own
entities: your doorbell, your lock, your device. You don't write any
YAML yourself.

## What's here

Most of these use **cards**. A card is a full-screen message on the
device, with buttons to answer. The device sends the answer back to Home
Assistant, and the automation acts on it. [prompts.md](../docs/prompts.md)
explains cards. It also has an import button for each blueprint.

| Blueprint | Kind | What it does |
|---|---|---|
| [prompt_demos](script/prompt_demos.yaml) | script | A two-minute tour of every kind of card: a yes/no question, an urgent alert, a card that stays, a scrolling list, two alerts at once. After each one, it shows the answer the device sent back. Start here. |
| [doorbell_prompt](automation/doorbell_prompt.yaml) | automation | When your doorbell rings, the device shows "Someone's at the door" with Unlock, Talk and Ignore. Unlock opens the lock you pick. Talk runs an action you pick, such as a two-way audio call. |
| [quiz](script/quiz.yaml) | script | A quiz from your own list of questions. Each question has four answers and a 50:50 button that hides two wrong ones, once per game. The device keeps the score. |
| [habitica_look_changed](automation/habitica_look_changed.yaml) | automation | Not a card. When your Habitica look changes, Home Assistant tells you to rebuild Daruma, so the Habitica persona shows the new look. It needs the "Habitica look" sensor from [habitica-avatar.md](../docs/habitica-avatar.md). |
| [task_list](script/task_list.yaml) | script | Not a card. The device's Tasks app can show tasks from a to-do list or from a script. This script reads a list of tasks from a sensor, so the app can show them. |

## Writing a new blueprint

- Use only what Daruma offers Home Assistant: its actions, its events
  and its entities. Then the blueprint works on any Daruma device, with
  any look.
- Make every entity an input. Never name a real device or a real house.
- Add a blueprint here when an automation proves useful in a real home.
- For how the device and Home Assistant talk:
  [Talking to Home Assistant](../docs/architecture/home-assistant.md) and
  [Prompts](../docs/architecture/prompts.md).

## Ideas

These are not built yet. Each one would be a good blueprint to write
next.

| Blueprint | Kind | What it would do |
|---|---|---|
| `joke_after_focus` | automation | After a focus session, or when you reach the daily goal, ask an AI for a short joke and show it on the device. |
| `window_weather` | automation | Set the sky in the window behind the character from a weather entity, and the temperature on screen from a sensor. |
| `quiet_during_calls` | automation | While you're on a call, mute the device's sounds, speaker and mic. Turn them back on after. |
| `goal_nudge` | automation | Late in the day, if the daily goal is still far off, make the device look sad and offer to start a focus session. |
| `calendar_heads_up` | automation | A few minutes before a meeting, show a card with its title and a "Start focus after" button. |
