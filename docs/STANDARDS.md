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
- [ ] Triggers: pushes to `main`, pull requests to `main`, and `merge_group` (the merge queue
      needs its own runs). Concurrency keyed on the event; runs on `main` are never canceled.
- [ ] The coverage badge is published to the orphan `badges` branch, never committed to `main`
      (the ruleset rejects it).
- [ ] `.github/dependabot.yml`: weekly uv updates in one grouped PR.
- [ ] `.coderabbit.yaml` (copied from highrise; adjust the tests rule) and CodeQL default
      setup on.

## Release (`.github/workflows/release.yml`)

- [ ] Triggered by a `v*` tag pushed after a "Release x.y.z" PR (version bump + CHANGELOG).
- [ ] Builds, all attached to the GitHub release:
  - [ ] desktop zips for Windows, macOS and Linux (PyInstaller, `<game>.spec`);
  - [ ] the browser build (`web/`, `scripts/build_web.py`, pygbag) as `<game>-web.zip`;
  - [ ] the Windows installer (`packaging/<game>.iss`, Inno Setup) as
        `<game>-windows-setup.exe`.
- [ ] Release and deployment are separate: the tag builds once and creates the GitHub release
      (its files never change); deploy jobs push those same files to the stores.

## Deployment (`.github/workflows/deploy-itch.yml`)

- [ ] A reusable workflow (`workflow_call`) that downloads a release's files and pushes them to
      itch.io with butler (desktop channels + `html5`). `release.yml` calls it at the end: a
      release made with `GITHUB_TOKEN` does not trigger a `release: published` workflow.
- [ ] It also has `workflow_dispatch` with a tag input, to redeploy an existing release without
      rebuilding.
- [ ] The deploy job runs in the `itch-io` environment (URL = the itch.io page), with the owner
      as required reviewer, so every deploy waits for approval and shows under Deployments.
      `BUTLER_API_KEY` is an environment secret, not a repo or org secret.

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
- [ ] Private vulnerability reporting and Dependabot alerts are on (Settings > Security), to go
      with `SECURITY.md`.
- [ ] Settings > General: automatically delete head branches on.

## Files

- [ ] `README.md` (badge row: CI, release, license, coverage, Python | pygame-ce; preview GIF
      and screenshots at 1920x1080), `CHANGELOG.md`, `LICENSE` (MIT),
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
