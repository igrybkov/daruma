# Habitica

[Habitica](https://habitica.com) turns your habits, dailies and to-dos
into a role-playing game. Home Assistant's
[Habitica integration](https://www.home-assistant.io/integrations/habitica/)
connects to your account. The device then shows your dailies, your
to-dos and your hero's stats, and each focus block you finish earns XP
and gold.

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

## Your hero on the device

The module [habitica.yaml](../packages/habitica.yaml) follows your
hero's stats. It adds the Character app, and the persona reacts when the
numbers change. It needs no automation in Home Assistant: the device
follows the Habitica entities itself.

```yaml
packages:
  daruma:
    url: https://github.com/igrybkov/daruma
    ref: main
    files:
      # ... your other packages
      - path: packages/habitica.yaml
        vars:
          user: <user>

daruma:
  apps: [dailies, todos, character, calendar, weather, stats]
```

`user` is the entity prefix from [Before you start](#before-you-start).
The module reads these entities:

- `sensor.<user>_health`, `_experience`, `_next_level`, `_mana`,
  `_max_mana`, `_level`, `_class` and `_gold`;
- `switch.<user>_rest_in_the_inn`;
- `button.<user>_buy_a_health_potion`, `_start_my_day`,
  `_revive_from_death` and `_allocate_all_stat_points`.

Home Assistant has no sensor for max HP. The var `hp_max` sets it, 50 by
default, as in Habitica.

### The Character app

- HP, XP and MP as bars with their numbers, in that order. Each has a
  label, so gray and mono screens tell them apart.
- Your level, class and gold on top. "In the inn" while you rest.
- Buttons for Buy potion, Start my day, Revive and Allocate. Each shows
  only while Home Assistant offers it: Start my day before the day
  starts, Revive at 0 HP.
- A tap presses the Home Assistant button. Buy potion asks first, since
  it spends 25 gold.
- The tile on the app board reads "Lv 12 · HP 45".

### Reactions

| When | State | Kind | Without its own animation |
|---|---|---|---|
| The level goes up | `level_up` | reaction | celebrate |
| HP drops by `hurt_threshold` or more (1 by default) | `hurt` | reaction | scared |
| HP is 0 | `fainted` | activity | sad |
| You rest in the inn | `resting` | activity | sleeping |
| Home Assistant sends a drop | `drop` | reaction | happy |

- The first numbers after a boot or a reconnect fill the sheet. They
  play nothing.
- The same numbers twice play once.
- The sheet keeps its numbers across a reboot. It shows them until Home
  Assistant sends new ones.

### Events from Home Assistant

The numbers can't show a drop or a quest. Send them with the action
`esphome.<device>_habitica_event`. Both fields are required; send `""`
for no message.

```yaml
action: esphome.daruma_habitica_event
data:
  kind: drop            # drop or quest
  message: Found a Wolf egg!
```

- `drop` plays the `drop` reaction and shows the message.
- `quest` shows the message.

The message waits while Do not disturb is on.

## Habits

The Habits app shows your habits with a plus and a minus. A tap scores
one in Habitica. It talks to one Home Assistant script. The blueprint
[Daruma: Habitica habits](../blueprints/script/habitica_habits.yaml)
makes it.

<a href="https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fraw.githubusercontent.com%2Figrybkov%2Fdaruma%2Fmain%2Fblueprints%2Fscript%2Fhabitica_habits.yaml"><img src="https://my.home-assistant.io/badges/blueprint_import.svg" alt="Import blueprint" width="296"></a>

1. Import the blueprint and make a script from it. Pick your Habitica
   account. Name it, for example, `script.habitica_habits`.
2. Add the app to the device:

   ```yaml
   packages:
     daruma:
       url: https://github.com/igrybkov/daruma
       ref: main
       files:
         # ... your other packages
         - path: packages/app_habits.yaml
           vars:
             entity: script.habitica_habits
             text_busy: "Habitica is busy"

   daruma:
     apps: [dailies, todos, habits, character, calendar, weather, stats]
   ```

3. The "Habits entity" setting in Home Assistant holds the script. You
   can change it there without a new build.

On the device:

- Each row has a bar in the habit's value color, red to blue, as in
  Habitica. Under the title are the counts for its period: "+3 -1
  today", "+5 this week".
- A plus or a minus shows only for the sides the habit has.
- The count moves at once. It moves back when Home Assistant says no,
  or does not answer in 10 seconds.
- With [habitica.yaml](../packages/habitica.yaml) in the build, a row of
  your stats sits on top. A score that levels you up plays `level_up`
  at once. A drop plays `drop` after it, and its text shows in the app.
  Quest progress shows there too: "Quest +3.5".
- The tile reads today's net score: "+4 today".
- Without touch: NEXT and PREV move over the rows. SELECT scores up.
  Two quick SELECTs score down.

Each tap is one request to Habitica. The device sends one at a time.
Two package vars keep your request budget:

- `max_waiting` (5): a tap past five waiting ones is dropped.
- `per_minute` (12): at most 12 scores a minute leave the device.

Either shows the `text_busy` notice: "Busy, try again soon" by default,
and "Habitica is busy" in the example above. So does a score that
Habitica turns down for its rate limit.

Listing the habits reads the integration's cache. It costs no request.
Your notes and the history of each habit stay in Home Assistant.
