"""The `sounds:` option that personas share: sound effects in the persona's own style.

Each entry replaces one built-in sound (daruma/synth.cpp: start, pause,
stop, focus_done, goal, break_over, pet, timer, notify, urgent) for this
persona. A sound is a
list of steps, played in order:

    sounds:
      pet:
        - { note: C6, to: G6, seconds: 0.09, duty: 0.25, release: 0.02 }
        - { rest: 0.04 }
        - { arp: [E5, G5, C6], step: 0.07, duty: 0.25, last: 0.2 }

  note     pitch, like A4 or C#5; `to` glides there over the step
  duty     0.5 is a full square wave; lower is thinner and brighter
  attack, release   fade in and out, in seconds
  vibrato  wobble speed in Hz
  arp      a quick run of notes, `step` seconds each; the last one rings
           for `last` seconds (twice `step` if left out)

A sound lasts 2 seconds at most. Preview the built-in ones with
sounds/preview.cpp.
"""

import esphome.codegen as cg
import esphome.config_validation as cv

CONF_SOUNDS = "sounds"
_NOTE_STEPS = {"C": -9, "D": -7, "E": -5, "F": -4, "G": -2, "A": 0, "B": 2}


def _note(value):
    value = cv.string_strict(value).strip()
    try:
        semis = _NOTE_STEPS[value[0].upper()]
        rest = value[1:]
        if rest.startswith("#"):
            semis, rest = semis + 1, rest[1:]
        octave = int(rest)
    except (KeyError, IndexError, ValueError) as err:
        raise cv.Invalid(f"'{value}' is not a note; use a letter, an optional #, and an octave: A4, C#5") from err
    return 440.0 * 2 ** ((semis + 12 * (octave - 4)) / 12)


_seconds = cv.float_range(min=0.0, max=10.0)

TONE_SCHEMA = cv.Schema(
    {
        cv.Required("note"): _note,
        cv.Required("seconds"): _seconds,
        cv.Optional("to"): _note,
        cv.Optional("duty", default=0.5): cv.float_range(min=0.01, max=0.99),
        cv.Optional("attack", default=0.004): _seconds,
        cv.Optional("release", default=0.03): _seconds,
        cv.Optional("vibrato", default=0.0): cv.float_range(min=0.0, max=50.0),
    }
)
REST_SCHEMA = cv.Schema({cv.Required("rest"): _seconds})
ARP_SCHEMA = cv.Schema(
    {
        cv.Required("arp"): cv.All(cv.ensure_list(_note), cv.Length(min=1)),
        cv.Required("step"): _seconds,
        cv.Optional("duty", default=0.5): cv.float_range(min=0.01, max=0.99),
        cv.Optional("last"): _seconds,
    }
)


def _step(value):
    if isinstance(value, dict) and "rest" in value:
        return REST_SCHEMA(value)
    if isinstance(value, dict) and "arp" in value:
        return ARP_SCHEMA(value)
    return TONE_SCHEMA(value)


MAX_SECONDS = 2.0  # 192 kB rendered; keeps the sound cache's limit meaningful.


def _not_too_long(steps):
    total = sum(seconds for _, _, seconds, *_ in _expand(steps))
    if total > MAX_SECONDS:
        raise cv.Invalid(f"This sound lasts {total:.2f} s; keep it at {MAX_SECONDS:g} s or less")
    return steps


SOUNDS_SCHEMA = cv.Schema(
    {cv.string_strict: cv.All(cv.ensure_list(_step), cv.Length(min=1), _not_too_long)}
)


def _expand(steps):
    """Steps as (f0, f1, seconds, duty, attack, release, vibrato), arps unrolled like Synth::arp."""
    out = []
    for s in steps:
        if "rest" in s:
            out.append((0, 0, s["rest"], 0.5, 0.004, 0.03, 0))
        elif "arp" in s:
            notes = s["arp"]
            for i, f in enumerate(notes):
                last = i == len(notes) - 1
                seconds = (s.get("last") or s["step"] * 2) if last else s["step"]
                out.append((f, 0, seconds, s["duty"], 0.004, 0.08 if last else 0.012, 0))
        else:
            out.append((s["note"], s.get("to", 0), s["seconds"], s["duty"], s["attack"], s["release"], s["vibrato"]))
    return out


async def sounds_to_code(persona, config):
    """Gives the persona its own sounds from its `sounds:` option, if any."""
    for name, steps in config.get(CONF_SOUNDS, {}).items():
        items = ", ".join(
            "Daruma::Synth::Step{" + ", ".join(f"{float(v)!r}f" for v in step) + "}"
            for step in _expand(steps)
        )
        cg.add(persona.set_sound(name, cg.RawExpression(f"std::vector<Daruma::Synth::Step>{{{items}}}")))
