# Characters

> Incomplete. Moved from the old ARCHITECTURE.md. Add what you learn
> when a task needs more, and keep it under 300 lines.

Drawing and choosing a persona. Start with [new-persona.md](../agents/new-persona.md) and [customize.md: Pixel art](../customize.md#pixel-art-pets-rooms-and-props).

- The eyes persona has a focus look: eyes down and narrowed, as if reading.

**The Persona select** stores the chosen persona by its id (an FNV-1a hash). So a
new persona anywhere in the list, or a renamed one, keeps the choice. Its
options follow the config order: the first persona package in the device
yaml is the default.
`legacy_options` lists the options of an older build that stored a
position, so an update keeps that choice too.
