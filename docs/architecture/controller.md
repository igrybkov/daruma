# The device as a controller

How the device controls something else through Home Assistant. Today
that is the Media app: a remote for the media players in the device's
room. Example tasks: add a button to the remote, put the remote's buttons
in a menu or on a device button, write a remote for another kind of
entity.

## How it works

The Media app is `packages/app_media.yaml` and `components/daruma_media`.
It reads the players with one HA call, sends each button as a
`media_player` action, and loads the cover over HTTP.

```
 open, every 5 s, 1 s after a button
   MediaApp -> fetcher -> hub.ha_calls() -> recorder.get_statistics + template
                                         <- {"a": area, "p": [[entity, name, state, ...]]}
 a button
   MediaApp -> commander -> homeassistant.action media_player.*   (no reply)
 the cover
   MediaApp -> cover loader -> online_image -> HTTP -> HA's media proxy
```

- **The carrier.** HA renders a `response_template` only for an action
  that answers. `recorder.get_statistics`, for a statistic that is not
  there, answers fast and is in every HA with the recorder. Its template
  reads every player's state. See
  [Talking to Home Assistant](home-assistant.md) for the gate.
- **The room.** With the "Media players" setting empty, the template finds
  the device in HA's device registry by its MAC address (the ESPHome
  integration stores it as a connection), then by its name. Then it takes
  the device's area and `area_entities`. The reply carries the area id,
  and the next fetch passes it back to skip the search. Opening the app
  looks again.
- **Commands** expect no reply. They skip the gate and go at once. A fetch
  follows after `command_refresh`.
- **The screen answers first.** `media_expect` changes the player as the
  command will. `MediaHold` keeps that for `hold`, while replies still
  show the old state or volume. Then HA's word wins.
- **The position** comes from HA as it was when the template ran. The
  device adds the time since the reply while the player plays.
- **Covers.** The picture is HA's `entity_picture_local`, else
  `entity_picture`: a path on HA. It is joined to the "Home Assistant URL"
  setting, or to the API client's address on `ha_port`. One download runs
  at a time, and the newest wish goes next. Covers load only while the
  app is open, and only on full-color screens.
- **Bindings and menus.** The module's actions (`media.play_pause`,
  `media.next`, ...) call `MediaApp::press`. Button hooks
  (`set_action_button`, see [Menus](menus.md)) show Pause while a player
  plays, and hide a button the player can't use. A press before the first
  reply waits for it.

## Conventions

- The rules are plain C++ in `components/daruma_media/media.h`,
  host-tested in `tests/test_media.cpp`: states, features, which player
  shows, the buttons, the position, the volume, the URLs.
- A button acts only when HA's `supported_features` allows it. Else it is
  gray in the app and out of menus.
- One `homeassistant.action` per data shape. HA refuses keys an action
  does not take, so `volume_set` and `media_seek` get their own.
- Text from HA goes through `drawable_text` before it is drawn.
- Tunables are options with defaults: `refresh`, `idle_refresh`,
  `volume_step`, `cover_size`.

## Traps

- **Subscriptions don't follow settings.** A `homeassistant` sensor's
  subscription reaches HA only when HA connects. A player picked at run
  time would need a reconnect. That is why the app polls.
- **Stale covers.** `online_image.update()` does nothing while a download
  runs, and `set_url()` keeps the old URL when the new one is not http.
  The next update then shows the old cover. Load one at a time, and only
  URLs that pass `media_is_http`.
- **The token.** HA changes a player's access token every 5 minutes, and
  the picture URL with it. The app keys a cover by its URL without the
  token (`media_cover_key`), or it downloads the same cover again.
- **Flicker.** A reply that comes right after a command often shows the
  old state. Without the hold, a button flips back, then forward again.
- **Free text in the template.** The players setting goes into Jinja as a
  string. Quote `'` and `\`, as the package does.
- **Polling settings move the personas.** A `template` text polls every
  60 s unless told otherwise, and the scheduler draws a random number for
  each interval. That shifts every later draw: the eyes glance elsewhere,
  and golden pictures of every persona fail. Give a setting without a
  lambda `update_interval: never`.
- **The demo runner** answers `recorder.get_statistics` for the statistic
  `daruma.media_players` with made-up players. Another statistic id in
  the package leaves the desktop tests without players.

## Example to copy

`MediaApp::run_()` with the package's `_command` script: one command, the
screen changed at once, and a fetch after. For a remote of another kind
(lights, blinds), start smaller: a module whose YAML actions run a
`homeassistant.action`, with a button look under `buttons:`.

## Check it

```sh
uv run pytest tests/test_media.cpp     # the rules
uv run pytest demos/test_media.py      # the app on the desktop
```

The runner plays three players and serves their covers
(`demos/demo_data.py`). `expect(device).to_call_action(...)` checks a
command. The golden picture is
`tests/golden/eyes/test_media_shows_the_playing_player/media.png`.
