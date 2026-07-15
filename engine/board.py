"""Board state representation for Jungle.

The board is a 7-column × 9-row grid stored as a 2-D list of ints.
  board[col][row] = piece_id  (0 = empty, >0 = Blue piece, <0 = Black piece)
  piece_id magnitude = Animal rank (1=Rat … 8=Elephant)

Zobrist hashing is updated incrementally on make_move / unmake_move.
"""

from __future__ import annotations

import random
from typing import NamedTuple

from config import (
    COLS, ROWS, TERRAIN,
)
from engine.pieces import (
    Color, STARTING_POSITIONS,
    make_piece_id, piece_id_color,
)

# ---------------------------------------------------------------------------
# Move representation
# ---------------------------------------------------------------------------

class Move(NamedTuple):
    fc: int         # from col
    fr: int         # from row
    tc: int         # to col
    tr: int         # to row
    captured: int   # piece_id of captured piece (0 if none)


# ---------------------------------------------------------------------------
# Zobrist table
# ---------------------------------------------------------------------------

_RNG = random.Random(0xDEADBEEF)

# zobrist_table[col][row][piece_id_index]
# piece_id_index maps: pid in range -8..-1, 1..8 → index 0..15
def _pid_index(pid: int) -> int:
    return pid + 8 if pid < 0 else pid - 1  # -8→0, -1→7, 1→8, 8→15

_ZOBRIST: list[list[list[int]]] = [
    [[_RNG.getrandbits(64) for _ in range(16)] for _ in range(ROWS)]
    for _ in range(COLS)
]
_ZOBRIST_TURN = _RNG.getrandbits(64)   # XOR this when it's Black's turn


# ---------------------------------------------------------------------------
# Board
# ---------------------------------------------------------------------------

class Board:
    """Mutable board state supporting incremental Zobrist hashing."""

    __slots__ = ("_grid", "hash", "_piece_positions")

    def __init__(self) -> None:
        # _grid[col][row] = piece_id
        self._grid: list[list[int]] = [[0] * ROWS for _ in range(COLS)]
        self.hash: int = 0
        # _piece_positions[color] = dict of piece_id -> (col, row)
        self._piece_positions: list[dict[int, tuple[int, int]]] = [{}, {}]

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def setup_starting_position(self) -> None:
        """Place all pieces in their standard starting positions."""
        self._grid = [[0] * ROWS for _ in range(COLS)]
        self.hash = 0
        self._piece_positions = [{}, {}]
        for (c, r, color, animal) in STARTING_POSITIONS:
            pid = make_piece_id(color, animal)
            self._grid[c][r] = pid
            self.hash ^= _ZOBRIST[c][r][_pid_index(pid)]
            self._piece_positions[int(color)][pid] = (c, r)

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def get(self, c: int, r: int) -> int:
        return self._grid[c][r]

    def is_empty(self, c: int, r: int) -> bool:
        return self._grid[c][r] == 0

    def in_bounds(self, c: int, r: int) -> bool:
        return 0 <= c < COLS and 0 <= r < ROWS

    def terrain(self, c: int, r: int) -> int:
        return TERRAIN[c][r]

    def pieces_of(self, color: Color) -> dict[int, tuple[int, int]]:
        """Return {piece_id: (col, row)} for all living pieces of color."""
        return self._piece_positions[int(color)]

    def alive_count(self, color: Color) -> int:
        return len(self._piece_positions[int(color)])

    # ------------------------------------------------------------------
    # Move application / undo
    # ------------------------------------------------------------------

    def make_move(self, move: Move) -> None:
        """Apply move in-place (updates grid and Zobrist hash)."""
        pid = self._grid[move.fc][move.fr]
        captured = move.captured

        # Remove mover from source
        self._grid[move.fc][move.fr] = 0
        self.hash ^= _ZOBRIST[move.fc][move.fr][_pid_index(pid)]

        # Remove captured piece from tracking
        if captured:
            cap_color = int(piece_id_color(captured))
            self._piece_positions[cap_color].pop(captured, None)
            self.hash ^= _ZOBRIST[move.tc][move.tr][_pid_index(captured)]

        # Place mover at destination
        self._grid[move.tc][move.tr] = pid
        self.hash ^= _ZOBRIST[move.tc][move.tr][_pid_index(pid)]

        # Update position tracking
        mover_color = int(piece_id_color(pid))
        self._piece_positions[mover_color][pid] = (move.tc, move.tr)

    def unmake_move(self, move: Move) -> None:
        """Undo a previously made move (exact inverse of make_move)."""
        pid = self._grid[move.tc][move.tr]
        captured = move.captured

        # Remove mover from destination
        self._grid[move.tc][move.tr] = 0
        self.hash ^= _ZOBRIST[move.tc][move.tr][_pid_index(pid)]

        # Restore captured piece
        if captured:
            cap_color = int(piece_id_color(captured))
            self._grid[move.tc][move.tr] = captured
            self.hash ^= _ZOBRIST[move.tc][move.tr][_pid_index(captured)]
            self._piece_positions[cap_color][captured] = (move.tc, move.tr)

        # Restore mover at source
        self._grid[move.fc][move.fr] = pid
        self.hash ^= _ZOBRIST[move.fc][move.fr][_pid_index(pid)]

        # Update position tracking
        mover_color = int(piece_id_color(pid))
        self._piece_positions[mover_color][pid] = (move.fc, move.fr)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def copy(self) -> "Board":
        b = Board()
        b._grid = [col[:] for col in self._grid]
        b.hash = self.hash
        b._piece_positions = [dict(d) for d in self._piece_positions]
        return b

    def turn_hash(self, color: Color) -> int:
        """Full position hash including whose turn it is."""
        return self.hash ^ (_ZOBRIST_TURN if color == Color.BLACK else 0)
