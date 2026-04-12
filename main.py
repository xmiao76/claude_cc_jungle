"""Jungle board game - entry point."""

import pygame
import config
from controller import Controller


def main() -> None:
    pygame.init()
    pygame.display.set_caption(config.WINDOW_TITLE)

    # Register custom event type for AI move results
    config.AI_MOVE_EVENT_TYPE = pygame.event.custom_type()

    surface = pygame.display.set_mode((config.WINDOW_WIDTH, config.WINDOW_HEIGHT))

    # Set window icon if available
    import os
    icon_path = config.asset_path(os.path.join("gui", "assets", "tiles", "icon.ico"))
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
