# Game project standard

What every active VectorViolet game built on pygamine has, on the model of chokepoint and
highrise. A new or revived project is "up to standard" when every box below is ticked. When a
copy-from file is named, copy it from highrise (the cleaner of the two) and adjust names.

## Engine

- [ ] `src/pygamine/` is the pygamine submodule, on the same version as the other active games.
- [ ] `pygamine` is an editable path dependency in `pyproject.toml` (`[tool.uv.sources]`).

## Tooling (`pyproject.toml`, `uv.lock`)

- [ ] uv with a committed `uv.lock`. Dependency groups: `dev` (pytest, pytest-cov, ruff, mypy,
      codespell, type stubs) and `build` (pyinstaller).
- [ ] ruff and mypy pinned to exact versions, the same in every repo.
- [ ] `[tool.ruff]`: line length 88, black-style format, the narrow rule set (F, return-type
      ANN rules, PLR6301, complexity caps), `src/pygamine` excluded.
- [ ] `[tool.codespell]`: American English (`en-GB_to_en-US` plus `.codespell-en-us.txt`).
- [ ] `[tool.mypy]` checks `src/`. Optional types are fixed at the source; use asserts, not
      silent guards.

## CI (`.github/workflows/ci.yml`)

- [ ] Jobs: `lint` (ruff check + format check), `spelling`, `typecheck`, `engine-tests`,
      `app-tests` (with coverage badge), smoke test (`scripts/smoke_test.py`), web stage check.
- [ ] Every job is a required check in the `main` ruleset.

## Release (`.github/workflows/release.yml`)

- [ ] Triggered by a `v*` tag pushed after a "Release x.y.z" PR (version bump + CHANGELOG).
- [ ] Jobs: desktop builds (PyInstaller, `<game>.spec`), browser build (`web/`,
      `scripts/build_web.py`), Windows installer (`packaging/<game>.iss`), GitHub release with
      every file attached, itch.io push (desktop channels + `html5`).

## Repository

- [ ] `main` ruleset: PR only, required checks green, branch up to date, no force push or
      deletion; `v*` tags can't be moved or deleted. (Rulesets need a public repo or GitHub Pro.)
- [ ] The repo is on the Roadmap board, and every issue has a milestone (next release, 1.1,
      Someday).
- [ ] About box: a one-line description ending in "Python + pygame-ce.", the itch.io page as
      the website, and topics (`2d-game`, `game`, `indie-game`, `pygame`, `pygame-ce`,
      `python`, plus the genre).
- [ ] Social preview: `docs/design/social-preview.png` (1280x640, the logo over game art),
      uploaded by hand in Settings > Social preview (GitHub has no API for it).
- [ ] Private vulnerability reporting is on (Settings > Security), to go with `SECURITY.md`.

## Files

- [ ] `README.md` (preview GIF and screenshots at 1920x1080), `CHANGELOG.md`, `LICENSE` (MIT),
      `CONTRIBUTING.md`, `SECURITY.md`, `CREDITS.md`, `CLAUDE.md`.
- [ ] `licenses/`: license texts of the bundled software (pygame-ce and its libraries).
- [ ] `docs/ARCHITECTURE.md`, `docs/devlog/` (an illustrated entry per feature or design
      decision), `docs/decisions/` (ADRs), `docs/store/` (itch.io page material).

## Assets and licensing

- [ ] Every file under `assets/` is listed in `assets/SOURCES.yaml` with its pack, author, URL
      and license. No `unknown` sources and no open `todo`s.
- [ ] Only CC0, CC BY or OFL. Anything else needs the owner's OK first.
- [ ] Each pack is kept, as downloaded, in the asset library, under the same slug as in
      SOURCES.yaml.
- [ ] The asset table in `CREDITS.md` is generated from SOURCES.yaml
      (`scripts/gen_credits.py`), and the game has an in-game CREDITS page with the same list.

## Game

- [ ] If the game saves anything, saves go in the user data folder in packaged builds (pygamine
      `packaged_data_dir`) and in localStorage in the browser build. Tests and play-tests never
      touch real saves.

### Optional (larger games)

Not required: a small game (like The Hunted) is up to standard without them. A game that grows
a settings page or several menus should add them.

- [ ] Settings: master volume, language and UI scale, saved when changed.
- [ ] UI built from YAML panels and config through pygamine's `PanelManager`.
