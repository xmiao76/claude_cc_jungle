"""Low-level board: a flat 63-square array plus incremental Zobrist hashing.

The board knows nothing about turns, draws, or win conditions — that lives in
``engine.game_state``. It only stores piece placement and supports the
allocation-free ``apply``/``revert`` primitives the search relies on.
"""

from __future__ import annotations

import random
from typing import NamedTuple

from config import NUM_SQUARES
from engine.pieces import EMPTY, code_color, make_code

# ---------------------------------------------------------------------------
# Zobrist tables (deterministic: fixed seed so hashes are reproducible)
# ---------------------------------------------------------------------------

_MAX_CODE = (1 << 4) | 8  # highest possible piece code (BLACK Elephant) == 24
_rng = random.Random(20240719)
ZOBRIST_PIECE = [
    [_rng.getrandbits(64) for _ in range(NUM_SQUARES)]
    for _ in range(_MAX_CODE + 1)
]
# XORed into the position key when it is Black's turn to move.
ZOBRIST_SIDE = _rng.getrandbits(64)


class Move(NamedTuple):
    """A move from ``frm`` to ``to``.

    ``captured`` is the code of the piece removed at ``to`` (0 for a quiet
    move). ``is_jump`` marks a Lion/Tiger river leap (used only for display).
    """

    frm: int
    to: int
    captured: int = 0
    is_jump: bool = False


class Board:
    __slots__ = ("sq", "zobrist")

    def __init__(self) -> None:
        self.sq = [EMPTY] * NUM_SQUARES
        self.zobrist = 0

    # -- construction -------------------------------------------------------

    def clear(self) -> None:
        self.sq = [EMPTY] * NUM_SQUARES
        self.zobrist = 0

    def place(self, square: int, code: int) -> None:
        """Place ``code`` on an empty square, updating the hash."""
        assert self.sq[square] == EMPTY, "place() onto an occupied square"
        self.sq[square] = code
        self.zobrist ^= ZOBRIST_PIECE[code][square]

    def set_piece(self, square: int, color: int, animal: int) -> None:
        self.place(square, make_code(color, animal))

    def remove(self, square: int) -> int:
        """Remove and return the code on ``square`` (0 if already empty)."""
        code = self.sq[square]
        if code != EMPTY:
            self.zobrist ^= ZOBRIST_PIECE[code][square]
            self.sq[square] = EMPTY
        return code

    # -- move application (allocation-free) ---------------------------------

    def apply(self, move: Move) -> None:
        """Apply ``move`` in place, updating the hash incrementally."""
        z = ZOBRIST_PIECE
        frm, to, captured = move.frm, move.to, move.captured
        mover = self.sq[frm]
        if captured != EMPTY:
            self.zobrist ^= z[captured][to]     # remove the captured piece
        self.zobrist ^= z[mover][frm]           # lift mover off frm
        self.zobrist ^= z[mover][to]            # drop mover on to
        self.sq[frm] = EMPTY
        self.sq[to] = mover

    def revert(self, move: Move) -> None:
        """Undo a move previously applied with :meth:`apply`."""
        z = ZOBRIST_PIECE
        frm, to, captured = move.frm, move.to, move.captured
        mover = self.sq[to]
        self.zobrist ^= z[mover][to]
        self.zobrist ^= z[mover][frm]
        self.sq[frm] = mover
        self.sq[to] = captured
        if captured != EMPTY:
            self.zobrist ^= z[captured][to]

    # -- queries ------------------------------------------------------------

    def piece_at(self, square: int) -> int:
        return self.sq[square]

    def iter_pieces(self, color: int | None = None):
        """Yield ``(square, code)`` for occupied squares (optionally by color)."""
        for s, code in enumerate(self.sq):
            if code != EMPTY and (color is None or code_color(code) == color):
                yield s, code

    def count(self, color: int) -> int:
        return sum(1 for code in self.sq if code != EMPTY and code_color(code) == color)

    def copy(self) -> Board:
        b = Board()
        b.sq = self.sq[:]
        b.zobrist = self.zobrist
        return b
