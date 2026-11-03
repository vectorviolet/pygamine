"""The display stack behind Application: window modes, resolution override,
render scale, fixed-aspect fit, presenting the logical canvas and mouse scaling.

Application owns one Display and forwards its public display API to it, so
games keep calling the same Application methods. Display knows nothing about
Application: it reports canvas size changes through a callback instead.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from typing import Literal

import pygame

from pygamine.app.mouse import Mouse

# Common desktop resolutions offered by a windowed-mode resolution picker
# (available_resolutions() filters this down to what fits the
# screen). 16:9/16:10 only -- covers the vast majority of desktop monitors.
COMMON_RESOLUTIONS: tuple[tuple[int, int], ...] = (
    (1024, 576),
    (1152, 648),
    (1280, 720),
    (1280, 800),
    (1366, 768),
    (1440, 900),
    (1536, 864),
    (1600, 900),
    (1680, 1050),
    (1920, 1080),
    (1920, 1200),
    (2560, 1440),
    (3200, 1800),
    (3840, 2160),
)

WindowMode = Literal["fullscreen", "borderless", "windowed"]

# Fraction of the screen a windowed-mode window may occupy, leaving headroom
# for window chrome (title bar/borders).
WINDOW_MARGIN = 0.8

# Cycle order for F11 / cycle_window_mode(): exclusive fullscreen (real
# display mode switch) -> borderless fullscreen (screen-filling window,
# no mode switch -- avoids the flash/flicker of a mode switch and plays
# nicer with Windows DPI/GPU scaling) -> bordered windowed.
WINDOW_MODES: tuple[WindowMode, ...] = ("fullscreen", "borderless", "windowed")


def fit_rect(src_size: tuple[int, int], dst_size: tuple[int, int]) -> pygame.Rect:
    """Largest rect with src_size's aspect ratio that fits inside dst_size,
    centered in it. Pure geometry, so it needs no display."""
    assert src_size[0] > 0 and src_size[1] > 0, f"fit_rect: bad source size {src_size}"
    assert dst_size[0] > 0 and dst_size[1] > 0, f"fit_rect: bad target size {dst_size}"
    dst_w, dst_h = dst_size
    src_w, src_h = src_size
    scale = min(dst_w / src_w, dst_h / src_h)
    w, h = round(src_w * scale), round(src_h * scale)
    return pygame.Rect((dst_w - w) // 2, (dst_h - h) // 2, w, h)


def center_window() -> None:
    """Ask SDL to center the next window it creates (it reads this env var on
    window creation)."""
    os.environ["SDL_VIDEO_CENTERED"] = "1"


def query_screen_size() -> tuple[int, int]:
    """The desktop size. Only valid after pygame.init() and before the first
    set_mode(): display.Info() reports the current mode once one is set."""
    info = pygame.display.Info()
    return info.current_w, info.current_h


class Display:
    def __init__(
        self,
        size: tuple[int, int],
        mouse: Mouse,
        on_canvas_resized: Callable[[tuple[int, int]], None],
        render_scale: float = 1.0,
        fixed_aspect: bool = False,
        window_modes: tuple[WindowMode, ...] = WINDOW_MODES,
        mode_setters: Mapping[WindowMode, Callable[[], None]] | None = None,
        resolution_setter: Callable[[tuple[int, int]], None] | None = None,
    ) -> None:
        """Query the screen size; creates no window yet. The owner must call
        set_fullscreen() (or another mode setter) once it is ready for
        `on_canvas_resized` to fire, because that first call creates the real
        display surface and the logical canvas.

        `size` is the preferred default windowed size before the player ever
        picks one (see windowed_physical_size()), and the fixed design
        resolution under fixed_aspect. Must run after pygame.init() and
        before the first set_mode().

        `mode_setters` maps each mode to the callable set_window_mode() runs
        for it; the owner passes its own set_* methods so that subclass
        overrides of them still take effect. Defaults to this Display's own.
        `resolution_setter` is the same for set_resolution(), which
        cycle_resolution() and restore_window_settings() call.
        """
        self._on_canvas_resized = on_canvas_resized
        # Which modes cycle_window_mode()/set_window_mode() accept, in order.
        self.window_modes = window_modes
        self._resolution_setter: Callable[[tuple[int, int]], None] = (
            resolution_setter if resolution_setter is not None else self.set_resolution
        )
        self._mode_setters: Mapping[WindowMode, Callable[[], None]] = (
            mode_setters
            if mode_setters is not None
            else {
                "fullscreen": self.set_fullscreen,
                "borderless": self.set_borderless_fullscreen,
                "windowed": self.set_windowed,
            }
        )
        self._window_mode: WindowMode = "windowed"  # overwritten by set_fullscreen()
        self._resolution_override: tuple[int, int] | None = None
        self.mouse = mouse
        # The real OS window/screen surface. set_fullscreen() creates it,
        # and set_windowed()/set_borderless_fullscreen() replace it on a mode switch.
        self.display_surface: pygame.Surface
        # The logical render target the game draws on. This empty placeholder
        # never matches a real render size, so the first mode setter always
        # replaces it with the real canvas (firing the first
        # on_canvas_resized()); _rebuild_window_surface() replaces it again
        # on every later resize.
        self.window: pygame.Surface = pygame.Surface((0, 0))
        # 1.0 (default): self.window always matches the real display exactly,
        # so present() is a plain 1:1 blit -- no scaling, ever. Lower this
        # (see set_render_scale()) to render at a fraction of the real
        # display's pixels and let present() upscale -- a cheap way to trade
        # sharpness for fewer per-frame software blits on weak/mobile
        # hardware, independent of window mode/resolution. Orthogonal to
        # fixed_aspect: this controls render *density*, not aspect ratio.
        self.render_scale = render_scale
        # False (default): self.window's aspect ratio always matches
        # display_surface's (see _scaled_render_size()), so present() never
        # needs to letterbox/pillarbox -- a mismatched-aspect monitor just
        # shows more or less of the world, never distortion.
        #
        # True: self.window is locked to `size` (cached in self.windowed_size)
        # as a genuinely fixed design resolution, scaled only by render_scale
        # -- for a hand-authored pixel layout that must never reveal extra
        # space on a wider/taller monitor. present()/_sync_mouse_scale() then
        # compute a centered fit_rect() and blit into that instead of the
        # full display, filling the leftover bars with black; Mouse.offset
        # accounts for those bars so clicks still map to the right logical
        # coordinate. This is the direct opposite tradeoff from the default:
        # a monitor whose aspect doesn't match `size` gets letterboxed bars
        # instead of extra revealed world space.
        self.fixed_aspect = fixed_aspect
        self.windowed_size = self.windowed_width, self.windowed_height = size
        self.fullscreen_size = self.fullscreen_width, self.fullscreen_height = (
            query_screen_size()
        )

    # ── window modes ────────────────────────────────────────────────────

    def set_windowed(self) -> None:
        # A bordered window sized to exactly fill the screen has nowhere to
        # put its title bar/borders -- they get pushed off-screen, and it
        # looks identical to FULLSCREEN. windowed_physical_size() shrinks
        # the real OS window enough to leave room for them.
        #
        # center_window() only sets an env var SDL reads on window creation;
        # the owner sets it once at startup, but re-set it right before every
        # set_mode() here too -- position is only meaningful in windowed mode
        # (set_fullscreen and set_borderless_fullscreen always fill the screen
        # at (0,0)), and this is the one call site that can run many times in
        # a session (window mode/resolution pickers, F11), not just at startup.
        center_window()
        self._apply_display(
            pygame.display.set_mode(self.windowed_physical_size()), "windowed"
        )

    def set_fullscreen(self) -> None:
        self._apply_display(
            pygame.display.set_mode(self.fullscreen_size, pygame.FULLSCREEN),
            "fullscreen",
        )

    def set_borderless_fullscreen(self) -> None:
        # A window sized to exactly the screen with no border/title bar --
        # fills the screen like FULLSCREEN but without an exclusive display
        # mode switch, so no flash/flicker on alt-tab and no interaction
        # with GPU/monitor scaling behavior tied to exclusive mode switches.
        self._apply_display(
            pygame.display.set_mode(self.fullscreen_size, pygame.NOFRAME),
            "borderless",
        )

    def _apply_display(self, surface: pygame.Surface, mode: WindowMode) -> None:
        """Shared tail of the three mode setters: adopt the new display
        surface and record the mode, then rebuild the render surface and mouse
        scale. The mode is recorded first so window_mode is already current
        inside the canvas-resized callback."""
        self.display_surface = surface
        self._window_mode = mode
        self._rebuild_window_surface()
        self._sync_mouse_scale()

    @property
    def window_mode(self) -> WindowMode:
        """Current window mode, one of WINDOW_MODES (read-only)."""
        return self._window_mode

    @property
    def is_fullscreen(self) -> bool:
        """True only for exclusive FULLSCREEN (borderless counts as not)."""
        return self._window_mode == "fullscreen"

    def set_window_mode(self, mode: WindowMode) -> None:
        """Apply one of WINDOW_MODES; raises ValueError for anything else."""
        if mode not in self.window_modes:
            raise ValueError(
                f"Unknown window mode {mode!r}; expected one of {self.window_modes}"
            )
        self._mode_setters[mode]()

    def cycle_window_mode(self, step: int = 1) -> None:
        """Advance through WINDOW_MODES by `step` (wraps around) and apply
        the result. F11 calls this with the default step to cycle
        fullscreen -> borderless -> windowed -> fullscreen ..."""
        index = self.window_modes.index(self._window_mode)
        new_mode = self.window_modes[(index + step) % len(self.window_modes)]
        self.set_window_mode(new_mode)

    # ── render target ───────────────────────────────────────────────────

    def _rebuild_window_surface(self) -> None:
        """Keep the logical render target (self.window) matching the real OS
        window's current size, scaled by render_scale -- at the default 1.0
        this makes present() a plain 1:1 blit with no scaling, stretching,
        or letterboxing; below 1.0, present() upscales a smaller render
        target instead (fewer pixels per frame, for weak/mobile hardware).
        A no-op if the size didn't actually change (e.g. toggling between
        fullscreen and borderless, which share fullscreen_size) -- avoids a
        spurious canvas-resized callback and a one-frame black flash from a
        fresh Surface.
        """
        new_size = self._scaled_render_size()
        if self.window.get_size() == new_size:
            return
        self.window = pygame.Surface(new_size).convert()
        self._on_canvas_resized(new_size)

    def _scaled_render_size(self) -> tuple[int, int]:
        if self.fixed_aspect:
            # Locked to the authored design resolution (self.windowed_size,
            # the original constructor `size`) regardless of the display's
            # own shape -- present() letterboxes/pillarboxes the result.
            base_size = self.windowed_size
        else:
            base_size = self.display_surface.get_size()
        if self.render_scale == 1.0:
            return base_size
        return (
            round(base_size[0] * self.render_scale),
            round(base_size[1] * self.render_scale),
        )

    def set_render_scale(self, scale: float) -> None:
        """Change the internal render resolution relative to the real
        display (e.g. 0.667 renders at ~720p-equivalent on a 1080p display,
        upscaled in present()). 1.0 renders at the display's exact size
        with no scaling. Independent of window mode/resolution -- applies
        under fullscreen, borderless, or windowed alike."""
        if scale == self.render_scale:
            return
        self.render_scale = scale
        self._rebuild_window_surface()
        self._sync_mouse_scale()

    # ── resolution ──────────────────────────────────────────────────────

    def windowed_physical_size(self) -> tuple[int, int]:
        if self._resolution_override is not None:
            return self._resolution_override
        # Leave headroom for window chrome (title bar/borders) and never
        # upscale past the preferred windowed size -- cap the shrink factor at 1.0.
        fit = min(
            1.0,
            WINDOW_MARGIN * self.fullscreen_width / self.windowed_width,
            WINDOW_MARGIN * self.fullscreen_height / self.windowed_height,
        )
        return round(self.windowed_width * fit), round(self.windowed_height * fit)

    def available_resolutions(self) -> list[tuple[int, int]]:
        """Common resolutions that fit this screen with room to spare for
        window chrome (same margin windowed_physical_size() uses when there's
        no explicit choice), plus whatever's currently selected so there's
        always at least one entry and the current pick is never dropped."""
        max_width = WINDOW_MARGIN * self.fullscreen_width
        max_height = WINDOW_MARGIN * self.fullscreen_height
        fitting = {
            r for r in COMMON_RESOLUTIONS if r[0] <= max_width and r[1] <= max_height
        }
        fitting.add(self.resolution)
        return sorted(fitting)

    def auto_windowed_physical_size(self) -> tuple[int, int]:
        override, self._resolution_override = self._resolution_override, None
        try:
            return self.windowed_physical_size()
        finally:
            self._resolution_override = override

    @property
    def resolution(self) -> tuple[int, int]:
        """The physical size set_windowed() will use right now -- either an
        explicit pick from set_resolution()/cycle_resolution(),
        or the automatic best-fit size. Useful for a settings label to show
        the current selection even before the player has ever gone windowed."""
        return self._resolution_override or self.auto_windowed_physical_size()

    def set_resolution(self, size: tuple[int, int]) -> None:
        """Explicitly choose the physical window size set_windowed() uses,
        overriding the automatic best-fit calculation. Window mode and
        resolution are independent settings -- picking a resolution never
        forces a mode switch. If already windowed, set_windowed() re-runs so
        the new size is immediately visible; if fullscreen/borderless
        (both always the native monitor resolution, unaffected by this),
        the pick is just remembered for whenever windowed mode is next
        entered, via F11 or the window-mode setting."""
        self._resolution_override = size
        if self._window_mode == "windowed":
            self._mode_setters["windowed"]()

    def clear_resolution_override(self) -> None:
        """Drop any explicit pick, reverting resolution to the
        automatic best-fit calculation. Doesn't switch mode or resize the
        window itself -- pair with set_windowed() (or leave it for the next
        set_windowed()/F11 press) if the change should be visible immediately."""
        self._resolution_override = None

    def cycle_resolution(self, step: int = 1) -> tuple[int, int]:
        """Advance through available_resolutions() by `step`
        (wraps around) and apply the result. Returns the newly selected size
        -- the return value is what a resolution-cycler label should show."""
        options = self.available_resolutions()
        current = self.resolution
        index = options.index(current) if current in options else 0
        new_size = options[(index + step) % len(options)]
        self._resolution_setter(new_size)
        return new_size

    # ── window settings persistence ─────────────────────────────────────
    #
    # The window-mode/resolution slice of a SaveStore-style settings dict --
    # deliberately just this, with no opinion on audio/gameplay settings a
    # project also wants to persist alongside it. Extracted after chokepoint
    # and standoff both grew the exact same three methods independently.

    def restore_window_settings(self, saved_settings: dict) -> None:
        """Applies a saved window mode/size on top of the default
        (always exclusive fullscreen). set_resolution() only resizes
        immediately if already windowed (mode and resolution are
        independent settings) -- called here while still in the just-
        constructed default fullscreen, it just remembers the size for
        whichever mode is applied next, below. Harmless on platforms with
        no windowing concept (e.g. Android): it just re-affirms fullscreen."""
        if "window_size" in saved_settings:
            self._resolution_setter(tuple(saved_settings["window_size"]))
        mode = saved_settings.get("window_mode", "fullscreen")
        # An unknown saved mode falls back to the first WINDOW_MODES entry
        # (exclusive fullscreen) rather than raising.
        try:
            self.set_window_mode(mode)
        except ValueError:
            self.set_window_mode(self.window_modes[0])

    def window_settings(self) -> dict:
        """The window-mode/resolution portion of a settings dict, for
        SaveStore-style persistence -- pair with restore_window_settings()
        to round-trip. Merge this into a project's own larger settings
        dict (audio, gameplay, ...) before saving, e.g.
        `store.save({**app.window_settings(), "sfx_volume": ...})`."""
        return {"window_mode": self._window_mode, "window_size": list(self.resolution)}

    def reset_window_settings(self) -> None:
        """Restores window mode/resolution to the defaults (exclusive
        fullscreen, no resolution override) -- pair with a project's own
        audio/gameplay reset logic for a full settings reset."""
        self.clear_resolution_override()
        self._mode_setters["fullscreen"]()

    # ── mouse and present ───────────────────────────────────────────────

    def _sync_mouse_scale(self) -> None:
        if self.fixed_aspect:
            rect = fit_rect(self.window.get_size(), self.display_surface.get_size())
            self.mouse.scale = (
                self.window.get_width() / rect.width,
                self.window.get_height() / rect.height,
            )
            self.mouse.offset = (rect.x, rect.y)
            return
        physical_width, physical_height = self.display_surface.get_size()
        self.mouse.scale = (
            self.window.get_width() / physical_width,
            self.window.get_height() / physical_height,
        )

    def present(self) -> None:
        """Blit the logical canvas onto the real display and flip."""
        if self.fixed_aspect:
            self._present_letterboxed()
        else:
            self._present_scaled()
        pygame.display.update()

    def _present_letterboxed(self) -> None:
        dst_size = self.display_surface.get_size()
        # self.window is locked to the design resolution (see
        # _scaled_render_size()), so its aspect ratio generally does
        # NOT match dst_size -- fill the whole display with black first,
        # then scale into a centered, aspect-preserving sub-rect rather
        # than stretching across the full (differently-shaped) display.
        rect = fit_rect(self.window.get_size(), dst_size)
        if rect.size == dst_size:
            pygame.transform.scale(self.window, dst_size, self.display_surface)
        else:
            self.display_surface.fill((0, 0, 0))
            pygame.transform.scale(
                self.window, rect.size, self.display_surface.subsurface(rect)
            )

    def _present_scaled(self) -> None:
        dst_size = self.display_surface.get_size()
        # At the default render_scale (1.0), self.window always matches
        # display_surface's size exactly (kept in sync by
        # _rebuild_window_surface() on every mode/resolution/render_scale
        # change), so this is a plain 1:1 blit -- no stretching, no
        # letterboxing. Only a render_scale < 1.0 engages the upscale.
        if self.window.get_size() == dst_size:
            self.display_surface.blit(self.window, (0, 0))
        else:
            pygame.transform.scale(self.window, dst_size, self.display_surface)
