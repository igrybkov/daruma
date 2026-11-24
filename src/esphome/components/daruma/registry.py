"""The Daruma registry: states, behaviors, modules, inputs and bindings.

Plain Python with no ESPHome imports, so the build checks can be tested on
their own (tests/test_registry.py). The ESPHome side
(__init__.py) collects the facts from the config, calls these functions in
its final validation step, and turns RegistryError into a config error.

States
------
Every state the core or a module can ask a persona to show is declared
once, with a kind and an optional fallback:

    mood      set by happiness and the mood select; lasts minutes
    activity  set by modules as a stack (focus, listening, ...)
    reaction  one-shot (petted, celebrate, ...); `duration` long, or sound
              only when the duration is 0

A persona that has no behavior for a state shows its fallback, and so on
down the chain. Only `neutral` has no fallback: every persona must have it.

Behaviors
---------
A persona's behavior for a state is an animation, a sound and optional
words. The animation is the one the persona's `behaviors:` names, or else
the one named like the state (any case: `focus` finds `Focus`), or else the
fallback's. The sound is the behavior's own, or else the state's default.
A sound does not follow the fallback: `petted` falling back to `loved` still
plays the `pet` sound.

A reaction shows over an activity, which stays on underneath. A persona
may give a reaction's animation a variant per activity (`during:`), so
props of the activity (the daruma's incense) stay in the picture.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

MOOD = "mood"
ACTIVITY = "activity"
REACTION = "reaction"
KINDS = (MOOD, ACTIVITY, REACTION)

# The built-in synth sounds (daruma/synth.cpp). A persona may add more.
BUILTIN_SOUNDS = ("start", "pause", "stop", "focus_done", "goal", "break_over", "pet", "timer", "notify", "urgent")


class RegistryError(ValueError):
    """A config problem the build must stop on. The message says what to fix."""


@dataclass(frozen=True)
class State:
    name: str
    kind: str
    fallback: str | None = None
    sound: str | None = None  # Default sound when the state starts.
    duration_ms: int = 0  # Reactions only: how long it shows. 0 = sound only.
    module: str = "core"
    # Activities only: random events wait while it is on (pomodoro's focus).
    quiet: bool = False


# The core's states. Modules add their own (each with a fallback).
CORE_STATES: tuple[State, ...] = (
    State("neutral", MOOD),
    State("happy", MOOD, "neutral"),
    State("sad", MOOD, "neutral"),
    State("loved", MOOD, "happy"),
    State("scared", MOOD, "neutral"),
    State("sleepy", MOOD, "neutral"),
    State("sleeping", MOOD, "sleepy"),
    State("listening", ACTIVITY, "neutral"),
    State("thinking", ACTIVITY, "neutral"),
    State("talking", ACTIVITY, "happy"),
    State("alarm", ACTIVITY, "scared", sound="timer"),
    State("offline", ACTIVITY, "sad"),
    State("error", ACTIVITY, "sad"),
    State("waking", ACTIVITY, "sleeping"),
    State("attention", ACTIVITY, "neutral"),
    State("petted", REACTION, "loved", sound="pet", duration_ms=2000),
    State("startled", REACTION, "scared", duration_ms=2000),
    State("celebrate", REACTION, "loved", duration_ms=3000),
    # Today's goal moved up a stage (the goal signal). Only a persona with
    # a look of its own for it plays it, such as the daruma painting an eye;
    # for the others the module's own reaction shows. As long as the
    # daruma's Paint, so it ends on its last frame.
    State("paint", REACTION, "celebrate", duration_ms=2700),
)

_NAME = re.compile(r"^[a-z][a-z0-9_]*$")
_ACTION = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")


@dataclass
class ModuleSpec:
    """What one module adds. Built from a `daruma: modules:` entry or a
    component's DARUMA_MODULE."""

    name: str
    states: list[State] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    apps: list[str] = field(default_factory=list)
    progress: list[str] = field(default_factory=list)
    colors: dict[str, int] = field(default_factory=dict)  # Theme keys without the module prefix.
    words: dict[str, str] = field(default_factory=dict)
    bindings: dict[str, str] = field(default_factory=dict)  # Default bindings: "input.gesture" -> action.
    # Adds context-dependent buttons to menus (a menu provider), so a menu
    # may list the module's name.
    menu: bool = False
    # Button looks of its actions, so a menu may list one: action -> {label, icon, color}.
    buttons: dict[str, dict] = field(default_factory=dict)
    # Menus it offers by default: name -> items. The device's `menus:` wins per name.
    menus: dict[str, list] = field(default_factory=dict)
    # Tap areas it draws on the device's own screen (plaque, badge, ...).
    areas: list[str] = field(default_factory=list)
    # Default targets: area -> {"app": id} | {"menu": name} | {"action": name} | "none".
    targets: dict[str, object] = field(default_factory=dict)
    # Old theme keys that still work: old -> new, both without the module prefix.
    aliases: dict[str, str] = field(default_factory=dict)


def check_name(name: str, what: str) -> str:
    if not _NAME.match(name):
        raise RegistryError(f"{what} '{name}': use lowercase letters, digits and _, starting with a letter")
    return name


def _check_module_state(module: ModuleSpec, state: State, seen: dict[str, State]) -> None:
    check_name(state.name, "State")
    if state.name in seen:
        raise RegistryError(
            f"Module '{module.name}' declares state '{state.name}', which {seen[state.name].module} already declares"
        )
    if state.kind not in KINDS:
        raise RegistryError(f"State '{state.name}': kind must be one of {', '.join(KINDS)}")
    if state.quiet and state.kind != ACTIVITY:
        raise RegistryError(f"State '{state.name}': only an activity can be quiet, not a {state.kind}")
    if state.fallback is None:
        raise RegistryError(
            f"Module '{module.name}': state '{state.name}' needs a fallback, so personas "
            "that lack it still show something"
        )


def collect_states(modules: list[ModuleSpec]) -> list[State]:
    """Core states first, then each module's, in module order. Checks names,
    kinds and fallbacks."""
    states = list(CORE_STATES)
    seen = {s.name: s for s in states}
    for module in modules:
        for state in module.states:
            _check_module_state(module, state, seen)
            seen[state.name] = state
            states.append(state)
    for state in states:
        if state.fallback is not None and state.fallback not in seen:
            raise RegistryError(f"State '{state.name}' falls back to '{state.fallback}', which no one declares")
    # No loops: every chain ends at a state without a fallback.
    for state in states:
        chain, current = [state.name], state
        while current.fallback is not None:
            if current.fallback in chain:
                raise RegistryError(f"Fallback loop: {' -> '.join(chain + [current.fallback])}")
            chain.append(current.fallback)
            current = seen[current.fallback]
    return states


def fallback_chain(states: list[State], name: str) -> list[str]:
    by_name = {s.name: s for s in states}
    chain = [name]
    while by_name[chain[-1]].fallback is not None:
        chain.append(by_name[chain[-1]].fallback)
    return chain


@dataclass
class Persona:
    """One persona, as the build sees it."""

    id: str
    animations: list[str]  # In the order the persona stores them.
    behaviors: dict[str, dict] = field(default_factory=dict)  # state -> {animation, sound, say}
    sounds: list[str] = field(default_factory=list)  # The persona's own `sounds:`.
    # activity -> {animation -> animation}: while that activity is on, a
    # reaction that would play the first animation plays the second.
    during: dict[str, dict[str, str]] = field(default_factory=dict)
    # name -> event, as random_events.py describes them.
    random_events: dict[str, dict] = field(default_factory=dict)
    # False for a persona that plays say-only events (images).
    event_animations: bool = True


@dataclass(frozen=True)
class During:
    """While `activity` is on, a reaction that would play animation `shown`
    plays `instead` (indices into Persona.animations)."""

    activity: int  # Index of the activity state, in registry order.
    shown: int
    instead: int


def resolve_during(char: Persona, states: list[State]) -> list[During]:
    """The persona's `during:` table, checked. A reaction replaces what
    is on screen, so an activity's props (incense, a book) would vanish
    while it plays; this names the animations that keep them."""
    index = {s.name: i for i, s in enumerate(states)}
    out = []
    for activity, swaps in char.during.items():
        if activity not in index:
            raise RegistryError(f"{char.id}: during: unknown state '{activity}'")
        if states[index[activity]].kind != ACTIVITY:
            raise RegistryError(
                f"{char.id}: during: '{activity}' is a {states[index[activity]].kind}; only an activity "
                "stays on under a reaction"
            )
        for shown, instead in swaps.items():
            for anim in (shown, instead):
                if anim not in char.animations:
                    raise RegistryError(
                        f"{char.id}: during: {activity}: no animation '{anim}' (it has: {', '.join(char.animations)})"
                    )
            out.append(During(index[activity], char.animations.index(shown), char.animations.index(instead)))
    return out


@dataclass
class Behavior:
    animation: int  # Index into Persona.animations.
    sound: str  # "" for none.
    say: str  # "" for none.
    shown_as: str  # The state whose look this is (itself, or a fallback).


def resolve_persona(char: Persona, states: list[State]) -> tuple[list[Behavior], list[str]]:
    """The behavior for every state, in registry order, and the build log
    lines for states shown through a fallback. Raises RegistryError for an
    unknown state, animation or sound, or a state with no look at all."""
    by_name = {s.name: s for s in states}
    for name in char.behaviors:
        if name not in by_name:
            close = [s for s in by_name if s.startswith(name[:3])]
            hint = f" (did you mean {', '.join(close)}?)" if close else ""
            raise RegistryError(f"{char.id}: behaviors: unknown state '{name}'{hint}")
    known_sounds = set(BUILTIN_SOUNDS) | set(char.sounds)
    lower = {a.lower(): i for i, a in enumerate(char.animations)}

    def own_animation(name: str) -> int | None:
        behavior = char.behaviors.get(name, {})
        if "animation" in behavior:
            anim = behavior["animation"]
            if anim not in char.animations:
                raise RegistryError(
                    f"{char.id}: behavior '{name}' uses animation '{anim}', which it does not have "
                    f"(it has: {', '.join(char.animations)})"
                )
            return char.animations.index(anim)
        return lower.get(name)

    out, log = [], []
    for state in states:
        chain = fallback_chain(states, state.name)
        anim, shown_as = None, None
        for step in chain:
            anim = own_animation(step)
            if anim is not None:
                shown_as = step
                break
        if anim is None:
            raise RegistryError(
                f"{char.id}: has no look for '{state.name}' and no fallback reaches one (tried {' -> '.join(chain)})"
            )
        behavior = char.behaviors.get(state.name, {})
        sound = behavior.get("sound", state.sound) or ""
        if sound and sound not in known_sounds:
            raise RegistryError(
                f"{char.id}: state '{state.name}' plays sound '{sound}', which is neither built in "
                f"({', '.join(BUILTIN_SOUNDS)}) nor in its sounds:"
            )
        if shown_as != state.name:
            log.append(f"{char.id}: {state.name} -> {shown_as}")
        out.append(Behavior(anim, sound, behavior.get("say", ""), shown_as))
    return out, log


# Random event keys that draw an animation (random_events.py).
EVENT_ANIMATION_KEYS = ("animation", "enter", "exit", "for")


def check_say_only(where: str, event: dict) -> None:
    """A persona without event animations (images) only says and sounds."""
    used = [key for key in EVENT_ANIMATION_KEYS if key in event]
    if used:
        raise RegistryError(f"{where}: the images persona plays say-only events; drop {', '.join(used)}")


def _event_animation(char: Persona, where: str, anim: str) -> None:
    if anim in char.animations:
        return
    close = [a for a in char.animations if a.lower() == anim.lower()]
    hint = f"did you mean '{close[0]}'?" if close else f"it has: {', '.join(char.animations)}"
    raise RegistryError(f"{where}: no animation '{anim}' ({hint})")


def _state_look(char: Persona, states: list[State], anim: str) -> str | None:
    """The state whose look `anim` also is: named like it, any case, with
    no `behaviors:` entry pointing that state elsewhere."""
    for state in states:
        if state.name == anim.lower() and "animation" not in char.behaviors.get(state.name, {}):
            return state.name
    return None


def _check_event_moods(where: str, event: dict, states: list[State]) -> None:
    moods = [s.name for s in states if s.kind == MOOD]
    for mood in event.get("when", {}).get("moods", []):
        if mood not in moods:
            raise RegistryError(f"{where}: moods: '{mood}' is no mood (moods: {', '.join(moods)})")


def resolve_random_events(char: Persona, states: list[State]) -> list[str]:
    """Checks the persona's events against its animations, the registry's
    moods and its sounds. Returns build log lines for event animations
    that are also a state's look, so a module that later adds a state
    named like a quirk shows up in the log."""
    sounds = set(BUILTIN_SOUNDS) | set(char.sounds)
    log = []
    for name, event in char.random_events.items():
        where = f"{char.id}: random_events: {name}"
        if not char.event_animations:
            check_say_only(where, event)
        for anim in (event[key] for key in ("enter", "animation", "exit") if key in event):
            _event_animation(char, where, anim)
            state = _state_look(char, states, anim)
            if state is not None:
                log.append(f"{char.id}: random event animation '{anim}' is also the look of state '{state}'")
        _check_event_moods(where, event, states)
        if "sound" in event and event["sound"] not in sounds:
            raise RegistryError(
                f"{where}: sound '{event['sound']}' is neither built in "
                f"({', '.join(BUILTIN_SOUNDS)}) nor in its sounds:"
            )
    return log


# --- Inputs ----------------------------------------------------------------------

BUTTON = "button"
TOUCH = "touch"
# Gestures each kind of input can offer. `swipe` in a board's list stands for
# all four directions.
GESTURES = {
    BUTTON: ("press", "double", "hold"),
    TOUCH: ("tap", "double", "hold", "long_hold", "swipe_left", "swipe_right", "swipe_up", "swipe_down", "stroke"),
}
NAVIGATION = ("back", "close", "next", "prev", "select")


@dataclass
class Input:
    name: str
    kind: str
    gestures: list[str]


def expand_gestures(kind: str, gestures: list[str]) -> list[str]:
    out = []
    for g in gestures:
        if g == "swipe" and kind == TOUCH:
            out += ["swipe_left", "swipe_right", "swipe_up", "swipe_down"]
        elif g in GESTURES[kind]:
            out.append(g)
        else:
            raise RegistryError(f"A {kind} input has no gesture '{g}' (it can have: {', '.join(GESTURES[kind])})")
    return list(dict.fromkeys(out))


def split_trigger(trigger: str, inputs: dict[str, Input]) -> tuple[str, str]:
    """'home.press' -> ('home', 'press'), checked against the board."""
    if "." not in trigger:
        raise RegistryError(f"'{trigger}': name an input and a gesture, like home.press")
    name, gesture = trigger.split(".", 1)
    if name not in inputs:
        raise RegistryError(f"'{trigger}': the board has no input '{name}' (it has: {', '.join(inputs) or 'none'})")
    if gesture not in inputs[name].gestures:
        raise RegistryError(
            f"'{trigger}': input '{name}' has no gesture '{gesture}' (it has: {', '.join(inputs[name].gestures)})"
        )
    return name, gesture


@dataclass
class Binding:
    input: str
    gesture: str
    action: str
    idle: bool  # Runs only on the device's own screen (no menu, app or prompt open).
    source: str  # "device" or the module that offered it as a default.


def check_navigation(inputs: dict[str, Input], navigation: dict[str, str]) -> dict[str, tuple[str, str]]:
    """Each navigation key -> (input, gesture). The board must be able to leave
    the menu: `back` always, and without touch also next, prev and select."""
    out = {}
    for key, trigger in navigation.items():
        if key not in NAVIGATION:
            raise RegistryError(f"navigation: unknown key '{key}' (keys: {', '.join(NAVIGATION)})")
        out[key] = split_trigger(trigger, inputs)
    if "back" not in out:
        raise RegistryError("navigation: every board needs `back`, or the menu could never be left")
    if not any(i.kind == TOUCH for i in inputs.values()):
        missing = [k for k in ("next", "prev", "select") if k not in out]
        if missing:
            raise RegistryError(f"navigation: a board without touch also needs {', '.join(missing)}")
    return out


OPEN_MENU = "menu.open"


def menu_action(action: str, menu: str | None) -> str:
    """A binding's action as the hub runs it: `menu.open` with a menu becomes
    `menu.open:<menu>`."""
    if menu is None:
        return action
    if action != OPEN_MENU:
        raise RegistryError(f"`menu: {menu}` goes only with the action {OPEN_MENU}, not '{action}'")
    return f"{OPEN_MENU}:{menu}"


def _check_action(action: str, actions: set[str], menus) -> str | None:
    """Why `action` can't run, or None. `menu.open:<name>` needs that menu."""
    if action == "none":
        return None
    base, _, menu = action.partition(":")
    if base not in actions:
        # pragma: no mutate block, message text
        return f"'{base}', which no included module offers (offered: {', '.join(sorted(actions))})"
    if menu and menu not in menus:
        # pragma: no mutate block, message text
        return f"the menu '{menu}', which is not defined (menus: {', '.join(sorted(menus)) or 'none'})"
    return None


def resolve_bindings(
    inputs: dict[str, Input],
    navigation: dict[str, tuple[str, str]],
    device: dict[str, dict],
    modules: list[ModuleSpec],
    actions: set[str],
    menus=(),
) -> tuple[list[Binding], list[str]]:
    """The bindings in force: the device yaml's, then module defaults for
    triggers it leaves free. Returns them and the build log lines.

    A module default for an input the board lacks is skipped (and logged).
    Two modules other than the core `daruma` module offering different actions
    for one trigger is an error: the device yaml must pick one."""
    log = []
    nav_triggers = {v: k for k, v in navigation.items()}
    bindings: dict[tuple[str, str], Binding] = {}
    for trigger, conf in device.items():
        name, gesture = split_trigger(trigger, inputs)
        action = menu_action(conf["action"], conf.get("menu"))
        problem = _check_action(action, actions, menus)
        if problem:
            raise RegistryError(f"bindings: '{trigger}' runs {problem}")
        idle = conf.get("when") == "idle"
        if (name, gesture) in nav_triggers and not idle and inputs[name].kind != TOUCH:
            raise RegistryError(
                f"bindings: '{trigger}' is also navigation '{nav_triggers[(name, gesture)]}'; "
                "add `when: idle` so it runs only on the device's own screen"
            )
        bindings[(name, gesture)] = Binding(name, gesture, action, idle, "device")

    defaults: dict[tuple[str, str], Binding] = {}
    # The core module goes first, so any other module's default wins over it.
    for module in sorted(modules, key=lambda m: m.name != "daruma"):
        for trigger, action in module.bindings.items():
            # A trigger with a second dot is skipped below either way.
            name, _, gesture = trigger.partition(".")  # pragma: no mutate
            if name not in inputs or gesture not in inputs[name].gestures:
                log.append(f"{module.name}: default binding {trigger} -> {action} skipped; the board has no {trigger}")
                continue
            owner_module = action.partition(".")[0]
            if action != "none" and owner_module not in {m.name for m in modules}:
                log.append(
                    f"{module.name}: default binding {trigger} -> {action} skipped; "
                    f"no module '{owner_module}' is included"
                )
                continue
            problem = _check_action(action, actions, menus)
            if problem:
                raise RegistryError(f"Module '{module.name}' binds {trigger} to {problem}")
            key = (name, gesture)
            if key in bindings:
                continue
            old = defaults.get(key)
            if old is not None and old.source != "daruma" and old.action != action:
                raise RegistryError(
                    f"Modules '{old.source}' and '{module.name}' both bind {trigger} "
                    f"({old.action}, {action}); pick one under daruma: bindings:"
                )
            # Screen gestures on a touch input only ever act on the device's own screen.
            idle = key in nav_triggers or inputs[name].kind == TOUCH
            defaults[key] = Binding(name, gesture, action, idle, module.name)
    for key, binding in defaults.items():
        bindings[key] = binding
        log.append(f"{binding.source}: default binding {binding.input}.{binding.gesture} -> {binding.action}")
    return list(bindings.values()), log


def check_menu_reachable(inputs: dict[str, Input], bindings: list[Binding], modules: list[ModuleSpec]) -> None:
    """On a board without touch, the menu's own default (a tap on the screen)
    does not exist. When the menu is included, a binding must open it."""
    if any(i.kind == TOUCH for i in inputs.values()):
        return
    if not any(m.name == "menu" for m in modules):
        return
    if not any(b.action.partition(":")[0] == OPEN_MENU for b in bindings):
        raise RegistryError(
            "bindings: this board has no touch, so nothing opens the menu; bind menu.open to a button, "
            "like `home.press: { action: menu.open, when: idle }`"
        )


# --- Display profile ------------------------------------------------------------

COLOR_MODES = ("full", "gray4", "mono")


@dataclass
class Profile:
    """What the screen can do (the board's `display_profile:`)."""

    colors: str = "full"
    animate: bool = True
    min_frame_ms: int = 100
    partial_refresh: bool = True
    full_refresh_every: int = 0

    @property
    def slow(self) -> bool:
        """Clocks and countdowns show minutes and redraw once a minute."""
        return self.min_frame_ms >= 1000


def check_profile(profile: Profile) -> None:
    """Combinations that cannot work on a real screen."""
    if profile.colors not in COLOR_MODES:
        raise RegistryError(f"display_profile: colors must be one of {', '.join(COLOR_MODES)}")
    if profile.animate and profile.min_frame_ms >= 1000:
        raise RegistryError(
            "display_profile: animate needs min_frame under 1s; a slower screen shows still frames (set animate: false)"
        )
    if profile.full_refresh_every and not profile.partial_refresh:
        raise RegistryError(
            "display_profile: full_refresh_every counts partial refreshes; it needs partial_refresh: true"
        )


def collect_actions(modules: list[ModuleSpec]) -> set[str]:
    actions: dict[str, str] = {}
    for module in modules:
        for action in module.actions:
            if not _ACTION.match(action):
                raise RegistryError(f"Module '{module.name}': action '{action}' must look like {module.name}.verb")
            if action.split(".")[0] != module.name:
                raise RegistryError(f"Module '{module.name}': action '{action}' must start with '{module.name}.'")
            if action in actions:
                raise RegistryError(f"Action '{action}' is offered by both '{actions[action]}' and '{module.name}'")
            actions[action] = module.name
    return set(actions)


def check_modules(modules: list[ModuleSpec]) -> None:
    seen = set()
    for module in modules:
        check_name(module.name, "Module")
        if module.name in seen:
            raise RegistryError(
                f"Two modules are named '{module.name}'. An app package included twice needs its own "
                "app_id in each include's vars"
            )
        seen.add(module.name)


def order_apps(order: list[str], modules: list[ModuleSpec]) -> tuple[list[str], list[str]]:
    """The board order: the device's `apps:` list, then any app it leaves out.
    Unknown names are an error."""
    offered, owner = [], {}
    for module in modules:
        for app in module.apps:
            if app in owner:
                raise RegistryError(
                    f"Two modules offer the app '{app}' ({owner[app]} and {module.name}). Give each copy "
                    "of an app its own app_id"
                )
            owner[app] = module.name
            offered.append(app)
    for app in order:
        if app not in offered:
            raise RegistryError(f"apps: no included module offers an app '{app}' (offered: {', '.join(offered)})")
    if len(set(order)) != len(order):
        raise RegistryError("apps: an app is listed twice")
    rest = [a for a in offered if a not in order]
    log = [f"apps: '{a}' is not in the apps: list; it goes last" for a in rest]
    return order + rest, log


def check_progress(weights: dict[str, float], modules: list[ModuleSpec]) -> list[str]:
    """Every weighted progress source must be fed by a module. Returns the
    sources in use: the weighted ones, or every offered one at weight 1."""
    offered = []
    for module in modules:
        offered += module.progress
    for name in weights:
        if name not in offered:
            raise RegistryError(
                f"progress: no included module feeds a source '{name}' (fed: {', '.join(offered) or 'none'})"
            )
    return list(weights) if weights else offered


def theme_aliases(modules: list[ModuleSpec]) -> dict[str, str]:
    """Old theme keys that still work, with the module prefix: old -> new."""
    out = {}
    for m in modules:
        for old, new in m.aliases.items():
            if new not in m.colors and new not in m.words:
                raise RegistryError(
                    f"Module '{m.name}': theme alias '{old}' points at '{new}', which it does not declare"
                )
            out[f"{m.name}.{old}"] = f"{m.name}.{new}"
    return out


def resolve_theme_key(key: str, aliases: dict[str, str]) -> str:
    """The key a theme sets: itself, or the new name of an old one."""
    return aliases.get(key, key)


def check_theme_keys(
    persona_id: str, colors: dict, words: dict, modules: list[ModuleSpec], builtin_words: tuple[str, ...] = ()
) -> None:
    """A persona's module theme keys (`pomodoro.focus`) must be declared by an
    included module, as a color or a word as used. Old keys a module keeps
    as aliases count as their new ones."""
    aliases = theme_aliases(modules)
    colors = {resolve_theme_key(k, aliases): v for k, v in colors.items()}
    words = {resolve_theme_key(k, aliases): v for k, v in words.items()}
    declared_colors = {f"{m.name}.{k}" for m in modules for k in m.colors}
    declared_words = {f"{m.name}.{k}" for m in modules for k in m.words} | set(builtin_words)
    names = {m.name for m in modules}
    for key in colors:
        if key not in declared_colors:
            raise RegistryError(_theme_error(persona_id, "color", key, names, declared_colors))
    for key in words:
        if key not in declared_words:
            raise RegistryError(_theme_error(persona_id, "word", key, names, declared_words))


def _theme_error(persona_id, what, key, names, declared):
    prefix = key.split(".")[0]
    if prefix not in names:
        return f"{persona_id}: theme {what} '{key}': no included module is named '{prefix}'"
    # pragma: no mutate block, message text
    mine = sorted(k for k in declared if k.startswith(prefix + "."))
    return f"{persona_id}: theme {what} '{key}' is not one of {prefix}'s: {', '.join(mine) or 'none'}"


def check_params(declared: list[tuple[str, str]]) -> None:
    """(persona id, param name) pairs; full names must not clash."""
    seen = set()
    for char_id, name in declared:
        full = f"{char_id}.{name}"
        if full in seen:
            raise RegistryError(f"Two personas declare the param '{full}'")
        seen.add(full)


# --- Menus -----------------------------------------------------------------------

MAIN_MENU = "main"
MORE = "more"
# What a menu item is, in the order the hub numbers them (MenuEntry::Kind).
MENU_KINDS = ("module", "app", "action", "more", "menu", "event")
# Apps the default main menu offers when the build has them.
DEFAULT_MENU_APPS = ("tasks", "calendar")


@dataclass
class MenuItemSpec:
    kind: str  # One of MENU_KINDS.
    id: str  # Module, app, action, menu or event name; "" for more.
    label: str = ""
    icon: str = ""
    color: str = ""  # A theme key ("pomodoro.break") or 6-digit hex; "" for the theme's default.


def collect_menus(device: dict[str, list] | None, modules: list[ModuleSpec]) -> tuple[dict[str, list], list[str]]:
    """The menus in force: each module's defaults, then the device's, which
    win per name. Without a `main`, the default one: the buttons of every
    module that has no menu of its own (pomodoro's are in its `pomodoro`
    menu, on a button), then Tasks and Calendar when the build has them.
    Returns the raw item lists and build log lines."""
    log = []
    menus: dict[str, list] = {}
    owner: dict[str, str] = {}
    device = device or {}
    for module in modules:
        for name, items in module.menus.items():
            check_name(name, "Menu")
            if name in device:
                log.append(f"menus: '{name}' from the device yaml replaces {module.name}'s")
                continue
            if name in owner:
                raise RegistryError(
                    f"Modules '{owner[name]}' and '{module.name}' both offer the menu '{name}'; "
                    "define it under daruma: menus:"
                )
            owner[name] = module.name
            menus[name] = list(items)
    for name, items in device.items():
        check_name(name, "Menu")
        menus[name] = list(items)
    if MAIN_MENU not in menus:
        apps = [a for m in modules for a in m.apps]
        menus[MAIN_MENU] = [m.name for m in modules if m.menu and not m.menus] + [
            a for a in DEFAULT_MENU_APPS if a in apps
        ]
        log.append(f"menus: main is {', '.join(menus[MAIN_MENU]) or 'empty'} (the default)")
    return menus, log


def resolve_menus(
    menus: dict[str, list], modules: list[ModuleSpec], actions: set[str]
) -> dict[str, list[MenuItemSpec]]:
    """Every menu's items, checked. An item is:

    - `more`: the app board;
    - an app id: opens the app;
    - a module's name: that module's buttons for the moment (it must declare `menu: true`);
    - a menu's name: opens that menu. An app id comes first, then a module,
      so a menu named like a module (`pomodoro`) can be bound but not nested;
    - an action (`pomodoro.break`): one button, looking as its module's `buttons:` says;
    - `{label, icon, event}`: a button that fires the HA event
      `esphome.daruma_menu` with `event: <event>` in its data.

    `main` ends with `more` when it does not list it and the build has apps,
    so the app board stays reachable."""
    apps = {a for m in modules for a in m.apps}
    menu_modules = {m.name for m in modules if m.menu}
    looks = {a: look for m in modules for a, look in m.buttons.items()}
    for module in modules:
        for action in module.buttons:
            if action not in module.actions:
                raise RegistryError(f"Module '{module.name}': buttons: '{action}' is not one of its actions")
    if not any(m.name == "menu" for m in modules):
        return {}  # No menu to show them; check_menus_included() catches a device that wants some.
    for name in menus:
        check_name(name, "Menu")
        if name == MORE:
            raise RegistryError("menus: 'more' is the app board's item; give the menu another name")

    out = {}
    for name, items in menus.items():
        specs = []
        for item in items:
            spec = _menu_item(name, item, menus, apps, menu_modules, actions, looks)
            if spec.kind != "event" and any(s.kind == spec.kind and s.id == spec.id for s in specs):
                raise RegistryError(f"menus: {name}: '{spec.id or spec.kind}' is listed twice")
            specs.append(spec)
        if name == MAIN_MENU and apps and not any(s.kind == "more" for s in specs):
            specs.append(MenuItemSpec("more", ""))
        if not specs:
            raise RegistryError(f"menus: {name} has no items")
        out[name] = specs
    return out


def check_menus_included(device: dict, modules: list[ModuleSpec]) -> None:
    if device and not any(m.name == "menu" for m in modules):
        raise RegistryError("menus: they need the menu (include menu.yaml)")


def _menu_item(menu, item, menus, apps, menu_modules, actions, looks) -> MenuItemSpec:
    if isinstance(item, dict):
        missing = [k for k in ("label", "icon", "event") if not item.get(k)]
        if missing:
            raise RegistryError(f"menus: {menu}: an event button needs {', '.join(missing)}")
        check_name(item["event"], "Event")
        return MenuItemSpec("event", item["event"], item["label"], item["icon"], item.get("color", ""))
    if item == MORE:
        return MenuItemSpec("more", "")
    if "." in item:
        if item not in actions:
            raise RegistryError(
                f"menus: {menu}: no included module offers the action '{item}' (offered: {', '.join(sorted(actions))})"
            )
        look = looks.get(item)
        if look is None:
            buttons = sorted(looks)
            raise RegistryError(
                f"menus: {menu}: the action '{item}' has no button look; its module declares them under "
                f"`buttons:` (actions with one: {', '.join(buttons) or 'none'})"
            )
        return MenuItemSpec("action", item, look["label"], look["icon"], look.get("color", ""))
    if item in apps:
        return MenuItemSpec("app", item)
    if item in menu_modules:
        return MenuItemSpec("module", item)
    if item in menus:
        if item == menu:
            raise RegistryError(f"menus: {menu} lists itself")
        return MenuItemSpec("menu", item, item.replace("_", " ").capitalize())
    choices = sorted(apps) + sorted(menu_modules) + sorted(n for n in menus if n != menu) + [MORE]
    raise RegistryError(
        f"menus: {menu}: '{item}' is no app, module with buttons, menu or action "
        f"(choose from: {', '.join(choices)}, or an action with a button look)"
    )


def check_device_themes(
    theme: dict, themes: dict, persona_ids: list[str], modules: list[ModuleSpec], builtin_words: tuple[str, ...] = ()
) -> None:
    """The device yaml's `theme:` (every persona) and `themes:` (one persona each, by
    persona id). Their keys are checked like a persona's own; a persona id must name
    a persona in the build."""
    check_theme_keys("daruma: theme", theme.get("colors", {}), theme.get("words", {}), modules, builtin_words)
    for persona_id, conf in themes.items():
        if persona_id not in persona_ids:
            raise RegistryError(
                f"daruma: themes: no persona has the id '{persona_id}' "
                f"(persona ids: {', '.join(persona_ids) or 'none'})"
            )
        check_theme_keys(
            f"daruma: themes: {persona_id}", conf.get("colors", {}), conf.get("words", {}), modules, builtin_words
        )


# --- Tap areas ---------------------------------------------------------------------

OPEN_APP = "menu.app"
TARGET_KINDS = ("app", "menu", "action")


def target_action(target) -> str:
    """A target as the hub runs it: `menu.app:<app>`, `menu.open:<menu>`, an
    action, or `none`."""
    if target == "none":
        return "none"
    kind, value = next(iter(target.items()))
    if kind == "app":
        return f"{OPEN_APP}:{value}"
    if kind == "menu":
        return f"{OPEN_MENU}:{value}"
    return value


def _target_problem(target, modules: list[ModuleSpec], actions: set[str], menus) -> str | None:
    """Why a target can't work, or None."""
    if target == "none":
        return None
    kind, value = next(iter(target.items()))
    has_menu = any(m.name == "menu" for m in modules)
    if kind in ("app", "menu") and not has_menu:
        # pragma: no mutate block, message text
        return f"opens {'an app' if kind == 'app' else 'a menu'}, which needs the menu (include menu.yaml)"
    if kind == "app":
        apps = [a for m in modules for a in m.apps]
        if value not in apps:
            # pragma: no mutate block, message text
            return f"opens the app '{value}', which no included module offers (apps: {', '.join(apps) or 'none'})"
        return None
    if kind == "menu":
        if value not in menus:
            # pragma: no mutate block, message text
            return f"opens the menu '{value}', which is not defined (menus: {', '.join(sorted(menus)) or 'none'})"
        return None
    problem = _check_action(value, actions, menus)
    return f"runs {problem}" if problem else None


def resolve_targets(
    device: dict, modules: list[ModuleSpec], actions: set[str], menus=()
) -> tuple[dict[str, str], list[str]]:
    """What a tap on each area does: the device yaml's `targets:`, then module
    defaults for areas it leaves out. Returns area -> action (as the hub
    runs it) and build log lines.

    An area must be one some module draws. A module default that names an
    app, menu or action the build lacks is skipped and logged, like default
    bindings. Two modules offering different defaults for one area: the
    first in the config wins, and the build log says so (copies of an app
    share an area this way)."""
    log = []
    areas: set[str] = set()
    for m in modules:
        for area in m.areas:
            check_name(area, "Tap area")
            areas.add(area)
    out: dict[str, str] = {}
    for area, target in device.items():
        if area not in areas:
            raise RegistryError(
                f"targets: no included module draws an area '{area}' (areas: {', '.join(sorted(areas)) or 'none'})"
            )
        problem = _target_problem(target, modules, actions, menus)
        if problem:
            raise RegistryError(f"targets: '{area}' {problem}")
        out[area] = target_action(target)
    chosen: dict[str, str] = {}
    for m in modules:
        for area, target in m.targets.items():
            if area not in areas:
                log.append(f"{m.name}: default target for '{area}' skipped; no included module draws it")
                continue
            if area in out and area not in chosen:
                continue  # The device yaml set it.
            problem = _target_problem(target, modules, actions, menus)
            if problem:
                log.append(f"{m.name}: default target for '{area}' skipped; it {problem}")
                continue
            action = target_action(target)
            if area in chosen:
                if out[area] != action:
                    log.append(
                        f"{m.name}: default target for '{area}' ({action}) skipped; "
                        f"{chosen[area]}'s ({out[area]}) came first"
                    )
                continue
            chosen[area] = m.name
            out[area] = action
            log.append(f"{m.name}: a tap on '{area}' runs {action}")
    return out, log
