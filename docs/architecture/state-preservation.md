# Preserving state

> Incomplete. Moved from the old ARCHITECTURE.md. Add what you learn
> when a task needs more, and keep it under 300 lines.

Keeping a choice or a value across a reboot or an update: the chosen
persona, a running timer, today's count.

## The Persona select

The select stores the chosen persona by its id, an FNV-1a hash. A new
persona anywhere in the list keeps the choice. So does a renamed one.

Its options follow the config order. The first persona package in the
device yaml is the default.

`legacy_options` lists the options of an older build that stored a
position. An update from that build keeps the choice too.
