"""Regression tests for the Zobrist piece-id → key-slot mapping.

`_pid_index` used to read ``pid + 8 if pid < 0 else pid - 1``. Both branches land
in 0..7, so the 16 piece ids only ever addressed 8 of the 16 key slots per square
and each Blue piece shared its key with the Black piece of complementary rank.
Two genuinely different legal positions could therefore hash identically, which
silently corrupts the transposition table, `is_repetition()` and the opening book.

`assert_board_consistent` cannot catch this: `recompute_hash` calls the same
`_pid_index`, so a wrong-but-consistent mapping passes. These tests check the
mapping itself and the property that actually matters — distinct positions get
distinct hashes.
"""

from __future__ import annotations

import itertools

from engine.board import _ZOBRIST, _pid_index
from engine.pieces import Animal, Color, make_piece_id
from tests.helpers import assert_board_consistent, make_gs

ALL_PIDS = [pid for pid in range(-8, 9) if pid != 0]


def test_every_piece_id_gets_a_distinct_index():
    """All 16 ids must address 16 different slots, and stay in range."""
    indices = {pid: _pid_index(pid) for pid in ALL_PIDS}
    assert len(set(indices.values())) == 16, f"index collision: {indices}"
    assert all(0 <= i < 16 for i in indices.values()), f"index out of range: {indices}"


def test_index_matches_the_documented_mapping():
    """The mapping the module comment promises: -8→0, -1→7, 1→8, 8→15."""
    assert _pid_index(-8) == 0
    assert _pid_index(-1) == 7
    assert _pid_index(1) == 8
    assert _pid_index(8) == 15


def test_every_square_and_piece_pair_has_a_distinct_key():
    """No two (square, piece) combinations may share a Zobrist key."""
    keys = [
        _ZOBRIST[c][r][_pid_index(pid)]
        for c in range(7)
        for r in range(9)
        for pid in ALL_PIDS
    ]
    assert len(set(keys)) == len(keys) == 63 * 16


def test_swapping_complementary_ranks_changes_the_hash():
    """The exact bug: Blue rank r and Black rank 9-r shared a key slot.

    Placing the pair on two squares and then swapping them produced a
    bit-identical hash under the old mapping, for all eight pairs — worst of all
    Rat/Elephant, the two pieces with a special capture rule between them.
    """
    for rank in range(1, 9):
        blue, black = Animal(rank), Animal(9 - rank)
        left, right = (0, 4), (6, 4)  # both land squares

        p1 = make_gs((*left, Color.BLUE, blue), (*right, Color.BLACK, black))
        p2 = make_gs((*right, Color.BLUE, blue), (*left, Color.BLACK, black))

        assert p1.board.grid != p2.board.grid, "positions should differ"
        assert p1.board.turn_hash(p1.turn) != p2.board.turn_hash(p2.turn), (
            f"Blue {blue.name} / Black {black.name} swap collides"
        )


def test_same_square_different_piece_hashes_differently():
    """Every pair of distinct pieces on the same square must hash differently."""
    hashes = {}
    for color, animal in itertools.product(Color, Animal):
        gs = make_gs((3, 4, color, animal))
        pid = make_piece_id(color, animal)
        hashes[pid] = gs.board.hash
    assert len(set(hashes.values())) == 16, f"collision among {hashes}"


def test_incremental_hash_survives_a_capture_round_trip():
    """make_move/unmake_move must restore the hash exactly, per piece pair."""
    for rank in range(1, 9):
        gs = make_gs(
            (3, 4, Color.BLUE, Animal(rank)),
            (3, 5, Color.BLACK, Animal(9 - rank)),
        )
        before = gs.board.hash
        assert_board_consistent(gs.board)

        for move in gs.legal_moves():
            gs.apply_move(move)
            assert_board_consistent(gs.board)
            gs.undo_move()
            assert gs.board.hash == before, f"hash not restored after {move}"
            assert_board_consistent(gs.board)
