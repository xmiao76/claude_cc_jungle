"""All drawing for the game: board, terrain, pieces, side panel, main menu, and
overlays. The renderer draws to a fixed logical surface; the SCALED display
scales that surface to the actual window, so nothing here depends on the real
window size.

Board *flip* is a pure display transform: ``self.flipped`` only changes where a
``(col, row)`` is drawn (and where a click maps back to), never the game state.
"""

from __future__ import annotations

import os

import pygame

import config
from engine.pieces import ANIMAL_NAME, Animal, Color, code_animal, code_color
from gui import fonts

COLS = config.COLS
ROWS = config.ROWS


class Renderer:
    def __init__(self, surface: pygame.Surface) -> None:
        self.surface = surface
        self.flipped = False
        self._layout()
        self._load_assets()
        # Button rects, refreshed each frame they are drawn (logical coords).
        self.buttons: dict[str, pygame.Rect] = {}
        self.menu_buttons: dict[str, pygame.Rect] = {}
        self.over_buttons: dict[str, pygame.Rect] = {}

    # -- layout -------------------------------------------------------------

    def _layout(self) -> None:
        self.cell = config.CELL_SIZE
        self.ox = config.BOARD_MARGIN
        self.oy = config.BOARD_MARGIN
        self.board_w = COLS * self.cell
        self.board_h = ROWS * self.cell
        self.panel_x = self.ox + self.board_w + config.BOARD_MARGIN
        self.panel_w = config.WINDOW_WIDTH - self.panel_x - config.BOARD_MARGIN // 2
        self.W = config.WINDOW_WIDTH
        self.H = config.WINDOW_HEIGHT

    def _load_assets(self) -> None:
        sprite_px = int(self.cell * 0.9)
        self.sprites: dict[tuple[int, int], pygame.Surface] = {}
        for animal in Animal:
            for color, owner in ((int(Color.BLUE), "blue"), (int(Color.BLACK), "black")):
                path = config.asset_path(
                    os.path.join("gui", "assets", "pieces", f"{ANIMAL_NAME[animal]}_{owner}.png"))
                img = pygame.image.load(path).convert_alpha()
                self.sprites[(int(animal), color)] = pygame.transform.smoothscale(
                    img, (sprite_px, sprite_px))

        self.tiles: dict[str, pygame.Surface] = {}
        for name in ("land", "river", "trap", "den_blue", "den_black"):
            path = config.asset_path(os.path.join("gui", "assets", "tiles", f"{name}.png"))
            try:
                img = pygame.image.load(path).convert()
                self.tiles[name] = pygame.transform.smoothscale(img, (self.cell, self.cell))
            except Exception:
                self.tiles[name] = None

    # -- coordinate mapping (applies flip) ----------------------------------

    def cell_topleft(self, col: int, row: int) -> tuple[int, int]:
        dcol = COLS - 1 - col if self.flipped else col
        drow = ROWS - 1 - row if self.flipped else row
        return self.ox + dcol * self.cell, self.oy + drow * self.cell

    def cell_center(self, col: int, row: int) -> tuple[int, int]:
        x, y = self.cell_topleft(col, row)
        return x + self.cell // 2, y + self.cell // 2

    # -- top-level frames ---------------------------------------------------

    def draw_game(self, gs, *, selected, target_squares, last_move, human_color,
                  ai_thinking, tick_ms, capture_flash, anim, difficulty,
                  mode_ava, muted, move_number) -> None:
        self.surface.fill(config.COLOR_BG)
        self._draw_terrain()
        self._draw_last_move(last_move)
        self._draw_selection(selected, target_squares, gs)
        self._draw_pieces(gs, anim)
        self._draw_capture_flash(capture_flash, tick_ms)
        self._draw_grid()
        self._draw_panel(gs, human_color=human_color, ai_thinking=ai_thinking,
                         difficulty=difficulty, mode_ava=mode_ava, muted=muted,
                         move_number=move_number, tick_ms=tick_ms)

    # -- board layers -------------------------------------------------------

    def _draw_terrain(self) -> None:
        surf = self.surface
        for col in range(COLS):
            for row in range(ROWS):
                x, y = self.cell_topleft(col, row)
                terr = config.TERRAIN[col][row]
                tile = None
                if terr == config.TERRAIN_RIVER:
                    tile = self.tiles.get("river")
                elif terr == config.TERRAIN_TRAP:
                    tile = self.tiles.get("trap")
                elif terr == config.TERRAIN_DEN:
                    owner = "black" if (col, row) == config.DEN_BLACK else "blue"
                    tile = self.tiles.get(f"den_{owner}")
                else:
                    tile = self.tiles.get("land")
                if tile is not None:
                    surf.blit(tile, (x, y))
                    if terr == config.TERRAIN_LAND and (col + row) % 2:
                        shade = pygame.Surface((self.cell, self.cell), pygame.SRCALPHA)
                        shade.fill((0, 0, 0, 22))
                        surf.blit(shade, (x, y))
                else:  # procedural fallback
                    color = {
                        config.TERRAIN_RIVER: config.COLOR_RIVER,
                        config.TERRAIN_TRAP: config.COLOR_TRAP,
                        config.TERRAIN_DEN: config.COLOR_DEN_BLUE,
                    }.get(terr, config.COLOR_LAND if (col + row) % 2 else config.COLOR_LAND_ALT)
                    pygame.draw.rect(surf, color, (x, y, self.cell, self.cell))

    def _draw_grid(self) -> None:
        surf = self.surface
        for col in range(COLS + 1):
            x = self.ox + col * self.cell
            pygame.draw.line(surf, config.COLOR_GRID, (x, self.oy), (x, self.oy + self.board_h), 1)
        for row in range(ROWS + 1):
            y = self.oy + row * self.cell
            pygame.draw.line(surf, config.COLOR_GRID, (self.ox, y), (self.ox + self.board_w, y), 1)
        pygame.draw.rect(surf, (18, 22, 18),
                         (self.ox, self.oy, self.board_w, self.board_h), 3)

    def _draw_last_move(self, last_move) -> None:
        if last_move is None:
            return
        for sq in (last_move.frm, last_move.to):
            x, y = self.cell_topleft(sq // ROWS, sq % ROWS)
            s = pygame.Surface((self.cell, self.cell), pygame.SRCALPHA)
            s.fill((*config.COLOR_HIGHLIGHT_LAST, 90))
            self.surface.blit(s, (x, y))

    def _draw_selection(self, selected, target_squares, gs) -> None:
        if selected is not None:
            x, y = self.cell_topleft(*selected)
            pygame.draw.rect(self.surface, config.COLOR_HIGHLIGHT_SELECT,
                             (x, y, self.cell, self.cell), max(3, self.cell // 18))
        if target_squares:
            for sq in target_squares:
                col, row = sq // ROWS, sq % ROWS
                cx, cy = self.cell_center(col, row)
                occupied = gs.board.sq[sq] != 0
                if occupied:  # capture target: ring
                    pygame.draw.circle(self.surface, config.COLOR_HIGHLIGHT_MOVE,
                                       (cx, cy), self.cell // 2 - 3, max(3, self.cell // 20))
                else:
                    dot = pygame.Surface((self.cell, self.cell), pygame.SRCALPHA)
                    pygame.draw.circle(dot, (*config.COLOR_HIGHLIGHT_MOVE, 190),
                                       (self.cell // 2, self.cell // 2), self.cell // 7)
                    self.surface.blit(dot, (self.cell_topleft(col, row)))

    def _draw_pieces(self, gs, anim) -> None:
        skip_sq = anim["dst"] if anim else -1
        for sq, code in enumerate(gs.board.sq):
            if code == 0 or sq == skip_sq:
                continue
            self._blit_piece(code, *self.cell_topleft(sq // ROWS, sq % ROWS))
        if anim:
            self._blit_piece(anim["code"], anim["x"], anim["y"])

    def _blit_piece(self, code: int, x: int, y: int) -> None:
        sprite = self.sprites[(code_animal(code), code_color(code))]
        off = (self.cell - sprite.get_width()) // 2
        self.surface.blit(sprite, (x + off, y + off))

    def _draw_capture_flash(self, capture_flash, tick_ms) -> None:
        if not capture_flash:
            return
        sq, start = capture_flash
        frac = (tick_ms - start) / config.CAPTURE_FLASH_MS
        if frac < 0 or frac > 1:
            return
        x, y = self.cell_topleft(sq // ROWS, sq % ROWS)
        s = pygame.Surface((self.cell, self.cell), pygame.SRCALPHA)
        s.fill((*config.COLOR_CAPTURE_FLASH, int(180 * (1 - frac))))
        self.surface.blit(s, (x, y))

    # -- side panel ---------------------------------------------------------

    def _draw_panel(self, gs, *, human_color, ai_thinking, difficulty, mode_ava,
                    muted, move_number, tick_ms) -> None:
        surf = self.surface
        px = self.panel_x
        pw = self.panel_w
        pygame.draw.rect(surf, config.COLOR_PANEL_BG, (px, 0, self.W - px, self.H))
        pad = px + 16
        y = 22

        title = fonts.get(int(self.cell * 0.42), bold=True)
        surf.blit(title.render("JUNGLE", True, config.COLOR_TEXT_LIGHT), (pad, y))
        y += int(self.cell * 0.5)
        sub = fonts.get(int(self.cell * 0.2))
        surf.blit(sub.render("Dou Shou Qi", True, config.COLOR_TEXT_MUTED), (pad, y))
        y += int(self.cell * 0.5)

        # Turn indicator
        f = fonts.get(int(self.cell * 0.24), bold=True)
        turn_col = config.COLOR_BLUE_PIECE if gs.to_move == int(Color.BLUE) else config.COLOR_BLACK_PIECE
        turn_name = "Blue" if gs.to_move == int(Color.BLUE) else "Black"
        line = f.render(f"{turn_name} to move", True, config.COLOR_TEXT_LIGHT)
        pygame.draw.circle(surf, turn_col, (pad + 9, y + line.get_height() // 2),
                           max(7, int(self.cell * 0.1)))
        surf.blit(line, (pad + 26, y))
        y += line.get_height() + 4
        if not mode_ava:
            tag = "Your move" if gs.to_move == human_color else "AI opponent"
            small = fonts.get(int(self.cell * 0.19))
            surf.blit(small.render(tag, True, config.COLOR_TEXT_MUTED), (pad + 26, y))
            y += int(self.cell * 0.3)
        else:
            y += int(self.cell * 0.06)

        # Piece counts
        cf = fonts.get(int(self.cell * 0.22))
        surf.blit(cf.render(f"Blue pieces:  {gs.counts[int(Color.BLUE)]}", True,
                            config.COLOR_TEXT_LIGHT), (pad, y))
        y += int(self.cell * 0.3)
        surf.blit(cf.render(f"Black pieces: {gs.counts[int(Color.BLACK)]}", True,
                            config.COLOR_TEXT_LIGHT), (pad, y))
        y += int(self.cell * 0.3)
        surf.blit(cf.render(f"Move {move_number}", True, config.COLOR_TEXT_MUTED), (pad, y))
        y += int(self.cell * 0.36)

        mode = "AI vs AI" if mode_ava else "Human vs AI"
        surf.blit(cf.render(f"Mode: {mode}", True, config.COLOR_TEXT_MUTED), (pad, y))
        y += int(self.cell * 0.28)
        surf.blit(cf.render(f"Difficulty: {config.DIFFICULTY_LABELS[difficulty]}", True,
                            config.COLOR_TEXT_MUTED), (pad, y))
        y += int(self.cell * 0.36)

        # AI thinking spinner
        if ai_thinking:
            self._spinner(pad + 12, y + 12, tick_ms)
            surf.blit(cf.render("AI thinking...", True, config.COLOR_HIGHLIGHT_SELECT),
                      (pad + 30, y))
        y += int(self.cell * 0.5)

        # Buttons at the bottom
        bh = max(30, int(self.cell * 0.42))
        gap = int(bh * 0.28)
        bx = pad - 4
        bw = pw - 12
        by = self.H - (bh + gap) * 3 - 32
        self.buttons = {}
        self.buttons["flip"] = self._button(
            pygame.Rect(bx, by, bw, bh), "Flip board: " + ("On (F)" if self.flipped else "Off (F)"))
        self.buttons["undo"] = self._button(
            pygame.Rect(bx, by + bh + gap, bw, bh), "Undo (U)")
        self.buttons["mute"] = self._button(
            pygame.Rect(bx, by + 2 * (bh + gap), bw, bh),
            "Sound: " + ("Off (M)" if muted else "On (M)"))

        hint = fonts.get(int(self.cell * 0.18))
        surf.blit(hint.render("ESC: menu", True, config.COLOR_TEXT_MUTED),
                  (pad, self.H - 14 - hint.get_height()))

    def _spinner(self, cx, cy, tick_ms) -> None:
        import math
        r = max(8, self.cell // 8)
        for i in range(8):
            a = tick_ms / 110.0 + i * math.pi / 4
            alpha = 60 + (i * 24) % 200
            ex, ey = cx + math.cos(a) * r, cy + math.sin(a) * r
            s = pygame.Surface((6, 6), pygame.SRCALPHA)
            pygame.draw.circle(s, (255, 215, 0, alpha), (3, 3), 3)
            self.surface.blit(s, (ex - 3, ey - 3))

    # -- buttons ------------------------------------------------------------

    def _button(self, rect: pygame.Rect, text: str, *, hovered=None,
                enabled=True, base=None) -> pygame.Rect:
        mx, my = pygame.mouse.get_pos()
        hover = rect.collidepoint(mx, my) if hovered is None else hovered
        base = base or config.COLOR_BUTTON_NORMAL
        color = config.COLOR_BUTTON_HOVER if (hover and enabled) else base
        if not enabled:
            color = (52, 56, 60)
        pygame.draw.rect(self.surface, color, rect, border_radius=8)
        pygame.draw.rect(self.surface, (150, 160, 180), rect, 1, border_radius=8)
        f = fonts.get(int(rect.height * 0.42), bold=True)
        label = f.render(text, True, config.COLOR_BUTTON_TEXT if enabled else (120, 124, 128))
        self.surface.blit(label, (rect.centerx - label.get_width() // 2,
                                  rect.centery - label.get_height() // 2))
        return rect

    # -- main menu ----------------------------------------------------------

    def draw_menu(self, *, difficulty, player_first, flipped) -> None:
        surf = self.surface
        surf.fill(config.COLOR_BG)
        # decorative board backdrop
        self._draw_terrain()
        self._draw_grid()
        veil = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        veil.fill((0, 0, 0, 150))
        surf.blit(veil, (0, 0))

        cx = self.W // 2
        title = fonts.get(int(self.cell * 0.95), bold=True)
        t = title.render("JUNGLE", True, config.COLOR_TEXT_LIGHT)
        surf.blit(t, (cx - t.get_width() // 2, int(self.H * 0.1)))
        sub = fonts.get(int(self.cell * 0.3))
        st = sub.render("Dou Shou Qi  -  Battle of the Animals", True, config.COLOR_TEXT_MUTED)
        surf.blit(st, (cx - st.get_width() // 2, int(self.H * 0.1) + int(self.cell)))

        bw = int(self.W * 0.44)
        bh = max(40, int(self.cell * 0.62))
        gap = int(bh * 0.34)
        y = int(self.H * 0.34)
        bx = cx - bw // 2
        self.menu_buttons = {}
        self.menu_buttons["hva"] = self._button(
            pygame.Rect(bx, y, bw, bh), "Play: Human vs AI", base=(70, 120, 90))
        y += bh + gap
        self.menu_buttons["ava"] = self._button(
            pygame.Rect(bx, y, bw, bh), "Watch: AI vs AI", base=(70, 100, 140))
        y += bh + gap
        first = "Human first" if player_first else "AI first"
        self.menu_buttons["first"] = self._button(
            pygame.Rect(bx, y, bw, bh), f"First move: {first}")
        y += bh + gap
        self.menu_buttons["difficulty"] = self._button(
            pygame.Rect(bx, y, bw, bh),
            f"Difficulty: {config.DIFFICULTY_LABELS[difficulty]}")
        y += bh + int(bh * 0.16)
        hint = fonts.get(int(self.cell * 0.2))
        ht = hint.render(config.DIFFICULTY_SUBTEXT[difficulty], True, config.COLOR_HIGHLIGHT_SELECT)
        surf.blit(ht, (cx - ht.get_width() // 2, y))
        y += int(bh * 0.7)
        self.menu_buttons["flip"] = self._button(
            pygame.Rect(bx, y, bw, bh), "Board view: " + ("Flipped" if flipped else "Normal"))

        foot = fonts.get(int(self.cell * 0.2))
        ft = foot.render(f"v{config.VERSION}   -   Blue always moves first",
                         True, config.COLOR_TEXT_MUTED)
        surf.blit(ft, (cx - ft.get_width() // 2, self.H - int(self.cell * 0.6)))

    # -- game over overlay --------------------------------------------------

    def draw_game_over(self, gs, *, human_color, mode_ava) -> None:
        from engine.game_state import DRAW
        overlay = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        overlay.fill(config.COLOR_OVERLAY_BG)
        self.surface.blit(overlay, (0, 0))

        cx, cy = self.W // 2, int(self.H * 0.4)
        if gs.result == DRAW:
            msg, color = "Draw", config.COLOR_TEXT_LIGHT
        else:
            winner = gs.winner()
            wname = "Blue" if winner == Color.BLUE else "Black"
            if mode_ava:
                msg = f"{wname} wins!"
            else:
                msg = "You win!" if winner == human_color else f"{wname} wins - you lose"
            color = config.COLOR_BLUE_PIECE if winner == Color.BLUE else config.COLOR_HIGHLIGHT_SELECT

        big = fonts.get(int(self.cell * 0.8), bold=True)
        t = big.render(msg, True, color)
        self.surface.blit(t, (cx - t.get_width() // 2, cy - t.get_height() // 2))

        bw = int(self.W * 0.3)
        bh = max(40, int(self.cell * 0.6))
        gap = 20
        y = int(self.H * 0.56)
        self.over_buttons = {}
        self.over_buttons["again"] = self._button(
            pygame.Rect(cx - bw - gap // 2, y, bw, bh), "Play again", base=(70, 120, 90))
        self.over_buttons["quit"] = self._button(
            pygame.Rect(cx + gap // 2, y, bw, bh), "Quit", base=(140, 80, 80))
