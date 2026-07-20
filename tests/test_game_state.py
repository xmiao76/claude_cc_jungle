"""Game state: initial layout, win/draw detection, and undo reversibility."""

import config
from engine.game_state import DRAW, GameState
from engine.move_generator import generate_moves
from engine.pieces import Animal, Color

BLUE = int(Color.BLUE)
BLACK = int(Color.BLACK)


def S(c, r):
    return c * config.ROWS + r


def test_initial_layout_corners_and_counts():
    gs = GameState()
    assert gs.to_move == BLUE
    assert gs.counts == [8, 8]
    assert gs.piece_at(0, 0) == (Color.BLACK, Animal.LION)
    assert gs.piece_at(6, 0) == (Color.BLACK, Animal.TIGER)
    assert gs.piece_at(0, 8) == (Color.BLUE, Animal.TIGER)
    assert gs.piece_at(6, 8) == (Color.BLUE, Animal.LION)
    # Rat/Elephant on the rank nearest the river.
    assert gs.piece_at(0, 2) == (Color.BLACK, Animal.RAT)
    assert gs.piece_at(6, 2) == (Color.BLACK, Animal.ELEPHANT)


def test_initial_position_is_symmetric_move_count():
    """Blue and Black have the same number of legal moves at the start."""
    gs = GameState()
    blue_moves = len(generate_moves(gs.board, BLUE))
    black_moves = len(generate_moves(gs.board, BLACK))
    assert blue_moves == black_moves


def test_den_entry_wins():
    gs = GameState()
    gs.setup_position(
        {(3, 1): (BLUE, Animal.RAT), (6, 6): (BLACK, Animal.WOLF)},
        to_move=BLUE,
    )
    move = next(m for m in gs.legal_moves() if m.to == S(3, 0))
    gs.make_move(move)
    assert gs.game_over
    assert gs.winner() == Color.BLUE


def test_capturing_last_piece_wins():
    gs = GameState()
    gs.setup_position(
        {(0, 0): (BLUE, Animal.LION), (0, 1): (BLACK, Animal.CAT)},
        to_move=BLUE,
    )
    move = next(m for m in gs.legal_moves() if m.to == S(0, 1))
    gs.make_move(move)
    assert gs.winner() == Color.BLUE
    assert gs.counts[BLACK] == 0


def test_stalemate_is_a_loss_for_side_to_move():
    gs = GameState()
    # Black to move; after Dog (2,0)->(1,0) the lone Blue Rat at (0,0) is boxed
    # in by two Black Dogs it cannot capture -> Blue has no move and loses.
    gs.setup_position(
        {(0, 0): (BLUE, Animal.RAT), (0, 1): (BLACK, Animal.DOG),
         (2, 0): (BLACK, Animal.DOG)},
        to_move=BLACK,
    )
    move = next(m for m in gs.legal_moves() if m.frm == S(2, 0) and m.to == S(1, 0))
    gs.make_move(move)
    assert gs.game_over
    assert gs.winner() == Color.BLACK


def test_threefold_repetition_is_a_draw():
    gs = GameState()
    gs.setup_position(
        {(0, 0): (BLUE, Animal.LION), (6, 8): (BLACK, Animal.LION)},
        to_move=BLUE,
    )
    # Shuffle both lions back and forth; the start position recurs every 4 plies.
    cycle = [
        (S(0, 0), S(0, 1)), (S(6, 8), S(6, 7)),
        (S(0, 1), S(0, 0)), (S(6, 7), S(6, 8)),
    ]
    for _ in range(2):          # two full cycles -> position seen 3 times total
        for frm, to in cycle:
            if gs.game_over:
                break
            mv = next(m for m in gs.legal_moves() if m.frm == frm and m.to == to)
            gs.make_move(mv)
    assert gs.result == DRAW


def test_no_capture_limit_is_a_draw():
    gs = GameState()
    gs.setup_position(
        {(0, 0): (BLUE, Animal.LION), (6, 8): (BLACK, Animal.LION)},
        to_move=BLUE,
    )
    gs.halfmove_clock = 99     # one ply short of the no-capture limit
    mv = next(m for m in gs.legal_moves() if m.frm == S(0, 0))
    gs.make_move(mv)            # 100th no-capture ply
    assert gs.result == DRAW


def test_undo_restores_state_exactly():
    gs = GameState()
    before_sq = gs.board.sq[:]
    before_hash = gs.hash
    before_counts = gs.counts[:]

    # Play a handful of legal moves then undo them all.
    played = 0
    for _ in range(6):
        moves = gs.legal_moves()
        if not moves:
            break
        gs.make_move(moves[len(moves) // 2])
        played += 1
    for _ in range(played):
        gs.undo_move()

    assert gs.board.sq == before_sq
    assert gs.hash == before_hash
    assert gs.counts == before_counts
    assert gs.to_move == BLUE
    assert gs.result is None
