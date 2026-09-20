# GitHub Profile Motion

Compact light/dark GIFs: a character moves through a GitHub-like contribution grid. They illustrate a dated snapshot; GitHub's native graph is untouched.

<picture>
  <source media="(max-width: 600px)" srcset="heading_mobile.gif">
  <img src="heading.gif" alt="Technical Boundary Audit & Repair for AI Systems in softly flowing light">
</picture>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="crowned_cat_dark.gif">
  <img src="crowned_cat.gif" alt="A crowned black cat crosses two green activity scenes, rests, wakes, and loops">
</picture>

The cat uses a **fixed** `shin4141` snapshot from 2026-09-20. The [one-image fox alternative](fox.gif) uses **synthetic** counts and a custom warm palette; [dark version](fox_dark.gif). Both keep the same compact frameless grid.

## Daily updates in your profile

Start with the [profile starter](starter/README.md): copy its workflow, JSON, one icon and README snippet; change your GitHub username; enable Actions and run once. Customize the icon and colors whenever you like. Successful daily/manual runs publish both theme GIFs and cache-busting links. A failed run keeps the previous images. No extra secret is needed for public contribution data.

## Make one with your character

Python 3.10+ is required. Clone this repository, then run the following from its root:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python render.py --config cat.json --activity shin_activity_2026-09-20.json --seed 216 --theme light --out my-profile.gif
python render.py --config cat.json --activity shin_activity_2026-09-20.json --seed 216 --theme dark --out my-profile-dark.gif
```

These are your first light/dark copies of the crowned-cat example. For your own version:

1. Save your icon as `your-icon.png` beside your JSON config (PNG, JPEG, or another Pillow-readable image; a transparent square icon looks best). Copy `config.example.json` to `my-config.json`; replace `YOUR_LOGIN` with your GitHub username, and change `icon`, `accent`, and `glow` to your image filename and `#RRGGBB` colors. Paths are relative to the config file. Optional `accent_dark` / `glow_dark` override only the dark version.
2. Make a clearly **synthetic** test snapshot for that username, then render it:

   ```sh
   python render.py --sample my-activity.json --username YOUR_LOGIN
   python render.py --config my-config.json --activity my-activity.json --out my-profile.gif
   python render.py --config my-config.json --activity my-activity.json --theme dark --out my-profile-dark.gif
   ```

Only one icon image is necessary: it bobs, tilts, rests and wakes in both scenes. The cat's `sleep_icon` and `wake_icon` are optional extra poses; omit both keys for a single-image character, as in `fox.json`. No custom animation frames or drawing program are needed.

For **your real public contribution data**, install the [GitHub CLI](https://cli.github.com/) and authenticate with `gh auth login` on your own machine. `gh auth status` should succeed; `gh api graphql` requires an authenticated token permitted to view that user's contribution calendar. The renderer only **reads** `user(login: ...) { contributionsCollection { contributionCalendar { ... } } }` and needs no GitHub write operation. [GitHub CLI's login defaults](https://cli.github.com/manual/gh_auth_login) include broader `repo`, `read:org`, and `gist` OAuth scopes; those are CLI defaults, not extra powers requested by this script. [GitHub documents](https://docs.github.com/en/graphql/reference/users#contributionscollection) optional `read:user` for including private/internal contributions; it is not needed for the public example. Do not paste tokens into config files, commits, or issues. Run:

```sh
python render.py --capture my-activity.json --username YOUR_LOGIN
python render.py --config my-config.json --activity my-activity.json --out my-profile.gif
python render.py --config my-config.json --activity my-activity.json --theme dark --out my-profile-dark.gif
```

Capture defaults to the last 196 UTC calendar days; use `--from-date YYYY-MM-DD --to-date YYYY-MM-DD` to set the range explicitly. Re-run these two commands whenever you want a new static snapshot/GIF, then commit the new GIF to the repository that serves your profile. The capture JSON includes `observed_at`; review it before publishing. Public counts can differ from what you expect because of GitHub's contribution and privacy rules. `--sample` is synthetic and never queries GitHub; `--capture` is the authenticated real-data path. These local commands do not schedule updates; the [starter workflow](starter/README.md) does.

Commit both GIFs to your special `YOUR_LOGIN/YOUR_LOGIN` profile repository and put this in its `README.md`:

```html
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="./my-profile-dark.gif">
  <img src="./my-profile.gif" alt="My decorative activity animation">
</picture>
```

If the GIF stays in this repository instead, reference an immutable commit, for example `https://raw.githubusercontent.com/OWNER/github-profile-motion/COMMIT/my-profile.gif`. A moving title is optional: `python render.py --heading-out heading.gif --heading-mobile-out heading_mobile.gif`, then use a `<picture>` element like the one above. The sample heading text is fixed in `render.py`; edit `HEADING` if your profile needs different words. Keep meaningful `alt` text: a reduced-motion client may show only frame one.

## What is included

- `render.py` makes deterministic, script-free light/dark GIFs from an icon, palette, seed, and dated JSON. The two-scene `shock` loop is the default. `--pattern touch` is a retained alternate, not another required sprite set.
- `cat.json` plus `crowned_cat*.png` are the ready-to-run character; `fox.json` and `fox.png` demonstrate one-image substitution. `make_icons.py` regenerates these original small icons.
- `shin_activity_2026-09-20.json` is a frozen public GitHub GraphQL snapshot; `example_activity.json` is explicitly synthetic. Each activity file contains a `username` and `days` entries with `date` and nonnegative integer `count`; the username must match the config. Rendering does not modify input counts.
- `test_render.py` checks stable frames, two-scene continuity, input preservation, and alternate-icon output. Run `python -m unittest -v test_render` after installing dependencies.
- `update_profile.py` and its tests prepare validated real-data GIFs for both themes plus dated README links; the [reusable workflow](.github/workflows/render-profile.yml) commits all three files in the caller's profile repository. A failure produces a failed Actions run, not a silent synthetic image.

The [daily refresh rollout record](DAILY_REFRESH_ROLLOUT.md) describes impact and rollback without changing the fixed V216 examples.

Code and original included artwork are available under [MIT](LICENSE). The renderer, config, icons, examples, and tests were extracted from [Decision-OS V13 LoopKit at `a3c3e6633b13684adc08beab28883a57b11d5cbb`](https://github.com/shin4141/decision-os-v13-loopkit/tree/a3c3e6633b13684adc08beab28883a57b11d5cbb/examples/profile_motion); that repository holds the design/decision history and [Aspire entry](https://github.com/shin4141/decision-os-v13-loopkit). This repository is the canonical place for future generator changes. See the [live example on Shin's profile](https://github.com/shin4141).
