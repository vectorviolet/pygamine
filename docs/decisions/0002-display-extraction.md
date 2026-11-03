# 0002. Display: extract the display stack from Application

Status: accepted (owner, 2026-11-03). Issue: #4 (audit item 20).

## Context

`Application` had 31 public methods. Besides the game loop, input and events it
held the whole display stack: window modes, resolution override, render scale,
fixed-aspect fit, presenting the logical canvas and mouse scaling. Chokepoint and
highrise subclass `Application` and use many of those members, so the change must
not break them.

## Decision

- A new `pygamine/app/display.py` `Display` class holds the display stack.
  `Application` creates one (`app.display`) and owns it: composition, not mixins,
  so a subclass cannot collide with display internals.
- `Application` keeps every public method as a thin delegate and every public
  attribute (`display_surface`, `window`, `render_scale`, `fixed_aspect`, `mouse`,
  `windowed_*`, `fullscreen_*`) as a forwarding descriptor, readable and writable.
  `_window_mode`, `_is_fullscreen` and `_present` stay as aliases because games
  read them. Not breaking, so no version bump is needed beyond a normal release.
- `Display` does not know `Application`. It reports canvas changes through a
  callback; `Application._on_canvas_resized` sets `size` and then calls the
  overridable `on_canvas_resized` hook, in the same order as before.
- Behavior subclasses could change stays on the subclass: `Application` passes its
  `WINDOW_MODES` and its (call-time looked-up) `set_fullscreen`,
  `set_borderless_fullscreen` and `set_windowed` to `Display`, so overriding them
  still affects `set_window_mode`, `cycle_window_mode` and F11.
- `COMMON_RESOLUTIONS`, `WINDOW_MARGIN`, `WINDOW_MODES`, `WindowMode` and
  `fit_rect` moved to `display.py` and are re-exported from `application.py`.

## Rejected

- **Mixins:** shared `self` state and name collisions; composition is safer for
  subclasses (the audit's recommendation).
- **Dropping the delegates and updating the games:** breaking, and the owner asked
  for a non-breaking change.
- **Keeping the private display helpers as delegates too:** nothing outside the
  tests used them, so they live only on `Display`.

## Known limits

Other display methods that call each other internally (`set_resolution` calling
`set_windowed`, `reset_window_settings` calling `set_fullscreen`) call
`Display`'s own methods, so an `Application` subclass overriding those would not
see the nested calls. No game does that.
