# Device-side modules

> Incomplete. Moved from the old ARCHITECTURE.md. Add what you learn
> when a task needs more, and keep it under 300 lines.

Modules that keep their own state on the device, like pomodoro: its page and its plaque.

- **Pomodoro page** (app id `stats`, named "Pomodoro"). It replaced the
  Stats app and keeps its id, so `apps:`, menus and the app's switch keep
  working. The timer big (the focus length while idle), the phase and
  "N of goal today", one dot per pomodoro of the goal, this week's bars
  with the goal line, the week's total and the streak, and a row of the
  buttons for now (see [menus.md](menus.md)). Custom swaps the row for the lengths; back
  leaves them. While open it redraws every second. NEXT, PREV and SELECT
  move a focus over the buttons. A tap on the plaque opens it.

- **The pomodoro plaque** (`plaque.h`, host-tested, bottom left):
  - Idle: today's tomatoes, three a row, 22 apart.
  - A focus or a break, running or paused: the timer. mm:ss in the phase
    color, each digit in a fixed cell so nothing shifts, the colon
    blinking. Under it one dot per pomodoro of the goal: filled when done,
    a ring when still to do. Paused: gray, a pause sign in the colon's
    place. Slow screens show "12m".
  - The timer plaque keeps one size for the session. Each tick repaints
    only its rect (`request_area`); a full frame only when its rect
    changed. No tick while the menu, a prompt or a bubble is up.
  - Don't add a countdown bar. Every step of it repaints the persona
    under it, and the plaque already shows the time.
  - Gray and mono: colors go through `theme.on()` against the plaque;
    done and to-do differ by shape (filled or a ring).
