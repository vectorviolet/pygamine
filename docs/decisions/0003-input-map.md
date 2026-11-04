# 0003. Input map: rebindable keyboard actions

Status: accepted (owner, 2026-11-04). Issue: #34.

## Context

Chokepoint (hotkeys, number-pad alternates) and Highrise (WASD with arrow-key
alternates, Space) want players to rebind keys. The engine provides the logic; the
CONTROLS screens and tooltips are separate cards.

## Decision

- **Actions:** `InputMap.declare(name, default, alternates=())` adds an action with
  one rebindable primary key plus fixed alternates that keep working after a rebind.
  `declare_fixed(name, *keys)` adds an action that is listed but cannot be rebound
  (Esc, F11). Keys only; mouse buttons are not rebindable.
- **Invariant:** a key belongs to at most one action, and a primary key is never
  also a fixed key or an alternate. `declare` enforces it for defaults.
- **Queries:** `is_action(event, name)` is true for a KEYDOWN of any bound key.
  `key_for` gives the key to display, `keys_for` all keys (for `get_pressed()`).
- **Rebinding:** `rebind(name, key)` returns `None` when applied. If another
  action's primary uses the key it changes nothing and returns that action's name,
  so the game can ask and call `swap(a, b)`. Fixed keys, alternates and fixed
  actions raise `KeyBindingError` (a `ValueError`) with the reason in the message.
  Alternates stay unbindable, so `swap` can never create a clash.
- **Saving:** `to_dict()` is `{action: pygame.key.name}` for rebindable actions
  only; the game stores it in its own settings. `from_dict()` validates the whole
  dict first and then applies it, so an invalid save changes nothing. Missing
  actions take defaults and unknown names are ignored, so a save survives an
  action being added or removed. Unknown key names, duplicates and reserved keys
  raise `KeyBindingError`; the game decides whether to fall back to defaults.
- **Callbacks:** `on_changed(cb)` / `remove_changed(cb)` (like localization), `cb()`
  runs after a real change; all run even if one raises, then an `ExceptionGroup`.
- **State:** a plain class the game instantiates; no process-wide instance.

## Rejected alternatives

- **Key codes in saves:** unreadable and not stable across SDL versions.
- **Auto-swap on conflict:** the game should ask the player first.
- **Rebinding onto alternates:** would need per-action alternate removal or allow
  one key to trigger two actions.

## Consequences

- Only KEYDOWN is matched by `is_action`; held-key checks use `keys_for`.
- Games opt in; nothing changes for existing code.
