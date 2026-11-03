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
- **Lookup:** `tr(key, **params)` fills `{name}` placeholders with `str.format`.
  A key missing in the current language falls back to `en`.
- **Missing everywhere raises `KeyError`.** The alternative, returning the key,
  hides typos: the label shows `settings.titel` and nobody notices until a player
  does. A raise fails in tests and at panel load, where a developer sees it. The
  key-coverage check keeps shipped language files consistent, so a missing key
  is a developer error, not a runtime condition to degrade gracefully.
- **Panels:** `text_key:` on a text object (`make_text_factory`); a literal `text:`
  works as before. The `TextObject` itself owns the key (`text_key`), so code that
  builds labels directly gets the same behavior.
- **Live switch:** `set_language(code)` re-renders every registered `TextObject`
  (`relocalize()`), then calls the `on_language_changed` callbacks, which games use
  to re-set text they format themselves. The registry is a `WeakSet`, so reloaded
  or dropped panels leak nothing. `TextObject.set_text()` on the default state
  replaces the key with a literal and unregisters the label.
- **Checks for game CI:** `check_key_coverage()` (missing and extra keys against
  `en.yaml`) and `check_glyph_coverage(font)`. `pygame.font.Font.metrics` does
  not return `None` for a missing glyph in pygame-ce 2.5 (it returns the font's
  `.notdef` box metrics), so a character counts as missing when it renders
  pixel-identical to U+FFFF, which no font defines.
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
