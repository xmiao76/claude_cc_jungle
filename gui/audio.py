"""Sound effects with graceful degradation (the game runs fine without audio)."""

from __future__ import annotations

import os

import pygame

import config


class Audio:
    def __init__(self) -> None:
        self.enabled = False
        self.muted = False
        self._sounds: dict[str, pygame.mixer.Sound] = {}
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            self.enabled = True
        except Exception:
            self.enabled = False
            return
        for name in ("move", "capture", "win"):
            path = config.asset_path(os.path.join("gui", "assets", "sounds", f"{name}.wav"))
            try:
                self._sounds[name] = pygame.mixer.Sound(path)
            except Exception:
                pass

    def play(self, name: str) -> None:
        if not self.enabled or self.muted:
            return
        snd = self._sounds.get(name)
        if snd is not None:
            try:
                snd.play()
            except Exception:
                pass

    def toggle_mute(self) -> bool:
        self.muted = not self.muted
        return self.muted
