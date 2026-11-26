"""Drive the Daruma desktop build from Python, like a browser test drives a page.

    with Device(build(), workdir, persona="Eyes") as device:
        device.pet()
        expect(device).to_have_state("petted")
        device.show_prompt(id="door", title="Doorbell", options=["Unlock", "Ignore"], style="urgent")
        device.get_by_role("button", name="Unlock").tap()
        expect(device).to_fire_event("esphome.daruma_prompt", choice="Unlock")
        expect(device).to_match_screenshot("after-unlock")

How it works:

- `build()` compiles `examples/desktop.yaml` for the host, in a scratch
  copy of this repository, and a small library (fakeclock.c).
- `Device` starts the program with that library loaded. The library hands
  the program a clock that only this harness moves, and a fixed random
  seed. So the same steps draw the same frames, run after run.
- The harness talks to the program over the ESPHome API, as Home Assistant
  does. It also plays Home Assistant: it answers the calendar and to-do
  actions with made-up data (demo_data.py) and records the events the
  device fires.
- Touch and buttons go through the desktop board's `desktop_*` actions,
  which move the SDL mouse and press the button sensors. The device's own
  gesture code sees them as a finger and a button.
- `ui()` lists what is on screen (buttons, tiles, prompt cards) with their
  rectangles, from the menu and prompt code. Locators find parts by text or
  role and tap their middle.

Time only moves in `advance()`. Waiting helpers (`expect`, `Locator.wait_for`)
advance the clock a frame at a time until the condition holds.
"""

from __future__ import annotations

import asyncio
import contextlib
import ctypes
import json
import mmap
import os
import platform
import re
import shutil
import socket
import struct
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import persona_path
from persona_path import Folder, persona_name

HERE = Path(__file__).resolve().parent
REPO_DIR = HERE.parent
# Another ESPHome to build with, for a try (a pip spec such as "esphome==<version>"). By
# default the build runs the version locked in uv.lock (the "esphome" group),
# from the environment the harness runs in.
ESPHOME_SPEC = os.environ.get("DARUMA_ESPHOME")
# A folder turns on coverage: the build gets its own folder and the
# --coverage flag (gcov), and ESPHome's Python runs under coverage.py, which
# writes its data here. Normal builds stay as they are.
COVERAGE = os.environ.get("DARUMA_COVERAGE")
# uvx ignores .python-version, so the build passes it on.
PYTHON = os.environ.get("DARUMA_PYTHON") or (REPO_DIR / ".python-version").read_text().strip()
DEVICE_YAML = "desktop.yaml"  # In examples/, next to the build's config folder.
SOURCES = ["examples", "packages", "src", "pixel", "art"]
GOLDEN_DIR = HERE.parent / "tests" / "golden"

# The time zone "Home Assistant" sends the device, unless a run asks for
# another one.
TIMEZONE = "America/New_York"
# The device's wall clock at the start of every run: Wednesday 11 March 2026,
# 10:00 in New York (14:00 UTC). A fixed morning, so screens repeat.
EPOCH = 1773237600
# Monotonic time at start; millis() starts here.
START_NS = 1_000_000_000
# One frame step: the BOX-3 profile draws at most every 100 ms.
STEP = 0.05
# Real seconds a device may take to finish one step: only a hung program
# takes this long.
SETTLE_TIMEOUT = 30


class DeviceError(RuntimeError):
    """The program or the harness failed (not an assertion)."""


# --------------------------------------------------------------------------
# Building
# --------------------------------------------------------------------------


@dataclass
class Build:
    program: Path
    clock_lib: Path
    port: int
    # Personas from DARUMA_PERSONA_PATH, by name, with their folders: their
    # goldens and demos go there, never into this repository.
    private_personas: dict[str, Folder] = field(default_factory=dict)


def _copy_sources(src: Path) -> None:
    """Copy the sources into `src`, fresh, but keep ESPHome's data folder.

    examples/.esphome holds the compiled programs and the drawn persona art
    (see daruma_sprites). Drawing the art takes most of a cold build, and both
    caches check their own inputs, so a build that keeps them only redoes
    what changed. The copy keeps file times, so the compiler sees what changed.
    The folder stays in place, so programs built before keep running.
    """
    src.mkdir(parents=True, exist_ok=True)
    for name in SOURCES:
        target = src / name
        if target.is_dir():
            _clear_but_esphome(target)
        shutil.copytree(
            REPO_DIR / name, target, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", ".esphome")
        )


def _clear_but_esphome(folder: Path) -> None:
    """Delete everything in `folder` except its .esphome folder."""
    for child in folder.iterdir():
        if child.name == ".esphome":
            continue
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()


def desktop_personas() -> list[str]:
    """The personas of the desktop build, read from examples/desktop.yaml
    without a build: each `persona_*` package, by the `persona_name` it
    passes, or else by its package's name."""
    import yaml

    class Loader(yaml.SafeLoader):
        pass

    def tagged(loader: yaml.SafeLoader, suffix: str, node: yaml.Node) -> Any:
        """Any ESPHome tag (!include, !extend, !lambda) as plain data; a
        scalar !include as {"file": ...}."""
        if isinstance(node, yaml.MappingNode):
            return loader.construct_mapping(node, deep=True)
        if isinstance(node, yaml.SequenceNode):
            return loader.construct_sequence(node, deep=True)
        value = loader.construct_scalar(node)
        return {"file": value} if suffix == "include" else value

    Loader.add_multi_constructor("!", tagged)
    config = REPO_DIR / "examples" / DEVICE_YAML
    packages = yaml.load(config.read_text(), Loader=Loader)["packages"]
    names = []
    for key, package in packages.items():
        if not key.startswith("persona_"):
            continue
        name = (package.get("vars") or {}).get("persona_name")
        names.append(name or persona_name(config.parent / package["file"]))
    return names


def build_clock_lib(out: Path) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    if platform.system() == "Darwin":
        lib, flags = out / "libfakeclock.dylib", ["-dynamiclib"]
    else:
        lib, flags = out / "libfakeclock.so", ["-shared", "-fPIC", "-ldl"]
    source = HERE / "fakeclock.c"
    if not lib.exists() or lib.stat().st_mtime < source.stat().st_mtime:
        subprocess.run(["cc", "-O2", "-Wall", *flags, "-o", str(lib), str(source)], check=True)
    return lib


def build(
    out: Path,
    *,
    variant: str = "standard",
    extra: list[Folder] | None = None,
    events: bool = False,
    port: int = 6053,
    quiet: bool = True,
) -> Build:
    """Compile the desktop build in `out` (a scratch folder) and return it.

    `variant` picks the screen: standard (320x240), wide (480x272) or square
    (240x240). `extra` are folders of persona packages (default: the ones
    DARUMA_PERSONA_PATH names, see persona_path.py); their personas are
    marked private. `events` turns the random events engine on, with its
    switch off: only play_random_event plays events. One build serves every
    time zone: the device takes its zone from "Home Assistant", as on the BOX-3.
    """
    out = Path(out)
    src = out / "src"
    _copy_sources(src)
    config_dir = src / "examples"
    extra = persona_path.folders() if extra is None else extra
    name = _build_name(variant, extra, events)
    subs = {"name": name, "desktop_api_port": str(port), **VARIANTS[variant]}
    yaml_name, private = _write_config(config_dir, name, extra, events)
    cmd, env = _esphome_command(src)
    for k, v in subs.items():
        cmd += ["-s", k, v]
    cmd += ["compile", yaml_name]
    log = out / f"compile-{name}.log"
    with open(log, "w") as fh:
        result = subprocess.run(cmd, cwd=config_dir, env=env, stdout=fh if quiet else None, stderr=subprocess.STDOUT)
    if result.returncode != 0:
        tail = "\n".join(log.read_text().splitlines()[-30:]) if quiet else ""
        raise DeviceError(f"Compile failed (log: {log})\n{tail}")
    program = config_dir / ".esphome" / "build" / name / ".pioenvs" / name / "program"
    return Build(program=program, clock_lib=build_clock_lib(out), port=port, private_personas=private)


def _build_name(variant: str, extra: list[Folder], events: bool = False) -> str:
    """The build's name, which is also its folder: one per kind of build."""
    name = "daruma-desktop" if variant == "standard" else f"daruma-desktop-{variant}"
    if events:
        name += "-events"
    if extra:
        name += "-private"  # Its own build folder: the public build stays as it is.
    if COVERAGE:
        name += "-cov"
    return name


def _write_config(
    config_dir: Path, name: str, extra: list[Folder], events: bool = False
) -> tuple[str, dict[str, Folder]]:
    """The config file for build `name`, and its private personas with their folders."""
    if name == "daruma-desktop":
        return DEVICE_YAML, {}
    # ESPHome keeps a record of the last build per config file, and cleans
    # the build folder when the name in it differs. A config file per build
    # name keeps each build's objects for the next build.
    lines = ["packages:", f"  base: !include {DEVICE_YAML}"]
    packages = [pkg for folder in extra for pkg in folder.packages]
    for i, pkg in enumerate(packages):
        lines.append(f"  private_{i}: !include {pkg}")
    private = persona_path.personas(extra)
    if events:
        # The main config merges over its packages, and a mapping replaces
        # a `random_events: false` there. The switch starts off, so no roll
        # plays on its own.
        lines += ["daruma:", "  random_events:", "    enabled: false"]
    if COVERAGE:
        # Lists merge by joining, so this adds to the board's build flags.
        lines += ["esphome:", "  build_flags:", "    - --coverage"]
    yaml_name = f"{name}.yaml"
    (config_dir / yaml_name).write_text("\n".join(lines) + "\n")
    return yaml_name, private


def _esphome_command(src: Path) -> tuple[list[str], dict[str, str]]:
    """The command that runs ESPHome, and its environment.

    With coverage on, ESPHome runs under coverage.py, which measures the
    components' Python and the pixel art in the scratch copy `src`.
    """
    if ESPHOME_SPEC:
        return ["uvx", "--python", PYTHON, "--from", ESPHOME_SPEC, "esphome"], dict(os.environ)
    if not COVERAGE:
        return [sys.executable, "-m", "esphome"], dict(os.environ)
    data = Path(COVERAGE).resolve()
    data.mkdir(parents=True, exist_ok=True)
    run = [sys.executable, "-m", "coverage", "run", "--parallel-mode", f"--data-file={data / '.coverage'}"]
    run += [f"--source={src / 'src' / 'esphome' / 'components'},{src / 'pixel'}", "-m", "esphome"]
    return run, dict(os.environ)


# Screen sizes, with font sizes to match (as examples/variant_*.yaml).
VARIANTS: dict[str, dict[str, str]] = {
    "standard": {},
    "wide": {
        "desktop_width": "480",
        "desktop_height": "272",
        "font_size_text": "19",
        "font_size_small": "15",
        "font_size_badge": "19",
        "font_size_icon": "34",
        "font_size_timer": "25",
        "font_size_title": "23",
    },
    "square": {"desktop_width": "240", "desktop_height": "240"},
}


# The screen is RGB565: 5 bits of red and blue, 6 of green. SDL widens them
# to 8 bits when it saves a screenshot, and SDL builds do it differently: on
# Linux some values come out one step off. They all keep the top bits,
# though. So keep those and widen them again, with the usual formula (copy
# the top bits into the empty low bits), and every system gives the same
# picture.
_WIDEN_5 = [((v >> 3) << 3) | (v >> 5) for v in range(256)]
_WIDEN_6 = [((v >> 2) << 2) | (v >> 6) for v in range(256)]


def rgb565_to_rgb888(img):
    """`img` (RGB) with each channel cut to RGB565 and widened to 8 bits again."""
    return img.point(_WIDEN_5 + _WIDEN_6 + _WIDEN_5)


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


# --------------------------------------------------------------------------
# What is on screen
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Node:
    role: str
    name: str
    x: int
    y: int
    w: int
    h: int
    focused: bool = False
    value: str = ""

    @property
    def center(self) -> tuple[int, int]:
        return self.x + self.w // 2, self.y + self.h // 2


@dataclass
class Event:
    """Something the device told Home Assistant."""

    type: str  # an HA event ("esphome.daruma_prompt") or "entity:<name>"
    data: dict[str, Any]
    at: float  # device seconds


class Locator:
    """A lazy query over the parts on screen; resolved on each use."""

    def __init__(self, device: Device, description: str, match: Callable[[Node], bool]):
        self.device = device
        self.description = description
        self._match = match

    def __repr__(self) -> str:
        return f"Locator({self.description})"

    def all(self) -> list[Node]:
        return [n for n in self.device.ui() if self._match(n)]

    def count(self) -> int:
        return len(self.all())

    def is_visible(self) -> bool:
        return bool(self.all())

    def wait_for(self, timeout: float = 5.0) -> Node:
        """Advance frame by frame until the part shows; return it."""
        found = self.device.wait_until(lambda: self.all(), timeout)
        if not found:
            raise AssertionError(f"{self} did not show within {timeout} s. On screen: {self.device.ui_text()}")
        return found[0]

    def bounding_box(self, timeout: float = 5.0) -> tuple[int, int, int, int]:
        n = self.wait_for(timeout)
        return n.x, n.y, n.w, n.h

    def tap(self, timeout: float = 5.0) -> None:
        x, y = self.wait_for(timeout).center
        self.device.tap(x, y)


# --------------------------------------------------------------------------
# The clock file
# --------------------------------------------------------------------------


class Clock:
    """The clock and seed that fakeclock.c reads, in a shared file."""

    def __init__(self, path: Path, seed: int, epoch: int):
        self.path = path
        path.write_bytes(b"\0" * 4096)
        self._fh = open(path, "r+b")  # noqa: SIM115 - mapped until close()
        self._map = mmap.mmap(self._fh.fileno(), 4096)
        self.ns = START_NS
        struct.pack_into("<QQQ", self._map, 0, self.ns, epoch, seed or 1)
        # One aligned 8-byte store, so the program never reads half a time.
        # (struct.pack_into clears the bytes before it writes them.)
        self._now = ctypes.c_uint64.from_buffer(self._map, 0)

    def set(self, ns: int) -> None:
        self.ns = ns
        self._now.value = ns

    def close(self) -> None:
        del self._now
        self._map.close()
        self._fh.close()


# --------------------------------------------------------------------------
# The device
# --------------------------------------------------------------------------


def _prompt_fields(
    id: str,
    title: str,
    body: str,
    options: list[str] | None,
    layout: str,
    style: str,
    timeout: int,
    state: str,
    sound: str,
    marks: list[str] | None,
    dismissable: bool,
) -> dict[str, Any]:
    """The fields of prompt_show and ask, as HA sends them."""
    return {
        "id": id,
        "layout": layout,
        "title": title,
        "body": body,
        "options": options or [],
        "marks": marks or [],
        "style": style,
        "timeout": timeout,
        "state": state,
        "sound": sound,
        "dismissable": dismissable,
    }


class Device:
    """One running desktop device. Use as a context manager."""

    def __init__(
        self,
        build: Build,
        workdir: Path,
        *,
        persona: str | None = None,
        seed: int = 1,
        epoch: int = EPOCH,
        timezone: str = TIMEZONE,
        window: bool = False,
        data: Any = None,
        golden: Path | None = None,
        update_golden: bool = False,
        port: int | None = None,
    ):
        from demo_data import DemoData

        self.build = build
        # The API port. A free one by default, so devices from one build
        # (and other runners on this machine) never share a port.
        self.port = port or free_port()
        self.workdir = Path(workdir)
        self.persona = persona
        self.seed = seed
        self.epoch = epoch
        # The clock's time zone (an IANA name). "HA" sends it with the time,
        # as Home Assistant does, and its calendar keeps the same days.
        utc_offset(timezone, epoch)  # An unknown zone fails here, not at start.
        self.timezone = timezone
        self.window = window
        self.data = data if data is not None else DemoData()
        self.data.zone = timezone
        # Where to_match_screenshot() keeps its pictures.
        self.golden = golden
        self.update_golden = update_golden
        self.events: list[Event] = []
        self.frames_dir: Path | None = None
        self.skipped: list[tuple[int, int]] = []  # (from, to) ms of the recording left out
        self.captions: list[tuple[int, str]] = []  # (ms of the recording, text) from caption()
        # Taps, swipes and presses while recording, for record.py's touch marks
        # (media.with_touches): {"ms", "kind", "points", "ms_long"}.
        self.touches: list[dict[str, Any]] = []
        self._proc: subprocess.Popen | None = None
        self._loop = asyncio.new_event_loop()
        self._client = None
        self._entities: dict[str, Any] = {}
        self._entity_by_key: dict[int, Any] = {}
        self._states: dict[str, Any] = {}
        self._services: dict[str, Any] = {}
        # HA states the device subscribed to: (entity, attribute or None).
        self._ha_subs: set[tuple[str, str | None]] = set()
        self._answers = 0
        self._calls_seen = 0  # Everything the device sent "HA": actions and events.
        self._status: dict[str, Any] = {}
        self._record_start_ns = 0
        self._paused_at: int | None = None

    # --- life cycle ---------------------------------------------------------

    def __enter__(self) -> Device:
        self.start()
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def start(self) -> None:
        """Start the program and connect. If any step fails, the program
        is stopped before the error goes on: no device is left running."""
        try:
            self._start()
        except BaseException:
            self.close()
            raise

    def _start(self) -> None:
        self.workdir.mkdir(parents=True, exist_ok=True)
        prefs = self.workdir / "prefs"
        shutil.rmtree(prefs, ignore_errors=True)
        prefs.mkdir()
        _wait_port_free(self.port)
        self.clock = Clock(self.workdir / "clock", self.seed, self.epoch)
        env = dict(os.environ)
        env.update(
            DARUMA_CLOCK=str(self.clock.path),
            DARUMA_API_PORT=str(self.port),
            ESPHOME_PREFDIR=str(prefs),
            ESPHOME_SNAPSHOT_DIR=str(self.workdir),
        )
        if platform.system() == "Darwin":
            env["DYLD_INSERT_LIBRARIES"] = str(self.build.clock_lib)
        else:
            env["LD_PRELOAD"] = str(self.build.clock_lib)
        if not self.window:
            env["SDL_VIDEODRIVER"] = "dummy"
        self._log = open(self.workdir / "device.log", "w")  # noqa: SIM115 - the program writes it until close()
        self._proc = subprocess.Popen([str(self.build.program)], env=env, stdout=self._log, stderr=subprocess.STDOUT)
        self._run(self._connect())
        self._wait_for_timezone()
        # The subscriptions take effect before the clock first moves, so the
        # device sees "HA" arrive at the same time on every run.
        self._settle()
        self.advance(1.0)
        if self.persona:
            self.set("Persona", self.persona)
            self.advance(1.0)
            if self.status()["persona"] != self.persona:
                raise DeviceError(f"No persona named {self.persona!r}; personas: {self.personas()}")

    def close(self) -> None:
        if self._client is not None:
            with contextlib.suppress(Exception):  # Closing anyway.
                self._run(self._client.disconnect(), timeout=3)
            self._client = None
        if self._proc is not None:
            self._proc.terminate()
            try:
                self._proc.wait(5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
            self._proc = None
            self._log.close()
        if hasattr(self, "clock"):
            self.clock.close()
        self._loop.close()

    def _run(self, coro, timeout: float = 30):
        if self._proc is not None and self._proc.poll() is not None:
            raise DeviceError(f"The program stopped (code {self._proc.returncode}); see {self.workdir / 'device.log'}")
        return self._loop.run_until_complete(asyncio.wait_for(coro, timeout))

    async def _connect(self) -> None:
        import logging

        from aioesphomeapi import APIClient

        # Refused connections while the program starts are expected; keep them out of the output.
        logging.getLogger("aioesphomeapi").setLevel(logging.ERROR)

        deadline = time.monotonic() + 20
        while True:
            # The client answers the device's time requests itself. `timezone`
            # is the zone it sends; without it, this machine's zone goes out.
            # (Its time goes out too, but the device keeps the runner's clock.)
            client = APIClient("127.0.0.1", self.port, None, client_info="daruma-harness", timezone=self.timezone)
            try:
                await client.connect(login=True)
                break
            except Exception as err:  # noqa: BLE001 - the program is still starting
                if time.monotonic() > deadline or self._proc.poll() is not None:
                    raise DeviceError(f"Could not reach the program; see {self.workdir / 'device.log'}") from err
                await asyncio.sleep(0.1)
        self._client = client
        entities, services = await client.list_entities_services()
        for e in entities:
            self._entities[e.name] = e
            self._entity_by_key[e.key] = e
        self._services = {s.name: s for s in services}
        client.subscribe_states(self._on_state)
        client.subscribe_service_calls(self._on_service_call)
        client.subscribe_home_assistant_states(self._on_ha_subscription)

    # --- Home Assistant's side -------------------------------------------------

    def _on_state(self, state) -> None:
        info = self._entity_by_key.get(state.key)
        if info is None:
            return
        self._states[info.name] = state
        event_type = getattr(state, "event_type", None)
        if event_type:
            self.events.append(Event(f"entity:{info.name}", {"event_type": event_type}, self.now()))

    def _on_ha_subscription(self, entity: str, attribute: str | None) -> None:
        # The device wants an HA entity's state, or an attribute, as it changes.
        self._ha_subs.add((entity, attribute or None))
        self._send_ha_state(entity, attribute or None)

    def _send_ha_state(self, entity: str, attribute: str | None) -> None:
        value = self.data.entity_value(entity, attribute)
        if value is None:
            return
        self._client.send_home_assistant_state(entity, attribute, value)
        self._calls_seen += 1

    def _push_ha_entity(self, entity: str) -> None:
        for sub_entity, attribute in sorted(self._ha_subs, key=lambda s: (s[0], s[1] or "")):
            if sub_entity == entity:
                self._send_ha_state(entity, attribute)

    def ha_state(self, entity: str, state: str | None = None, **attributes: str) -> None:
        """Change an HA entity the device subscribes to, as HA would, and push it."""
        values = self.data.entities.setdefault(entity, {})
        if state is not None:
            values["state"] = state
        values.update(attributes)
        self._push_ha_entity(entity)
        self._settle()

    def _on_service_call(self, call) -> None:
        self._calls_seen += 1
        if call.is_event:
            data = dict(call.data)
            for k, v in call.data_template.items():
                # The device's templates here only cast a variable: "{{ index | int }}".
                m = re.fullmatch(r"\{\{\s*(\w+)[^}]*\}\}", v)
                data[k] = call.variables.get(m.group(1), v) if m else v
            self.events.append(Event(call.service, data, self.now()))
            return
        ok, response = self.data.reply(call.service, dict(call.data), self.wall_time())
        entity = call.data.get("entity_id", "")
        if entity in self.data.entities:
            self._push_ha_entity(entity)
        if call.call_id:
            body = json.dumps({"response": response}).encode() if call.wants_response and ok else b""
            self._client.send_homeassistant_action_response(
                call.call_id, success=ok, error_message="" if ok else self.data.error, response_data=body
            )
            self._answers += 1

    # --- time ------------------------------------------------------------------

    def now(self) -> float:
        """Seconds on the device's monotonic clock since start."""
        return (self.clock.ns - START_NS) / 1e9

    def wall_time(self) -> int:
        """The device's wall clock now, in epoch seconds."""
        return self.epoch + self.clock.ns // 1_000_000_000

    def _sync(self) -> dict:
        svc = self._services["desktop_status"]
        result = self._run(self._client.execute_service(svc, {}, return_response=True))
        if result is None or not result.success:
            raise DeviceError(f"desktop_status failed: {result}")
        self._status = json.loads(result.response_data or b"{}")
        return self._status

    def _settle(self) -> None:
        # Wait until the device has done everything that is due at the
        # current time. Every reply says on which turn of its main loop the
        # device handled the request ("loops"). Whatever the runner sent
        # before that request was handled on that turn or earlier. "idle" is
        # the last turn that started with nothing due at its time (see
        # idle_loop_ in daruma_desktop). An idle turn two turns after the
        # mark means every component has run since, and nothing is left over:
        # no timer, no frame, no call to "HA" waiting for its answer.
        #
        # An answer to "HA" goes out while the runner waits for a reply, so
        # the next reply after it gives the new mark.
        want = (self.clock.ns // 1_000_000) & 0xFFFFFFFF
        deadline = time.monotonic() + SETTLE_TIMEOUT
        seen = self._calls_seen
        s = self._sync()
        while s["millis"] != want:
            self._check_deadline(deadline, "does not take the runner's clock (is fakeclock loaded?)")
            s = self._sync()
        mark = s["loops"]
        while True:
            if self._calls_seen != seen:
                seen = self._calls_seen
                s = self._sync()
                mark = s["loops"]
                continue
            if s["idle"] >= mark + 2:
                return
            self._check_deadline(deadline, f"still has work due at this time: {s.get('busy') or 'unknown'}")
            s = self._sync()

    def _wait_for_timezone(self) -> None:
        # The device keeps the zone it was built in until "HA" answers its
        # first time request. The clock stands still until the run's zone is
        # in place, so no screen shows the build's zone.
        want = utc_offset(self.timezone, self.wall_time())
        deadline = time.monotonic() + SETTLE_TIMEOUT
        while self._sync()["utc_offset"] != want:
            self._check_deadline(deadline, f'did not take the time zone {self.timezone} from "HA"')

    def _check_deadline(self, deadline: float, what: str) -> None:
        if time.monotonic() > deadline:
            raise DeviceError(f"After {SETTLE_TIMEOUT} s, the device {what}; see {self.workdir / 'device.log'}")

    def advance(self, seconds: float, step: float = STEP) -> None:
        """Move the device's clock on, a step at a time."""
        target = self.clock.ns + int(round(seconds * 1e9))
        step_ns = int(round(step * 1e9))
        while self.clock.ns < target:
            self.clock.set(min(target, self.clock.ns + step_ns))
            self._settle()

    def skip(self, seconds: float) -> None:
        """Advance fast, in 1 s steps, and leave the time out of the recording."""
        recording = self.frames_dir is not None
        if recording:
            self._call("desktop_record_pause", paused=True)
            # Handled before the clock moves, or the first skipped frame is kept.
            self._settle()
            start = self._rec_ms()
        self.advance(seconds, step=1.0)
        if recording:
            self.skipped.append((start, self._rec_ms()))
            self._call("desktop_record_pause", paused=False)
            self._settle()

    def wait_until(self, condition: Callable[[], Any], timeout: float = 5.0) -> Any:
        """Advance frame by frame until condition() is truthy; return its value, or None."""
        end = self.clock.ns + int(timeout * 1e9)
        while True:
            value = condition()
            if value:
                return value
            if self.clock.ns >= end:
                return None
            self.advance(STEP)

    # --- device state ------------------------------------------------------------

    def status(self) -> dict:
        return self._status or self._sync()

    def state(self) -> str:
        """The state the persona shows now: a reaction, the top activity or the mood."""
        return self.status()["state"]

    def ui(self) -> list[Node]:
        return [Node(**n) for n in self.status().get("ui", [])]

    def ui_text(self) -> str:
        return ", ".join(f"{n.role}:{n.name!r}" for n in self.ui()) or "(no parts)"

    def personas(self) -> list[str]:
        return list(self._entities["Persona"].options)

    def entity_state(self, name: str) -> Any:
        s = self._states.get(name)
        if s is None:
            return None
        # A light: its brightness, 0 when off.
        if type(s).__name__ == "LightState":
            return round(s.brightness, 2) if s.state else 0
        # A time entity: "HH:MM".
        if type(s).__name__ == "TimeState":
            return f"{s.hour:02d}:{s.minute:02d}"
        return getattr(s, "state", None)

    def get_by_text(self, text: str, exact: bool = True) -> Locator:
        if exact:
            return Locator(self, f"text={text!r}", lambda n: n.name == text)
        return Locator(self, f"text~={text!r}", lambda n: text.lower() in n.name.lower())

    def get_by_role(self, role: str, name: str | None = None) -> Locator:
        return Locator(
            self, f"role={role} name={name!r}", lambda n: n.role == role and (name is None or n.name == name)
        )

    # --- input -------------------------------------------------------------------

    def _call(self, action: str, **data: Any) -> None:
        if action not in self._services:
            raise DeviceError(f"No API action {action!r}; there are: {', '.join(sorted(self._services))}")
        self._run(self._client.execute_service(self._services[action], data))

    def _until_input_done(self) -> None:
        self._settle()
        self.wait_until(lambda: not self._sync().get("touch_busy"), timeout=30)
        # Gestures fire on lift-off; give the hub a frame to act and draw.
        self.advance(0.15)

    def _touch(self, kind: str, points: list[tuple[int, int]], ms_long: int = 0) -> None:
        if self.frames_dir is not None:
            self.touches.append({"ms": self._rec_ms(), "kind": kind, "points": points, "ms_long": ms_long})

    def tap(self, x: int, y: int) -> None:
        self._touch("tap", [(x, y)])
        self._call("desktop_tap", x=int(x), y=int(y))
        self._until_input_done()

    def hold(self, x: int, y: int, seconds: float) -> None:
        self._touch("hold", [(x, y)], int(seconds * 1000))
        self._call("desktop_hold", x=int(x), y=int(y), ms=int(seconds * 1000))
        self._until_input_done()

    def swipe(self, x1: int, y1: int, x2: int, y2: int, seconds: float = 0.25) -> None:
        self._touch("swipe", [(x1, y1), (x2, y2)], int(seconds * 1000))
        self._call("desktop_swipe", x1=int(x1), y1=int(y1), x2=int(x2), y2=int(y2), ms=int(seconds * 1000))
        self._until_input_done()

    def stroke(self, x: int, y: int) -> None:
        self._touch("stroke", [(x, y)])
        self._call("desktop_stroke", x=int(x), y=int(y))
        self._until_input_done()

    def pet(self) -> None:
        """Stroke the middle of the persona."""
        w, h = self.screen_size()
        self.stroke(w // 2, h * 2 // 5)

    def react(self, state: str) -> None:
        """Play a reaction by its state name ("petted", "startled", ...), as a module would."""
        self._call("desktop_react", state=state)
        self._settle()

    def states(self) -> list[dict[str, Any]]:
        """Every state the build knows, in StateId order: {name, kind, duration_ms}."""
        if not hasattr(self, "_state_list"):
            svc = self._services["desktop_states"]
            result = self._run(self._client.execute_service(svc, {}, return_response=True))
            if result is None or not result.success:
                raise DeviceError(f"desktop_states failed: {result}")
            self._state_list = json.loads(result.response_data or b"{}")["states"]
        return self._state_list

    def show(self, state: str) -> None:
        """Show any registered state by name: a mood is forced, an activity
        held, a reaction played. "" ends the forced mood and the activity."""
        known = {s["name"]: s for s in self.states()}
        if state and state not in known:
            raise DeviceError(f"No state {state!r}; states: {', '.join(known)}")
        self._call("desktop_show", state=state)
        self._settle()
        info = known.get(state)
        # A sound-only reaction (duration 0) never shows as the state.
        if info and not (info["kind"] == "reaction" and info["duration_ms"] == 0):
            expect(self).to_have_state(state, timeout=2)

    def voice(self, phase: str, text: str = "") -> None:
        """The voice assistant's screen for a phase: listening, thinking,
        replying, error, timer, or idle to end it."""
        self._call("desktop_voice", phase=phase, words=text)
        self._settle()

    def caption(self, text: str) -> None:
        """A caption for the recording from now on (record.py draws it under the screen)."""
        if self.frames_dir is not None:
            self.captions.append((self._rec_ms(), text))

    def press(self, input_name: str, seconds: float = 0.08) -> None:
        """Press a board input ("home", "top") for `seconds`."""
        self._touch(f"press:{input_name}", [], int(seconds * 1000))
        self._call("desktop_press", input=input_name, ms=int(seconds * 1000))
        self._until_input_done()

    def screen_size(self) -> tuple[int, int]:
        img = self.screenshot()
        return img.size

    # --- Home Assistant actions and entities -----------------------------------------

    def action(self, name: str, **data: Any) -> None:
        """Call one of the device's API actions, as an HA automation would."""
        self._call(name, **data)
        self._settle()

    def random_event(self, name: str = "") -> None:
        """Play a random event by name, as an HA automation does. "" rolls the pool.

        Only a build with the engine has the action (build(events=True)).
        action() can't take it: its first parameter is called `name` too.
        """
        self._call("play_random_event", name=name)
        self._settle()

    def show_message(self, text: str, seconds: int = 5) -> None:
        self.action("show_message", message=text, seconds=seconds)

    def show_prompt(
        self,
        id: str,
        title: str = "",
        body: str = "",
        options: list[str] | None = None,
        layout: str = "message",
        style: str = "info",
        timeout: int = 0,
        state: str = "",
        sound: str = "",
        marks: list[str] | None = None,
        dismissable: bool = True,
    ) -> None:
        """prompt_show with HA's "empty means default" values filled in."""
        self.action(
            "prompt_show",
            **_prompt_fields(id, title, body, options, layout, style, timeout, state, sound, marks, dismissable),
        )

    def ask(
        self,
        id: str,
        title: str = "",
        body: str = "",
        options: list[str] | None = None,
        layout: str = "message",
        style: str = "info",
        timeout: int = 0,
        state: str = "",
        sound: str = "",
        marks: list[str] | None = None,
        dismissable: bool = True,
    ) -> Callable[[], Any]:
        """Starts the `ask` action, as an HA script would. It waits for the
        answer, so it runs in the background while the test taps and moves the
        clock. Returns a function that waits for the reply and returns it:
        `.success`, `.error_message`, and the answer in `.response_data`."""
        fields = _prompt_fields(id, title, body, options, layout, style, timeout, state, sound, marks, dismissable)
        call = self._client.execute_service(self._services["ask"], fields, return_response=True)
        task = self._loop.create_task(call)
        self._settle()

        def reply(timeout: float = 10.0) -> Any:
            return self._run(task, timeout)

        return reply

    def run_action(self, name: str) -> None:
        """Run one of the hub's named actions, as a binding would ("prompts.dismiss")."""
        self._call("desktop_action", name=name)
        self._settle()

    def update_prompt(self, id: str, body: str = "", marks: list[str] | None = None, countdown: int = -1) -> None:
        self.action("prompt_update", id=id, body=body, marks=marks or [], countdown=countdown)

    def set(self, entity: str, value: Any) -> None:
        """Set a select, number, switch, text or time ("HH:MM") entity by its name, as HA would."""
        info = self._entities.get(entity)
        if info is None:
            raise DeviceError(f"No entity {entity!r}")
        kind = type(info).__name__
        c = self._client
        if kind == "SelectInfo":
            c.select_command(info.key, str(value))
        elif kind == "NumberInfo":
            c.number_command(info.key, float(value))
        elif kind == "SwitchInfo":
            c.switch_command(info.key, bool(value))
        elif kind == "TextInfo":
            c.text_command(info.key, str(value))
        elif kind == "ButtonInfo":
            c.button_command(info.key)
        elif kind == "TimeInfo":
            hour, minute = (int(p) for p in str(value).split(":"))
            c.time_command(info.key, hour, minute, 0)
        else:
            raise DeviceError(f"Can't set {entity!r} ({kind})")
        self._settle()

    # --- pictures ----------------------------------------------------------------------

    def screenshot(self, path: Path | None = None):
        """The screen now, as a PIL image (RGB). Saved as PNG when `path` is given.

        The colors are the screen's RGB565 colors, widened to 8 bits the same
        way everywhere (see rgb565_to_rgb888).
        """
        from PIL import Image

        shots = self.workdir / "shots"
        self._call("desktop_screenshot", dir=str(shots), name="now")
        self._settle()
        bmp = shots / "now.bmp"
        with Image.open(bmp) as im:
            img = rgb565_to_rgb888(im.convert("RGB"))
        if path is not None:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            img.save(path)
        return img

    def _rec_ms(self) -> int:
        return (self.clock.ns - self._record_start_ns) // 1_000_000

    def record_start(self, frames_dir: Path) -> None:
        """Save every frame (and sound) from now on, for a GIF or a trace."""
        frames_dir = Path(frames_dir)
        shutil.rmtree(frames_dir, ignore_errors=True)
        self.frames_dir = frames_dir
        self.skipped = []
        self.captions = []
        self.touches = []
        self._record_start_ns = self.clock.ns
        self._call("desktop_record_start", dir=str(frames_dir))
        self._settle()

    def record_stop(self) -> Path | None:
        if self.frames_dir is None:
            return None
        self._call("desktop_record_stop")
        self._settle()
        out, self.frames_dir = self.frames_dir, None
        return out


def free_port() -> int:
    """A TCP port that nothing listens on now, for a device of its own."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def utc_offset(zone: str, epoch: int) -> int:
    """The seconds to add to UTC for the local time in `zone` at `epoch`."""
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    try:
        tz = ZoneInfo(zone)
    except (ZoneInfoNotFoundError, ValueError) as err:
        raise DeviceError(f"Unknown time zone {zone!r}") from err
    return int(datetime.fromtimestamp(epoch, tz).utcoffset().total_seconds())


def _wait_port_free(port: int, timeout: float = 10) -> None:
    """A program from the last run may still hold the API port for a moment."""
    deadline = time.monotonic() + timeout
    while True:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return
        if time.monotonic() > deadline:
            raise DeviceError(f"Port {port} is in use: is another desktop device running?")
        time.sleep(0.1)


# --------------------------------------------------------------------------
# Expectations
# --------------------------------------------------------------------------


def _count_over(diff, tolerance: int) -> int:
    """Pixels where any channel differs by more than `tolerance`."""
    data = diff.tobytes()
    return sum(1 for i in range(0, len(data), 3) if max(data[i], data[i + 1], data[i + 2]) > tolerance)


def expect(target: Device | Locator) -> DeviceAssertions | LocatorAssertions:
    if isinstance(target, Locator):
        return LocatorAssertions(target)
    return DeviceAssertions(target)


class LocatorAssertions:
    def __init__(self, locator: Locator):
        self.locator = locator

    def to_be_visible(self, timeout: float = 5.0) -> None:
        self.locator.wait_for(timeout)

    def to_be_hidden(self, timeout: float = 5.0) -> None:
        if self.locator.device.wait_until(lambda: not self.locator.all(), timeout) is None:
            raise AssertionError(f"{self.locator} still shows after {timeout} s")

    def to_have_value(self, value: str, timeout: float = 5.0) -> None:
        if not self.locator.device.wait_until(lambda: any(n.value == value for n in self.locator.all()), timeout):
            raise AssertionError(f"{self.locator} has no value {value!r}: {self.locator.all()}")


class DeviceAssertions:
    def __init__(self, device: Device):
        self.device = device

    def to_have_state(self, state: str | list[str], timeout: float = 5.0) -> None:
        """The persona shows this state, or one of a list (a persona may play its own reaction first)."""
        wanted = [state] if isinstance(state, str) else list(state)
        if not self.device.wait_until(lambda: self.device.state() in wanted, timeout):
            raise AssertionError(f"State is {self.device.state()!r}, not {state!r}, after {timeout} s")

    def to_fire_event(self, event: str, /, timeout: float = 5.0, **data: Any) -> Event:
        """An HA event ("esphome.daruma_prompt") or an event entity ("entity:Event")
        whose data has these values."""

        def match() -> Event | None:
            for e in self.device.events:
                if e.type == event and all(str(e.data.get(k)) == str(v) for k, v in data.items()):
                    return e
            return None

        found = self.device.wait_until(match, timeout)
        if not found:
            seen = [(e.type, e.data) for e in self.device.events]
            raise AssertionError(f"No event {event} {data} within {timeout} s; seen: {seen}")
        return found

    def to_have_entity(self, name: str, value: Any, timeout: float = 5.0) -> None:
        def ok() -> bool:
            v = self.device.entity_state(name)
            return v == value or str(v) == str(value)

        if not self.device.wait_until(ok, timeout):
            raise AssertionError(f"{name} is {self.device.entity_state(name)!r}, not {value!r}")

    def to_match_screenshot(
        self, name: str, *, mask: list[tuple[int, int, int, int]] = (), tolerance: int = 0, max_diff_pixels: int = 0
    ) -> None:
        """Compare the screen with the golden PNG `name`.

        A pixel differs when a channel is off by more than `tolerance`; the
        check fails with more than `max_diff_pixels` such pixels. `mask`
        rectangles (x, y, w, h) are left out. Writes the actual picture and a
        diff next to the frames on failure; with update_golden, writes the
        golden instead.
        """
        from PIL import Image, ImageChops

        b = self.device
        if b.golden is None:
            raise DeviceError("No golden folder set for this device")
        golden = b.golden / f"{name}.png"
        actual = b.screenshot()
        for x, y, w, h in mask:
            actual.paste((255, 0, 255), (x, y, x + w, y + h))
        if b.update_golden:
            # Keep a golden that shows the same pixels: PNG files from another
            # system's zlib differ in their bytes, not in their pixels.
            if golden.exists():
                with Image.open(golden) as g:
                    same = g.size == actual.size and not ImageChops.difference(g.convert("RGB"), actual).getbbox()
                if same:
                    return
            golden.parent.mkdir(parents=True, exist_ok=True)
            actual.save(golden, optimize=True)
            return
        out = b.workdir / "results"
        if not golden.exists():
            out.mkdir(parents=True, exist_ok=True)
            actual.save(out / f"{name}-actual.png")
            raise AssertionError(
                f"No golden {golden}; run with --update-golden. Actual: {out / (name + '-actual.png')}"
            )
        with Image.open(golden) as g:
            expected = g.convert("RGB")
        if expected.size != actual.size:
            out.mkdir(parents=True, exist_ok=True)
            actual.save(out / f"{name}-actual.png")
            expected.save(out / f"{name}-expected.png")
            raise AssertionError(f"{name}: size {actual.size}, golden {expected.size}")
        diff = ImageChops.difference(actual, expected)
        bad = _count_over(diff, tolerance)
        if bad > max_diff_pixels:
            out.mkdir(parents=True, exist_ok=True)
            actual.save(out / f"{name}-actual.png")
            expected.save(out / f"{name}-expected.png")
            mark = diff.point(lambda v: 255 if v > tolerance else 0).convert("L")
            red = Image.new("RGB", actual.size, (255, 0, 0))
            Image.composite(red, Image.blend(expected, Image.new("RGB", actual.size), 0.6), mark).save(
                out / f"{name}-diff.png"
            )
            raise AssertionError(f"{name}: {bad} pixels differ (allowed {max_diff_pixels}); see {out}")
