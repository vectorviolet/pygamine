from __future__ import annotations

import sys
import os
import pygame
from pygame import mixer
from pygamine.app.mouse import Mouse
from pygamine.app.splash_screen import SplashScreen

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


class Application:
    # Cycle order for F11 / cycle_window_mode(): exclusive fullscreen (real
    # display mode switch) -> borderless fullscreen (screen-filling window,
    # no mode switch -- avoids the flash/flicker of a mode switch and plays
    # nicer with Windows DPI/GPU scaling) -> bordered windowed.
    WINDOW_MODES: tuple[str, ...] = ("fullscreen", "borderless", "windowed")

    def __init__(
        self,
        size: tuple[int, int],
        title: str,
        fps: int,
        mouse=None,
        render_scale: float = 1.0,
        fixed_aspect: bool = False,
    ) -> None:
        self._is_running = False
        self._fps = fps
        self._is_in_debug_mode = False
        self._window_mode = "windowed"  # overwritten below by full_screen()
        self._resolution_override: tuple[int, int] | None = None
        # By default, (fixed_aspect=False) this is no longer a "design/
        # authoring resolution" -- just the preferred default *windowed*
        # size before the player ever picks one explicitly (see
        # _windowed_physical_size()); the logical canvas (self.window) is
        # dynamic, rebuilt to match whatever size is actually chosen.
        # fixed_aspect=True changes what this means -- see below.
        self.size: tuple[int, int] = size
        # The real OS window/screen surface. full_screen() below creates it,
        # and minimize()/borderless_full_screen() replace it on a mode switch.
        self.display_surface: pygame.Surface
        self.window: pygame.Surface | None = None
        # 1.0 (default): self.window always matches the real display exactly,
        # so _present() is a plain 1:1 blit -- no scaling, ever. Lower this
        # (see set_render_scale()) to render at a fraction of the real
        # display's pixels and let _present() upscale -- a cheap way to trade
        # sharpness for fewer per-frame software blits on weak/mobile
        # hardware, independent of window mode/resolution. Orthogonal to
        # fixed_aspect: this controls render *density*, not aspect ratio.
        self.render_scale = render_scale
        # False (default): self.window's aspect ratio always matches
        # display_surface's (see _scaled_render_size()), so _present() never
        # needs to letterbox/pillarbox -- a mismatched-aspect monitor just
        # shows more or less of the world, never distortion.
        #
        # True: self.window is locked to `size` (the constructor argument,
        # cached in self.minimized_size) as a genuinely fixed design
        # resolution, scaled only by render_scale -- for a hand-authored
        # pixel layout that must never reveal extra space on a wider/
        # taller monitor. _present()/_sync_mouse_scale() then compute a
        # centered _fit_rect() and blit into that instead of the full
        # display, filling the leftover bars with black; Mouse.offset
        # accounts for those bars so clicks still map to the right logical
        # coordinate. This is the direct opposite tradeoff from the default:
        # a monitor whose aspect doesn't match `size` gets letterboxed bars
        # instead of extra revealed world space.
        self.fixed_aspect = fixed_aspect
        self.mouse = mouse if mouse is not None else Mouse()
        # Set this (typically in a subclass's own __init__, once a display
        # surface exists for SplashScreen's own image loading) to have
        # run() show it automatically before the main loop starts. None
        # (the default) skips straight to the loop -- see show_splash().
        self.splash: SplashScreen | None = None

        self.init_pygame()
        # Pressed state of every key, refreshed each frame by _listen_inputs();
        # read here once so it exists before the first frame (e.g. during the
        # splash).
        self.keys = pygame.key.get_pressed()
        self.set_title(title)
        # The constructor's `size`: the default windowed size, and the fixed
        # design resolution under fixed_aspect (see _scaled_render_size()).
        self.minimized_size = self.minimized_width, self.minimized_height = size
        # Must run after pygame.init() and before the first set_mode() below:
        # display.Info() only reports the desktop size until a mode is set.
        self.full_screen_size = self.full_screen_width, self.full_screen_height = (
            self._query_screen_size()
        )
        self.full_screen()  # sets display_surface and rebuilds self.window to match it (scaled by render_scale)
        self.center_window()
        self.clock = pygame.time.Clock()

    @staticmethod
    def init_pygame() -> None:
        Application._set_windows_dpi_aware()
        pygame.init()
        mixer.init()

    @staticmethod
    def _set_windows_dpi_aware() -> None:
        # Without this, Windows treats the process as DPI-unaware and reports
        # a scaled-down virtual desktop size (e.g. 1536x864 on a 1920x1080
        # screen at 125% scaling). Exclusive FULLSCREEN still renders at the
        # real resolution, but windowed mode gets bitmap-stretched by the
        # OS to match -- the window ends up larger than the physical screen
        # and only its (stretched, zoomed-looking) center is visible.
        if sys.platform != "win32":
            return
        import ctypes

        try:
            ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
            return
        except (AttributeError, OSError):
            pass
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
            return
        except (AttributeError, OSError):
            pass
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass

    @staticmethod
    def center_window() -> None:
        os.environ["SDL_VIDEO_CENTERED"] = "1"

    @staticmethod
    def _query_screen_size() -> tuple[int, int]:
        info = pygame.display.Info()
        return info.current_w, info.current_h

    @staticmethod
    def get_title() -> str:
        return pygame.display.get_caption()[0]

    @staticmethod
    def set_title(title: str) -> None:
        pygame.display.set_caption(title)

    def minimize(self) -> None:
        # A bordered window sized to exactly fill the screen has nowhere to
        # put its title bar/borders -- they get pushed off-screen, and it
        # looks identical to FULLSCREEN. _windowed_physical_size() shrinks
        # the real OS window enough to leave room for them.
        #
        # center_window() only sets an env var SDL reads on window creation;
        # __init__ sets it once, but re-set it right before every set_mode()
        # here too -- position is only meaningful in windowed mode (full_screen
        # and borderless_full_screen always fill the screen at (0,0)), and
        # this is the one call site that can run many times in a session
        # (window mode/resolution pickers, F11), not just at startup.
        self.center_window()
        self.display_surface = pygame.display.set_mode(self._windowed_physical_size())
        self._rebuild_window_surface()
        self._sync_mouse_scale()
        self._window_mode = "windowed"

    def full_screen(self) -> None:
        self.display_surface = pygame.display.set_mode(
            self.full_screen_size, pygame.FULLSCREEN
        )
        self._rebuild_window_surface()
        self._sync_mouse_scale()
        self._window_mode = "fullscreen"

    def borderless_full_screen(self) -> None:
        # A window sized to exactly the screen with no border/title bar --
        # fills the screen like FULLSCREEN but without an exclusive display
        # mode switch, so no flash/flicker on alt-tab and no interaction
        # with GPU/monitor scaling behavior tied to exclusive mode switches.
        self.display_surface = pygame.display.set_mode(
            self.full_screen_size, pygame.NOFRAME
        )
        self._rebuild_window_surface()
        self._sync_mouse_scale()
        self._window_mode = "borderless"

    def _rebuild_window_surface(self) -> None:
        """Keep the logical render target (self.window) matching the real OS
        window's current size, scaled by render_scale -- at the default 1.0
        this makes _present() a plain 1:1 blit with no scaling, stretching,
        or letterboxing; below 1.0, _present() upscales a smaller render
        target instead (fewer pixels per frame, for weak/mobile hardware).
        A no-op if the size didn't actually change (e.g. toggling between
        fullscreen and borderless, which share full_screen_size) -- avoids a
        spurious on_canvas_resized() and a one-frame black flash from a
        fresh Surface.
        """
        new_size = self._scaled_render_size()
        if self.window is not None and self.window.get_size() == new_size:
            return
        self.window = pygame.Surface(new_size).convert()
        self.set_size(new_size)
        self.on_canvas_resized(new_size)

    def _scaled_render_size(self) -> tuple[int, int]:
        if self.fixed_aspect:
            # Locked to the authored design resolution (self.minimized_size,
            # the original constructor `size`) regardless of the display's
            # own shape -- _present() letterboxes/pillarboxes the result.
            base_size = self.minimized_size
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
        upscaled in _present()). 1.0 renders at the display's exact size
        with no scaling. Independent of window mode/resolution -- applies
        under fullscreen, borderless, or windowed alike."""
        if scale == self.render_scale:
            return
        self.render_scale = scale
        self._rebuild_window_surface()
        self._sync_mouse_scale()

    def on_canvas_resized(self, new_size: tuple[int, int]) -> None:
        """Override in a subclass to react to the logical canvas changing
        size (window mode toggled via F11, a new windowed resolution
        picked, render_scale changed, ...) -- e.g. resize a camera viewport
        or re-anchor UI chrome to the new edges. No-op by default."""
        pass

    def cycle_window_mode(self, step: int = 1) -> None:
        """Advance through WINDOW_MODES by `step` (wraps around) and apply
        the result. F11 calls this with the default step to cycle
        fullscreen -> borderless -> windowed -> fullscreen ..."""
        methods = {
            "fullscreen": self.full_screen,
            "borderless": self.borderless_full_screen,
            "windowed": self.minimize,
        }
        index = self.WINDOW_MODES.index(self._window_mode)
        new_mode = self.WINDOW_MODES[(index + step) % len(self.WINDOW_MODES)]
        methods[new_mode]()

    @property
    def _is_fullscreen(self) -> bool:
        """True only for exclusive FULLSCREEN -- kept as a read-only alias
        of `_window_mode` for existing callers that only care about the
        fullscreen/not-fullscreen distinction (e.g. resolution
        picking, which treats borderless the same as windowed)."""
        return self._window_mode == "fullscreen"

    def _windowed_physical_size(self) -> tuple[int, int]:
        if self._resolution_override is not None:
            return self._resolution_override
        # Leave headroom for window chrome (title bar/borders) and never
        # upscale past the preferred windowed size -- cap the shrink factor at 1.0.
        margin = 0.8
        fit = min(
            1.0,
            margin * self.full_screen_width / self.minimized_width,
            margin * self.full_screen_height / self.minimized_height,
        )
        return round(self.minimized_width * fit), round(self.minimized_height * fit)

    def available_resolutions(self) -> list[tuple[int, int]]:
        """Common resolutions that fit this screen with room to spare for
        window chrome (same margin _windowed_physical_size() uses when there's
        no explicit choice), plus whatever's currently selected so there's
        always at least one entry and the current pick is never dropped."""
        margin = 0.8
        max_width = margin * self.full_screen_width
        max_height = margin * self.full_screen_height
        fitting = {
            r for r in COMMON_RESOLUTIONS if r[0] <= max_width and r[1] <= max_height
        }
        fitting.add(self.resolution)
        return sorted(fitting)

    def _auto_windowed_physical_size(self) -> tuple[int, int]:
        override, self._resolution_override = self._resolution_override, None
        try:
            return self._windowed_physical_size()
        finally:
            self._resolution_override = override

    @property
    def resolution(self) -> tuple[int, int]:
        """The physical size minimize() will use right now -- either an
        explicit pick from set_resolution()/cycle_resolution(),
        or the automatic best-fit size. Useful for a settings label to show
        the current selection even before the player has ever gone windowed."""
        return self._resolution_override or self._auto_windowed_physical_size()

    def set_resolution(self, size: tuple[int, int]) -> None:
        """Explicitly choose the physical window size minimize() uses,
        overriding the automatic best-fit calculation. Window mode and
        resolution are independent settings -- picking a resolution never
        forces a mode switch. If already windowed, minimize() re-runs so
        the new size is immediately visible; if fullscreen/borderless
        (both always the native monitor resolution, unaffected by this),
        the pick is just remembered for whenever windowed mode is next
        entered, via F11 or the window-mode setting."""
        self._resolution_override = size
        if self._window_mode == "windowed":
            self.minimize()

    def clear_resolution_override(self) -> None:
        """Drop any explicit pick, reverting resolution to the
        automatic best-fit calculation. Doesn't switch mode or resize the
        window itself -- pair with minimize() (or leave it for the next
        minimize()/F11 press) if the change should be visible immediately."""
        self._resolution_override = None

    def cycle_resolution(self, step: int = 1) -> tuple[int, int]:
        """Advance through available_resolutions() by `step`
        (wraps around) and apply the result. Returns the newly selected size
        -- the return value is what a resolution-cycler label should show."""
        options = self.available_resolutions()
        current = self.resolution
        index = options.index(current) if current in options else 0
        new_size = options[(index + step) % len(options)]
        self.set_resolution(new_size)
        return new_size

    # ── window settings persistence ─────────────────────────────────────
    #
    # The window-mode/resolution slice of a SaveStore-style settings dict --
    # deliberately just this, with no opinion on audio/gameplay settings a
    # project also wants to persist alongside it. Extracted after chokepoint
    # and standoff both grew the exact same three methods independently.

    def restore_window_settings(self, saved_settings: dict) -> None:
        """Applies a saved window mode/size on top of __init__'s default
        (always exclusive fullscreen). set_resolution() only resizes
        immediately if already windowed (mode and resolution are
        independent settings) -- called here while still in the just-
        constructed default fullscreen, it just remembers the size for
        whichever mode is applied next, below. Harmless on platforms with
        no windowing concept (e.g. Android): it just re-affirms fullscreen."""
        if "window_size" in saved_settings:
            self.set_resolution(tuple(saved_settings["window_size"]))
        mode = saved_settings.get("window_mode", "fullscreen")
        mode_methods = {
            "fullscreen": self.full_screen,
            "borderless": self.borderless_full_screen,
            "windowed": self.minimize,
        }
        mode_methods.get(mode, self.full_screen)()

    def window_settings(self) -> dict:
        """The window-mode/resolution portion of a settings dict, for
        SaveStore-style persistence -- pair with restore_window_settings()
        to round-trip. Merge this into a project's own larger settings
        dict (audio, gameplay, ...) before saving, e.g.
        `store.save({**app.window_settings(), "sfx_volume": ...})`."""
        return {"window_mode": self._window_mode, "window_size": list(self.resolution)}

    def reset_window_settings(self) -> None:
        """Restores window mode/resolution to Application's own defaults
        (exclusive fullscreen, no resolution override) -- pair with a
        project's own audio/gameplay reset logic for a full settings reset."""
        self.clear_resolution_override()
        self.full_screen()

    def _fit_rect(self, dst_size: tuple[int, int]) -> pygame.Rect:
        """Largest rect that fits dst_size while preserving self.window's
        aspect ratio, centered inside it. Only meaningful under
        fixed_aspect=True -- self.window's aspect always matches dst_size's
        otherwise, so this would just return the full dst_size rect."""
        assert self.window is not None, (
            "self.window is only None before __init__ finishes"
        )
        dst_w, dst_h = dst_size
        src_w, src_h = self.window.get_size()
        scale = min(dst_w / src_w, dst_h / src_h)
        w, h = round(src_w * scale), round(src_h * scale)
        return pygame.Rect((dst_w - w) // 2, (dst_h - h) // 2, w, h)

    def _sync_mouse_scale(self) -> None:
        if not self.mouse:
            return
        assert self.window is not None, (
            "self.window is only None before __init__ finishes"
        )
        if self.fixed_aspect:
            rect = self._fit_rect(self.display_surface.get_size())
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

    def set_size(self, size: tuple[int, int]) -> None:
        self.size = size

    @property
    def width(self) -> int:
        return self.size[0]

    @property
    def height(self) -> int:
        return self.size[1]

    def show_splash(self) -> None:
        """Runs self.splash's own blocking loop (if one was set), then
        returns once it's done -- a no-op if self.splash is still None.

        SplashScreen.run() calls pygame.display.update() itself each frame
        against display_surface directly, bypassing _present()'s scale
        step entirely -- drawing it onto the offscreen logical canvas
        (self.window) instead would never actually reach the screen, since
        nothing would blit that canvas until the main loop below starts."""
        if self.splash is not None:
            self.splash.run(self.display_surface, self.clock, self._fps)

    def run(self) -> None:
        self.show_splash()
        self._is_running = True

        while self._is_running:
            self.clock.tick(self._fps)
            self._listen_inputs()
            self._handle_events()
            self.update()
            self.draw()
            self.draw_mouse()
            if self._is_in_debug_mode:
                self.draw_debug()
            self._present()

    def _present(self) -> None:
        assert self.window is not None, (
            "self.window is only None before __init__ finishes"
        )
        dst_size = self.display_surface.get_size()

        if self.fixed_aspect:
            # self.window is locked to the design resolution (see
            # _scaled_render_size()), so its aspect ratio generally does
            # NOT match dst_size -- fill the whole display with black first,
            # then scale into a centered, aspect-preserving sub-rect rather
            # than stretching across the full (differently-shaped) display.
            rect = self._fit_rect(dst_size)
            if rect.size == dst_size:
                pygame.transform.scale(self.window, dst_size, self.display_surface)
            else:
                self.display_surface.fill((0, 0, 0))
                pygame.transform.scale(
                    self.window, rect.size, self.display_surface.subsurface(rect)
                )
            pygame.display.update()
            return

        # At the default render_scale (1.0), self.window always matches
        # display_surface's size exactly (kept in sync by
        # _rebuild_window_surface() on every mode/resolution/render_scale
        # change), so this is a plain 1:1 blit -- no stretching, no
        # letterboxing. Only a render_scale < 1.0 engages the upscale.
        if self.window.get_size() == dst_size:
            self.display_surface.blit(self.window, (0, 0))
        else:
            pygame.transform.scale(self.window, dst_size, self.display_surface)
        pygame.display.update()

    def _listen_inputs(self) -> None:
        if self.mouse:
            self.mouse.update()
        self.keys = pygame.key.get_pressed()

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            self._handle_core_event(event)
            self.handle_event(event)

    def _handle_core_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.on_exit_request()
            elif event.key == pygame.K_F1:
                self._is_in_debug_mode = not self._is_in_debug_mode
            elif event.key == pygame.K_F11:
                self.cycle_window_mode()
        elif event.type == pygame.QUIT:
            self.on_exit_request()

    # region Override these methods in subclasses (Abstract Methods)

    def handle_event(self, event: pygame.event.Event) -> None:
        """Override this method in subclasses to handle events. This method is called once per event."""

        pass

    def update(self) -> None:
        """Override this method in subclasses to update the game state. This method is called once per frame."""

        pass

    def draw(self) -> None:
        """Override this method in subclasses to draw the game state. This method is called once per frame."""

        pass

    def draw_mouse(self) -> None:
        assert self.window is not None, (
            "self.window is only None before __init__ finishes"
        )
        if self.mouse:
            self.mouse.draw(self.window)

    def draw_debug(self) -> None:
        """Override this method in subclasses to draw debug information. This method is called once per frame when debug mode is enabled."""

        pass

    # endregion

    def on_exit_request(self) -> None:
        self.exit()

    def exit(self) -> None:
        self._is_running = False
        pygame.quit()
        sys.exit()
