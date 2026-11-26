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

A change of look in Habitica needs a new build of the firmware. The new
build reads the new look by itself. Home Assistant can tell you when a
build is due (below).

## When your look changes

The device has a diagnostic sensor, "Avatar look". It shows a short id
of the look the firmware was built with. Home Assistant can read your
look from Habitica too, and compare. Then the "Habitica look changed"
blueprint tells you to rebuild.

Home Assistant can't rebuild Daruma by itself. Rebuild it in the ESPHome
builder when the notification comes.

### 1. The template file

Save this as `custom_templates/habitica.jinja` in Home Assistant's
config folder. It writes the look the way the build does: skin, hair,
size, shirt, chair, background, costume, the gear on show, pet and
mount. It leaves out sleep, buffs and class: those change at run time,
and a new build would draw nothing different for them.

```jinja
{#- Daruma: the Habitica look, as daruma_personas.habitica.look writes it. -#}
{%- macro _or(value, default) -%}{{ default if value is none else value }}{%- endmacro -%}

{%- macro habitica_look(user) -%}
  {%- set p = user.get('preferences') if user.get('preferences') is mapping else {} -%}
  {%- set i = user.get('items') if user.get('items') is mapping else {} -%}
  {%- set h = p.get('hair') if p.get('hair') is mapping else {} -%}
  {%- set sets = i.get('gear') if i.get('gear') is mapping else {} -%}
  {%- set worn = sets.get('costume' if p.get('costume') else 'equipped') -%}
  {%- set worn = worn if worn is mapping else {} -%}
  {%- set ns = namespace(gear=[], hair=[_or(h.get('color'), 'red')]) -%}
  {%- for slot in ['back', 'armor', 'body', 'eyewear', 'head', 'headAccessory', 'shield', 'weapon'] -%}
    {%- if worn.get(slot) -%}{%- set ns.gear = ns.gear + [slot ~ ':' ~ worn.get(slot)] -%}{%- endif -%}
  {%- endfor -%}
  {%- for part in ['base', 'bangs', 'mustache', 'beard', 'flower'] -%}
    {%- set ns.hair = ns.hair + [(h.get(part) or 0) | int] -%}
  {%- endfor -%}
  skin={{ _or(p.get('skin'), '915533') }};hair={{ ns.hair | join('/') }};size={{ _or(p.get('size'), 'slim') }};
  {{- '' }}shirt={{ _or(p.get('shirt'), 'black') }};chair={{ _or(p.get('chair'), 'none') }};
  {{- '' }}background={{ _or(p.get('background'), '') }};costume={{ 1 if p.get('costume') else 0 }};
  {{- '' }}gear={{ ns.gear | join(',') }};pet={{ _or(i.get('currentPet'), '') }};mount={{ _or(i.get('currentMount'), '') }}
{%- endmacro -%}

{#- A short id of a look: 8 hex digits, as the device's "Avatar look" shows. -#}
{%- macro habitica_look_id(look) -%}
  {%- set ns = namespace(h=0) -%}
  {%- for c in look -%}{%- set ns.h = (ns.h * 31 + (c | ord)) % 4294967296 -%}{%- endfor -%}
  {{- '%08x' | format(ns.h) -}}
{%- endmacro -%}
```

### 2. The sensors

Put this in a package of Home Assistant's configuration. It reads your
user from Habitica every 30 minutes: change `scan_interval` for another
pace. A REST sensor can't be a blueprint, so you add it by hand.

```yaml
# Daruma: Habitica look. One request to Habitica every 30 minutes.
rest:
  - resource: "https://habitica.com/api/v3/user?userFields=preferences,items.gear.equipped,items.gear.costume,items.currentPet,items.currentMount"
    scan_interval: 1800
    timeout: 20
    headers:
      x-api-user: !secret habitica_user_id
      x-api-key: !secret habitica_api_token
      x-client: !secret habitica_x_client
    sensor:
      - name: Habitica user
        unique_id: daruma_habitica_user
        value_template: "{{ 'ok' if value_json.success else 'error' }}"
        json_attributes_path: "$.data"
        json_attributes: [preferences, items]

template:
  - sensor:
      - name: Habitica look
        unique_id: daruma_habitica_look
        icon: mdi:account-box-outline
        availability: "{{ state_attr('sensor.habitica_user', 'preferences') is mapping }}"
        state: >-
          {% from 'habitica.jinja' import habitica_look, habitica_look_id %}
          {% set user = {'preferences': state_attr('sensor.habitica_user', 'preferences'),
                         'items': state_attr('sensor.habitica_user', 'items')} %}
          {{ habitica_look_id(habitica_look(user)) }}
        attributes:
          look: >-
            {% from 'habitica.jinja' import habitica_look %}
            {{ habitica_look({'preferences': state_attr('sensor.habitica_user', 'preferences'),
                              'items': state_attr('sensor.habitica_user', 'items')}) }}
```

In `secrets.yaml`, `habitica_x_client` is your user id followed by
`-daruma`: Habitica asks every tool to name itself in this header.

The state of "Habitica look" is the same short id the device shows in
"Avatar look" when it was built from that look.

### 3. The blueprint

Import the "Habitica look changed" blueprint
([prompts.md](prompts.md#try-it-first) has the button). Pick the "Habitica
look" sensor, and the device's "Avatar look" sensor if you like. When
the look changes, Home Assistant shows "Your Habitica look changed.
Rebuild Daruma." A trip to the inn, a restart, or the sensor going
unavailable shows nothing. With the device's sensor picked, a look the
device already shows shows nothing too.

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
