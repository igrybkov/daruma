# Private packages

You can keep your own personas, art and apps in a git repository of your own,
private or public, and use them next to Daruma. A device yaml pulls both:
Daruma's packages and yours. This guide uses a private repository called
`my-daruma-private` with one pixel-art persona, `my_persona`.

## How it fits together

ESPHome fetches each package repository into its cache. Daruma's
components then resolve every path in a package next to that package's own
file, wherever the cache is:

- `pixel_art: { script: ../pixel/my_persona.py }` finds the persona module in your
  checkout.
- `art: ../art/my_set` finds a picture folder in your checkout.
- `path: ../src/esphome/components` finds your own components, if you have any.

A pixel-art script runs with its own folder on Python's import path, and
every pixel package of the Daruma checkout (`pixel/*/src`). So your script
imports them by name: the drawing layer (`daruma_pixel`), the shapes
(`daruma_shapes.pets`, `.rooms`, `.plants`, `.office`), and a persona's
parts if you build on one. For example:
`from daruma_shapes.office.boss import Persona, Look`. No pip step is
needed on the builder; the packages come from the Daruma checkout.

The hub checks the merged config at build time: every persona, state and
binding, from every package. A mistake in your package fails the build,
not the device.

## The repository

```
my-daruma-private/
  packages/
    persona_my_persona.yaml     the persona: a daruma_sprites entry
  pixel/
    my_persona.py       the look on a library engine, and its PERSONA
  art/                    picture sets, if you have picture personas
  .gitignore              .esphome/, secrets.yaml
```

### The look

A look is a module with the names every persona module has: `scene`,
`background`, `foreground`, `WINDOW`, `ANIMATIONS`, `BLINKS` and `WINKS`.
The easy way is a look on an engine. For a person at a desk:

```python
# pixel/my_persona.py
from daruma_shapes.office.boss import Persona, Look, Pose, animations, with_
from daruma_pixel.scene import Spot
...
LOOK = Look(...)  # skin, hair, clothes, room, desk props
_c = Persona(LOOK, desk=Spot(53, 61))  # the middle of the desk's top edge
background, foreground, scene = _c.background, _c.foreground, _c.scene
WINDOW = None
ANIMATIONS = animations(rest=Pose(), ...)
BLINKS = {...}
WINKS = {...}
```

`pixel/persona-the-boss/` in Daruma is a complete example of a look on
the office (`daruma_shapes.office.boss`). `pixel/persona-jack-russell/` is
a breed on the pet rig (`daruma_shapes.pets`).

### The persona declaration

The art module says it is a persona with one line at its end. The
component builds it from that; no build script is needed.

```python
# pixel/my_persona.py, at the end
from daruma_pixel.personas import Spec

PERSONA = Spec("my_persona", background=0x203040)
```

### The persona package

```yaml
# packages/persona_my_persona.yaml
daruma_sprites:
  - id: my_persona
    name: My persona
    pixel_art: { script: ../pixel/my_persona.py, persona: my_persona }
    theme:
      style: paper
      frame: "203040"
      # ... see Daruma's packages/persona_*.yaml for every key
```

A picture persona works the same way: a `daruma_images` entry with
`art: ../art/my_set` (see Daruma's `packages/persona_images.yaml`).

### Rules for a package others can use too

- **Unique names.** Persona ids, `Spec` names and component names must
  not clash with Daruma's or another package's. Prefix them.
- **Prefixed modules.** Daruma's modules sit in the `daruma_pixel`,
  `daruma_shapes` and `daruma_personas` packages, so yours cannot replace
  them. But the modules of every package
  in a build share one top-level namespace: two repositories with a
  `util.py` clash. Name yours `my_persona_*.py`.
- **Pin Daruma.** Say which Daruma version your package works with, and
  pin both refs in the device yaml.

## The device yaml

Pin both repositories to a tag or a full commit hash (`main` follows the
latest changes):

```yaml
substitutions:
  name: daruma
  friendly_name: Daruma
  daruma_url: https://github.com/igrybkov/daruma
  daruma_ref: main
  private_url: https://github.com/<you>/my-daruma-private
  private_ref: v1.0.0

packages:
  daruma:
    url: ${daruma_url}
    ref: ${daruma_ref}
    files:
      - packages/board_box3.yaml
      - packages/core.yaml
      - packages/persona_daruma.yaml
      - packages/menu.yaml
      - packages/pomodoro.yaml
  private:
    url: ${private_url}
    ref: ${private_ref}
    username: git
    password: !secret my_daruma_private_token
    files:
      - packages/persona_my_persona.yaml
```

Personas appear in the Persona select in the order the packages list them. To
put yours between Daruma's personas, split Daruma's files over two entries
with the same `url` and `ref`; ESPHome fetches the repository once.

For a public repository, leave out `username` and `password`.

## Access to a private repository

Every machine that compiles the device must fetch your repository:
Home Assistant's ESPHome builder, and any remote builder you use.

### Recommended: https with a fine-grained token

1. On GitHub: Settings > Developer settings > Personal access tokens >
   Fine-grained tokens > Generate new token.
2. Repository access: "Only select repositories", then pick
   `my-daruma-private`.
3. Permissions: Repository permissions > Contents: Read-only. Nothing
   else.
4. Set an expiry and put a reminder in your calendar to renew it.
5. Put the token in the `secrets.yaml` of the ESPHome config folder on
   every machine that compiles. In Home Assistant's ESPHome builder that
   is `/config/esphome/secrets.yaml`:

   ```yaml
   my_daruma_private_token: "github_pat_..."
   ```

6. Use `username: git` and `password: !secret my_daruma_private_token` in
   the package entry, as above.

ESPHome hides the credentials in its log. Two places still hold the token:

- **The git cache.** Git stores the remote URL with the token in
  `.esphome/packages/<hash>/.git/config` on each builder. Keep `.esphome/`
  out of git and out of shared backups.
- **Bundles.** `esphome bundle` ships the `secrets.yaml` keys the config
  uses, the token among them, so a remote builder can fetch the
  repository. Treat a bundle like a password file.

### Other options

- **SSH with a deploy key.** Use `url: ssh://git@github.com/<you>/my-daruma-private.git`
  and add a read-only deploy key to the repository. The key is scoped to
  one repository. The builder needs the private key and GitHub's host key
  in its own `~/.ssh`. That works on a computer you control. In Home
  Assistant's ESPHome builder it is hard: the builder's home folder does
  not survive an update.
- **Vendoring.** Copy the files into your ESPHome config folder and use
  `!include` (and a `pixel_art` script path relative to it). No access to
  set up, but the files are no longer a repository of their own.

## Secrets stay out of git

- Tokens, Wi-Fi passwords and API keys go in `secrets.yaml`, and the
  YAML names them with `!secret`. Add `secrets.yaml` to `.gitignore` in
  every repository.
- Never put a token in a URL in YAML (`https://token@github.com/...`).
  Use `username` and `password`.
- Add `.esphome/` to `.gitignore` too: it holds the git cache with the
  token.

## Test before you push

The packages are fetched with git, so commit your changes first (no push
needed). Then point both entries at your local clones:

```sh
esphome \
  -s daruma_url file:///path/to/daruma -s daruma_ref main \
  -s private_url file:///path/to/my-daruma-private -s private_ref main \
  compile my-device.yaml
```

A ref can be a branch or a full commit hash. A short hash cannot be
fetched. `username` and `password` can stay in the yaml: git ignores them
for a local path.

To see the persona without a device, record it in Daruma's desktop build,
from a Daruma clone:

```sh
uv run demos/record.py --private-persona /path/to/my-daruma-private/packages/persona_my_persona.yaml \
    --personas "My persona" --scenario tour
```

Its GIF goes to the temp folder, not into the Daruma repository.

To check it against golden pictures, run the scenario tests with the same
package. The first run with `--update-golden` writes the pictures to
`golden/` in the temp folder (or `$DARUMA_WORK`). Later runs compare with
them:

```sh
uv run pytest demos -m scenario --scenario tour --update-golden \
    --private-persona /path/to/my-daruma-private/packages/persona_my_persona.yaml \
    --persona "My persona"
```

To look at the frames only, run your persona module in the environment
of a Daruma clone (`uv sync` there installs every pixel package), from
your repository's root:

```sh
uv run --project /path/to/daruma python -c "import sys; sys.path.insert(0, 'pixel'); \
from daruma_pixel import personas; \
print(len(personas.build('my_persona', 'my_persona').animations), 'animations')"
```
