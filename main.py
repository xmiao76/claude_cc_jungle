"""Jungle board game - entry point.

Windowing strategy for crisp, correct rendering across Windows resolutions,
DPI/display-scaling settings, and window sizes (see prompt.md):

  1. Declare the process DPI-aware (ctypes) BEFORE creating the window, so
     Windows does not bitmap-stretch (blur) our output under 125/150/175%
     display scaling.
  2. Size a fixed *logical* surface from the primary display's usable height.
  3. Create it with pygame.SCALED | pygame.RESIZABLE so SDL scales that single
     logical surface uniformly (letterboxed) to any window/monitor size and
     aspect ratio - no clipping, distortion, or overlapping controls. Mouse
     events are reported in logical coordinates, so the rest of the code is
     resolution-agnostic.
"""

from __future__ import annotations

import ctypes
import os
import sys

import pygame

import config
from controller import Controller


def _set_dpi_awareness() -> None:
    """Best-effort per-monitor DPI awareness on Windows (no-op elsewhere)."""
    if sys.platform != "win32":
        return
    try:  # Windows 10 1703+: Per-Monitor v2
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        return
    except Exception:
        pass
    try:  # Windows 8.1+: Per-Monitor
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return
    except Exception:
        pass
    try:  # Vista+: System DPI aware
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def _set_window_icon() -> None:
    for name in ("icon.png", "icon.ico"):
        path = config.asset_path(os.path.join("gui", "assets", "tiles", name))
        if os.path.exists(path):
            try:
                pygame.display.set_icon(pygame.image.load(path))
                return
            except Exception:
                continue


def main() -> None:
    _set_dpi_awareness()
    os.environ.setdefault("SDL_VIDEO_CENTERED", "1")

    pygame.init()
    try:
        pygame.mixer.init()
    except Exception:
        pass  # the game runs without audio

    pygame.display.set_caption(config.WINDOW_TITLE)
    config.AI_MOVE_EVENT_TYPE = pygame.event.custom_type()

    # Fixed logical size derived from the primary display height.
    info = pygame.display.Info()
    screen_h = info.current_h if info.current_h > 0 else 900
    cell = config.compute_cell_size(screen_h)
    config.CELL_SIZE = cell
    config.WINDOW_WIDTH, config.WINDOW_HEIGHT = config.layout_for_cell(cell)

    size = (config.WINDOW_WIDTH, config.WINDOW_HEIGHT)
    flags = pygame.SCALED | pygame.RESIZABLE
    try:
        surface = pygame.display.set_mode(size, flags, vsync=1)
    except Exception:
        surface = pygame.display.set_mode(size, flags)

    _set_window_icon()

    Controller(surface).run()
    pygame.quit()


if __name__ == "__main__":
    main()
