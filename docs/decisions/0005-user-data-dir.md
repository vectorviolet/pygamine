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
- **Packaged helper (#53):** `packaged_data_dir(game, sub, *, vendor=...) -> Path | None` returns `user_data_dir(game, vendor=vendor) / sub` when `sys._MEIPASS` is set (the same test as `resource_root`, so assets and saves can't disagree) and `None` otherwise (source runs and the web build keep the stores' cwd-relative defaults, so worktree saves stay isolated and `localStorage` keys don't change). `sub` is validated like `game`, in every mode. `SaveStore` and `Database` don't accept `directory=None` (their `directory` default is what the games' tests patch to a temp folder), so games pass `directory=` only when the helper returns a path.
- **Packaged without a home folder:** the rule lives in `user_data_dir`'s own fallback, so every caller is safe. In a packaged build it would otherwise give the cwd-relative `userdata/<game>`, inside the bundle (`_internal`): read-only under Program Files and wiped by an installer update. It logs one warning naming the real path and uses `<executable folder>/userdata/<game>` instead (on macOS the folder that contains the `.app`, never inside it); `packaged_data_dir` just adds `sub`. An empty `sys.executable` raises `RuntimeError` (resolving it would land in the cwd). Raising on the no-home case itself was rejected: a game that can't start is worse than one that saves next to itself, and a read-only folder fails loudly on the first save. A relative `APPDATA` is ignored like an unset one.

## Rejected

- A global `set_game_name()` registry: silent shared state, order-dependent.
- Reading the window caption: changes with language and with the game's state.
- Making `directory` required: breaks every caller for no gain over passing it explicitly.
