# Habitica avatar persona

The persona `packages/persona_habitica.yaml` shows a Habitica avatar on
the device. The build stacks the avatar from Habitica's sprites, in the
order Habitica uses. It shows them at one pixel per art pixel, in front
of the avatar's Habitica background. On the BOX-3 that is 5x. Plain sky
and ground fill the sides.

As shipped, the persona shows a made-up fixture avatar. It is drawn in
this repository, so the repository's pictures hold no Habitica art. To
see your own avatar, add a private persona that reads your look.

## Your own avatar

Add a persona package to your private folder
([private-packages.md](private-packages.md)). It uses the same module
with options:

```yaml
daruma_sprites:
  - id: my_habitica
    name: My Habitica
    pixel_art:
      module: daruma_personas.habitica
      persona: habitica
      options:
        source: cdn
        user_id: !secret habitica_user_id
        token: !secret habitica_api_token
    during:
      focus: { Petted: PettedFocus, Startled: StartledFocus, Celebrate: CelebrateFocus }
```

Put the user id and the API token in the secrets of the ESPHome builder.
Habitica shows both in its settings.

The options:

| Option | What it does |
|---|---|
| `source` | Where the sprites come from: `fixture` (the default), `cdn` (Habitica's asset server), or `dir:<path>` (PNG files in a folder). |
| `user_id`, `token` | Read the look from Habitica's API when the firmware builds. |
| `look` | A pinned look, in the shape of Habitica's user object. It wins over the API. Use it to freeze a look. |

What the build does:

- It makes one request to Habitica for your preferences, gear, pet,
  mount and class. It sends the `x-client` header Habitica asks for.
- It saves the look as the last look in the builder's data folder. When
  Habitica can't be reached, it uses the last look and logs a warning.
- With `source: cdn`, it downloads each sprite once into
  `daruma_habitica/` in the builder's data folder. A build without the
  network uses the sprites it has.
- A missing sprite is left out, with a warning. One piece of gear never
  stops the build.
- The token is used for the request only. It is never logged, saved or
  part of a cache key.
- The inn and buffs are left out. They change at run time, and a new
  build is not needed for them.

A change of look in Habitica needs a new build of the firmware.

## Pictures of your avatar

Keep pictures of your own avatar out of this repository. Run the
recorder and the golden tests on your private folder, with
`DARUMA_PERSONA_PATH`. They write the pictures there, never to
`docs/demos` or `tests/golden` here
([private-packages.md](private-packages.md)).

## Credits and license

The avatar art belongs to [Habitica](https://habitica.com) and its
artists. It is licensed
[CC-BY-NC-SA 3.0](https://creativecommons.org/licenses/by-nc-sa/3.0/).

- This repository holds no Habitica sprite, downloaded sprite, or picture
  of a real avatar. A test checks it.
- A firmware built with `source: cdn` holds Habitica's art. It is fine
  for your own device. Do not sell devices with it.
- Habitica does not endorse this project.
