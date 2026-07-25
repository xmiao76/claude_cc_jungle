"""Test-side helpers: position builders plus shared invariant assertions.

The position builders live in :mod:`tools.positions` so the strength harness can
use them too; they are re-exported here so tests have a single import.
"""

from __future__ import annotations

from config import COLS, ROWS
from engine.board import Board
from engine.game_state import GameState
from engine.pieces import Color
from tools.positions import (  # (re-exported for tests)
    FIXED_MIDGAME,
    PieceSpec,
    empty_board,
    fixed_midgame,
    make_gs,
    place,
    recompute_hash,
)

__all__ = [
    "FIXED_MIDGAME",
    "PieceSpec",
    "apply_step",
    "assert_board_consistent",
    "empty_board",
    "find_move",
    "fixed_midgame",
    "make_gs",
    "place",
    "recompute_hash",
]


def assert_board_consistent(board: Board) -> None:
    """Assert the grid, the piece-position index and the hash all agree.

    Three independent representations of the same state have to line up:
    ``_grid`` (what `get` reads), ``_piece_positions`` (what move generation
    iterates) and ``hash`` (what the TT, repetition detection and the opening
    book key on). A divergence between them is silent in play but corrupts
    search, so this is the invariant to lean on when changing the board.
    """
    assert board.hash == recompute_hash(board), "incremental Zobrist hash diverged"

    on_grid: dict[int, tuple[int, int]] = {}
    for c in range(COLS):
        for r in range(ROWS):
            pid = board.get(c, r)
            if pid != 0:
                assert pid not in on_grid, f"piece {pid} appears twice on the grid"
                on_grid[pid] = (c, r)

    tracked: dict[int, tuple[int, int]] = {}
    for color in (Color.BLUE, Color.BLACK):
        for pid, pos in board.pieces_of(color).items():
            assert pid != 0, "piece_id 0 leaked into the position index"
            assert (pid > 0) == (color == Color.BLUE), f"piece {pid} filed under {color.name}"
            tracked[pid] = pos

    assert tracked == on_grid, (
        f"position index disagrees with the grid: index={tracked} grid={on_grid}"
    )


def find_move(gs: GameState, fc: int, fr: int, tc: int, tr: int):
    """Return the legal move matching these coordinates, or None."""
    for m in gs.legal_moves():
        if (m.fc, m.fr, m.tc, m.tr) == (fc, fr, tc, tr):
            return m
    return None


def apply_step(gs: GameState, fc: int, fr: int, tc: int, tr: int) -> None:
    """Apply the legal move matching these coordinates; raise if it is illegal."""
    move = find_move(gs, fc, fr, tc, tr)
    if move is None:
        raise AssertionError(f"({fc},{fr}) -> ({tc},{tr}) is not legal for {gs.turn.name}")
    gs.apply_move(move)
