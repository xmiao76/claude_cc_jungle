"""Tests for GameState: undo/redo, turn tracking, copy."""

import pytest
from engine.board import Board, Move
from engine.game_state import GameState
from engine.pieces import Animal, Color, make_piece_id


# ---------------------------------------------------------------------------
# Test: Undo move restores identical board state
# ---------------------------------------------------------------------------

def test_undo_restores_state():
    gs = GameState()
    gs.new_game()

    # Capture the initial hash
    initial_hash = gs.board.hash
    initial_turn = gs.turn

    # Apply first move
    move = gs.legal_moves()[0]
    gs.apply_move(move)

    assert gs.board.hash != initial_hash
    assert gs.turn != initial_turn

    # Undo
    gs.undo_move()

    assert gs.board.hash == initial_hash, "Hash should be restored after undo"
    assert gs.turn == initial_turn, "Turn should be restored after undo"


def test_undo_restores_captured_piece():
    """After undoing a capture, the captured piece is restored."""
    gs = GameState()
    gs.board = Board()
    # Blue Wolf at (3,4), Black Cat at (3,3)
    wolf_pid = make_piece_id(Color.BLUE, Animal.WOLF)
    cat_pid = make_piece_id(Color.BLACK, Animal.CAT)
    gs.board._grid[3][4] = wolf_pid
    gs.board._grid[3][3] = cat_pid
    gs.board._piece_positions[int(Color.BLUE)][wolf_pid] = (3, 4)
    gs.board._piece_positions[int(Color.BLACK)][cat_pid] = (3, 3)
    gs.turn = Color.BLUE

    move = Move(3, 4, 3, 3, cat_pid)
    gs.apply_move(move)

    assert gs.board.get(3, 3) == wolf_pid
    assert cat_pid not in gs.board._piece_positions[int(Color.BLACK)]

    gs.undo_move()

    assert gs.board.get(3, 4) == wolf_pid, "Wolf should be back at source"
    assert gs.board.get(3, 3) == cat_pid, "Cat should be restored"
    assert cat_pid in gs.board._piece_positions[int(Color.BLACK)]


# ---------------------------------------------------------------------------
# Test: Turn alternates correctly
# ---------------------------------------------------------------------------

def test_turn_alternates():
    gs = GameState()
    gs.new_game()
    assert gs.turn == Color.BLUE

    move = gs.legal_moves()[0]
    gs.apply_move(move)
    assert gs.turn == Color.BLACK

    move2 = gs.legal_moves()[0]
    gs.apply_move(move2)
    assert gs.turn == Color.BLUE


# ---------------------------------------------------------------------------
# Test: copy produces independent state
# ---------------------------------------------------------------------------

def test_copy_is_independent():
    gs = GameState()
    gs.new_game()

    gs2 = gs.copy()

    # Modify original
    move = gs.legal_moves()[0]
    gs.apply_move(move)

    # Copy should be unchanged
    assert gs2.board.hash != gs.board.hash
    assert gs2.turn == Color.BLUE
    assert len(gs2.history) == 0


# ---------------------------------------------------------------------------
# Test: Zobrist hashes differ for different positions
# ---------------------------------------------------------------------------

def test_zobrist_different_positions():
    gs = GameState()
    gs.new_game()

    hashes = set()
    for move in gs.legal_moves()[:10]:
        gs.apply_move(move)
        hashes.add(gs.board.hash)
        gs.undo_move()

    assert len(hashes) == len(gs.legal_moves()[:10]), "Different positions should have different hashes"


# ---------------------------------------------------------------------------
# Test: Multiple undos work correctly
# ---------------------------------------------------------------------------

def test_multiple_undos():
    gs = GameState()
    gs.new_game()
    initial_hash = gs.board.hash

    moves_applied = []
    for _ in range(6):
        move = gs.legal_moves()[0]
        gs.apply_move(move)
        moves_applied.append(move)

    for _ in range(6):
        gs.undo_move()

    assert gs.board.hash == initial_hash
    assert gs.turn == Color.BLUE
    assert len(gs.history) == 0
