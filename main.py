"""Jungle board game - entry point."""

import pygame

import config
from controller import Controller


def main() -> None:
    pygame.init()
    try:
        pygame.mixer.init()
    except Exception:
        pass   # game still works without audio
    pygame.display.set_caption(config.WINDOW_TITLE)

    # Register custom event type for AI move results
    config.AI_MOVE_EVENT_TYPE = pygame.event.custom_type()

    # --- Screen-aware sizing ---
    # Query actual screen height and compute a cell size that fits comfortably.
    # RESERVED_PX accounts for: Windows title bar (~30px) + taskbar (~40px) + margin (~10px).
    info = pygame.display.Info()
    screen_h = info.current_h
    RESERVED_PX = 90
    usable_h = max(screen_h - RESERVED_PX, 540)   # floor at 540 so game is always usable
    raw_cell = (usable_h - 2 * config.BOARD_OFFSET_Y) // config.ROWS
    cell_size = max(60, min(90, raw_cell))          # clamp 60–90 px

    # Override derived constants so all modules see consistent values
    config.CELL_SIZE = cell_size
    config.WINDOW_WIDTH = config.COLS * cell_size + config.BOARD_OFFSET_X * 2 + config.PANEL_WIDTH
    config.WINDOW_HEIGHT = config.ROWS * cell_size + config.BOARD_OFFSET_Y * 2

    surface = pygame.display.set_mode((config.WINDOW_WIDTH, config.WINDOW_HEIGHT))

    # Set window icon if available
    import os
    # icon.png is what generate_assets.py actually writes; the old code looked
    # for an icon.ico that is never produced, so this block never ran.
    icon_path = config.asset_path(os.path.join("gui", "assets", "tiles", "icon.png"))
    if os.path.exists(icon_path):
        try:
            icon = pygame.image.load(icon_path)
            pygame.display.set_icon(icon)
        except Exception:
            pass

    controller = Controller(surface)
    controller.run()

    pygame.quit()


if __name__ == "__main__":
    main()
