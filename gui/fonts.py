"""Cached font loading. Sizes are derived from the (fixed) cell size so text
scales with the board; the whole surface is then uniformly scaled to the window
by pygame's SCALED display, keeping text crisp at any resolution."""

from __future__ import annotations

import pygame

_cache: dict[tuple[int, bool], pygame.font.Font] = {}
_FAMILY = "arial,segoeui,sans"


def get(size: int, bold: bool = False) -> pygame.font.Font:
    size = max(8, int(size))
    key = (size, bold)
    font = _cache.get(key)
    if font is None:
        if not pygame.font.get_init():
            pygame.font.init()
        font = pygame.font.SysFont(_FAMILY, size, bold=bold)
        _cache[key] = font
    return font


def clear() -> None:
    _cache.clear()
