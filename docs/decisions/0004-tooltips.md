# 0004. Tooltips

Status: accepted (owner, 2026-11-04: 0.4 s hover delay). Issue: #35.

## Context

Buttons should show their name and key after a short hover, with the key drawn as an
input-prompt icon. The engine ships no icon images; the games supply them.

## Decision

- **Manager:** a game creates one `TooltipManager(input_map, font, icons)` and passes it
  to `PanelLoader(..., tooltips=manager)`. It holds the look, the delay (`delay_ms`,
  default 400), the icon cache and the one visible tooltip, so showing a tooltip hides
  the previous one. No process-wide instance.
- **Icons:** `icons` is a mapping or a callable from a `pygame.key.name` string (`"f5"`)
  to an image path, or `None`. A key without an icon is drawn as its bracketed upper-case
  name, `[F5]`. Icons are scaled to the font height.
- **YAML:** `tooltip: {text_key: ..., action: ..., text_params: ...}` on any object.
  `action` is optional (text-only tooltip). The loader validates the mapping, then adds a
  `Tooltip` named `<object>.tooltip` after all other objects of the panel, so it draws on
  top of that panel's UI.
- **Behavior:** hover is worked out every `update()` from the real cursor
  (`pygame.mouse.get_pos()`, or a `Mouse` passed as `mouse=` for logical coordinates), so a
  cursor that leaves the window (no mouse focus, `WINDOWLEAVE`) or a target that moves under
  a still cursor are handled. After the delay it shows below the target (above if there is
  no room), clamped to the loader's window rect, and follows a moving target. It hides on
  leave, on a left/middle/right click on the target (then stays hidden until the mouse
  leaves and returns; the wheel doesn't count), and when the target becomes inactive.
  `PanelManager` calls `on_hidden()` on the old panel's objects when `current_panel`
  changes, so a pending or visible tooltip is dropped.
- **Refresh:** the box is rendered when the tooltip shows and again from
  `InputMap.on_changed` / `Localization.on_language_changed` callbacks (`refresh()`); `draw()`
  only blits.
- **Cleanup:** `Tooltip.on_removed()` (called by `GameObjectDict`) unregisters both
  callbacks and hides it.

## Rejected alternatives

- **A TextObject child per tooltip:** the box needs text and an icon side by side, and a
  TextObject only renders text.
- **A draw layer owned by the game:** tooltips would need a manual draw call. Adding them
  last in the panel needs no extra wiring.
- **Mouse-position placement:** jumps with the cursor; anchoring to the target is steadier.

## Limits

- Setting `PanelManager._panels` entries directly (not via `current_panel`) bypasses the hook.
- Objects the game adds to a panel after loading draw above its tooltips.
