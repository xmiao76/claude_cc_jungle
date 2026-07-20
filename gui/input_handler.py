"""Two-click board input, translating logical pixels to board squares.

All pixel coordinates arrive already in the renderer's logical coordinate space
(pygame's SCALED display maps mouse events into it), so this module only has to
undo the optional board flip.
"""

from __future__ import annotations

import config
from engine.board import Move
from engine.pieces import code_color

COLS = config.COLS
ROWS = config.ROWS


def pixel_to_board(px: int, py: int, flipped: bool) -> tuple[int, int] | None:
    """Return the ``(col, row)`` under the pixel, or ``None`` if off-board."""
    ox = config.BOARD_MARGIN
    oy = config.BOARD_MARGIN
    cell = config.CELL_SIZE
    dcol = (px - ox) // cell
    drow = (py - oy) // cell
    if not (0 <= dcol < COLS and 0 <= drow < ROWS):
        return None
    col = COLS - 1 - dcol if flipped else dcol
    row = ROWS - 1 - drow if flipped else drow
    return int(col), int(row)


class InputHandler:
    def __init__(self) -> None:
        self.selected: tuple[int, int] | None = None
        self.targets: list[Move] = []

    def reset(self) -> None:
        self.selected = None
        self.targets = []

    def target_squares(self) -> set[int]:
        return {m.to for m in self.targets}

    def handle_click(self, px: int, py: int, gs, human_color: int,
                     flipped: bool) -> Move | None:
        """Process a click. Returns a Move if one was completed, else None."""
        cell = pixel_to_board(px, py, flipped)
        if cell is None:
            self.reset()
            return None
        col, row = cell
        csq = col * ROWS + row

        # Completing a move: click on a highlighted target.
        if self.selected is not None:
            for m in self.targets:
                if m.to == csq:
                    self.reset()
                    return m

        # Otherwise (re)select one of our own pieces whose turn it is.
        code = gs.board.sq[csq]
        if code != 0 and code_color(code) == human_color and gs.to_move == human_color:
            self.selected = (col, row)
            self.targets = [m for m in gs.legal_moves() if m.frm == csq]
        else:
            self.reset()
        return None
