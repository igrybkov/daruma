# Talking to Home Assistant

> Incomplete. Moved from the old ARCHITECTURE.md. Add what you learn
> when a task needs more, and keep it under 300 lines.

Events the device sends, and HA actions it calls and waits on.

## Home Assistant calls with a reply

In ESPHome 2026.10.2, each `homeassistant.action` keeps its own call id
counter. So two actions hand out the same ids, and the API server runs
the first callback registered under an id. A call sent before HA
subscribes is dropped, but its callback stays. A later action can then
reach that id, and its reply goes to the stale callback. Seen: a to-do
check-off answered as an old fetch, never confirmed, so the row flipped
back.

The hub's gate (`ha_calls.h`, tested in `test_ha_calls.cpp`) fixes the
cases we can:

- Every action with `capture_response`, `on_success` or `on_error` goes
  through `hub.ha_calls().call(name, send)`. Its `on_success` and
  `on_error` call `done(token)`.
- Nothing goes until HA has been connected, with its subscription, for
  3 s. Calls asked for earlier wait and go then.
- One call is in flight at a time; the rest queue (16 at most). A call
  with no answer frees the gate after 8 s, under the apps' own 10 s.
- Calendar fetches, Tasks fetches and Tasks check-offs use it.
- A call cut off by a disconnect can still leave a stale callback. Drop
  the gate when ESPHome shares one counter and forgets dropped calls.

A home's own things stay in its own config: entity IDs, automations and
any private personas. Everything the device sends to HA carries its
`device_id`, so one automation or blueprint can serve every device.

## HA states the device follows

A component can follow an HA entity without a `homeassistant` sensor. The
Controls app does: `global_api_server->subscribe_home_assistant_state()`
for the state, and once more for an attribute.

- Subscribe in `setup()`. HA reads the list of subscriptions when it
  connects. One added later reaches HA only after a reconnect.
- Use the `std::string` overload. The `const char *` one keeps the
  pointer, not the text.
- Copy the `StringRef` in the callback. It does not outlive the call.
- Add the define `USE_API_HOMEASSISTANT_STATES` in `to_code`, or the
  subscription code is not built.
- HA sends every state again when it connects. Drop the old ones when it
  goes away, or a tile shows a stale state.
- The runner on the desktop answers subscriptions from `demos/demo_data.py`
  (`Device._on_ha_subscription` in `demos/harness.py`).
