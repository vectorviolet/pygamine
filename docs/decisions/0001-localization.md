# 0001. Localization: YAML string tables, live switch, English fallback

Status: accepted (owner, 2026-11-03). Issue: #23.

## Context

Chokepoint and Highrise need English and Turkish first, more later. The language
must change instantly (no restart), English is the default and the fallback, and
there is no system-language detection. UI text mostly lives in panels YAML, so
the solution has to fit that, and it has to be checkable in each game's CI.

## Decision

- **Files:** one YAML file per language in a folder the game passes to
  `localization.load(folder)` (games use `config/lang/<code>.yaml`). The code is the
  file stem. `_meta: {name: "Türkçe"}` holds the display name.
- **Keys:** nested mappings, addressed with dots (`settings.title`). Leaves must be
  strings (a bare `yes` or `10` is rejected: quote it).
- **Lookup:** `tr(key, **params)` always runs `str.format_map(params)` (also with
  no params), so `{name}` is filled and `{{` is a literal brace everywhere.
  A key missing in the current language falls back to `en`.
- **Missing everywhere raises `KeyError`.** The alternative, returning the key,
  hides typos: the label shows `settings.titel` and nobody notices until a player
  does. A raise fails in tests and at panel load, where a developer sees it. The
  key-coverage check keeps shipped language files consistent, so a missing key
  is a developer error, not a runtime condition to degrade gracefully.
- **Panels:** `text_key:` (and optional `text_params:`) on a text object
  (`make_text_factory`); a literal `text:` works as before. Combining `text_key` with
  `text` or a `states.default` is a `ValueError` naming the object. The `TextObject`
  owns the key (`text_key`, `text_params`), so code building labels directly gets the
  same behavior; `set_params(**p)` changes the values, which persist across switches.
- **Live switch:** `set_language(code)` first computes the new text of every
  registered label (nothing changes if one cannot render), then applies it and calls
  every `on_language_changed` callback; if callbacks raise, all still run and the
  errors are re-raised as an `ExceptionGroup`. `load(folder)` validates the new tables
  first (including that live labels' keys still exist), then swaps, re-renders and
  fires the callbacks if the tables or the effective language changed (also on a
  fallback from `tr` to `en`); on a validation error nothing changes.
- **Registry lifetime:** deterministic. `TextObject.on_removed()` unregisters the
  label; `GameObjectDict` calls that optional hook when an object is replaced or the
  dict is cleared, and `PanelManager.remove_panel(name)` clears the panel (use it
  before reloading a panel). A `WeakSet` stays as a safety net for objects dropped
  another way (`GameObjectDict.pop` does not call the hook: the caller owns that
  object). `set_text()` on the default state replaces the key with a literal and
  unregisters.
- **Checks for game CI:** `check_key_coverage()` reports missing keys, extra keys
  and keys whose `{placeholder}` names differ from `en.yaml`;
  `check_glyph_coverage(font_path)` takes the font file. Glyphs are detected with
  `pygame.freetype.Font.get_metrics`, which returns `None` for a glyph the font lacks
  (checked on pygame-ce 2.5.7 with a missing CJK character and U+2800).
  `pygame.font.Font.metrics` is not usable: it returns the `.notdef` box metrics.
  Placeholders are skipped and escaped braces are checked.
- **State:** a process-wide `localization` instance with module-level `tr` and
  `set_language`. `Localization` can be instantiated separately (used in tests).

## Rejected alternatives

- **gettext / `.po`:** extra tooling (extraction, compilation), source-text keys,
  and not YAML-native like the panels and config.
- **Returning the key (or `None`) for a missing key:** see above.
- **Keys flat with dots in the file:** nested YAML is easier to read and group.
- **System-language detection:** out of scope by owner decision.
- **Restart to apply a language:** rejected by owner; live re-render is cheap.

## Consequences

- Only the default-state text of a `TextObject` is key-driven; labels with
  `states:` still take literal state texts.
- Plural forms and number formatting are not handled; use separate keys.
