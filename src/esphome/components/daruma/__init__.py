"""Daruma hub: state, signals, input routing, and the module registry.

    daruma:
      id: daruma_hub
      # Modules: one entry per package. A C++ component may instead declare
      # DARUMA_MODULE in its __init__.py (same keys, no setup or automations).
      modules:
        - name: pomodoro
          states:                  # each with a fallback (registry.py)
            focus: { kind: activity, fallback: neutral, sound: start, quiet: true }  # quiet: no random events
          actions:                 # named actions that bindings run
            pomodoro.toggle:
              - script.execute: pomodoro_toggle
          apps: [stats]            # app ids its setup registers; {id, name} names the switch
          progress: [pomodoro]     # progress sources it feeds
          theme:                   # theme keys under the module's name, with defaults
            colors: { focus: "FF6347" }
            words: { title: "Focus" }
            aliases: { tomato: done }   # an old key that still works
          bindings:                # defaults; the device yaml wins
            screen.hold: pomodoro.toggle
            home.press: { action: menu.open, menu: pomodoro }
          menu: true               # adds buttons for the moment to menus that list it
          buttons:                 # button looks, so a menu may list an action
            pomodoro.break: { label: Break, icon: "\U000f0176", color: pomodoro.break }
          menus:                   # default menus; the device's menus: win per name
            pomodoro: [pomodoro]
          areas: [plaque]          # tap areas its setup draws (hub.add_tap_area)
          settings:                # rows on the Settings page (app_settings.yaml), each over a switch
            - { id: sounds, label: Sounds, icon: "\U000f057e", switch: sounds_enabled }
            # held: a lambda; true shows the row as held off (Sounds during Do not disturb)
          targets:                 # default: what a tap on an area does; the device's targets: win
            plaque: { app: stats } # or { menu: pomodoro }, { action: pomodoro.toggle }, none
          setup: !lambda |-        # (Daruma::Hub &hub): apps, layers, menu items, ...
            ...
      # The board: its display and what the screen can do (all optional).
      display: s3_box_lcd          # the layout comes from its size
      display_profile:
        colors: full               # full, gray4 or mono
        animate: true              # false: still frames only
        min_frame: 100ms           # shortest time between frames
        partial_refresh: true      # personas may repaint only what moved
        full_refresh_every: 0      # with partial_refresh: every Nth frame repaints all (e-ink)
      # The board names its inputs and how the menu is driven.
      inputs:
        - name: home
          button: home_button      # a binary_sensor id; or touch: <touchscreen id>
          gestures: [press, double, hold]
          hold_time: 1.5s          # optional: double_window, hold_time, long_hold_time
      navigation:
        back: home.press
        close: home.hold
      # The device yaml binds actions to inputs.
      bindings:
        home.press: { action: pomodoro.toggle, when: idle }
        top.press: voice.start
        top.double: { action: menu.open, menu: quick }   # opens a named menu
      expose_bindings: true        # one select per binding above, in HA
      apps: [calendar, tasks, stats]   # board order; every app gets an "App: <Name>" switch
      settings: [dnd, sounds]      # Settings page order; rows it leaves out go last
      menus:                       # named menus of dock buttons (registry.resolve_menus)
        main: [tasks, calendar, weather]    # a tap on the persona opens main (default: Tasks, Calendar, More)
        quick: [pomodoro.stop, stats, more, { label: Lights, icon: "\U000f0335", event: desk_lights }]
      progress:                    # progress sources and their weights
        pomodoro: 1
      targets:                     # what a tap on a part of the persona does (see the modules' areas)
        badge: { app: weather }
        plaque: none
      theme:                       # module colors and words for every persona
        colors: { pomodoro.done: "E8322B" }
        words: { pomodoro.ready: "Ready" }
      themes:                      # and for one persona, by its id; wins over theme:
        eyes:
          colors: { pomodoro.plaque: "000000" }
      # Random events: quirks the personas declare (daruma/persona.py). The
      # engine is built only when a persona has events or `personas:` has
      # some; `random_events: false` leaves it out. Every key is optional.
      random_events:
        enabled: true              # first value of the "Random events" switch
        tick: { min: 2min, max: 20min }   # the wait between random rolls
        min_gap: 15min             # first value of "Min gap"
        liveliness: 100            # first value of "Liveliness", in %
        time_id: daruma_time       # for dates, times, `at:` and cooldowns
        event_id: daruma_event     # fires "random_event"
        personas:                  # the device's changes, by persona id
          pixel_corgi:
            sneeze: false          # drop an event
            lick_paw: { frequency: 6 }   # change one
            snack_q: { say: ["Snack?"] } # add one

Theme precedence for a module key, lowest first: the module's default, the
persona's own `theme:`, the device's `theme:`, the device's `themes: <persona id>`.

The final validation step (FINAL_VALIDATE_SCHEMA) checks the whole config:
states and behaviors of every persona, theme keys, params, bindings,
navigation, apps and progress sources. See registry.py for the rules.
"""

import dataclasses
import logging

import esphome.automation as automation
import esphome.codegen as cg
import esphome.config_validation as cv
import esphome.final_validate as fv
from esphome.components import binary_sensor, touchscreen
from esphome.components import display as ha_display
from esphome.components import event as ha_event
from esphome.components import number as ha_number
from esphome.components import select as ha_select
from esphome.components import switch as ha_switch
from esphome.components import time as ha_time
from esphome.const import CONF_ID, CONF_NAME, CONF_TRIGGER_ID
from esphome.core import CORE
from esphome.helpers import cpp_string_escape
from esphome.loader import get_component

from . import random_events, registry
from .registry import RegistryError

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ["display", "font", "number"]
AUTO_LOAD = ["select", "switch"]
CODEOWNERS = []

CONF_DARUMA_ID = "daruma_id"
CONF_MODULES = "modules"
CONF_STATES = "states"
CONF_ACTIONS = "actions"
CONF_APPS = "apps"
CONF_PROGRESS = "progress"
CONF_THEME = "theme"
CONF_COLORS = "colors"
CONF_WORDS = "words"
CONF_BINDINGS = "bindings"
CONF_SETUP = "setup"
CONF_INPUTS = "inputs"
CONF_BUTTON = "button"
CONF_TOUCH = "touch"
CONF_GESTURES = "gestures"
CONF_DOUBLE_WINDOW = "double_window"
CONF_HOLD_TIME = "hold_time"
CONF_LONG_HOLD_TIME = "long_hold_time"
CONF_NAVIGATION = "navigation"
CONF_EXPOSE_BINDINGS = "expose_bindings"
CONF_ACTION = "action"
CONF_WHEN = "when"
CONF_KIND = "kind"
CONF_FALLBACK = "fallback"
CONF_SOUND = "sound"
CONF_DURATION = "duration"
CONF_QUIET = "quiet"
CONF_DISPLAY = "display"
CONF_DISPLAY_PROFILE = "display_profile"
CONF_COLORS_MODE = "colors"
CONF_ANIMATE = "animate"
CONF_MIN_FRAME = "min_frame"
CONF_PARTIAL_REFRESH = "partial_refresh"
CONF_FULL_REFRESH_EVERY = "full_refresh_every"
CONF_MENU = "menu"
CONF_MENUS = "menus"
CONF_BUTTONS = "buttons"
CONF_LABEL = "label"
CONF_ICON = "icon"
CONF_EVENT = "event"
CONF_COLOR = "color"
CONF_AREAS = "areas"
CONF_TARGETS = "targets"
CONF_ALIASES = "aliases"
CONF_THEMES = "themes"
CONF_APP = "app"
CONF_RANDOM_EVENTS = "random_events"
CONF_ENABLED = "enabled"
CONF_TICK = "tick"
CONF_MIN = "min"
CONF_MAX = "max"
CONF_MIN_GAP = "min_gap"
CONF_LIVELINESS = "liveliness"
CONF_TIME_ID = "time_id"
CONF_EVENT_ID = "event_id"
CONF_PERSONAS = "personas"
CONF_SWITCH = "switch"
CONF_LIVELINESS_NUMBER = "liveliness_number"
CONF_SETTINGS = "settings"
CONF_HELD = "held"
CONF_MIN_GAP_NUMBER = "min_gap_number"

# C++ classes live in the global Daruma namespace.
daruma_ns = cg.esphome_ns.namespace("Daruma")
Hub = daruma_ns.class_("Hub", cg.Component)
Persona = daruma_ns.class_("Persona")
LambdaModule = daruma_ns.class_("LambdaModule")
AppSwitch = daruma_ns.class_("AppSwitch", ha_switch.Switch, cg.Component)
BindingSelect = daruma_ns.class_("BindingSelect", ha_select.Select, cg.Component)
TouchInput = daruma_ns.class_("TouchInput")
RandomEventsComponent = daruma_ns.class_("RandomEventsComponent", cg.Component)
RandomEventsSwitch = daruma_ns.class_("RandomEventsSwitch", ha_switch.Switch, cg.Component)
TunableNumber = daruma_ns.class_("TunableNumber", ha_number.Number, cg.Component)
StateId = daruma_ns.enum("StateId", is_class=True)
Gesture = daruma_ns.enum("Gesture", is_class=True)
InputEnum = daruma_ns.enum("Input", is_class=True)

# Config keys of components that register personas. The persona select reads
# their names at build time to build its option list; final validation
# asks each for its personas (daruma_personas()).
PERSONA_COMPONENTS = ("daruma_eyes", "daruma_images", "daruma_sprites")

# Theme words the core and menu use, by key.
CORE_WORDS = ("menu.apps",)


def _name(value):
    value = cv.string_strict(value)
    try:
        return registry.check_name(value, "Name")
    except RegistryError as err:
        raise cv.Invalid(str(err)) from err


def _hex_color(value):
    value = cv.string_strict(value).lstrip("#")
    if len(value) != 6:
        raise cv.Invalid("Use a 6-digit hex color like 000000")
    return int(value, 16)


STATE_SCHEMA = cv.Schema(
    {
        cv.Required(CONF_KIND): cv.one_of(*registry.KINDS, lower=True),
        cv.Required(CONF_FALLBACK): _name,
        cv.Optional(CONF_SOUND): _name,
        cv.Optional(CONF_DURATION, default="0s"): cv.positive_time_period_milliseconds,
        # Activities only: random events wait while it is on.
        cv.Optional(CONF_QUIET, default=False): cv.boolean,
    }
)

_ACTION_AUTOMATION = automation.validate_automation(
    {cv.GenerateID(CONF_TRIGGER_ID): cv.declare_id(automation.Trigger.template())}, single=True
)


def _actions(value):
    if not isinstance(value, dict):
        raise cv.Invalid("actions: a map of action name to the steps it runs")
    out = {}
    for key, steps in value.items():
        with cv.prepend_path(key):
            out[cv.string_strict(key)] = _ACTION_AUTOMATION(steps)
    return out


def _app(value):
    """An app id ("tasks"), or {id, name} for an app whose switch shows
    another name ("App: Family" for tasks_family)."""
    if isinstance(value, dict):
        value = cv.Schema({cv.Required(CONF_ID): _name, cv.Optional(CONF_NAME): cv.string_strict})(value)
        return {CONF_ID: value[CONF_ID], CONF_NAME: value.get(CONF_NAME, _app_title(value[CONF_ID]))}
    app = _name(value)
    return {CONF_ID: app, CONF_NAME: _app_title(app)}


def _app_title(app: str) -> str:
    return app.replace("_", " ").capitalize()


def _button_color(value):
    """A module theme key ("pomodoro.break") or a 6-digit hex color."""
    value = cv.string_strict(value)
    if "." in value:
        return value
    return f"{_hex_color(value):06X}"


BUTTON_SCHEMA = cv.Schema(
    {
        cv.Required(CONF_LABEL): cv.string_strict,
        cv.Required(CONF_ICON): cv.string_strict,
        cv.Optional(CONF_COLOR): _button_color,
    }
)


SETTING_SCHEMA = cv.Schema(
    {
        cv.Required(CONF_ID): _name,
        cv.Required(CONF_LABEL): cv.string_strict,
        cv.Required(CONF_ICON): cv.string_strict,
        cv.Required(CONF_SWITCH): cv.use_id(ha_switch.Switch),
        # True while something else keeps the switch's effect off.
        cv.Optional(CONF_HELD): cv.returning_lambda,
    }
)


def _menu_item(value):
    """A name (module, app, action, menu or `more`), or an event button."""
    if isinstance(value, dict):
        return BUTTON_SCHEMA.extend({cv.Required(CONF_EVENT): _name})(value)
    return cv.string_strict(value)


MENUS_SCHEMA = cv.Schema({_name: cv.All(cv.ensure_list(_menu_item), cv.Length(min=1))})


def _target(value):
    """What a tap on an area does: {app: id}, {menu: name}, {action: name}, or none."""
    if isinstance(value, str):
        if value.strip().lower() == "none":
            return "none"
        raise cv.Invalid("A target is {app: <id>}, {menu: <name>}, {action: <name>} or none")
    value = cv.Schema({cv.Optional(k): cv.string_strict for k in registry.TARGET_KINDS})(value)
    if len(value) != 1:
        raise cv.Invalid("A target names one of app, menu or action")
    return dict(value)


TARGETS_SCHEMA = cv.Schema({_name: _target})

# Module colors and words for every persona, or one persona (the device yaml).
DEVICE_THEME_SCHEMA = cv.Schema(
    {
        cv.Optional(CONF_COLORS, default={}): cv.Schema({cv.string_strict: _hex_color}),
        cv.Optional(CONF_WORDS, default={}): cv.Schema({cv.string_strict: cv.string}),
    }
)


def _default_binding(value):
    """A module's default binding: an action, or {action, menu} for menu.open."""
    if isinstance(value, dict):
        value = cv.Schema({cv.Required(CONF_ACTION): cv.string_strict, cv.Optional(CONF_MENU): _name})(value)
        try:
            return registry.menu_action(value[CONF_ACTION], value.get(CONF_MENU))
        except RegistryError as err:
            raise cv.Invalid(str(err)) from err
    return cv.string_strict(value)


MODULE_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(LambdaModule),
        cv.Required(CONF_NAME): _name,
        cv.Optional(CONF_STATES, default={}): cv.Schema({_name: STATE_SCHEMA}),
        cv.Optional(CONF_ACTIONS, default={}): _actions,
        # App ids its setup registers, each optionally with {id, name}.
        cv.Optional(CONF_APPS, default=[]): cv.ensure_list(_app),
        cv.Optional(CONF_PROGRESS, default=[]): cv.ensure_list(_name),
        cv.Optional(CONF_THEME, default={}): cv.Schema(
            {
                cv.Optional(CONF_COLORS, default={}): cv.Schema({_name: _hex_color}),
                cv.Optional(CONF_WORDS, default={}): cv.Schema({_name: cv.string}),
                # Old keys that still work, as their new names: {old: new}.
                cv.Optional(CONF_ALIASES, default={}): cv.Schema({_name: _name}),
            }
        ),
        cv.Optional(CONF_BINDINGS, default={}): cv.Schema({cv.string_strict: _default_binding}),
        cv.Optional(CONF_AREAS, default=[]): cv.ensure_list(_name),
        cv.Optional(CONF_TARGETS, default={}): TARGETS_SCHEMA,
        cv.Optional(CONF_MENU, default=False): cv.boolean,
        cv.Optional(CONF_BUTTONS, default={}): cv.Schema({cv.string_strict: BUTTON_SCHEMA}),
        cv.Optional(CONF_MENUS, default={}): MENUS_SCHEMA,
        cv.Optional(CONF_SETTINGS, default=[]): cv.ensure_list(SETTING_SCHEMA),
        cv.Optional(CONF_SETUP): cv.lambda_,
    }
)


def _gestures(value):
    return cv.ensure_list(cv.string_strict)(value)


def _long_after_hold(config):
    if config[CONF_LONG_HOLD_TIME] <= config[CONF_HOLD_TIME]:
        raise cv.Invalid("long_hold_time must be longer than hold_time")
    return config


INPUT_SCHEMA = cv.All(
    cv.Schema(
        {
            cv.Required(CONF_NAME): _name,
            cv.Exclusive(CONF_BUTTON, "source"): cv.use_id(binary_sensor.BinarySensor),
            cv.Exclusive(CONF_TOUCH, "source"): cv.use_id(touchscreen.Touchscreen),
            cv.Required(CONF_GESTURES): _gestures,
            cv.Optional(CONF_DOUBLE_WINDOW, default="300ms"): cv.All(
                cv.positive_time_period_milliseconds,
                cv.Range(min=cv.TimePeriod(milliseconds=100), max=cv.TimePeriod(milliseconds=1000)),
            ),
            cv.Optional(CONF_HOLD_TIME, default="1s"): cv.All(
                cv.positive_time_period_milliseconds,
                cv.Range(min=cv.TimePeriod(milliseconds=300), max=cv.TimePeriod(seconds=5)),
            ),
            cv.Optional(CONF_LONG_HOLD_TIME, default="3s"): cv.All(
                cv.positive_time_period_milliseconds,
                cv.Range(min=cv.TimePeriod(seconds=1), max=cv.TimePeriod(seconds=9)),
            ),
        }
    ),
    cv.has_exactly_one_key(CONF_BUTTON, CONF_TOUCH),
    _long_after_hold,
)


def _binding(value):
    if isinstance(value, str):
        value = {CONF_ACTION: value}
    return cv.Schema(
        {
            cv.Required(CONF_ACTION): cv.string_strict,
            cv.Optional(CONF_WHEN): cv.one_of("idle", lower=True),
            # With menu.open: the menu to open (default: main).
            cv.Optional(CONF_MENU): _name,
        }
    )(value)


PROFILE_SCHEMA = cv.Schema(
    {
        cv.Optional(CONF_COLORS_MODE, default="full"): cv.one_of(*registry.COLOR_MODES, lower=True),
        cv.Optional(CONF_ANIMATE, default=True): cv.boolean,
        cv.Optional(CONF_MIN_FRAME, default="100ms"): cv.All(
            cv.positive_time_period_milliseconds,
            cv.Range(min=cv.TimePeriod(milliseconds=10), max=cv.TimePeriod(seconds=60)),
        ),
        cv.Optional(CONF_PARTIAL_REFRESH, default=True): cv.boolean,
        cv.Optional(CONF_FULL_REFRESH_EVERY, default=0): cv.int_range(min=0, max=1000),
    }
)


def profile_of(config) -> registry.Profile:
    conf = config[CONF_DISPLAY_PROFILE]
    return registry.Profile(
        conf[CONF_COLORS_MODE],
        conf[CONF_ANIMATE],
        conf[CONF_MIN_FRAME].total_milliseconds,
        conf[CONF_PARTIAL_REFRESH],
        conf[CONF_FULL_REFRESH_EVERY],
    )


def build_profile() -> registry.Profile:
    """The display profile, for components that draw at build time (sprites)."""
    conf = CORE.config.get("daruma") if CORE.config else None
    return profile_of(conf) if conf and CONF_DISPLAY_PROFILE in conf else registry.Profile()


def _check_profile(config):
    try:
        registry.check_profile(profile_of(config))
    except RegistryError as err:
        raise cv.Invalid(str(err), [CONF_DISPLAY_PROFILE]) from err
    return config


def _tick_order(value):
    if value[CONF_MIN] > value[CONF_MAX]:
        raise cv.Invalid("random_events: tick: min is longer than max")
    return value


def _event_overrides(value):
    from .persona import event_override  # persona.py imports this module.

    return cv.Schema({cv.string_strict: event_override})(value)


RANDOM_EVENTS_HUB_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(RandomEventsComponent),
        cv.Optional(CONF_ENABLED, default=True): cv.boolean,
        cv.Optional(CONF_TICK, default={}): cv.All(
            cv.Schema(
                {
                    cv.Optional(CONF_MIN, default="2min"): cv.All(
                        cv.positive_time_period_milliseconds, cv.Range(min=cv.TimePeriod(seconds=30))
                    ),
                    cv.Optional(CONF_MAX, default="20min"): cv.All(
                        cv.positive_time_period_milliseconds, cv.Range(max=cv.TimePeriod(hours=24))
                    ),
                }
            ),
            _tick_order,
        ),
        cv.Optional(CONF_MIN_GAP, default="15min"): cv.All(
            cv.positive_time_period_minutes, cv.Range(max=cv.TimePeriod(minutes=240))
        ),
        cv.Optional(CONF_LIVELINESS, default=100): cv.int_range(min=0, max=200),
        cv.Optional(CONF_TIME_ID, default="daruma_time"): cv.use_id(ha_time.RealTimeClock),
        cv.Optional(CONF_EVENT_ID, default="daruma_event"): cv.use_id(ha_event.Event),
        # Overrides by persona id, checked like themes: at final validation.
        cv.Optional(CONF_PERSONAS, default={}): cv.Schema({_name: _event_overrides}),
    }
)


def _random_events_conf(value):
    """`false` leaves the engine out; `true` is the same as `{}`."""
    if value is False:
        return False
    return RANDOM_EVENTS_HUB_SCHEMA({} if value is True else value)


CONF_APP_SWITCHES = "app_switches"
CONF_BINDING_SELECTS = "binding_selects"


def _entities(config):
    """HA entity configs for the app switches and, with expose_bindings, the
    binding selects, made here so their ids are declared like any other."""
    names = {}
    for module in config[CONF_MODULES]:
        for app in module[CONF_APPS]:
            names.setdefault(app[CONF_ID], app[CONF_NAME])
    apps = list(config[CONF_APPS]) + [a for a in names if a not in config[CONF_APPS]]
    config[CONF_APP_SWITCHES] = {
        app: ha_switch.switch_schema(
            AppSwitch, entity_category="config", icon="mdi:apps", default_restore_mode="RESTORE_DEFAULT_ON"
        )({CONF_NAME: f"App: {names.get(app, _app_title(app))}"})
        for app in apps
    }
    config[CONF_BINDING_SELECTS] = {}
    if config[CONF_EXPOSE_BINDINGS]:
        for trigger in config[CONF_BINDINGS]:
            name, _, gesture = trigger.partition(".")
            config[CONF_BINDING_SELECTS][trigger] = ha_select.select_schema(
                BindingSelect, entity_category="config", icon="mdi:gesture-tap-button"
            )({CONF_NAME: f"{name.capitalize()} {gesture.replace('_', ' ')}"})
    _random_events_entities(config[CONF_RANDOM_EVENTS])
    return config


def _random_events_entities(rc):
    """The engine's settings. Declared unless `random_events: false`; the
    personas are unknown here, so to_code makes them only with the engine."""
    if rc is False:
        return
    restore = "RESTORE_DEFAULT_ON" if rc[CONF_ENABLED] else "RESTORE_DEFAULT_OFF"
    rc[CONF_SWITCH] = ha_switch.switch_schema(
        RandomEventsSwitch, entity_category="config", icon="mdi:dice-multiple-outline", default_restore_mode=restore
    )({CONF_NAME: "Random events"})
    rc[CONF_LIVELINESS_NUMBER] = ha_number.number_schema(
        TunableNumber, entity_category="config", icon="mdi:run-fast", unit_of_measurement="%"
    )({CONF_NAME: "Liveliness"})
    rc[CONF_MIN_GAP_NUMBER] = ha_number.number_schema(
        TunableNumber, entity_category="config", icon="mdi:timer-sand", unit_of_measurement="min"
    )({CONF_NAME: "Min gap"})


CONFIG_SCHEMA = cv.All(
    cv.Schema(
        {
            cv.GenerateID(): cv.declare_id(Hub),
            cv.Optional(CONF_DISPLAY): cv.use_id(ha_display.Display),
            cv.Optional(CONF_DISPLAY_PROFILE, default={}): PROFILE_SCHEMA,
            cv.Optional(CONF_MODULES, default=[]): cv.ensure_list(MODULE_SCHEMA),
            cv.Optional(CONF_INPUTS, default=[]): cv.ensure_list(INPUT_SCHEMA),
            cv.Optional(CONF_NAVIGATION, default={}): cv.Schema({cv.string_strict: cv.string_strict}),
            cv.Optional(CONF_BINDINGS, default={}): cv.Schema({cv.string_strict: _binding}),
            cv.Optional(CONF_EXPOSE_BINDINGS, default=False): cv.boolean,
            cv.Optional(CONF_APPS, default=[]): cv.ensure_list(_name),
            # The Settings page order, by setting id.
            cv.Optional(CONF_SETTINGS, default=[]): cv.ensure_list(_name),
            # Named menus of dock buttons; `main` is what a tap on the persona opens.
            cv.Optional(CONF_MENUS, default={}): MENUS_SCHEMA,
            cv.Optional(CONF_PROGRESS, default={}): cv.Schema({_name: cv.float_range(min=0.0, max=100.0)}),
            # What a tap on a part of the persona does, by area (the modules' `areas:`).
            cv.Optional(CONF_TARGETS, default={}): TARGETS_SCHEMA,
            # Module colors and words for every persona, and per persona by id (theme.py applies them).
            cv.Optional(CONF_THEME, default={}): DEVICE_THEME_SCHEMA,
            cv.Optional(CONF_THEMES, default={}): cv.Schema({_name: DEVICE_THEME_SCHEMA}),
            cv.Optional(CONF_RANDOM_EVENTS, default={}): _random_events_conf,
        }
    ).extend(cv.COMPONENT_SCHEMA),
    _check_profile,
    _entities,
)


# --- Collecting the facts -------------------------------------------------------------


def _module_from_yaml(conf) -> registry.ModuleSpec:
    name = conf[CONF_NAME]
    states = [
        registry.State(
            state,
            s[CONF_KIND],
            s[CONF_FALLBACK],
            s.get(CONF_SOUND),
            s[CONF_DURATION].total_milliseconds,
            name,
            s[CONF_QUIET],
        )
        for state, s in conf[CONF_STATES].items()
    ]
    return registry.ModuleSpec(
        name=name,
        states=states,
        actions=list(conf[CONF_ACTIONS]),
        apps=[a[CONF_ID] for a in conf[CONF_APPS]],
        progress=list(conf[CONF_PROGRESS]),
        colors=dict(conf[CONF_THEME][CONF_COLORS]),
        words=dict(conf[CONF_THEME][CONF_WORDS]),
        bindings=dict(conf[CONF_BINDINGS]),
        menu=conf[CONF_MENU],
        buttons={a: dict(b) for a, b in conf[CONF_BUTTONS].items()},
        menus={n: list(items) for n, items in conf[CONF_MENUS].items()},
        areas=list(conf[CONF_AREAS]),
        targets=dict(conf[CONF_TARGETS]),
        aliases=dict(conf[CONF_THEME][CONF_ALIASES]),
        settings=[s[CONF_ID] for s in conf[CONF_SETTINGS]],
    )


def collect_modules(full) -> list[registry.ModuleSpec]:
    """Every module in the config: C++ components that declare DARUMA_MODULE,
    then the `daruma: modules:` entries."""
    modules = []
    for key in full:
        try:
            manifest = get_component(key)
        except Exception:  # noqa: BLE001  Core keys and platforms have no manifest.
            manifest = None
        spec = getattr(getattr(manifest, "module", None), "DARUMA_MODULE", None)
        if spec is not None:
            modules.append(spec)
    for conf in full.get("daruma", {}).get(CONF_MODULES, []):
        modules.append(_module_from_yaml(conf))
    registry.check_modules(modules)
    return modules


def collect_personas(full) -> list[tuple[registry.Persona, dict, list]]:
    """(persona, theme config, declared params) for every persona."""
    out = []
    for key in PERSONA_COMPONENTS:
        confs = full.get(key) or []
        if not confs:
            continue
        module = get_component(key).module
        out += module.daruma_personas(confs)
    return out


def event_personas(full) -> list[tuple[registry.Persona, dict, bool]]:
    """(persona, its config, takes random events) for every persona."""
    out = []
    for key in PERSONA_COMPONENTS:
        confs = full.get(key) or []
        if confs:
            chars = get_component(key).module.daruma_personas(confs)
            out += [(char, conf, CONF_RANDOM_EVENTS in conf) for conf, (char, _, _) in zip(confs, chars, strict=True)]
    return out


def _random_event_pools(rc, full):
    """(personas, persona id -> pool with the device's overrides), or None
    when the engine is off."""
    if rc is False:
        return None
    personas = event_personas(full)
    if not random_events.active([char.random_events for char, _, _ in personas], rc[CONF_PERSONAS]):
        return None
    pools = random_events.device_pools([(c.id, c.random_events, ok) for c, _, ok in personas], rc[CONF_PERSONAS])
    return personas, pools


def states_for_build() -> list[registry.State]:
    """The registry's states, in StateId order, for the persona components' to_code."""
    return registry.collect_states(collect_modules(CORE.config))


def _inputs(config) -> dict[str, registry.Input]:
    inputs = {}
    for conf in config[CONF_INPUTS]:
        kind = registry.TOUCH if CONF_TOUCH in conf else registry.BUTTON
        if conf[CONF_NAME] in inputs:
            raise RegistryError(f"inputs: two inputs are named '{conf[CONF_NAME]}'")
        inputs[conf[CONF_NAME]] = registry.Input(
            conf[CONF_NAME], kind, registry.expand_gestures(kind, conf[CONF_GESTURES])
        )
    return inputs


def _check_persona(char, theme, states, modules) -> None:
    """One persona's looks, `during:`, random events and theme keys. The
    random event checks run also with the engine off, so a typo always fails."""
    _, log = registry.resolve_persona(char, states)
    registry.resolve_during(char, states)
    log += registry.resolve_random_events(char, states)
    for line in log:
        _LOGGER.info(line)
    registry.check_theme_keys(char.id, theme.get(CONF_COLORS, {}), theme.get(CONF_WORDS, {}), modules, CORE_WORDS)


def _final_validate(config):
    full = fv.full_config.get()
    try:
        modules = collect_modules(full)
        states = registry.collect_states(modules)
        actions = registry.collect_actions(modules)
        params = []
        persona_ids = []
        for char, theme, declared in collect_personas(full):
            persona_ids.append(char.id)
            _check_persona(char, theme, states, modules)
            params += [(char.id, p) for p in declared]
        registry.check_params(params)
        registry.check_device_themes(config[CONF_THEME], config[CONF_THEMES], persona_ids, modules, CORE_WORDS)
        registry.check_menus_included(config[CONF_MENUS], modules)
        menus, log = registry.collect_menus(config[CONF_MENUS], modules)
        for line in log:
            _LOGGER.info(line)
        registry.resolve_menus(menus, modules, actions)
        _, log = registry.resolve_targets(config[CONF_TARGETS], modules, actions, menus)
        for line in log:
            _LOGGER.info(line)
        inputs = _inputs(config)
        if inputs:
            navigation = registry.check_navigation(inputs, config[CONF_NAVIGATION])
            bindings, log = registry.resolve_bindings(
                inputs, navigation, config[CONF_BINDINGS], modules, actions, menus
            )
            for line in log:
                _LOGGER.info(line)
            registry.check_menu_reachable(inputs, bindings, modules)
        elif config[CONF_BINDINGS]:
            raise RegistryError("bindings: the board declares no inputs")
        _, log = registry.order_apps(config[CONF_APPS], modules)
        for line in log:
            _LOGGER.info(line)
        registry.order_settings(config[CONF_SETTINGS], modules)
        registry.check_progress(config[CONF_PROGRESS], modules)
        _random_events_final(config, full, states)
    except RegistryError as err:
        raise cv.Invalid(str(err)) from err


def _random_events_final(config, full, states) -> None:
    """The engine's checks: the overrides, the merged pools, and what the
    engine needs from the build. The personas' own events are checked in
    _check_persona, also with the engine off."""
    rc = config[CONF_RANDOM_EVENTS]
    found = _random_event_pools(rc, full)
    if found is None:
        _LOGGER.info("random events: off (%s)", "random_events: false" if rc is False else "no persona declares any")
        return
    personas, pools = found
    for char, _, _ in personas:
        if pools.get(char.id):
            registry.resolve_random_events(dataclasses.replace(char, random_events=pools[char.id]), states)
            _LOGGER.info("random events: %s: %d (%s)", char.id, len(pools[char.id]), ", ".join(pools[char.id]))
    if "api" not in full:
        raise RegistryError("random_events: the engine needs `api:`, for its action and events")


FINAL_VALIDATE_SCHEMA = _final_validate


# --- Code ---------------------------------------------------------------------------


def _state_list(states) -> str:
    index = {s.name: i for i, s in enumerate(states)}
    entries = []
    for s in states:
        chain = registry.fallback_chain(states, s.name)
        celebrates = "true" if "celebrate" in chain else "false"
        fallback = index[s.fallback] if s.fallback else -1
        entries.append(f'X({s.name.upper()}, "{s.name}", {s.kind.upper()}, {fallback}, {s.duration_ms}, {celebrates})')
    return " ".join(entries)


def state_id(name: str):
    return StateId.enum(name.upper())


_GESTURES = {
    "press": "PRESS",
    "double": "DOUBLE",
    "hold": "HOLD",
    "long_hold": "LONG_HOLD",
    "tap": "TAP",
    "swipe_left": "SWIPE_LEFT",
    "swipe_right": "SWIPE_RIGHT",
    "swipe_up": "SWIPE_UP",
    "swipe_down": "SWIPE_DOWN",
    "stroke": "STROKE",
    "swipe_from_top": "SWIPE_FROM_TOP",
}


async def to_code(config):
    full = CORE.config
    modules = collect_modules(full)
    states = registry.collect_states(modules)
    cg.add_define("DARUMA_STATE_LIST", cg.RawExpression(_state_list(states)))

    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)

    if CONF_DISPLAY in config:
        cg.add(var.set_display(await cg.get_variable(config[CONF_DISPLAY])))
    profile = profile_of(config)
    cg.add(
        var.set_profile(
            registry.COLOR_MODES.index(profile.colors),
            profile.animate,
            profile.min_frame_ms,
            profile.partial_refresh,
            profile.full_refresh_every,
        )
    )

    # Module theme defaults.
    for module in modules:
        for key, rgb in module.colors.items():
            cg.add(cg.RawStatement(f'Daruma::Theme::set_default_color("{module.name}.{key}", {rgb});'))
        for key, text in module.words.items():
            cg.add(
                cg.RawStatement(
                    f"Daruma::Theme::set_default_word({cg.safe_exp(f'{module.name}.{key}')}, {cg.safe_exp(text)});"
                )
            )

    # Modules from yaml: their actions, and setup as a LambdaModule.
    for conf in config[CONF_MODULES]:
        for name, auto in conf[CONF_ACTIONS].items():
            trigger = cg.new_Pvariable(auto[CONF_TRIGGER_ID])
            await automation.build_automation(trigger, [], auto)
            cg.add(var.add_action(name, cg.RawExpression(f"[]() {{ {trigger}->trigger(); }}")))
        setup = cg.RawExpression("nullptr")
        if CONF_SETUP in conf:
            setup = await cg.process_lambda(conf[CONF_SETUP], [(Hub.operator("ref"), "hub")], return_type=cg.void)
        module = cg.new_Pvariable(conf[CONF_ID], conf[CONF_NAME], setup)
        cg.add(var.add_module(module))

    # Progress sources and weights: the device's, else every offered one at 1.
    weights = config[CONF_PROGRESS]
    for name in registry.check_progress(weights, modules):
        cg.add(var.add_progress_source(name, weights.get(name, 1.0)))

    # Menus: every item, in order, for the menu to lay out.
    menus, _ = registry.collect_menus(config[CONF_MENUS], modules)
    for name, items in registry.resolve_menus(menus, modules, registry.collect_actions(modules)).items():
        for item in items:
            cg.add(
                var.add_menu_entry(
                    name, registry.MENU_KINDS.index(item.kind), item.id, item.label, item.icon, item.color
                )
            )

    # Tap areas: what a tap on each does.
    targets, _ = registry.resolve_targets(config[CONF_TARGETS], modules, registry.collect_actions(modules), menus)
    for area, action in targets.items():
        cg.add(var.add_tap_target(area, action))

    # Apps: board order, and a switch each.
    order, _ = registry.order_apps(config[CONF_APPS], modules)
    cg.add(var.set_app_order(order))
    for app, conf in config[CONF_APP_SWITCHES].items():
        sw = await ha_switch.new_switch(conf, var, app)
        await cg.register_component(sw, conf)

    # The screen tests build a device and see its rows; host tests reach to_code no further.
    await _settings_to_code(var, config, modules)  # pragma: no mutate
    await _inputs_to_code(var, config, modules, menus)
    await _random_events_to_code(var, config, states)


async def _settings_to_code(var, config, modules):
    """Settings rows in page order. Each reads and sets its switch, and a
    change of the switch (from HA too) redraws the page."""
    rows = {s[CONF_ID]: s for conf in config[CONF_MODULES] for s in conf[CONF_SETTINGS]}
    for setting in registry.order_settings(config[CONF_SETTINGS], modules):
        row = rows[setting]
        sw = await cg.get_variable(row[CONF_SWITCH])
        held = cg.RawExpression("nullptr")
        if CONF_HELD in row:
            held = await cg.process_lambda(row[CONF_HELD], [], return_type=cg.bool_)
        cg.add(
            var.add_setting(
                setting,
                row[CONF_LABEL],
                row[CONF_ICON],
                cg.RawExpression(f"[]() {{ return {sw}->state; }}"),
                cg.RawExpression(f"[](bool on) {{ if (on) {{ {sw}->turn_on(); }} else {{ {sw}->turn_off(); }} }}"),
                held,
            )
        )
        cg.add(sw.add_on_state_callback(cg.RawExpression(f"[](bool) {{ {var}->request_redraw(); }}")))


async def _inputs_to_code(var, config, modules, menus):
    if not config[CONF_INPUTS]:
        return
    inputs = _inputs(config)
    index = {}
    for i, conf in enumerate(config[CONF_INPUTS]):
        index[conf[CONF_NAME]] = i
        touch = CONF_TOUCH in conf
        cg.add(
            var.add_input(
                conf[CONF_NAME],
                touch,
                conf[CONF_DOUBLE_WINDOW].total_milliseconds,
                conf[CONF_HOLD_TIME].total_milliseconds,
                conf[CONF_LONG_HOLD_TIME].total_milliseconds,
            )
        )
        if touch:
            screen = await cg.get_variable(conf[CONF_TOUCH])
            cg.add(screen.register_listener(TouchInput.new(var)))
        else:
            sensor = await cg.get_variable(conf[CONF_BUTTON])
            cg.add(
                sensor.add_on_state_callback(cg.RawExpression(f"[](bool state) {{ {var}->button_edge({i}, state); }}"))
            )

    navigation = registry.check_navigation(inputs, config[CONF_NAVIGATION])
    for key, (name, gesture) in navigation.items():
        cg.add(var.add_navigation(index[name], Gesture.enum(_GESTURES[gesture]), InputEnum.enum(key.upper())))

    actions = registry.collect_actions(modules)
    bindings, _ = registry.resolve_bindings(inputs, navigation, config[CONF_BINDINGS], modules, actions, menus)
    options = ["none"] + sorted(actions)
    if "menu" in {m.name for m in modules}:
        options += [f"{registry.OPEN_MENU}:{m}" for m in sorted(menus)]
    for b in bindings:
        slot = cg.RawExpression(
            f"{var}->add_binding({index[b.input]}, Daruma::Gesture::{_GESTURES[b.gesture]}, "
            f"{cg.safe_exp(b.action)}, {'true' if b.idle else 'false'})"
        )
        conf = config[CONF_BINDING_SELECTS].get(f"{b.input}.{b.gesture}")
        if conf is not None and b.source == "device":
            sel = await ha_select.new_select(conf, var, slot, options=options)
            await cg.register_component(sel, conf)
        else:
            cg.add(slot)


# --- Random events ------------------------------------------------------------------


def _cpp_array(name: str, ctype: str, items: list[str]) -> str:
    """A constant table for the engine; "nullptr" when empty."""
    if not items:
        return "nullptr"
    cg.add_global(cg.RawStatement(f"static const {ctype} {name}[] = {{{', '.join(items)}}};"))
    return name


def _event_def(pid: str, index: int, name: str, event: dict, animations: list[str]) -> str:
    """One EventDef initializer, in random_events.h's field order."""
    e = random_events.encode_event(pid, name, event, animations)
    w = e.when
    at = f"{pid}_random_event_{index}"
    say = _cpp_array(f"{at}_say", "char *const", [cpp_string_escape(line) for line in e.say])
    dates = _cpp_array(f"{at}_dates", "Daruma::RandomEvents::DateRange", [f"{{{a}, {b}}}" for a, b in w.dates])
    times = _cpp_array(f"{at}_times", "Daruma::RandomEvents::TimeRange", [f"{{{a}, {b}}}" for a, b in w.between])
    minutes = _cpp_array(f"{at}_at", "uint16_t", [str(m) for m in w.at])
    moods = _cpp_array(f"{at}_moods", "Daruma::StateId", [f"Daruma::StateId::{m.upper()}" for m in w.moods])
    kind = "SPELL" if e.spell else "ONE_SHOT"
    fields = [
        cpp_string_escape(name),
        f"{e.key}u",
        f"Daruma::RandomEvents::Kind::{kind}",
        str(e.enter),
        str(e.animation),
        str(e.exit),
        f"{e.hold_ms}u",
        str(e.frequency),
        f"{e.cooldown_s}u",
        cpp_string_escape(e.sound),
        say,
        str(len(e.say)),
        dates,
        str(len(w.dates)),
        str(w.weekdays),
        times,
        str(len(w.between)),
        minutes,
        str(len(w.at)),
        moods,
        str(len(w.moods)),
        "true" if "sleeping" in w.moods else "false",
    ]
    return "{" + ", ".join(fields) + "}"


async def _random_events_to_code(hub, config, states) -> None:
    """The engine, its pools, its entities and its action; nothing when it is off."""
    rc = config[CONF_RANDOM_EVENTS]
    found = _random_event_pools(rc, CORE.config)
    if found is None:
        return
    personas, pools = found
    cg.add_define("USE_DARUMA_RANDOM_EVENTS")
    # For the bus event esphome.daruma_random_event.
    cg.add_define("USE_API_HOMEASSISTANT_SERVICES")
    engine = cg.new_Pvariable(rc[CONF_ID], hub)
    await cg.register_component(engine, rc)
    cg.add(engine.set_tick(rc[CONF_TICK][CONF_MIN].total_milliseconds, rc[CONF_TICK][CONF_MAX].total_milliseconds))
    cg.add(engine.set_clock(await cg.get_variable(rc[CONF_TIME_ID])))
    cg.add(engine.set_event(await cg.get_variable(rc[CONF_EVENT_ID])))
    for state in states:
        if state.quiet:
            cg.add(engine.add_quiet(state_id(state.name)))
    for char, conf, _ in personas:
        pool = pools.get(char.id)
        if not pool:
            continue
        rows = [_event_def(char.id, i, name, event, char.animations) for i, (name, event) in enumerate(pool.items())]
        table = _cpp_array(f"{char.id}_random_events", "Daruma::RandomEvents::EventDef", rows)
        persona = await cg.get_variable(conf[CONF_ID])
        cg.add(engine.add_pool(persona, char.id, cg.RawExpression(table), len(rows)))
    switch = await ha_switch.new_switch(rc[CONF_SWITCH], engine)
    await cg.register_component(switch, rc[CONF_SWITCH])
    numbers = (
        (CONF_LIVELINESS_NUMBER, float(rc[CONF_LIVELINESS]), "set_liveliness", 200, 10),
        (CONF_MIN_GAP_NUMBER, float(rc[CONF_MIN_GAP].total_minutes), "set_min_gap", 240, 5),
    )
    for key, initial, setter, top, step in numbers:
        apply = cg.RawExpression(f"[](float value) {{ {engine}->{setter}(value); }}")
        number = await ha_number.new_number(rc[key], initial, apply, min_value=0, max_value=top, step=step)
        await cg.register_component(number, rc[key])
