"""Safe font construction.

pygame.font.SysFont enumerates fonts via the Windows registry, and on some
machines a registry value comes back as an int instead of a string, which makes
pygame's internal os.path.splitext raise:

    TypeError: expected str, bytes or os.PathLike object, not int

Falling back to pygame.font.Font(None, size) (the bundled freesansbold) keeps
the game usable on those systems.
"""

from __future__ import annotations

import pygame


def safe_sysfont(name: str, size: int, bold: bool = False) -> pygame.font.Font:
    try:
        return pygame.font.SysFont(name, size, bold=bold)
    except Exception:
        font = pygame.font.Font(None, size)
        if bold:
            font.set_bold(True)
        return font
