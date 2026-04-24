"""Lightweight pygame.mixer wrapper for game SFX.

Sounds are loaded lazily and gracefully degrade to silence if files or the
mixer subsystem are unavailable (e.g., headless test runs).
"""

from __future__ import annotations

import os

import pygame

from config import asset_path

_SOUNDS = {
    "move":    "move.wav",
    "capture": "capture.wav",
    "win":     "win.wav",
}


class Audio:
    def __init__(self) -> None:
        self._cache: dict[str, pygame.mixer.Sound | None] = {}
        self.muted = False
        self._available = False
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            self._available = pygame.mixer.get_init() is not None
        except Exception:
            self._available = False
        if self._available:
            self._load_all()

    def _load_all(self) -> None:
        for name, fname in _SOUNDS.items():
            path = asset_path(os.path.join("gui", "assets", "sounds", fname))
            if os.path.exists(path):
                try:
                    self._cache[name] = pygame.mixer.Sound(path)
                except Exception:
                    self._cache[name] = None
            else:
                self._cache[name] = None

    def play(self, name: str) -> None:
        if self.muted or not self._available:
            return
        snd = self._cache.get(name)
        if snd is not None:
            try:
                snd.play()
            except Exception:
                pass

    def toggle_mute(self) -> None:
        self.muted = not self.muted
