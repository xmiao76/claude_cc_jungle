"""Evaluation: antisymmetry, symmetric start = 0, and material sensitivity."""

import config
from ai.evaluator import _blue_score, evaluate
from engine.game_state import GameState
from engine.pieces import Animal, Color

BLUE = int(Color.BLUE)
BLACK = int(Color.BLACK)


def S(c, r):
    return c * config.ROWS + r


def test_symmetric_start_evaluates_to_zero():
    gs = GameState()
    assert _blue_score(gs.board) == 0
    assert evaluate(gs) == 0
    assert gs.board.eval_score == 0


def test_incremental_eval_matches_full_recompute():
    """board.eval_score (maintained on make/undo) must equal a full recompute
    at every step of random games, including after undo."""
    import random

    from engine.move_generator import generate_moves
    for seed in range(8):
        gs = GameState()
        rng = random.Random(seed)
        assert gs.board.eval_score == _blue_score(gs.board)
        played = 0
        for _ in range(80):
            if gs.game_over:
                break
            legal = generate_moves(gs.board, gs.to_move)
            if not legal:
                break
            gs.make_move(legal[rng.randrange(len(legal))])
            assert gs.board.eval_score == _blue_score(gs.board)
            played += 1
        for _ in range(played):
            gs.undo_move()
            assert gs.board.eval_score == _blue_score(gs.board)
        assert gs.board.eval_score == 0        # back to the symmetric start


def test_evaluate_is_antisymmetric_in_side_to_move():
    gs = GameState()
    gs.setup_position(
        {(3, 4): (BLUE, Animal.LION), (3, 6): (BLACK, Animal.WOLF)},
        to_move=BLUE,
    )
    blue_pov = evaluate(gs)
    gs.to_move = BLACK
    black_pov = evaluate(gs)
    assert blue_pov == -black_pov


def test_tiger_jump_readiness_excludes_four_row_only_squares():
    from config import HAS_JUMP, HAS_JUMP_TIGER
    s12 = S(1, 2)   # only a 4-row (Lion-only) jump originates here
    s04 = S(0, 4)   # a 3-col jump (Lion + Tiger) originates here
    assert HAS_JUMP[s12] and not HAS_JUMP_TIGER[s12]
    assert HAS_JUMP[s04] and HAS_JUMP_TIGER[s04]


def test_tiger_not_credited_for_a_jump_it_cannot_make():
    """A Tiger on a 4-row-only square must not get the jump-ready bonus (the
    bug the code review caught); a Lion on the same square does."""
    from config import EVAL_WEIGHTS, PIECE_VALUES
    gs = GameState()
    gs.setup_position({(1, 2): (BLUE, Animal.LION)}, to_move=BLUE)
    lion_score = _blue_score(gs.board)
    gs.setup_position({(1, 2): (BLUE, Animal.TIGER)}, to_move=BLUE)
    tiger_score = _blue_score(gs.board)
    material_gap = PIECE_VALUES[int(Animal.LION)] - PIECE_VALUES[int(Animal.TIGER)]
    # Only the Lion earns the jump bonus here, so the gap is material + jump_ready.
    assert lion_score - tiger_score == material_gap + EVAL_WEIGHTS["jump_ready"]


def test_extra_material_favors_that_side():
    gs = GameState()
    gs.setup_position(
        {(3, 4): (BLUE, Animal.ELEPHANT), (3, 5): (BLUE, Animal.RAT),
         (3, 2): (BLACK, Animal.ELEPHANT)},
        to_move=BLUE,
    )
    assert _blue_score(gs.board) > 0     # Blue is up a Rat
