# Changelog

All notable changes to this project are documented here. Format loosely
follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/); versioning
follows [SemVer](https://semver.org/) with the 0.y.z caveat it defines
itself — this is major version zero, so a MINOR bump can and does include
breaking changes, since the public API isn't considered stable yet.

No tags existed before this file was added (2026-07-28) despite `pyproject.toml`
carrying a `version` field since `e5c1fa6` — the four releases below were cut
retroactively from git history at that point, grouped by what actually shipped
together rather than reconstructing a commit-by-commit rationale for every
change. Anything before `e5c1fa6` (the commit that first introduced
`pyproject.toml` itself) isn't versioned at all; see `git log` for that era.

## [Unreleased]

- **Changed** every function and method in `pygamine/` declares its return
  type (`-> None` included), and ruff's ANN201-ANN206 rules keep it that way
  in CI (`tests/` is exempt; its fixtures and helpers that return a value are
  annotated anyway). Annotation-only: no behaviour change. Side effects for
  type-checked callers: `load_image()` returns `Surface`, or
  `(Surface, size)` with `return_size=True`; the `make_*_factory()` functions
  return typed factories; `TiledMap.iter_objects()`,
  `SpatialGrid.query_radius()` / `query_rect()`, `GameObjectDict.values()`
  and `PanelManager.keys()` return typed iterators/views.
- **Changed** (breaking) `Application.minimize()` is renamed
  `Application.set_windowed()`. It never minimized (iconified) the window:
  it switches to windowed mode, beside `full_screen()` and
  `borderless_full_screen()`. Saved settings are unaffected (the mode is
  still stored as `"windowed"`).
- **Changed** (breaking) `Application.minimized_size`, `minimized_width` and
  `minimized_height` are renamed `default_size`, `default_width` and
  `default_height`. They hold the constructor's `size` (the default windowed
  size, and the design resolution under `fixed_aspect=True`), not a
  minimized size.
- **Changed** (breaking) `PanelLoader.pm` is renamed
  `PanelLoader.panel_manager`, matching the constructor argument it stores.
- **Changed** (breaking) `angle_between_delta()` is renamed
  `angle_of_delta()`, both in `pygamine` and `pygamine.util.math_utils`: it
  returns the angle of one delta vector, not an angle between two things.
- **Fixed** the `ObjectFactory` type alias `PanelLoader.register()` takes
  now matches what factories actually receive, `(cfg, parent: Transform)`,
  not `(cfg, window_size)`.

## [0.26.0] — 2026-10-26

- **Changed** `GameAudio.play_sfx()` plays each sound effect on a free mixer
  channel from a pool (16 by default) instead of the one shared channel 1, so
  a new SFX no longer cuts off the one before it. It now returns the
  `Channel` it plays on, or `None` if the sound was dropped. Still callable
  on the class or an instance. Each sound file is decoded once and cached.
- **Changed** channels 0-2 (`RESERVED_CHANNELS = 3`) are reserved and never
  used for SFX: 0 is the music; 1 (the old `SFX_CHANNEL`) and 2 stay free for
  a game's own `SoundManager` use, e.g. a dedicated alert channel.
- **Changed** the SFX volume is kept by `GameAudio` (class-wide, since the
  mixer is global) and applied to every pool channel, including SFX already
  playing; channel 1 is kept at the same volume. `sfx_volume()` returns the
  value set, not the mixer's quantised read-back. Music volume is unaffected.
- **Added** `GameAudio.configure_sfx(channels=, steal_oldest=,
  max_copies_per_sound=)`, also accepted by the constructor as
  `sfx_channels=`, `steal_oldest=` and `max_copies_per_sound=` (left as None,
  each keeps its setting). When every pool channel is busy, the new sound is
  dropped (`steal_oldest=False`, the default), or, with `steal_oldest=True`,
  the SFX that has played longest is stopped for it. `max_copies_per_sound`
  (off by default) caps how many copies of one file play at once.

## [0.25.0] — 2026-10-26

- **Removed** (breaking) `Application.fetch_screen_dimensions()` and
  `Application.info_object`. `__init__` now sets `minimized_size` and
  `full_screen_size` (and their `_width`/`_height` parts) itself; the desktop
  size comes from the new private `_query_screen_size()`. The attributes are unchanged. No game called
  the removed method.
- **Removed** (breaking) `Application.mouse_pos`. It was always `(0, 0)`:
  nothing updated or read it. Use `app.mouse.position` for the cursor.
- **Changed** (breaking) `Application.width` and `Application.height` are now
  read-only properties derived from `size`, so the three can't drift apart. Assigning
  them directly no longer works; use `set_size()`.
- **Fixed** `Application.keys` and `Application.display_surface` are created in
  `__init__`. `keys` used to appear only on the first frame, so reading it
  earlier (e.g. during the splash) raised `AttributeError`.

## [0.24.0] — 2026-10-25

- **Added** the solid VectorViolet lockup and wordmark
  (`lockup-{dark,light}-solid.png`, `wordmark-{dark,light}-solid.png`) to
  `branding/vectorviolet/`, beside the glitch ones: no glitch lines, for
  small sizes and busy backgrounds.
- **Added** `licenses/`: the license texts of pygame-ce, pygamine and every
  native library pygame-ce bundles on Windows, macOS and Linux (SDL2 and its
  satellites, FreeType, libpng, libjpeg, libtiff, libwebp, Ogg/Vorbis, Opus,
  FLAC, mpg123, ...), with a README mapping each library to its text. Those
  licenses want their notices to travel with binary copies, so a game's build
  should ship this folder next to its executable.
- **Changed** `branding/NOTICE.md` separates the two cases: the `vectorviolet/`
  files may not be used without permission, while the third-party logos are
  subject to their owners' rules.

## [0.23.0] — 2026-10-25

- **Added** fade-in / fade-out options for splash media.
  `ImageSequenceMedia(..., fade_in_ms=0, fade_out_ms=0)` fades the clip in
  from black and out to black; the audio stays at full volume.
  `ImageMedia(..., fade_out_ms=0)` fades the image out after its hold.
  `standard_splash_media(audio, fade_in_ms=None, fade_out_ms=None)` applies
  the given fades to both items; left as None, each keeps its own default.
  Defaults are unchanged, so existing splashes look the same.
- **Changed** (breaking) `ImageMedia`'s `fade_ms` is renamed `fade_in_ms`,
  to pair with `fade_out_ms`.
- **Changed** a negative fade duration raises `ValueError`.
- **Changed** (breaking) the VectorViolet logos' `-light` / `-dark` suffixes
  are swapped to name the background they are for, as the brand guide
  defines them: `-dark` is now the white-artwork version for dark
  backgrounds, `-light` the black-artwork one for light backgrounds. Swap
  the suffix in any `source: branding` entry that uses them.

## [0.22.0] — 2026-10-25

- **Changed** the publisher splash is renamed to `branding/vectorviolet/splash/`
  (frames + `meta.yaml`) and `branding/vectorviolet/splash.ogg`;
  `standard_splash_media()` loads the new names.
- **Added** VectorViolet lockup and wordmark PNGs (`lockup-{dark,light}-glitch.png`,
  `wordmark-{dark,light}-glitch.png`) to `branding/vectorviolet/`, so every game
  can show the publisher logo through `source: branding` instead of keeping its
  own copy.
- **Changed** `branding/itch.io/` is renamed to `branding/itchio/`; update
  `source: branding` manifest entries that use `folder: itch.io/...`.
- **Added** `branding/NOTICE.md`: the branding files are not covered by
  pygamine's MIT license.

## [0.21.0] — 2026-10-25

- **Changed** `branding/` is organised by owner: `vectorviolet/` (the
  publisher splash clip and audio), `pygame/` (the pygame-ce logo),
  `github/` and `itch.io/` (their official logo files).
  `standard_splash_media()` reads the new locations. Frozen builds still
  bundle the whole folder as `pygamine/branding`.
- **Added** `source: branding` for asset-manifest entries: the `folder`
  is then relative to pygamine's `branding/` instead of the game's
  `assets/<category>/`, so a game can show the bundled platform logos,
  e.g. `{source: branding, folder: github, name: GitHub_Invertocat_White}`.
  `BRANDING_DIR` now lives in `pygamine.assets.asset_path` (still
  importable from `pygamine.app.splash_screen`).

## [0.20.1] — 2026-10-25

- **Changed** the shared splash's second slide (`branding/pygame_logo.png`)
  from the original pygame logo to pygame-ce's "powered" logo, rendered
  from the SVG at https://pyga.me/docs/logos.html ("These logos are
  available for use in your own game projects"). It sits on a transparent 1920x1080 canvas so
  the fit-to-screen scaling shows it at about 60% of the screen width.

## [0.20.0] — 2026-10-25

- **Added** `Camera.center_on(world_pos)`: scrolls so a world point sits
  at the viewport centre, clamped at the map edges like any scroll.
- **Added** a `frames` argument to `Camera.update_with_mouse()` (default
  1.0, the old behaviour): how many frames' worth of edge scroll the call
  covers, so a host can keep the scroll rate independent of its frame
  rate by passing elapsed_ms / frame_ms.
- **Fixed** full-window objects (`size: WINDOW`, e.g. a popup's dim
  overlay) being shifted off the window's top-left when the window's
  aspect ratio differs from the authored layout's (16:10 vs 16:9 left a
  60px uncovered strip): their position is now scaled, not centre-remapped.

## [0.19.0] — 2026-10-24

- **Added** `pygamine.devtools.smoke.run_briefly(app, frames=30)` for host
  projects' smoke tests: runs the app's real `run()` -- splash, any `run()`
  override, main loop -- for a few frames, then stops it. Building a
  `Game()` and rendering panels never exercised that path, which is how
  0.15.0's second-splash-run crash reached highrise's releases unseen. The
  splash plays through to its natural end (the clock is fast-forwarded
  while it's up) rather than being skipped, since skipping a
  `skip_completely` splash never reaches that crash; a hang raises instead
  of stalling CI.

## [0.18.0] — 2026-10-24

- **Added** `standard_splash_media(audio_manager=None)`: the splash every
  game opens with -- the publisher clip (with its audio), then the pygame
  logo -- so it's identical across projects and changes in one place.
  Its assets ship in `pygamine/branding/` (240 frames + `meta.yaml`, the
  clip's `.ogg`, the logo), resolved next to the package, not a game's
  `assets/`. A frozen build must bundle that folder as data:
  `(str(ROOT / "src/pygamine/pygamine/branding"), "pygamine/branding")`.
  Without an audio manager it plays the clip through its own `GameAudio`.
- **Added** `GameAudio.stop_music()` and `SoundManager.stop(channel)`.
- **Fixed** `SplashScreen.run()` crashing with `IndexError` when called on
  a splash that already finished (regression from 0.15.0's rewrite; the
  old version returned at once). A game that shows the splash itself and
  then reaches `Application.run()`, which shows it again -- highrise does
  -- crashed on startup.
- **Changed** `ImageSequenceMedia` stops its audio when it ends or is
  skipped, instead of pausing it: a paused channel stays busy forever,
  since nothing ever resumes a splash clip's audio. Start a game's own
  music after the splash, as before.
- The repository moved from `umutcanekinci/pygamine` to
  **`https://github.com/vectorviolet/pygamine`**, alongside the games that
  use it. GitHub redirects the old URL, but consumers should point their
  `.gitmodules` at the new one (then `git submodule sync`) rather than rely
  on the redirect, which breaks if a new repo ever takes the old name.

## [0.17.1] — 2026-10-24

- **Fixed** `load_font` silently ignoring `bold` / `italic` for fonts
  registered in the asset manifest -- only the SysFont fallback honoured
  them, so switching a panel from a system font to a bundled file quietly
  dropped its bold. Font files now get pygame's synthetic bold/italic;
  for a real weight, register its own file (e.g. `*-Bold.ttf`) and leave
  the flag off. No current consumer combines a manifest font with these
  flags, so nothing renders differently today.

## [0.17.0] — 2026-10-24

- **Added** the `pygamine-mp4-converter` devtool
  (`pygamine.devtools.mp4_converter`): turns a video into numbered `.jpg`
  frames plus a `meta.yaml` (fps, frame_count, size) in `frames/`, and its
  audio into an `.ogg` -- exactly what `ImageSequenceMedia` plays. Rerunning
  clears stale frames. Needs moviepy (which bundles ffmpeg), the new
  optional `video` extra; from a host project:
  `uv run --with moviepy pygamine-mp4-converter intro.mp4 -o out`.
  Previously a loose script outside any repo.
- **Changed** `PanelLoader` scales a numeric `speed` (px/s) by the UI
  scale, like positions and sizes, so a `ScrollingPanel` keeps pace with
  its scaled layout instead of crossing smaller windows faster.

## [0.16.0] — 2026-10-24

- **Added** a `sequences:` section to the asset manifest, for image
  sequences (folders of numbered frames): `{folder, name, extension}`
  resolves to the folder `assets/images/<folder>/<name>/` holding
  `*.<extension>` frames (default `jpg`). Backed by the new
  `SequencePath` (with `frame_paths()`) and
  `AssetManager.sequence_path(key)`; `validate()` reports a sequence
  whose folder has no frames, not just a missing path.
- **Changed** `ImageSequenceMedia` reads its frame rate from a
  `meta.yaml` (`fps: ...`) in the frames folder when `fps` isn't passed,
  falling back to `DEFAULT_SEQUENCE_FPS` (30) as before. A mismatched
  rate makes the picture drift from the audio and end early or late.
  It also accepts a `SequencePath`, taking its frames (of its
  `extension`) from it.

## [0.15.0] — 2026-10-24

- **Breaking:** `SplashScreen` now plays a list of `SplashMedia` items
  instead of loading image paths itself:
  `SplashScreen(image_paths, fade_ms, hold_ms)` becomes
  `SplashScreen([ImageMedia(path, fade_ms=..., hold_ms=...), ...])`.
  `ImageMedia` keeps the old per-image fade-in/hold behaviour.
- **Breaking:** Escape no longer ends the whole splash; like a click,
  Space or Enter it skips only the current item. Pass
  `skip_completely=True` to make any skip end the whole splash (which also
  stops the current item, so its audio doesn't keep playing).
- **Added** `ImageSequenceMedia`: plays a folder of numbered `.jpg` frames
  as a video, with optional audio through `GameAudio`. Frames stream from a
  background thread into a small bounded buffer; the frame shown is derived
  from elapsed time, so it stays in sync with the audio and drops late
  frames rather than drifting. No video-decoding dependency -- convert a
  video to frames + `.ogg` ahead of time.
- **Added** `ScrollingPanel` (`type: scrolling_panel` via the new
  `make_scrolling_panel_factory`): a clipped viewport (its `position` /
  `size`) that adopts the panel objects named in `targets` and scrolls them
  upward at `speed` px/s, looping or stopping (`loop: false`, then
  `is_finished`). Adopted objects are removed from the panel, so the
  scroller alone updates, draws and forwards events to them.
- **Added** `PanelLoader` calls `on_panel_loaded(panel)` on each object of a
  panel once the whole panel has loaded, for objects that need siblings
  declared after them. **Added** `GameObjectDict.pop()`.
- **Changed** `AssetManager.load_manifest()` and the `*_path()` lookups
  share one helper per concern; unknown-key errors for fonts and sounds
  now list known keys too, like images already did.
- `SplashMedia`, `ImageMedia`, `ImageSequenceMedia`, `ScrollingPanel` and
  `make_scrolling_panel_factory` are exported from the package root.

## [0.14.1] — 2026-07-30

- **Fixed** `test_resource_root_falls_back_to_project_root_when_not_frozen`,
  broken the moment [0.14.0]'s new CI matrix actually ran this repo's own
  test suite as its own standalone checkout for the first time (previously
  this test only ever ran nested inside a host project's `src/pygamine/`,
  since that's the only context anyone had run it in) -- it asserted
  against `Path(__file__)`, silently assuming the ambient checkout
  happened to be vendored inside a host project three levels down, which
  isn't true when pygamine's own repo is checked out on its own (exactly
  what CI does, and what a plain `git clone` + `pytest` does too). Fixed
  by building a fake `<root>/src/pygamine/pygamine/assets/paths.py` tree
  in `tmp_path` and pointing `paths.py`'s own `__file__` at it, so the
  test no longer depends on where the suite itself happens to be checked
  out. Confirmed it still catches the real regression it was written for
  (reverting to the pre-[0.13.1] `parents[3]` fails it again).

## [0.14.0] — 2026-07-29

- **Added** a real Python version compatibility matrix (3.12/3.13/3.14) to
  the `test` CI job -- `classifiers` has claimed all three since day one,
  but CI only ever ran the one version pinned for lint/typecheck/coverage,
  so that claim was never actually verified. Split into two jobs: `test`
  (the new 3-version matrix, no coverage) and `coverage` (single pinned
  3.12 run, still the one that generates/commits the badge -- coverage
  numbers come from one canonical version, not the compatibility matrix).
  Manually verified full suite (650 tests), ruff, and mypy all clean on
  3.13 and 3.14 before adding the matrix, not just "it installs".

## [0.13.1] — 2026-07-29

- **Fixed** a real regression from [0.13.0], caught immediately by a
  consumer's own test suite (chokepoint's config loader): `paths.py`'s
  move into `assets/` made it one directory deeper
  (`pygamine/paths.py` -> `pygamine/assets/paths.py`), so
  `resource_root()`'s `Path(__file__).resolve().parents[N]` needed `N`
  to grow from `3` to `4` -- it didn't, so every host project's
  `resource_root()` silently resolved one level too shallow (landing on
  `<project>/src/pygamine` instead of `<project>/`) the instant it
  stopped being frozen-only and someone actually loaded a real
  cwd-relative config path. `test_resource_root_falls_back_to_project_
  root_when_not_frozen` didn't catch this at review time because it only
  asserted `root.is_dir()` -- true at *any* ancestor depth of a real
  file, not just the correct one -- strengthened to verify
  `resource_root()` actually contains this repo's own known file at its
  fixed relative path instead.
- **Fixed** a matching gap in the [0.10.0]/[0.13.0] import migrations:
  they only scanned each consumer's `src/`/`bench/`/`__main__.py`, never
  each project's own `tests/`/`scripts/` directories -- 6 files across 4
  projects (`chokepoint`, `highrise`, `standoff`, `artifical-chaos`)
  still had deep-path `from pygamine.<old path> import X` imports
  referencing pre-reorg module locations, broken by [0.13.0]. Migrated
  to the top-level API along with everything else.

## [0.13.0] — 2026-07-29

- **Changed** (breaking for deep-path imports only): reorganized the 21
  loose files that previously sat directly in the package root into
  subpackages, mirroring the README's own existing module-map sections
  so no new mental model was invented, just made literal:
  - `app/` — `application`, `mouse`, `camera`, `splash_screen`, `debug`
  - `assets/` — `asset_path`, `asset_manager`, `image`, `font`,
    `sprite_sheet`, `database`, `save_store`, `tilemap`, `paths`
  - `panels/` — `panel_manager`, `panel_loader`, `panel_loader_ext`,
    `panel_factory`
  - `util/` — `utils`, `math_utils`, `spatial_grid`

  `ecs/`, `ui_widgets/`, `net/`, `devtools/` were already organized and
  are unchanged. The package root now holds only `__init__.py` and
  `py.typed`.

  This is invisible to every consumer already on the curated top-level
  API (`from pygamine import X`) -- verified by round-tripping all 70
  exported names through `pygamine._EXPORTS` after the move -- since
  only `_EXPORTS`' *values* (which submodule defines each name) changed,
  not its keys. Only deep-path imports (`from pygamine.<old path> import
  X`) break; there were none left in any of the 6 consumer projects after
  the [0.10.0] top-level-API migration, but any code still using the old
  paths needs updating (see the module map for the new locations, or the
  git history of `pygamine/__init__.py` for the exact old→new mapping).

## [0.12.0] — 2026-07-29

- **Changed** (breaking): standardized the debug-info reporting API across
  `Camera`/`Mouse`/`StateObject` -- all three now expose a plain `.info()`
  method returning `tuple[str, dict]`. Previously all three disagreed:
  `Camera.info()` (method, no prefix), `Mouse.get_info()` (method, `get_`
  prefix), `StateObject.get_info` (a **property** with a `get_` prefix --
  the actively misleading combination, since a property already reads
  like an attribute; naming it `get_X` invites calling it as
  `get_info()`, which would `TypeError` on the returned tuple). Found by
  a real consumer call site (chokepoint's debug overlay) mixing all
  three conventions in one list literal. `Mouse.get_info()` ->
  `Mouse.info()`; `StateObject.get_info` (property) -> `StateObject.info()`
  (method).

## [0.11.0] — 2026-07-29

- **Fixed** a real bug in `MouseInteractive.is_mouse_over()`: its
  parent-offset branch (`self.parent.rect + self.rect`) would raise
  `TypeError` if ever triggered -- `pygame.Rect` doesn't support `Rect +
  Rect` -- and, confirmed by grepping every consumer project, nothing
  anywhere ever actually sets a bare `self.parent` on a
  `MouseInteractive` object (parenting goes through `Transform`'s own
  `.parent` field everywhere, e.g. `self.rect.set_parent(...)`, which
  already bakes the parent's offset into absolute coordinates at
  `set_position()` time). The branch was dead *and* broken; removed it --
  `is_mouse_over` now just calls `self.rect.collidepoint(...)` directly.
- **Removed** `PanelLoader._resolve_position`/`_resolve_size`: confirmed
  dead via 0% coverage and zero call sites anywhere -- panel factories
  (`make_factory`, etc.) already resolve position/size themselves.
- **Added** `pytest-cov` to the dev group and wired up coverage
  reporting + a `.github/badges/coverage.json` badge in this repo's own
  CI and README, dogfooding the `pygamine-coverage-badge` console
  script every host project's CI now runs. Coverage sat at 97% before
  this release surfaced the two items above (both now covered,
  currently 98%) -- it was previously untracked, unlike every project
  that depends on this package.
- **Added** direct unit tests for `MouseInteractive` (`is_mouse_over`/
  `is_clicked`), previously only exercised indirectly through
  `StateObject`/`Slider`/`InputBox`'s own tests, which never hit every
  branch (a non-left mouse button, visibility toggling mid-press, an
  unrelated event type in between press and release).

## [0.10.0] — 2026-07-29

- **Added** `DatabaseError` to the curated top-level API (`from pygamine
  import DatabaseError`) -- an omission from when `database.py` was
  rewritten to raise it instead of `sys.exit()`ing.

## [0.9.0] — 2026-07-29

- **Added** `pygamine.paths`: `resource_root()`/`resource_path()`, the
  frozen-vs-source filesystem anchor every host project's `__main__`
  chdirs into at startup. Extracted after finding the exact same
  `resource_root()` function body duplicated (only the module docstring
  varied) across `chokepoint`/`highrise`/`hunted`/`standoff`'s own
  `src/util/paths.py`. Those four now re-export from here instead of
  carrying their own copy of the implementation.
- **Added** a `pygamine-coverage-badge` console script
  (`pygamine.devtools.coverage_badge`), replacing the byte-identical
  `scripts/make_coverage_badge.py` five sibling projects each carried a
  copy of. Host CI now runs `uv run pygamine-coverage-badge` instead.
- **Fixed** the README's `[tool.uv.sources]` note, which claimed (as of
  the 0.3.0-era text) that no host project lists `pygamine` under
  `[project.dependencies]`, making the override "inert boilerplate
  everywhere." All six now do list it, and `uv.lock` confirms the
  override is genuinely active (`source = { editable = "src/pygamine" }`)
  — corrected the note instead of leaving it telling people a working
  mechanism is dead weight.

## [0.8.0] — 2026-07-29

- **Changed** (breaking): `InputBox` now matches every other widget's
  conventions (`StateObject`, `Slider`, `TextObject`) instead of predating
  them -- it's `GameObject`-based and takes `parent`/`pos`/`size`/`anchor`
  instead of raw `x, y, w, h`, and accepts a `font` instead of always
  building `pygame.font.Font(None, 32)` on every keystroke. Focus state is
  now `.focused` (was `.active`, which collided in meaning with
  `GameObject.active`). Border color is exposed as `.border_color`; text
  color is a fixed `text_color` instead of switching with focus state the
  way the border does. Migration: `InputBox(x, y, w, h)` -> `InputBox(pos=(x,
  y), size=(w, h))`.
- **Changed** `GameAudio` no longer duplicates `SoundManager`'s
  play/clamp-volume logic -- it's now a 2-channel (music/sfx) convenience
  layer built on top of `SoundManager`'s generic per-channel primitives,
  adding only the music pause/resume/toggle state SoundManager has no
  opinion on. No public API change for either class. `SoundManager` gained
  `pause(channel)`/`unpause(channel)` (previously only reachable through
  `GameAudio`'s music-specific methods).
- **Removed** `image.load_image`'s dead `1/3`-means-"one-fifth-of-source"
  sentinel -- grepped every consumer project; nothing used it. It was a
  fragile float-equality check on top of an already-undocumented legacy
  convention.

## [0.7.0] — 2026-07-29

- **Changed** (breaking): `Database.connect()`/`.execute()` no longer
  `print()` and `sys.exit()` the whole process on failure -- they raise the
  new `pygamine.database.DatabaseError` instead, so a consumer can catch,
  log, or recover instead of the process dying mid-frame. `connect()` also
  no longer returns a `bool`; call it and handle `DatabaseError` (or let it
  propagate) instead of checking a return value. `execute_safely()` now
  disconnects in a `finally`, so a failed query no longer leaks an open
  connection the way a mid-call `sys.exit()` used to skirt around by
  killing the process before it mattered. Paths are now built with
  `pathlib.Path` instead of string concatenation, matching `SaveStore`'s
  convention; `Database.__init__` also gained an optional `directory`
  parameter (defaults to `"databases"`, the prior hardcoded value) for the
  same reason `SaveStore` has one.
- **Added** a `LICENSE` file (MIT) -- the package is public and
  pip-installable from GitHub but never actually declared a license.
- **Added** a `py.typed` marker (PEP 561) plus `[tool.setuptools.package-data]`
  so type checkers pick up this package's inline hints when it's installed,
  not just when it's vendored on `sys.path` inside the same checkout being
  checked.
- **Added** a `typecheck` CI job (`mypy`), deliberately permissive to match
  `[tool.ruff.lint]`'s "start narrow" precedent: no `--strict`, untyped
  function bodies aren't checked yet. Fixed the handful of real issues it
  surfaced: `Application`'s `self.window: Surface | None` dereferenced
  without narrowing in `_fit_rect`/`_sync_mouse_scale`/`_present`/
  `draw_mouse` (added `assert self.window is not None` guards -- true for
  the whole lifetime of these calls, since `__init__` always populates it
  before any of them can run), `Mouse.position` inferred as `tuple[int,
  int]` from its `(0, 0)` initializer despite being assigned floats in
  `update()`, and a stale `# type: ignore[override]` on
  `Transform.update()` that mypy's default (non-strict) mode never
  actually needed.
- **Fixed** two stray Turkish-language fragments left in comments/docstrings
  (`asset_path.py`, `utils.py`) -- translated to English.
- **Changed** `.idea/` project files are no longer tracked in the repo
  (IDE-local config, not shared-library source) -- added to `.gitignore`
  and untracked.

## [0.6.0] — 2026-07-29

- **Changed** (breaking): renamed the package/distribution/repository from
  `pygame_core`/`pygame-core` to **`pygamine`** -- PyPI already has an
  unrelated package literally named `pygame-core` (and a near-identical
  `pygame-pygame-core`), so publishing this under that name was never
  actually available. `import pygamine` replaces `import pygame_core`
  everywhere (deep-path imports too: `pygamine.ecs.game_object`, etc.);
  the GitHub repository itself moved to
  `https://github.com/umutcanekinci/pygamine` (old URL redirects, but
  consumers should point `.gitmodules`/`pyproject.toml` at the new one
  directly rather than relying on that indefinitely). No behavioral
  changes -- this is a pure rename, every module/class/function keeps its
  previous name and semantics.

## [0.5.0] — 2026-07-28

- **Added** `Application.restore_window_settings(saved_settings)`,
  `.window_settings()`, and `.reset_window_settings()` -- the window-mode/
  resolution slice of a `SaveStore`-style settings dict, extracted after
  chokepoint and standoff both independently grew the exact same three
  private methods (`_restore_window_mode`/`_save_settings`/
  `_reset_settings`) around this. Deliberately has no opinion on
  audio/gameplay settings a project also wants to persist alongside it --
  merge `window_settings()`'s dict into a larger one before saving.

## [0.4.1] — 2026-07-28

- **Fixed** a real regression from 0.4.0, caught immediately by a consumer's
  own test suite: `GameObject.image` was a read-only property, which broke
  every entity that manages its own image directly with no `SpriteRenderer2D`
  involved at all (e.g. one rendered straight from text) and expects a plain
  `self.image = ...` assignment to keep working -- `AttributeError: property
  'image' of 'GameObject' object has no setter`. `image` is now a full
  property backed by `_image`: a direct assignment takes priority over the
  `SpriteRenderer2D` fallback, exactly matching the pre-0.4.0 behavior for
  anything that never explicitly sets it.

## [0.4.0] — 2026-07-28

- **Changed** (breaking): `Camera.draw(surface, entity)` now reads `entity.image`
  directly instead of guessing between `entity.rotated_image` (when
  `entity.is_rotated`) and `entity.get_component(SpriteRenderer2D).image` --
  `Camera` no longer imports or knows about `SpriteRenderer2D`, ECS
  components, or rotation at all. `GameObject` gained a default `image`
  property (resolves to the attached `SpriteRenderer2D`'s image, or `None`
  without one) satisfying the new `Drawable` protocol for free; an entity
  that switches between multiple images (a rotated variant of its base
  sprite, an animation frame, ...) overrides that property itself instead
  of `Camera` special-casing `is_rotated`/`rotated_image` by name.
  Consumers with their own rotating/multi-image entities (e.g. chokepoint's
  `RotatableObject`) need to add an `image` property override before
  bumping past this version, or rotated sprites will silently render
  un-rotated instead of raising.

## [0.3.1] — 2026-07-28

- **Added** a CI lint job (`ruff check .`) and a `[tool.ruff.lint]` config,
  deliberately narrow: `F` (pyflakes — real bugs) and `I002` specifically
  (enforces `from __future__ import annotations` repo-wide via isort's
  required-imports check, not the full `I` sort-order category). Fixed the
  handful of files this caught: two real files missing the future import
  (`animation_clip.py`, `ui_widgets/input_box.py`), an unused `pathlib.Path`
  import, and every test file that was also missing it.
- **Fixed** a real bug this surfaced: `MouseInteractive.is_clicked()` computed
  a local `pressed` variable that was never used, and had a string literal
  positioned one line too late to actually function as the method's
  docstring (docstrings must be the first statement in the body).
- **Added** type hints (return types, mostly) to `Component`/`Behaviour`/
  `MonoBehaviour`, `Database`, `Camera`, `MouseInteractive`/`Anchorable`
  (`utils.py`), and a full pass (hints + a class docstring) on
  `ui_widgets/input_box.py`, which previously had neither.

## [0.3.0] — 2026-07-28

- **Added** a curated public API at the package root: `from pygamine import
  Application, GameObject, Camera, ...` now covers the ~66 names actually used
  across every consumer project, resolved lazily (PEP 562 module `__getattr__`)
  so importing a lightweight name never forces optional dependencies
  (`pyyaml`/`pytmx`) that a consumer might not otherwise need. Deep-path
  imports still work unchanged.
- **Added** `Application.splash` / `Application.show_splash()` — `run()` calls
  it automatically before the main loop, replacing the identical `run()`
  override + comment every consumer project had duplicated for this.
- **Added** `Application(..., fixed_aspect=True)` — locks `self.window` to the
  constructor's `size` as a genuine fixed design resolution regardless of the
  real display's shape, letterboxing/pillarboxing it with black bars
  (`Mouse.offset` added to keep click coordinates correct) instead of either
  distorting it or letting the default dynamic-canvas behavior reveal extra
  world space on a mismatched monitor.
- **Changed** `AnimationClip` now lives in its own `ecs.components.animation_clip`
  module instead of inside `animator.py` (which still re-exports it — source
  compatible either way).
- **Changed** every ECS/rendering module from tab to space indentation (no
  functional change, pure PEP 8 cleanup).
- **Fixed** README's module map, which was missing 7 modules including the
  entire `net` (protocol/transport) subsystem.
- **Fixed** (documentation) — every consumer's `[tool.uv.sources]` override for
  an editable local install had no effect, since none of them actually listed
  `pygamine` under `[project.dependencies]`; documented in the README so
  it's not copy-pasted as dead boilerplate again.

## [0.2.0] — 2026-07-08

- **Changed** (breaking): `self.window` is now dynamically rebuilt to always
  match the real display's current size/aspect ratio (scaled by the new
  `render_scale`), instead of being a fixed authored-resolution surface
  scaled onto the display via `pygame.FULLSCREEN | pygame.SCALED`. Consumers
  relying on the old fixed-canvas behavior need `fixed_aspect=True` (added in
  0.3.0) to get an equivalent result.
- **Added** `render_scale` — decouples internal render resolution from the
  real display's, so a project can render at a fraction of the display's
  pixels and let `_present()` upscale.
- **Changed** (breaking) the `windowed_resolution` API was renamed to
  `resolution`, and window mode / resolution became independent settings —
  picking a resolution no longer forces a mode switch.
- **Added** a windowed-resolution picker (`available_resolutions()`,
  `cycle_resolution()`, `set_resolution()`, `clear_resolution_override()`) and
  a borderless-fullscreen window mode (screen-filling, no exclusive mode
  switch — avoids the flash/flicker of a real display-mode change).
- **Added** `SaveStore` — JSON-backed key-value persistence for settings/saves,
  atomic writes, plus `SaveStore.delete()`.
- **Added** a `Slider` UI widget, registered as a panel factory type.
- **Fixed** the window re-centering on every `minimize()`, not just at startup.
- **Fixed** `_scale_def`'s centre-remapping for non-top-left anchors landing
  off-screen.

## [0.1.2] — 2026-07-07

- **Added** a real test suite (one file per module) and CI.
- **Fixed** F11 fullscreen toggle: tracked window-mode state explicitly
  instead of comparing `.size`, which could desync from the actual mode.
- **Fixed** `size: WINDOW` in `make_gui_object` using `parent.size` instead of
  `parent` directly.
- **Fixed** a missing `pytmx` dependency declaration.

## [0.1.1] — first tracked version

Baseline: packaging consolidated into `pyproject.toml` (`setup.py`/
`requirements.txt` dropped). Everything before this point (the initial
`Application`/`Mouse`/`PanelManager`/`AssetManager`/ECS core, ~60 commits) predates
this changelog and was never versioned — see `git log` for that history directly.
