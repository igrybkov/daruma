"""Screen tests on the desktop build. See conftest.py for how to run them."""

from __future__ import annotations

import pytest
import scenario as scenarios
from harness import expect


def test_showcase_covers_every_state(device):
    """The showcase demos (scenarios with `showcase: true`) show every state
    this build knows. A new state in the core or a module fails here until
    a showcase scenario shows it."""
    showcase = [s for s in scenarios.all_scenarios() if s.showcase]
    assert showcase, "no scenario has showcase: true"
    covered = set().union(*(scenarios.covered_states(s) for s in showcase))
    known = [s["name"] for s in device.states()]
    missing = [name for name in known if name not in covered]
    assert not missing, f"no showcase scenario shows {missing}; add them to {[s.path.name for s in showcase]}"
    unknown = sorted(covered - set(known))
    assert not unknown, f"the showcase scenarios name states the build does not know: {unknown}"


def test_pet_shows_petted(device):
    device.pet()
    expect(device).to_have_state("petted")
    expect(device).to_fire_event("entity:Event", event_type="petted")


def test_doorbell_unlock(device):
    device.show_prompt(
        id="door",
        title="Doorbell",
        body="Someone is at the front door.",
        options=["Unlock", "Talk", "Ignore"],
        style="urgent",
    )
    expect(device.get_by_role("button", name="Unlock")).to_be_visible()
    expect(device).to_have_state("attention")
    expect(device).to_match_screenshot("doorbell")
    device.get_by_role("button", name="Unlock").tap()
    expect(device).to_fire_event("esphome.daruma_prompt", id="door", choice="Unlock", reason="chosen")
    expect(device.get_by_role("dialog")).to_be_hidden()


SNACKS = ["Apples", "Bagels", "Chips", "Dates", "Eclairs", "Fudge", "Grapes", "Popcorn", "Quiche", "Raisins"]


def test_scrolling_a_list_never_chooses(device):
    device.show_prompt(id="snack", title="Snack?", options=SNACKS, layout="list")
    expect(device.get_by_role("button", name="Apples")).to_be_visible()
    w, h = device.screen_size()
    device.swipe(w // 2, h * 3 // 4, w // 2, h // 3)
    popcorn = device.get_by_role("button", name="Popcorn")
    x, y = popcorn.wait_for().center
    # The finger comes straight back for another quick flick. The screen is
    # read every 50 ms here, so the hub sees less than its tap slop of it:
    # it reaches the list as a tap.
    device.swipe(x, y - 6, x, y + 8, seconds=0.1)
    # Later, a slow, short drag on a row (inside the hub's slop) is still no tap.
    device.advance(1)
    device.swipe(x, y - 8, x, y + 8, seconds=0.4)
    device.advance(1)
    assert not [e for e in device.events if e.type == "esphome.daruma_prompt"], device.events
    expect(popcorn).to_be_visible()
    # A plain tap, once the list has settled, chooses.
    popcorn.tap()
    expect(device).to_fire_event("esphome.daruma_prompt", id="snack", choice="Popcorn", reason="chosen")


def test_focus_starts_at_once(device):
    device.press("home")
    device.get_by_text("Focus").tap()
    expect(device).to_have_state("focus")
    expect(device).to_have_entity("Pomodoro remaining", 25)


def test_focus_from_the_menu(device):
    device.tap(160, 100)
    device.get_by_text("Custom").tap()
    device.get_by_text("10 min").tap()
    expect(device).to_have_state("focus")
    device.skip(10 * 60)
    expect(device).to_have_state("focus_done")


def test_break_buttons_follow_the_focus(device):
    """Break shows only between a focus that ended and the end of the break it earned."""
    device.set("Pomodoro focus", 5)
    device.press("home")
    expect(device.get_by_text("Focus")).to_be_visible()
    expect(device.get_by_text("Break")).to_be_hidden()
    device.get_by_text("Focus").tap()
    expect(device).to_have_state("focus")
    # During the focus: Pause, Stop and Skip; no Break.
    device.press("home")
    expect(device.get_by_text("Pause")).to_be_visible()
    expect(device.get_by_text("Stop")).to_be_visible()
    expect(device.get_by_text("Break")).to_be_hidden()
    device.press("home")
    # The focus ends and its break starts by itself: Focus and End.
    device.skip(5 * 60)
    expect(device).to_have_state("break", timeout=8)
    device.press("home")
    expect(device.get_by_text("End")).to_be_visible()
    expect(device.get_by_text("Break")).to_be_hidden()
    device.get_by_text("End").tap()
    # Idle again, well inside the break it earned: both breaks are on offer.
    device.press("home")
    expect(device.get_by_text("Break")).to_be_visible()
    expect(device.get_by_text("Long break")).to_be_visible()
    device.press("home")
    # Five minutes on, the break is over: no Break buttons.
    device.skip(5 * 60)
    device.press("home")
    expect(device.get_by_text("Custom")).to_be_visible()
    expect(device.get_by_text("Break")).to_be_hidden()
    expect(device.get_by_text("Long break")).to_be_hidden()


def test_plaque_opens_the_pomodoro_page(device):
    device.advance(1)
    device.get_by_role("target", "plaque").tap()
    expect(device.get_by_role("app", "Pomodoro")).to_be_visible()
    device.get_by_text("Focus").tap()
    expect(device).to_have_state("focus")
    expect(device.get_by_text("Pause")).to_be_visible()
    device.advance(2)
    expect(device).to_match_screenshot("pomodoro-page")
    # Opened from the persona, back closes it.
    device.press("home")
    expect(device.get_by_role("app")).to_be_hidden()
    expect(device.get_by_role("target", "plaque")).to_be_visible()


def test_custom_length_on_the_page(device):
    device.get_by_role("target", "plaque").tap()
    device.get_by_text("Custom").tap()
    device.get_by_text("15 min").tap()
    expect(device).to_have_state("focus")
    expect(device).to_have_entity("Pomodoro remaining", 15)


def test_badge_opens_weather(device):
    device.set("Outside temperature", 64)
    device.advance(1)
    device.get_by_role("target", "badge").tap()
    expect(device.get_by_role("app", "Weather")).to_be_visible()
    expect(device.get_by_role("text", "Partly cloudy")).to_have_value("64°")
    expect(device.get_by_role("cell", "Now")).to_be_visible()
    expect(device).to_match_screenshot("weather")


def test_next_event_opens_calendar(device):
    device.advance(2)
    device.get_by_role("target", "next_event").tap()
    expect(device.get_by_role("app", "Calendar")).to_be_visible()


def test_task_checked_off(device):
    device.tap(160, 100)
    device.get_by_text("More").tap()
    device.get_by_role("tile", name="Tasks").tap()
    row = device.get_by_role("row", name="Water the fern")
    row.tap()
    expect(row).to_have_value("done")
    expect(device).to_have_state("task_done")


@pytest.mark.persona("Pixel corgi")
def test_corgi_idle(device):
    device.set("Outside temperature", 64)
    device.advance(2)
    expect(device).to_match_screenshot("idle")


# --- Props stay while a reaction plays ----------------------------------------
# A reaction shows over the activity under it, which stays on. Props of the
# activity (the daruma's incense) must stay in the picture all through it.
# Per persona and activity: screen boxes (x0, y0, x1, y1, end exclusive) that
# hold the props, on the 320x240 screen. The prop pixels are the ones in a
# box that the activity changes from the idle screen. Add a persona here when
# one of its activities has props.
ACTIVITY_PROPS = {
    "Daruma": {"focus": [(241, 168, 268, 210)]},  # The incense bowl and stick.
    "Pixel corgi": {"focus": [(121, 165, 202, 205)]},  # The book in its lap.
    "Jack Russell": {"focus": [(148, 90, 175, 117)]},  # The ball in its mouth.
}
# Core reactions, with how long each plays: any of them can come during an
# activity. Module reactions (focus_done, goal, ...) end their activity.
CORE_REACTIONS = {"petted": 2.0, "startled": 2.0, "celebrate": 3.0, "paint": 2.7}
KEEP = 0.95  # Share of the prop pixels each frame must show unchanged.


def _start_focus(device):
    device.set("Pomodoro focus", 5)
    device.tap(160, 100)
    device.get_by_text("Focus").tap()
    expect(device).to_have_state("focus")
    device.advance(1)


def _box_pixels(img, box):
    x0, y0, x1, y1 = box
    return {(x, y): img.getpixel((x, y)) for y in range(y0, y1) for x in range(x0, x1)}


def _props_on_screen(device, activity):
    """Starts the activity; per box, the prop pixels: where it differs from idle."""
    idle = device.screenshot()
    if activity != "focus":
        raise NotImplementedError(f"teach the test to start {activity!r}")
    _start_focus(device)
    on = device.screenshot()
    out = []
    for box in ACTIVITY_PROPS[device.persona][activity]:
        before, now = _box_pixels(idle, box), _box_pixels(on, box)
        props = {xy: v for xy, v in now.items() if before[xy] != v}
        assert len(props) >= 20, f"{device.persona}: no props of {activity} in {box} ({len(props)} pixels changed)"
        out.append((box, props))
    return out


def _check_props_through(device, props, seconds, what):
    """Every 0.1 s for `seconds`, the prop pixels must still be on screen."""
    t = 0.0
    while t < seconds:
        shot = device.screenshot()
        for box, want in props:
            kept = sum(1 for xy, v in want.items() if shot.getpixel(xy) == v)
            assert kept >= KEEP * len(want), (
                f"{device.persona}: {what} at {t:.1f} s (state {device.state()}): "
                f"{kept} of {len(want)} prop pixels in {box}"
            )
        device.advance(0.1)
        t += 0.1


_PROP_CASES = [
    pytest.param(persona, activity, reaction, marks=pytest.mark.persona(persona), id=f"{persona}-{activity}-{reaction}")
    for persona, activities in ACTIVITY_PROPS.items()
    for activity in activities
    for reaction in CORE_REACTIONS
]


@pytest.mark.parametrize("persona, activity, reaction", _PROP_CASES)
def test_reaction_keeps_activity_props(device, persona, activity, reaction):
    device.set("Outside temperature", 64)
    device.advance(1)
    props = _props_on_screen(device, activity)
    device.react(reaction)
    expect(device).to_have_state(reaction)
    _check_props_through(device, props, CORE_REACTIONS[reaction], f"{reaction} during {activity}")
    expect(device).to_have_state(activity, timeout=3)


@pytest.mark.persona("Daruma")
def test_daruma_pet_during_focus_keeps_the_incense(device):
    """Petting by touch, as the owner does: the incense must not vanish."""
    device.set("Outside temperature", 64)
    device.advance(1)
    props = _props_on_screen(device, "focus")
    device.pet()
    expect(device).to_have_state("petted")
    _check_props_through(device, props, 2.0, "petted during focus")
    expect(device).to_have_state("focus", timeout=3)


@pytest.mark.persona("Pixel corgi")
def test_corgi_petted_while_reading(device):
    # Petted over the focus: it keeps its glasses and book, and its head
    # leans with the wagging body ("Loved over Focus").
    _start_focus(device)
    device.advance(2)
    device.pet()
    expect(device).to_have_state("petted")
    device.advance(0.3)
    expect(device).to_match_screenshot("petted-reading")
    # Back to reading afterwards.
    device.advance(2.5)
    expect(device).to_have_state("focus")


@pytest.mark.persona("Jack Russell")
def test_jack_russell_petted_while_guarding(device):
    # Petted over the focus: the ball stays in its mouth.
    _start_focus(device)
    device.advance(2)
    device.pet()
    expect(device).to_have_state("petted")
    device.advance(0.3)
    expect(device).to_match_screenshot("petted-guarding")


# --- The weekday rug follows the local clock ------------------------------------

# Saturday 14 November 2026, 19:59:30 in Chicago (CST, UTC-6): half a minute
# before 8 pm, which is already 02:00 on Sunday in UTC.
SATURDAY_EVENING = 1794707970
# A spot on the corgi's rug left of its paws, below the bottom band's top.
RUG_SPOT = (224, 212)
# The rug's main color per day (room.py RUG_BY_WEEKDAY), and plain red.
RUG_MAIN = {
    "plain": (150, 58, 58),
    "Sunday": (236, 228, 210),
    "Monday": (58, 92, 160),
    "Tuesday": (222, 182, 48),
    "Wednesday": (62, 128, 76),
    "Thursday": (100, 62, 40),
    "Friday": (214, 104, 146),
    "Saturday": (112, 70, 150),
}


def rug_day(device) -> str:
    """The day whose rug color the screen shows at RUG_SPOT."""
    px = device.screenshot().getpixel(RUG_SPOT)
    return min(RUG_MAIN, key=lambda day: sum((a - b) ** 2 for a, b in zip(RUG_MAIN[day], px, strict=False)))


@pytest.mark.persona("Pixel corgi")
@pytest.mark.clock(epoch=SATURDAY_EVENING, timezone="America/Chicago")
def test_rug_follows_the_local_weekday(device):
    # At boot: Saturday's rug, not the plain one.
    device.advance(6)
    assert rug_day(device) == "Saturday"
    # Across 8 pm (Sunday in UTC): still Saturday.
    device.advance(60)
    assert rug_day(device) == "Saturday"
    # Up to just before midnight (in 30 s steps), then across it: Sunday.
    device.advance(4 * 3600 - 90, step=30)
    assert rug_day(device) == "Saturday"
    device.advance(60)
    assert rug_day(device) == "Sunday"
