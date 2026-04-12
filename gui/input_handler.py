"""Mouse input handling: translates pygame events to board actions."""

from __future__ import annotations

from config import COLS, ROWS, CELL_SIZE, BOARD_OFFSET_X, BOARD_OFFSET_Y
from engine.board import Move
from engine.pieces import Color, piece_id_color


def pixel_to_board(px: int, py: int) -> tuple[int, int] | None:
    """Convert pixel coordinates to (col, row). Returns None if outside board."""
    col = (px - BOARD_OFFSET_X) // CELL_SIZE
    row = (py - BOARD_OFFSET_Y) // CELL_SIZE
    if 0 <= col < COLS and 0 <= row < ROWS:
        return col, row
    return None


class InputHandler:
    """Two-click selection model.

    Click 1: select own piece → show legal moves
    Click 2: click legal target → execute move, OR click elsewhere/own piece → reselect
    """

    def __init__(self) -> None:
        self.selected: tuple[int, int] | None = None
        self.legal_targets: set[tuple[int, int]] = set()
        self._legal_moves_list: list[Move] = []

    def reset(self) -> None:
        self.selected = None
        self.legal_targets = set()
        self._legal_moves_list = []

    def handle_click(
        self,
        px: int,
        py: int,
        state,
        human_color: Color,
    ) -> Move | None:
        """Process a left-click at pixel (px, py).

        Returns a Move if the click completes a valid move, else None.
        """
        sq = pixel_to_board(px, py)
        if sq is None:
            self.reset()
            return None

        col, row = sq

        # If clicking a legal target → execute move
        if self.selected and sq in self.legal_targets:
            move = self._find_move(col, row)
            self.reset()
            return move

        # Try to select a piece
        pid = state.board.get(col, row)
        if pid != 0 and piece_id_color(pid) == human_color:
            # Select this piece and compute its legal moves
            all_moves = state.legal_moves()
            piece_moves = [m for m in all_moves if m.fc == col and m.fr == row]
            if piece_moves:
                self.selected = (col, row)
                self.legal_targets = {(m.tc, m.tr) for m in piece_moves}
                self._legal_moves_list = piece_moves
                return None
            else:
                # Piece has no legal moves — deselect
                self.reset()
                return None

        # Clicked empty or enemy square — deselect
        self.reset()
        return None

    def _find_move(self, tc: int, tr: int) -> Move | None:
        for m in self._legal_moves_list:
            if m.tc == tc and m.tr == tr:
                return m
        return None
