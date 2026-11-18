"""Keeps the README's table of screens whole: a still for every app.

Each app a package offers (`daruma: modules: apps:`) needs a snapshot in
demos/scenarios/screens.yaml named after the app ("calendar", or
"calendar-day" for a second one). `make gifs SCENARIO=screens` writes each
snapshot to docs/demos/screens/, and the README shows them.
"""

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
PACKAGES = ROOT / "packages"
SCENARIO = ROOT / "demos" / "scenarios" / "screens.yaml"
SCREENS = ROOT / "docs" / "demos" / "screens"
README = ROOT / "README.md"
PERSONA = "daruma"


def _load(path: Path):
    class Loader(yaml.SafeLoader):
        pass

    Loader.add_multi_constructor("!", lambda loader, suffix, node: None)
    return yaml.load(path.read_text(), Loader=Loader)  # noqa: S506 - a SafeLoader that drops ESPHome tags


def _fill(text: str, subs: dict[str, object]) -> str:
    return re.sub(r"\$\{(\w+)\}", lambda m: str(subs[m.group(1)]), text)


def _apps() -> list[str]:
    """The name of every app, with the package's defaults filled in."""
    names = []
    for path in sorted(PACKAGES.glob("*.yaml")):
        raw = _load(path) or {}
        subs = {**(raw.get("substitutions") or {}), **(raw.get("defaults") or {})}
        for module in (raw.get("daruma") or {}).get("modules") or []:
            for app in module.get("apps") or []:
                names.append(_fill(str(app["name"]), subs))
    return names


def _snapshots(steps: list[dict]) -> list[str]:
    out = []
    for step in steps:
        if "steps" in step:
            out += _snapshots(step["steps"])
        elif "snapshot" in step:
            arg = step["snapshot"]
            out.append(arg if isinstance(arg, str) else arg["name"])
    return out


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


SNAPSHOTS = _snapshots(_load(SCENARIO)["steps"])


def test_packages_offer_apps():
    assert len(_apps()) >= 4, _apps()


@pytest.mark.parametrize("app", _apps())
def test_every_app_has_a_still(app):
    slug = _slug(app)
    mine = [s for s in SNAPSHOTS if s == slug or s.startswith(f"{slug}-")]
    assert mine, f"No snapshot named '{slug}' in {SCENARIO.relative_to(ROOT)}: add one that shows the {app} app"


@pytest.mark.parametrize("name", SNAPSHOTS)
def test_every_still_is_in_the_readme(name):
    png = SCREENS / f"{PERSONA}-{name}.png"
    assert png.exists(), f"{png.relative_to(ROOT)} is missing: run make gifs SCENARIO=screens"
    assert str(png.relative_to(ROOT)) in README.read_text(), f"README.md does not show {png.relative_to(ROOT)}"


def test_no_stale_stills():
    known = {f"{PERSONA}-{name}.png" for name in SNAPSHOTS}
    stale = sorted(p.name for p in SCREENS.glob("*.png") if p.name not in known)
    assert not stale, f"No snapshot in {SCENARIO.name} makes {stale}: delete them"
