"""Scenario files: a demo or a test as a list of steps.

Each step is one harness call (harness.py), so a scenario reads like a
test written in Python:

    name: tour
    personas: all            # or a list of persona names
    test_personas: all       # personas the test mode checks (snapshots, expects)
    setup:                # optional: runs before the recording starts
      - set: {Outside temperature: 68}
    steps:
      - set: {Outside temperature: 68}
      - wait: 2
      - pet: true
      - expect: {state: petted}
      - snapshot: petted
      - tap: {text: Focus}

Steps:

    wait: 1.5                       advance the clock
    skip: 300                       advance fast; left out of the recording
    tap: [x, y]                     tap a point
    tap: {text: Unlock}             tap a part found by text (or role + name)
    tap: {role: button, name: Ok}
    hold: {at: [x, y], seconds: 2}
    swipe: {from: [x, y], to: [x, y], seconds: 0.25}
    stroke: [x, y]
    pet: true                       stroke the middle of the persona
    press: home                     a board input; or {input: home, seconds: 2}
    set: {Window: Rain}             entities by name, as HA sets them
    action: {name: wink}            any API action; other keys are its fields
    show: sad                       any registered state by name: a mood is
                                    forced, an activity held, a reaction played;
                                    show: "" ends the forced mood and activity
    voice: {phase: thinking, text: What's the weather?}
                                    the voice assistant's screen: listening,
                                    thinking, replying, error, timer or idle
    caption: Start a focus block    a caption under the screen in the GIF,
    steps:                          shown while the steps it holds run (the
      - tap: {text: Focus}          same keys; blocks may nest)
      - wait: 2
    message: {text: Hi, seconds: 5}
    prompt: {id: door, title: ..., options: [...], style: urgent}
    update_prompt: {id: quiz, marks: [correct]}
    snapshot: name                  compare with the golden picture (test mode)
    snapshot: {name: x, mask: [[x, y, w, h]], tolerance: 8, max_diff_pixels: 20}
    expect: {state: focus}          wait for it; fail after `timeout` (5 s)
    expect: {visible: {text: Unlock}}
    expect: {hidden: {role: dialog}}
    expect: {event: {type: esphome.daruma_prompt, choice: Unlock}}
    expect: {entity: {name: Pomodoro phase, value: focus}}

A scenario with `showcase: true` is one of the demos that together show
every state the build knows. covered_states() lists what one shows, and
demos/test_daruma.py checks that the showcase scenarios cover the registry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from harness import Device, DeviceError, Locator, expect

SCENARIO_DIR = Path(__file__).resolve().parent / "scenarios"


@dataclass
class Scenario:
    name: str
    path: Path
    steps: list[dict[str, Any]]
    setup: list[dict[str, Any]] = field(default_factory=list)
    personas: list[str] | str = "all"
    test_personas: list[str] | str = field(default_factory=list)
    description: str = ""
    showcase: bool = False
    gif_scale: int = 2  # The GIF's size: 2 = twice the screen, 1 = as the screen.

    def runs_on(self, persona: str, test: bool) -> bool:
        wanted = self.test_personas if test else self.personas
        return wanted == "all" or persona in (wanted or [])


def flatten(steps: list[dict[str, Any]], outer: str = "") -> list[dict[str, Any]]:
    """The steps as the runner takes them: each `caption` + `steps:` block
    becomes a caption step, the steps it holds, and a step back to the
    caption around it ("" at the top) where the block ends."""
    out: list[dict[str, Any]] = []
    for step in steps:
        if "caption" not in step:
            out.append(step)
            continue
        if set(step) != {"caption", "steps"} or not isinstance(step["steps"], list):
            raise DeviceError(f"A caption holds its steps: `caption: ...` and a `steps:` list. Got: {step}")
        text = str(step["caption"])
        out.append({"caption": text})
        out += flatten(step["steps"], text)
        out.append({"caption": outer})
    return out


def load(name_or_path: str) -> Scenario:
    path = Path(name_or_path)
    if not path.exists():
        path = SCENARIO_DIR / f"{name_or_path}.yaml"
    raw = yaml.safe_load(path.read_text())
    return Scenario(
        name=raw.get("name", path.stem),
        path=path,
        steps=flatten(raw["steps"]),
        setup=flatten(raw.get("setup", [])),
        personas=raw.get("personas", "all"),
        test_personas=raw.get("test_personas", []),
        description=raw.get("description", ""),
        showcase=bool(raw.get("showcase", False)),
        gif_scale=int(raw.get("gif_scale", 2)),
    )


def all_scenarios() -> list[Scenario]:
    return [load(str(p)) for p in sorted(SCENARIO_DIR.glob("*.yaml"))]


# The state each voice phase draws (packages/core.yaml, the renderer).
VOICE_STATES = {"listening": "listening", "thinking": "thinking", "replying": "talking", "error": "error",
                "timer": "alarm"}


def covered_states(scenario: Scenario) -> set[str]:
    """The states a scenario shows: by `show`, a voice phase, `pet`, or an
    `expect: {state: ...}` with one state (a list means any one of them)."""
    out: set[str] = set()
    for step in scenario.setup + scenario.steps:
        (kind, arg), = step.items()
        if kind == "show" and arg:
            out.add(arg)
        elif kind == "voice":
            phase = arg["phase"] if isinstance(arg, dict) else arg
            if phase in VOICE_STATES:
                out.add(VOICE_STATES[phase])
        elif kind == "pet":
            out.add("petted")
        elif kind == "expect" and isinstance(arg.get("state"), str):
            out.add(arg["state"])
    return out


def _locator(device: Device, spec: dict[str, Any]) -> Locator:
    if "text" in spec:
        return device.get_by_text(spec["text"], exact=spec.get("exact", True))
    if "role" in spec:
        return device.get_by_role(spec["role"], spec.get("name"))
    raise DeviceError(f"A part needs `text` or `role`: {spec}")


def run_step(device: Device, step: dict[str, Any], *, test: bool) -> None:
    """Run one step. Snapshots compare only in test mode."""
    if len(step) != 1:
        raise DeviceError(f"A step has one key: {step}")
    (kind, arg), = step.items()
    if kind == "wait":
        device.advance(float(arg))
    elif kind == "skip":
        device.skip(float(arg))
    elif kind == "tap":
        if isinstance(arg, dict):
            _locator(device, arg).tap(timeout=arg.get("timeout", 5))
        else:
            device.tap(*arg)
    elif kind == "hold":
        device.hold(*arg["at"], seconds=arg.get("seconds", 1.5))
    elif kind == "swipe":
        device.swipe(*arg["from"], *arg["to"], seconds=arg.get("seconds", 0.25))
    elif kind == "stroke":
        device.stroke(*arg)
    elif kind == "pet":
        device.pet()
    elif kind == "press":
        if isinstance(arg, dict):
            device.press(arg["input"], seconds=arg.get("seconds", 0.08))
        else:
            device.press(arg)
    elif kind == "set":
        for entity, value in arg.items():
            device.set(entity, value)
    elif kind == "action":
        data = dict(arg)
        device.action(data.pop("name"), **data)
    elif kind == "show":
        device.show(arg or "")
    elif kind == "voice":
        if isinstance(arg, dict):
            device.voice(arg["phase"], arg.get("text", ""))
        else:
            device.voice(arg)
    elif kind == "caption":
        device.caption(str(arg))
    elif kind == "message":
        device.show_message(arg["text"], arg.get("seconds", 5))
    elif kind == "prompt":
        device.show_prompt(**arg)
    elif kind == "update_prompt":
        device.update_prompt(**arg)
    elif kind == "snapshot":
        if test:
            spec = {"name": arg} if isinstance(arg, str) else dict(arg)
            expect(device).to_match_screenshot(
                spec["name"], mask=[tuple(m) for m in spec.get("mask", [])],
                tolerance=spec.get("tolerance", 0), max_diff_pixels=spec.get("max_diff_pixels", 0))
    elif kind == "expect":
        _expect(device, dict(arg))
    else:
        raise DeviceError(f"Unknown step {kind!r}")


def _expect(device: Device, spec: dict[str, Any]) -> None:
    timeout = spec.pop("timeout", 5)
    for kind, arg in spec.items():
        if kind == "state":
            expect(device).to_have_state(arg, timeout=timeout)
        elif kind == "visible":
            expect(_locator(device, arg)).to_be_visible(timeout=timeout)
        elif kind == "hidden":
            expect(_locator(device, arg)).to_be_hidden(timeout=timeout)
        elif kind == "event":
            data = dict(arg)
            expect(device).to_fire_event(data.pop("type"), timeout=timeout, **data)
        elif kind == "entity":
            expect(device).to_have_entity(arg["name"], arg["value"], timeout=timeout)
        else:
            raise DeviceError(f"Unknown expectation {kind!r}")


def run_setup(device: Device, scenario: Scenario) -> None:
    for step in scenario.setup:
        run_step(device, step, test=False)


def run(device: Device, scenario: Scenario, *, test: bool) -> None:
    for i, step in enumerate(scenario.steps, 1):
        try:
            run_step(device, step, test=test)
        except AssertionError as e:
            raise AssertionError(f"{scenario.name} step {i} {step}: {e}") from e
