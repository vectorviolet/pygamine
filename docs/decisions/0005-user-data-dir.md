# 0005. Per-user data folder

Status: accepted (owner, 2026-11-17: no migration of old saves, web keeps localStorage). Issue: #44.

## Context

`SaveStore` and `Database` default to `saves/` and `databases/` relative to the current
working directory. An install in Program Files is read-only for normal users, so saving fails.

## Decision

- **Helper:** `user_data_dir(game, *, vendor="VectorViolet") -> Path` in `pygamine.assets.paths`, stdlib only.
  Windows `%APPDATA%\<vendor>\<game>` (fallback `~/AppData/Roaming`), macOS
  `~/Library/Application Support/<vendor>/<game>`, Linux `$XDG_DATA_HOME` or
  `~/.local/share` (a relative `XDG_DATA_HOME` is ignored) plus `<vendor>/<game>`. `game` and `vendor` must be single folder names (`ValueError` otherwise). If the home folder can't be found it logs a warning and uses `./userdata/<game>`. It creates nothing; the stores already
  create their folder on first write.
- **No implicit default:** the engine has no notion of the game's name. The window title
  is localized and mutable, and `Application` has no name setting. Deriving the folder
  from either, or from a process-wide registry, would be hidden global state and hard to
  test. So the stores keep their `directory` parameter and their cwd-relative defaults, and
  games pass `directory=user_data_dir("<game>") / "saves"`. This is not a breaking change
  and keeps tests free to pass `tmp_path`.
- **Web:** on emscripten `user_data_dir` returns `Path(".")`, so `user_data_dir(game) / "saves"` equals the old default `saves` and the `localStorage` key (`pygamine:saves/<name>.json`) is unchanged. Only `SaveStore` persists on the web; `Database` uses pygbag's in-memory file system and is lost on reload.
- **No migration** of saves from the old cwd-relative folders (owner decision).
- **Packaged helper (#53):** `packaged_data_dir(game, sub, *, vendor=...) -> Path | None` returns `user_data_dir(game, vendor=vendor) / sub` when `sys._MEIPASS` is set (the same test as `resource_root`, so assets and saves can't disagree) and `None` otherwise (source runs and the web build keep the stores' cwd-relative defaults, so worktree saves stay isolated and `localStorage` keys don't change). `sub` is validated like `game`, in every mode. Games pass it straight as `directory`.
- **Packaged without a home folder:** `user_data_dir` would give the cwd-relative `userdata/<game>`, which in a packaged build is inside the bundle (`_internal`): read-only under Program Files and wiped by an installer update. `packaged_data_dir` instead logs a warning and uses `<executable folder>/userdata/<game>/<sub>`. Raising was rejected: a game that can't start is worse than one that saves next to itself; if that folder is read-only, the first save fails loudly rather than silently losing data on update.

## Rejected

- A global `set_game_name()` registry: silent shared state, order-dependent.
- Reading the window caption: changes with language and with the game's state.
- Making `directory` required: breaks every caller for no gain over passing it explicitly.
