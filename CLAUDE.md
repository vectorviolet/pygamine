# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

pygamine is the shared engine layer of VectorViolet's pygame-ce games. Each game vendors it
as a git submodule at `src/pygamine`.

## Which games follow pygamine

**Active projects:** these track pygamine's `main` and get its updates.

- **Chokepoint** (`vectorviolet/chokepoint`)
- **Highrise** (`vectorviolet/highrise`)

**Every other game stays where it is.** Standoff, Logic Games and Artificial Chaos are frozen
at the **`v0.24.0`** tag (the freeze point); Hunted and Terraria are not bumped either. Don't
move their submodules.

So a new pygamine release is bumped into the active projects only. "Bump the others" or
"bump all games" is no longer a step after a release.

## Code style

Run `uv run --group dev ruff format .` and `uv run --group dev ruff check .` before every commit.
Formatting is Black-compatible (`[tool.ruff.format]` in `pyproject.toml`). CI fails on
`ruff format --check .` and on lint errors. Keep pure reformatting out of feature commits; a
repo-wide reformat goes in its own commit, with its hash added to `.git-blame-ignore-revs`.

## Releasing

1. Update `CHANGELOG.md` and bump `version` in `pyproject.toml` (and `uv.lock`, via `uv lock`).
2. Run the tests (`pytest`), `mypy pygamine` and `ruff check .`.
3. Push pygamine **before** the games that point at the new commit. Otherwise their CI can't
   find the submodule commit.
4. Annotated tag, `vX.Y.Z` with the message `X.Y.Z - <summary>`, at least for releases that
   frozen or archived projects might pin.

## Bundled third-party material

- `branding/` holds splash and logo artwork. It's not under pygamine's MIT license; see
  `branding/NOTICE.md`.
- `licenses/` holds the license texts of pygame-ce and the native libraries it bundles. Every
  game's build ships it. After upgrading pygame-ce, refresh it (see `licenses/README.md`).
