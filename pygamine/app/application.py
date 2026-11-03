from __future__ import annotations

from typing import Generic, TypeVar, overload
import sys
import pygame
from pygame import mixer
from pygamine.app.display import (
    COMMON_RESOLUTIONS as COMMON_RESOLUTIONS,
    WINDOW_MARGIN as WINDOW_MARGIN,
    WINDOW_MODES,
    Display,
    WindowMode as WindowMode,
    center_window,
    fit_rect as fit_rect,
)
from pygamine.app.mouse import Mouse
from pygamine.app.splash_screen import SplashScreen

_T = TypeVar("_T")


class _Forward(Generic[_T]):
    """Attribute of Application that lives on its Display. Keeps the
    attributes games read and write (display_surface, window, render_scale,
    ...) available on Application unchanged."""

    def __init__(self, name: str) -> None:
        self._name = name

    @overload
    def __get__(self, obj: None, owner: type) -> _Forward[_T]: ...
    @overload
    def __get__(self, obj: Application, owner: type) -> _T: ...
    def __get__(self, obj: Application | None, owner: type) -> _Forward[_T] | _T:
        if obj is None:
            return self
        return getattr(obj.display, self._name)

    def __set__(self, obj: Application, value: _T) -> None:
        setattr(obj.display, self._name, value)


class Application:
    """Game loop, input and events. The display stack (window modes,
    resolution, render scale, fixed aspect, present, mouse scaling) lives in
    `self.display` (a Display); every display method and attribute below
    forwards to it, so subclasses and games keep using Application directly."""

    # Cycle order for F11 / cycle_window_mode(); see display.WINDOW_MODES.
    WINDOW_MODES: tuple[WindowMode, ...] = WINDOW_MODES

    # The real OS window/screen surface, replaced on every mode switch.
    display_surface = _Forward[pygame.Surface]("display_surface")
    # The logical render target the game draws on, rebuilt on every resize.
    window = _Forward[pygame.Surface]("window")
    # Render density relative to the real display; see set_render_scale().
    render_scale = _Forward[float]("render_scale")
    # Lock the canvas to the constructor `size` and letterbox it; see Display.
    fixed_aspect = _Forward[bool]("fixed_aspect")
    mouse = _Forward[Mouse]("mouse")
    # The constructor's `size`: the default windowed size, and the fixed
    # design resolution under fixed_aspect.
    windowed_size = _Forward[tuple[int, int]]("windowed_size")
    windowed_width = _Forward[int]("windowed_width")
    windowed_height = _Forward[int]("windowed_height")
    # The desktop size, queried once at startup.
    fullscreen_size = _Forward[tuple[int, int]]("fullscreen_size")
    fullscreen_width = _Forward[int]("fullscreen_width")
    fullscreen_height = _Forward[int]("fullscreen_height")

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
        # The logical canvas size: starts as the constructor `size` and is
        # kept equal to the canvas by _on_canvas_resized() (the canvas is
        # dynamic, rebuilt to match whatever window size is actually chosen).
        self.size: tuple[int, int] = size
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
        # Must run after pygame.init() and before the first set_mode() below
        # (Display queries the desktop size).
        self.display = Display(
            size,
            mouse if mouse is not None else Mouse(),
            self._on_canvas_resized,
            render_scale,
            fixed_aspect,
            self.WINDOW_MODES,
            # Looked up at call time, so a subclass override of a setter is
            # still what set_window_mode()/F11/cycle_resolution() run.
            {
                "fullscreen": lambda: self.set_fullscreen(),
                "borderless": lambda: self.set_borderless_fullscreen(),
                "windowed": lambda: self.set_windowed(),
            },
            lambda size: self.set_resolution(size),
        )
        self.set_fullscreen()  # sets display_surface and rebuilds self.window to match it (scaled by render_scale)
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
        center_window()

    @staticmethod
    def get_title() -> str:
        return pygame.display.get_caption()[0]

    @staticmethod
    def set_title(title: str) -> None:
        pygame.display.set_caption(title)

    def _on_canvas_resized(self, new_size: tuple[int, int]) -> None:
        """Display's callback: record the new canvas size, then run the
        subclass hook (so an overridden set_size() is still honored)."""
        self.set_size(new_size)
        self.on_canvas_resized(new_size)

    def on_canvas_resized(self, new_size: tuple[int, int]) -> None:
        """Override in a subclass to react to the logical canvas changing
        size (window mode toggled via F11, a new windowed resolution
        picked, render_scale changed, ...) -- e.g. resize a camera viewport
        or re-anchor UI chrome to the new edges. No-op by default."""
        pass

    # region Display delegates (see Display for the behavior)

    def set_windowed(self) -> None:
        self.display.set_windowed()

    def set_fullscreen(self) -> None:
        self.display.set_fullscreen()

    def set_borderless_fullscreen(self) -> None:
        self.display.set_borderless_fullscreen()

    @property
    def window_mode(self) -> WindowMode:
        """Current window mode, one of WINDOW_MODES (read-only)."""
        return self.display.window_mode

    @property
    def _window_mode(self) -> WindowMode:
        """Read-only alias of window_mode, kept for games that read it."""
        return self.display.window_mode

    @property
    def _is_fullscreen(self) -> bool:
        """True only for exclusive FULLSCREEN -- kept as a read-only alias
        for existing callers that only care about the
        fullscreen/not-fullscreen distinction."""
        return self.display.is_fullscreen

    def set_window_mode(self, mode: WindowMode) -> None:
        """Apply one of WINDOW_MODES; raises ValueError for anything else."""
        self.display.set_window_mode(mode)

    def cycle_window_mode(self, step: int = 1) -> None:
        """Advance through WINDOW_MODES by `step` (wraps around) and apply
        the result. F11 calls this with the default step."""
        self.display.cycle_window_mode(step)

    def set_render_scale(self, scale: float) -> None:
        """Change the internal render resolution relative to the real
        display; see Display.set_render_scale()."""
        self.display.set_render_scale(scale)

    def available_resolutions(self) -> list[tuple[int, int]]:
        """Common resolutions that fit this screen, plus the current pick."""
        return self.display.available_resolutions()

    @property
    def resolution(self) -> tuple[int, int]:
        """The physical size set_windowed() will use right now."""
        return self.display.resolution

    def set_resolution(self, size: tuple[int, int]) -> None:
        """Explicitly choose the physical window size set_windowed() uses."""
        self.display.set_resolution(size)

    def clear_resolution_override(self) -> None:
        """Drop any explicit pick, reverting to the automatic best-fit size."""
        self.display.clear_resolution_override()

    def cycle_resolution(self, step: int = 1) -> tuple[int, int]:
        """Advance through available_resolutions() by `step` and apply it.
        Returns the newly selected size."""
        return self.display.cycle_resolution(step)

    def restore_window_settings(self, saved_settings: dict) -> None:
        """Applies a saved window mode/size on top of the default
        (always exclusive fullscreen)."""
        self.display.restore_window_settings(saved_settings)

    def window_settings(self) -> dict:
        """The window-mode/resolution portion of a settings dict, for
        SaveStore-style persistence."""
        return self.display.window_settings()

    def reset_window_settings(self) -> None:
        """Restores window mode/resolution to the defaults (exclusive
        fullscreen, no resolution override)."""
        self.display.reset_window_settings()

    # endregion

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
        self.display.present()

    def _listen_inputs(self) -> None:
        if self.mouse:
            self.mouse.update()
        self.keys = pygame.key.get_pressed()

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            # Drops the release of the press that skipped the splash (see
            # SplashScreen.swallow_held_input()), so it can't fire the menu
            if self.splash is not None and self.splash.swallow_held_input(event):
                continue
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
