# Sounds

> Incomplete. Moved from the old ARCHITECTURE.md. Add what you learn
> when a task needs more, and keep it under 300 lines.

How a state picks its sound, and what can stop a sound. How to add one: [customize.md: Sounds](../customize.md#sounds).

A sound belongs to a state's behavior. Code calls
`device.react(StateId::PETTED)`, not a sound by name. The persona's
behavior picks the sound, and the built-in synth sounds are the defaults.

- A state's sound is its behavior's, else the registry's default for that
  state. A sound does not follow the fallback: `petted` shown as `loved`
  still plays `pet`.
- An activity plays its sound when it starts, unless the caller passes
  `sound = false`. A break right after a focus block is quiet, because
  `focus_done` just played.
- Core's `play_sound` script still plays every sound. It keeps the guards:
  the Sounds switch, a ringing timer, the voice assistant, announcements,
  and the shared I2S bus.
- The timer chime is the persona's sound for `alarm` (default `timer`).
- Urgent sounds pass a held Sounds switch. Do not disturb turns Sounds
  off and calls `Hub::set_sounds_held()`. `play_sound(name, true)` then
  sets `Hub::urgent_sound()` while the player runs. The `play_sound`
  script plays when Sounds is on or that flag is set. Only urgent prompts
  pass `true`.

Trap: the flag is true only during the call. A `play_sound` script that
waits before its `if` reads it too late. Keep the check first.
