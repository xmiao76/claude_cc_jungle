"""Board and piece rendering for Jungle.

Phase 1: Colored rectangle terrain + text piece labels (placeholder visuals).
Phase 2: Replaced with sprite artwork.
"""

from __future__ import annotations

import math
import os

import pygame

import config as _config  # imported as module so _config.CELL_SIZE etc. are read dynamically
from config import (
    COLS, ROWS, BOARD_OFFSET_X, BOARD_OFFSET_Y,
    TERRAIN_LAND, TERRAIN_RIVER, TERRAIN_TRAP, TERRAIN_DEN,
    TERRAIN,
    COLOR_LAND, COLOR_RIVER, COLOR_TRAP, COLOR_DEN, COLOR_GRID,
    COLOR_HIGHLIGHT_SELECT, COLOR_HIGHLIGHT_MOVE, COLOR_CAPTURE_FLASH,
    COLOR_BLUE_PIECE, COLOR_BLACK_PIECE, COLOR_TEXT_LIGHT, COLOR_TEXT_DARK,
    COLOR_PANEL_BG, COLOR_BG,
    PANEL_WIDTH, CAPTURE_FLASH_MS,
    asset_path,
)
from engine.pieces import Animal, Color, piece_id_color, piece_id_animal, ANIMAL_NAMES

# Terrain background colors
_TERRAIN_COLOR = {
    TERRAIN_LAND: COLOR_LAND,
    TERRAIN_RIVER: COLOR_RIVER,
    TERRAIN_TRAP: COLOR_TRAP,
    TERRAIN_DEN: COLOR_DEN,
}

# Short labels drawn on every piece so the animal is always identifiable
_PIECE_LABEL = {
    Animal.RAT:      "Rat",
    Animal.CAT:      "Cat",
    Animal.DOG:      "Dog",
    Animal.WOLF:     "Wolf",
    Animal.LEOPARD:  "Leo",
    Animal.TIGER:    "Tig",
    Animal.LION:     "Lion",
    Animal.ELEPHANT: "Ele",
}

# Abbreviations kept for the fallback placeholder circle (no sprite)
_ABBREV = {
    Animal.RAT: "Ra", Animal.CAT: "Ca", Animal.DOG: "Do",
    Animal.WOLF: "Wo", Animal.LEOPARD: "Le", Animal.TIGER: "Ti",
    Animal.LION: "Li", Animal.ELEPHANT: "El",
}


def _cell_rect(col: int, row: int) -> pygame.Rect:
    x = BOARD_OFFSET_X + col * _config.CELL_SIZE
    y = BOARD_OFFSET_Y + row * _config.CELL_SIZE
    return pygame.Rect(x, y, _config.CELL_SIZE, _config.CELL_SIZE)


def _pixel_center(col: int, row: int) -> tuple[int, int]:
    r = _cell_rect(col, row)
    return r.centerx, r.centery


class Renderer:
    """Draws all game visuals onto a pygame Surface."""

    def __init__(self, surface: pygame.Surface) -> None:
        self.surface = surface
        self._font_piece = pygame.font.SysFont("segoeui", 16, bold=True)
        self._font_label = pygame.font.SysFont("segoeui", 13)
        self._font_status = pygame.font.SysFont("segoeui", 18, bold=True)
        self._font_big = pygame.font.SysFont("segoeui", 36, bold=True)
        self._font_small = pygame.font.SysFont("segoeui", 14)

        # Sprite cache: dict of (animal, color) -> pygame.Surface | None
        self._sprites: dict[tuple[Animal, Color], pygame.Surface | None] = {}
        self._sprites_loaded = False

        # Terrain tile cache
        self._tile_cache: dict[int, pygame.Surface | None] = {}
        self._tiles_loaded = False

        # Capture flash: dict of (col, row) -> end_time_ms
        self._flashes: dict[tuple[int, int], int] = {}

        # AI thinking spinner state
        self._spinner_angle = 0.0

    # ------------------------------------------------------------------
    # Asset loading (called once after pygame.display is set)
    # ------------------------------------------------------------------

    def load_assets(self) -> None:
        """Attempt to load sprite and tile assets. Falls back to placeholder if missing."""
        self._load_tiles()
        self._load_sprites()

    def _load_tiles(self) -> None:
        tile_names = {
            TERRAIN_LAND: "land.png",
            TERRAIN_RIVER: "river.png",
            TERRAIN_TRAP: "trap.png",
            TERRAIN_DEN: "den.png",
        }
        for terrain_id, filename in tile_names.items():
            path = asset_path(os.path.join("gui", "assets", "tiles", filename))
            if os.path.exists(path):
                try:
                    img = pygame.image.load(path).convert_alpha()
                    self._tile_cache[terrain_id] = pygame.transform.smoothscale(
                        img, (_config.CELL_SIZE, _config.CELL_SIZE)
                    )
                except Exception:
                    self._tile_cache[terrain_id] = None
            else:
                self._tile_cache[terrain_id] = None

    def _load_sprites(self) -> None:
        color_names = {Color.BLUE: "blue", Color.BLACK: "black"}
        for animal in Animal:
            for color in Color:
                fname = f"{animal.name.lower()}_{color_names[color]}.png"
                path = asset_path(os.path.join("gui", "assets", "pieces", fname))
                if os.path.exists(path):
                    try:
                        img = pygame.image.load(path).convert_alpha()
                        size = int(_config.CELL_SIZE * 0.78)
                        self._sprites[(animal, color)] = pygame.transform.smoothscale(
                            img, (size, size)
                        )
                    except Exception:
                        self._sprites[(animal, color)] = None
                else:
                    self._sprites[(animal, color)] = None

    # ------------------------------------------------------------------
    # Main draw entry point
    # ------------------------------------------------------------------

    def draw(
        self,
        state,
        selected: tuple[int, int] | None,
        legal_targets: set[tuple[int, int]],
        ai_thinking: bool,
        tick_ms: int,
    ) -> None:
        """Redraw the entire frame."""
        self.surface.fill(COLOR_BG)
        self._draw_board_terrain()
        self._draw_highlights(selected, legal_targets)
        self._draw_capture_flashes(tick_ms)
        self._draw_pieces(state.board, selected)
        self._draw_grid()
        self._draw_board_labels()
        self._draw_panel(state, ai_thinking, tick_ms)

    # ------------------------------------------------------------------
    # Board terrain
    # ------------------------------------------------------------------

    def _draw_board_terrain(self) -> None:
        for c in range(COLS):
            for r in range(ROWS):
                terrain = TERRAIN[c][r]
                rect = _cell_rect(c, r)
                tile = self._tile_cache.get(terrain)
                if tile:
                    self.surface.blit(tile, rect)
                else:
                    color = _TERRAIN_COLOR[terrain]
                    pygame.draw.rect(self.surface, color, rect)

                    # Extra visual cues for placeholder mode
                    if terrain == TERRAIN_DEN:
                        # Draw crown symbol
                        center = rect.center
                        pygame.draw.circle(self.surface, (255, 220, 0), center, _config.CELL_SIZE // 3, 3)
                    elif terrain == TERRAIN_TRAP:
                        # Draw X
                        m = 8
                        pygame.draw.line(self.surface, (120, 60, 0),
                                         (rect.x + m, rect.y + m),
                                         (rect.right - m, rect.bottom - m), 2)
                        pygame.draw.line(self.surface, (120, 60, 0),
                                         (rect.right - m, rect.y + m),
                                         (rect.x + m, rect.bottom - m), 2)

    def _draw_grid(self) -> None:
        for c in range(COLS + 1):
            x = BOARD_OFFSET_X + c * _config.CELL_SIZE
            pygame.draw.line(self.surface, COLOR_GRID,
                             (x, BOARD_OFFSET_Y),
                             (x, BOARD_OFFSET_Y + ROWS * _config.CELL_SIZE), 1)
        for r in range(ROWS + 1):
            y = BOARD_OFFSET_Y + r * _config.CELL_SIZE
            pygame.draw.line(self.surface, COLOR_GRID,
                             (BOARD_OFFSET_X, y),
                             (BOARD_OFFSET_X + COLS * _config.CELL_SIZE, y), 1)

    def _draw_board_labels(self) -> None:
        # Column labels A-G
        for c in range(COLS):
            label = chr(ord('A') + c)
            surf = self._font_label.render(label, True, (180, 180, 180))
            x = BOARD_OFFSET_X + c * _config.CELL_SIZE + _config.CELL_SIZE // 2 - surf.get_width() // 2
            y = BOARD_OFFSET_Y + ROWS * _config.CELL_SIZE + 4
            self.surface.blit(surf, (x, y))
        # Row labels 1-9
        for r in range(ROWS):
            label = str(r + 1)
            surf = self._font_label.render(label, True, (180, 180, 180))
            x = BOARD_OFFSET_X - surf.get_width() - 4
            y = BOARD_OFFSET_Y + r * _config.CELL_SIZE + _config.CELL_SIZE // 2 - surf.get_height() // 2
            self.surface.blit(surf, (x, y))

    # ------------------------------------------------------------------
    # Highlights
    # ------------------------------------------------------------------

    def _draw_highlights(
        self,
        selected: tuple[int, int] | None,
        legal_targets: set[tuple[int, int]],
    ) -> None:
        # Selected piece: gold border
        if selected:
            rect = _cell_rect(*selected)
            pygame.draw.rect(self.surface, COLOR_HIGHLIGHT_SELECT, rect, 4)

        # Legal move targets: semi-transparent green circle
        for (c, r) in legal_targets:
            center = _pixel_center(c, r)
            dot_surf = pygame.Surface((_config.CELL_SIZE, _config.CELL_SIZE), pygame.SRCALPHA)
            pygame.draw.circle(dot_surf, (100, 230, 100, 120), (_config.CELL_SIZE // 2, _config.CELL_SIZE // 2),
                               _config.CELL_SIZE // 4)
            self.surface.blit(dot_surf, _cell_rect(c, r))

    # ------------------------------------------------------------------
    # Capture flash
    # ------------------------------------------------------------------

    def trigger_capture_flash(self, col: int, row: int, tick_ms: int) -> None:
        self._flashes[(col, row)] = tick_ms + CAPTURE_FLASH_MS

    def _draw_capture_flashes(self, tick_ms: int) -> None:
        expired = []
        for (c, r), end_ms in self._flashes.items():
            if tick_ms < end_ms:
                rect = _cell_rect(c, r)
                flash_surf = pygame.Surface((_config.CELL_SIZE, _config.CELL_SIZE), pygame.SRCALPHA)
                alpha = int(180 * (end_ms - tick_ms) / CAPTURE_FLASH_MS)
                flash_surf.fill((220, 50, 50, alpha))
                self.surface.blit(flash_surf, rect)
            else:
                expired.append((c, r))
        for k in expired:
            del self._flashes[k]

    # ------------------------------------------------------------------
    # Pieces
    # ------------------------------------------------------------------

    def _draw_pieces(self, board, selected: tuple[int, int] | None) -> None:
        for c in range(COLS):
            for r in range(ROWS):
                pid = board.get(c, r)
                if pid == 0:
                    continue
                color = piece_id_color(pid)
                animal = piece_id_animal(pid)
                self._draw_piece(c, r, color, animal, selected == (c, r))

    def _draw_outlined_text(
        self,
        text: str,
        font: pygame.font.Font,
        cx: int,
        cy: int,
        fg: tuple,
        outline: tuple,
        outline_width: int = 1,
    ) -> None:
        """Draw text centered at (cx, cy) with a solid outline for readability."""
        for dx in range(-outline_width, outline_width + 1):
            for dy in range(-outline_width, outline_width + 1):
                if dx == 0 and dy == 0:
                    continue
                s = font.render(text, True, outline)
                self.surface.blit(s, (cx - s.get_width() // 2 + dx,
                                      cy - s.get_height() // 2 + dy))
        s = font.render(text, True, fg)
        self.surface.blit(s, (cx - s.get_width() // 2, cy - s.get_height() // 2))

    def _draw_piece(
        self,
        col: int, row: int,
        color: Color, animal: Animal,
        is_selected: bool,
    ) -> None:
        rect = _cell_rect(col, row)
        cx, cy = rect.centerx, rect.centery
        sprite = self._sprites.get((animal, color))

        if sprite:
            x = cx - sprite.get_width() // 2
            y = cy - sprite.get_height() // 2
            self.surface.blit(sprite, (x, y))
        else:
            # Placeholder: colored circle with abbreviated name
            piece_color = COLOR_BLUE_PIECE if color == Color.BLUE else COLOR_BLACK_PIECE
            radius = _config.CELL_SIZE // 2 - 6
            pygame.draw.circle(self.surface, piece_color, (cx, cy), radius)
            pygame.draw.circle(self.surface, (200, 200, 200), (cx, cy), radius, 2)

            abbrev = _ABBREV[animal]
            surf = self._font_piece.render(abbrev, True, COLOR_TEXT_LIGHT)
            self.surface.blit(surf, (cx - surf.get_width() // 2, cy - surf.get_height() // 2))

        # --- Animal name label at bottom of cell ---
        # White text with dark outline so it reads on any terrain/piece color.
        label = _PIECE_LABEL[animal]
        label_y = rect.bottom - self._font_label.get_height() - 1
        self._draw_outlined_text(
            label, self._font_label,
            cx, label_y,
            fg=(255, 255, 255),
            outline=(0, 0, 0),
            outline_width=1,
        )

        # Rank badge: small circle in top-left with number
        rank = int(animal)
        badge_x = rect.x + 3
        badge_y = rect.y + 3
        badge_r = 8
        badge_color = (60, 120, 220) if color == Color.BLUE else (50, 50, 60)
        pygame.draw.circle(self.surface, badge_color, (badge_x + badge_r, badge_y + badge_r), badge_r)
        pygame.draw.circle(self.surface, (200, 200, 200), (badge_x + badge_r, badge_y + badge_r), badge_r, 1)
        rank_surf = self._font_small.render(str(rank), True, (255, 255, 255))
        self.surface.blit(rank_surf, (badge_x + badge_r - rank_surf.get_width() // 2,
                                      badge_y + badge_r - rank_surf.get_height() // 2))

    # ------------------------------------------------------------------
    # Side panel
    # ------------------------------------------------------------------

    def _draw_panel(self, state, ai_thinking: bool, tick_ms: int) -> None:
        panel_x = BOARD_OFFSET_X + COLS * _config.CELL_SIZE + 20
        panel_rect = pygame.Rect(panel_x, 0, PANEL_WIDTH, _config.WINDOW_HEIGHT)
        pygame.draw.rect(self.surface, COLOR_PANEL_BG, panel_rect)

        y = 30
        # Title
        title = self._font_status.render("JUNGLE", True, (220, 180, 60))
        self.surface.blit(title, (panel_x + 10, y))
        y += 50

        # Current turn
        if not state.is_terminal():
            turn_color = "Blue" if state.turn == Color.BLUE else "Black"
            turn_surf = self._font_status.render(f"{turn_color}'s turn", True, COLOR_TEXT_LIGHT)
            self.surface.blit(turn_surf, (panel_x + 10, y))
            y += 40

            if ai_thinking:
                self._draw_spinner(panel_x + 10, y, tick_ms)
                think_surf = self._font_small.render("AI thinking...", True, (160, 160, 160))
                self.surface.blit(think_surf, (panel_x + 40, y + 8))
                y += 40
        else:
            winner = state.get_winner()
            if winner is not None:
                wname = "Blue" if winner == Color.BLUE else "Black"
                win_surf = self._font_big.render(f"{wname} wins!", True, (255, 215, 0))
                self.surface.blit(win_surf, (panel_x + 10, y))
            y += 60

        y += 20
        # Piece counts
        blue_count = state.board.alive_count(Color.BLUE)
        black_count = state.board.alive_count(Color.BLACK)
        bc_surf = self._font_small.render(f"Blue pieces: {blue_count}", True, (100, 160, 255))
        bkc_surf = self._font_small.render(f"Black pieces: {black_count}", True, (160, 160, 160))
        self.surface.blit(bc_surf, (panel_x + 10, y))
        y += 22
        self.surface.blit(bkc_surf, (panel_x + 10, y))
        y += 40

        # Move count
        moves_surf = self._font_small.render(f"Move #{len(state.history)}", True, (140, 140, 140))
        self.surface.blit(moves_surf, (panel_x + 10, y))

    def _draw_spinner(self, x: int, y: int, tick_ms: int) -> None:
        cx, cy = x + 14, y + 14
        angle = (tick_ms / 600) * 2 * math.pi
        for i in range(8):
            a = angle + i * math.pi / 4
            px = cx + int(12 * math.cos(a))
            py = cy + int(12 * math.sin(a))
            alpha = int(255 * (i + 1) / 8)
            c = (alpha, alpha, alpha)
            pygame.draw.circle(self.surface, c, (px, py), 3)

    # ------------------------------------------------------------------
    # Win / game-over overlay
    # ------------------------------------------------------------------

    def draw_game_over_overlay(
        self,
        surface: pygame.Surface,
        winner: Color | None,
        hover_replay: bool,
        hover_quit: bool,
    ) -> tuple[pygame.Rect, pygame.Rect]:
        """Draw win overlay. Returns (replay_btn_rect, quit_btn_rect)."""
        overlay = pygame.Surface((_config.WINDOW_WIDTH, _config.WINDOW_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        surface.blit(overlay, (0, 0))

        cx = _config.WINDOW_WIDTH // 2
        cy = _config.WINDOW_HEIGHT // 2

        if winner is not None:
            wname = "Blue" if winner == Color.BLUE else "Black"
            msg = f"{wname} wins!"
            color = (100, 160, 255) if winner == Color.BLUE else (200, 200, 200)
        else:
            msg = "Draw!"
            color = (220, 180, 60)

        msg_surf = self._font_big.render(msg, True, color)
        surface.blit(msg_surf, (cx - msg_surf.get_width() // 2, cy - 80))

        sub = self._font_small.render("Game Over", True, (180, 180, 180))
        surface.blit(sub, (cx - sub.get_width() // 2, cy - 35))

        # Buttons
        btn_w, btn_h = 140, 44
        replay_rect = pygame.Rect(cx - btn_w - 10, cy + 10, btn_w, btn_h)
        quit_rect = pygame.Rect(cx + 10, cy + 10, btn_w, btn_h)

        for rect, label, hover in [
            (replay_rect, "Play Again", hover_replay),
            (quit_rect, "Quit", hover_quit),
        ]:
            btn_color = (100, 100, 160) if hover else (60, 60, 100)
            pygame.draw.rect(surface, btn_color, rect, border_radius=8)
            pygame.draw.rect(surface, (180, 180, 220), rect, 2, border_radius=8)
            lsurf = self._font_status.render(label, True, COLOR_TEXT_LIGHT)
            surface.blit(lsurf, (rect.centerx - lsurf.get_width() // 2,
                                  rect.centery - lsurf.get_height() // 2))

        return replay_rect, quit_rect

    # ------------------------------------------------------------------
    # Main menu
    # ------------------------------------------------------------------

    def draw_main_menu(
        self,
        surface: pygame.Surface,
        difficulty: int,
        hover_hva: bool,
        hover_ava: bool,
        hover_diff: bool,
        difficulty_labels: list[str],
    ) -> tuple[pygame.Rect, pygame.Rect, pygame.Rect]:
        """Draw main menu. Returns (hva_rect, ava_rect, diff_rect)."""
        surface.fill((20, 30, 20))

        cx = _config.WINDOW_WIDTH // 2
        cy = _config.WINDOW_HEIGHT // 2

        # Title
        title = self._font_big.render("JUNGLE", True, (220, 180, 60))
        surface.blit(title, (cx - title.get_width() // 2, cy - 200))
        sub = self._font_small.render("Dou Shou Qi  •  斗兽棋", True, (140, 140, 140))
        surface.blit(sub, (cx - sub.get_width() // 2, cy - 155))

        btn_w, btn_h = 220, 50
        hva_rect = pygame.Rect(cx - btn_w // 2, cy - 80, btn_w, btn_h)
        ava_rect = pygame.Rect(cx - btn_w // 2, cy - 10, btn_w, btn_h)
        diff_rect = pygame.Rect(cx - btn_w // 2, cy + 70, btn_w, btn_h)

        for rect, label, hover in [
            (hva_rect, "Human vs AI", hover_hva),
            (ava_rect, "Watch AI vs AI", hover_ava),
            (diff_rect, f"Difficulty: {difficulty_labels[difficulty]}", hover_diff),
        ]:
            btn_color = (80, 110, 80) if hover else (40, 70, 40)
            pygame.draw.rect(surface, btn_color, rect, border_radius=10)
            pygame.draw.rect(surface, (100, 160, 100), rect, 2, border_radius=10)
            lsurf = self._font_status.render(label, True, COLOR_TEXT_LIGHT)
            surface.blit(lsurf, (rect.centerx - lsurf.get_width() // 2,
                                  rect.centery - lsurf.get_height() // 2))

        hint = self._font_small.render("ESC: return to menu during game", True, (80, 80, 80))
        surface.blit(hint, (cx - hint.get_width() // 2, cy + 140))

        return hva_rect, ava_rect, diff_rect
