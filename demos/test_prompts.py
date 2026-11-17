"""Screen tests of prompts that HA waits on (the `ask` action) and of the
prompts.dismiss action."""

from __future__ import annotations

import json

from harness import expect


def _answer(result) -> dict:
    assert result is not None and result.success, result
    return json.loads(result.response_data)


def test_ask_returns_the_choice(device):
    reply = device.ask(id="lights", title="Lights off?", options=["Yes", "No"])
    device.get_by_role("button", name="Yes").tap()
    assert _answer(reply()) == {"id": "lights", "choice": "Yes", "index": 0, "reason": "chosen"}
    expect(device.get_by_role("dialog")).to_be_hidden()


def test_ask_times_out(device):
    # An ask ends itself after 25 s by default, before HA gives up on it.
    reply = device.ask(id="late", title="Still there?", options=["Yes"])
    expect(device.get_by_role("dialog", name="late")).to_be_visible()
    device.advance(26, step=0.5)
    answer = _answer(reply())
    assert answer["reason"] == "timeout", answer
    expect(device.get_by_role("dialog")).to_be_hidden()


def test_ask_with_a_bad_layout_fails(device):
    result = device.ask(id="bad", layout="grid", options=["Yes"])()
    assert result is not None and not result.success, result
    assert "layout" in result.error_message, result.error_message
    expect(device.get_by_role("dialog")).to_be_hidden()


def test_dismiss_action_closes_the_prompt(device):
    device.show_prompt(id="note", title="Parcel", body="A parcel came.")
    expect(device.get_by_role("dialog", name="note")).to_be_visible()
    device.run_action("prompts.dismiss")
    expect(device).to_fire_event("esphome.daruma_prompt", id="note", reason="dismissed")
    expect(device.get_by_role("dialog")).to_be_hidden()


def test_dismiss_action_keeps_a_prompt_that_must_be_answered(device):
    device.show_prompt(id="pick", title="Pick one", options=["Left", "Right"], layout="choice", dismissable=False)
    device.run_action("prompts.dismiss")
    device.advance(1)
    expect(device.get_by_role("dialog", name="pick")).to_be_visible()
    device.get_by_role("button", name="Left").tap()
    expect(device).to_fire_event("esphome.daruma_prompt", id="pick", choice="Left", reason="chosen")


def test_ask_without_a_timeout_ends_when_ha_stops_waiting(device):
    # timeout -1 keeps the prompt up, but the action answers within 28 s.
    reply = device.ask(id="open", title="Take your time", options=["Done"], timeout=-1)
    device.advance(29, step=1.0)
    answer = _answer(reply())
    assert answer["id"] == "open", answer
    expect(device.get_by_role("dialog")).to_be_hidden()
