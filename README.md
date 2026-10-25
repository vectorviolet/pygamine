# pygamine

![tests](https://github.com/vectorviolet/pygamine/actions/workflows/tests.yml/badge.svg)
![Coverage](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/vectorviolet/pygamine/main/.github/badges/coverage.json)

Shared pygame-ce utilities used across personal game projects. Provides an `Application` base, a component-based game-object layer, a YAML-driven panel/UI system, asset loaders, and a handful of helpers (camera, sprite sheet, audio, database).

See [CHANGELOG.md](CHANGELOG.md) for what changed between versions — useful before bumping a consumer project's submodule pointer past a MINOR version, since 0.y.z means breaking changes can land in a MINOR bump.

## Installation

This package is consumed as a **git submodule** by the host project — typically vendored under `src/pygamine/` and added to `PYTHONPATH` (or `sys.path`) by the host's entry point.

```bash
git submodule add https://github.com/vectorviolet/pygamine.git src/pygamine
```

Then in the host's entry script:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src" / "pygamine"))

# Now imports work:
from pygamine import Application
```

The package's public API is re-exported at the top level (`pygamine/__init__.py`), so `from pygamine import Application, GameObject, Camera, ...` covers the classes/functions most consumers need — deep-path imports (`from pygamine.ecs.game_object import GameObject`) still work too, for anything not surfaced there.

It can also be installed via pip directly from GitHub:

```bash
pip install git+https://github.com/vectorviolet/pygamine.git
```

Requires Python 3.12+ and `pygame-ce`.

### A note on `[tool.uv.sources]`

Every current host project's `pyproject.toml` also carries:

```toml
[tool.uv.sources]
pygamine = { path = "src/pygamine", editable = true }
```

This override only takes effect for a dependency `uv` actually resolves —
i.e. it requires `"pygamine"` to also be listed under
`[project.dependencies]`. Every current host project does list it there,
so `uv sync` installs this submodule in editable mode (`uv.lock` shows
`source = { editable = "src/pygamine" }`) rather than relying on
`sys.path` alone — the `sys.path` insertion above is still what makes
`import pygamine` work for anything invoked without going through `uv`
(e.g. a frozen PyInstaller build), so keep both. A host project that
skips `"pygamine"` in `[project.dependencies]` gets an inert
`[tool.uv.sources]` block — the override only ever matters alongside a
matching dependency entry.

## Module map

### Game loop
| Module | Exports | Notes |
|---|---|---|
| `app.application` | `Application` | Top-level run loop (`init/run/handle_event/update/draw`), fullscreen toggle, debug overlay hook, `self.splash`/`show_splash()`, opt-in `fixed_aspect` letterboxing |
| `app.mouse` | `Mouse` | Cursor position + optional custom-cursor `GameObject` |
| `app.camera` | `Camera` | Edge-scroll camera with world↔screen transforms |
| `app.splash_screen` | splash helper | Pre-loop splash render |
| `app.debug` | debug helpers | Wireframes and live state overlay |

### Assets
| Module | Exports |
|---|---|
| `assets.asset_path` | `AssetPath`, `ImagePath`, `FontPath`, `SoundPath`, `PathLike` |
| `assets.asset_manager` | `AssetManager` — loads images/sounds/fonts from a YAML manifest |
| `assets.image` | `load_image`, `scale`, `scale_by`, `nine_slice_scale` |
| `assets.font` | `load_font` (asset-key first, falls back to `SysFont`) |
| `assets.sprite_sheet` | `SpriteSheet` (`from_path`, `strip`, `grid`, `frame`) |
| `assets.database` | `Database`, `DatabaseError` — thin SQLite wrapper, stores `.db` under `databases/` |
| `assets.save_store` | `SaveStore` — JSON-backed key-value persistence for settings/saves under `saves/`, atomic writes |
| `assets.tilemap` | `TiledMap` — Tiled `.tmx` loader (pytmx-backed): tile dims, object-group iteration, offscreen pre-render, camera-aware draw |
| `assets.paths` | `resource_root`, `resource_path` — cwd anchor that works from source and inside a frozen PyInstaller bundle; a host's entry point `chdir()`s into `resource_root()` at startup |

### Panel / UI system
| Module | Exports |
|---|---|
| `panels.panel_manager` | `PanelManager` — named panels with `current_panel` switching |
| `panels.panel_loader` | `PanelLoader` — YAML → objects via registered factories |
| `panels.panel_loader_ext` | `PanelLoaderExt` — adds `object_templates` inheritance |
| `panels.panel_factory` | `make_factory`, `make_text_factory` |

### ECS
| Module | Exports |
|---|---|
| `ecs.game_object` | `GameObject` (active/hierarchy/`invoke[_repeating]`/components) |
| `ecs.game_object_dict` | `GameObjectDict` — named child container with lifecycle dispatch |
| `ecs.game_object_list` | `GameObjectList` — plain-list variant of the same dispatch (`handle_event`/`update`, skipping inactive objects) |
| `ecs.state_object` | `StateObject`, `HoverableStateObject` |
| `ecs.animated_sprite` | `AnimatedSprite`, `AnimatedSpriteFactory` |
| `ecs.game_audio` | `GameAudio` — music + sfx channels with volume control |
| `ecs.sound_manager` | `SoundManager` — static per-channel volume/play helpers on top of `pygame.mixer` |
| `ecs.components.component` | `Component`, `Behaviour`, `MonoBehaviour` |
| `ecs.components.transform` | `Transform` — anchored pos/size relative to parent |
| `ecs.components.sprite_renderer2d` | `SpriteRenderer2D` |
| `ecs.components.rigidbody2d` | `Rigidbody2D` |
| `ecs.components.animator` | `Animator`, `AnimationClip` |

### UI widgets
| Module | Exports |
|---|---|
| `ui_widgets.text_object` | `TextObject` — single- or multi-state label |
| `ui_widgets.menu_controller` | `MenuController` — keyboard-navigable button list |
| `ui_widgets.input_box` | `InputBox` |

### Utilities
| Module | Exports |
|---|---|
| `util.utils` | `MouseInteractive`, `Anchorable`, `resolve_size`, `ANCHORS` |
| `util.math_utils` | Vector and angle helpers |
| `util.spatial_grid` | `SpatialGrid` — uniform spatial hash grid; turns O(N²) neighbour/overlap queries into roughly O(N) |

### Networking

GUI-free and application-agnostic — these classes move framed messages over TCP and report back via callbacks; they never hold a reference upward into application logic. Used by `standoff` (see its own docs for a worked example); most single-player projects don't need this section at all.

| Module | Exports |
|---|---|
| `net.protocol` | `Protocol` — wire framing (4-byte length prefix + body) and pluggable `Codec`s: `JSONCodec` (default, safe for untrusted peers), `TypedJSONCodec`, `PickleCodec` (trusted peers only — see its own warning), `ProtocolError` |
| `net.transport` | `Connection`, `BaseClient`, `BaseServer` — socket plumbing built on `Protocol`, callback-driven |

## Quick examples

### Load a sprite sheet → animated sprite

```python
from pygamine import SpriteSheet, AnimatedSprite

frames = SpriteSheet.from_path("coin_strip4.png").strip(4)
coin = AnimatedSprite(frames=frames, fps=8, pos=(100, 100))
# inside the game loop:
coin.update()
coin.draw(surface)
```

### Asset path helpers

```python
from pygamine import ImagePath, FontPath, SoundPath

ImagePath("player")  # → assets/images/player.png
ImagePath("hero", "sprites")  # → assets/images/sprites/hero.png
FontPath("comic")  # → assets/fonts/comic.ttf
SoundPath("jump")  # → assets/sounds/jump.ogg
```

All `AssetPath` subclasses implement `__fspath__`, so they can be passed directly to `pygame.image.load` / `pygame.font.Font` / `pygame.mixer.Sound`.

### Database

```python
from pygamine import Database

db = Database("savefile")
rows = db.execute_safely(
    "SELECT name, value FROM scores ORDER BY value DESC LIMIT 10",
    fetch=True,
)
```

`execute_safely` handles connect/commit/disconnect in one call; use `connect/execute/commit/disconnect` directly when you need to batch operations. Any failure raises `DatabaseError` (`from pygamine import DatabaseError`) — catch it (or let it propagate) rather than checking a return value.

## Code style

- **Formatting:** Black-compatible, enforced by `ruff format` (line length 88, double quotes,
  otherwise Black's defaults; see `[tool.ruff.format]` in `pyproject.toml`).
- **Lint:** `ruff check`, deliberately narrow (see `[tool.ruff.lint]`).
- **CI:** runs both, plus `mypy`.

Run both locally before committing:

```bash
uv run --group dev ruff format .          # reformat
uv run --group dev ruff check .           # lint
uv run --group dev ruff format --check .  # what CI runs: fails if anything would be reformatted
```

The commit that first applied the formatter is listed in `.git-blame-ignore-revs`. To have
`git blame` skip it and show the real author of each line:

```bash
git config blame.ignoreRevsFile .git-blame-ignore-revs
```

## Adding a new module

1. Create `pygamine/<subpackage>/<module>.py` — pick the subpackage from the
   module map above (`app`, `assets`, `panels`, `ecs`, `ui_widgets`, `net`,
   `util`); add a new subpackage only if the module genuinely doesn't fit
   any existing one.
2. Add the public names to `pygamine/__init__.py`'s `_EXPORTS` dict (and the
   matching `TYPE_CHECKING` import, kept in sync with it) so `from pygamine
   import <Name>` works — this is the form consumers should use; deep-path
   imports (`from pygamine.assets.image import load_image`) still work too,
   for anything not surfaced there.
3. No reinstall required when consumed as a submodule on `sys.path`.