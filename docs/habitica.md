# Habitica

[Habitica](https://habitica.com) turns your habits, dailies and to-dos
into a role-playing game. Home Assistant's
[Habitica integration](https://www.home-assistant.io/integrations/habitica/)
connects to your account. The device then shows your dailies and to-dos,
and each focus block you finish earns XP and gold.

The device never holds your Habitica token. It talks only to Home
Assistant, and Home Assistant talks to Habitica.

## Before you start

1. Add the Habitica integration in Home Assistant.
2. Find its entity prefix. Home Assistant names the entities after your
   Habitica name, such as `todo.<user>_dailies`. Below, `<user>` stands for
   that prefix.
3. Turn on "Allow the device to perform Home Assistant actions" for the
   device (Settings > Devices > ESPHome > your device > Configure).

## Dailies and to-dos

The Tasks app shows any to-do list. Add two copies of it, one per
Habitica list:

```yaml
packages:
  daruma:
    url: https://github.com/igrybkov/daruma
    ref: main
    files:
      # ... your other packages
      - path: packages/app_tasks.yaml
        vars:
          app_id: dailies
          app_name: Dailies
          entity: todo.<user>_dailies
          due_today_only: "true"
      - path: packages/app_tasks.yaml
        vars:
          app_id: todos
          app_name: To-dos
          entity: todo.<user>_to_do_s

daruma:
  apps: [dailies, todos, calendar, weather, stats]
```

- A tap checks a task off. Home Assistant scores it in Habitica.
- The dailies list also holds the dailies that are not due today.
  `due_today_only: "true"` hides them, so the tile says what is left today.
- A daily from a day you did not start shows as overdue (a red dot).
  Start the day in Habitica to clear it.
- The scores come back to the device about 5 to 8 seconds later, when
  Home Assistant reads Habitica again.

## Focus earns XP

The blueprint
[Daruma: focus scores a Habitica habit](../blueprints/automation/habitica_focus_habit.yaml)
scores a habit each time you finish a focus block.

<a href="https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fraw.githubusercontent.com%2Figrybkov%2Fdaruma%2Fmain%2Fblueprints%2Fautomation%2Fhabitica_focus_habit.yaml"><img src="https://my.home-assistant.io/badges/blueprint_import.svg" alt="Import blueprint" width="296"></a>

1. In Habitica, make a habit with a plus, such as "Focus block".
2. Import the blueprint and make an automation from it.
3. Pick the device's "Pomodoro event" entity, your Habitica account and
   the habit.
4. Under "Score on", keep all three to score every block. Pick only "The
   block that meets the goal" to score once a day.

Each score is one request to Habitica. Habitica allows 30 a minute for
your account, shared with its apps and Home Assistant's own polling.
