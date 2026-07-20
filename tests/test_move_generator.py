"""Move generation: steps, river entry, and the Lion/Tiger jump ruleset."""

import config
from engine.game_state import GameState
from engine.move_generator import generate_moves
from engine.pieces import Animal, Color

BLUE = int(Color.BLUE)
BLACK = int(Color.BLACK)


def S(c, r):
    return c * config.ROWS + r


def targets_from(gs, color, frm):
    """Set of destination squares for the piece on ``frm``."""
    return {m.to for m in generate_moves(gs.board, color) if m.frm == frm}


def test_only_rat_may_enter_river():
    gs = GameState()
    # Rat and Dog both sit at (1,2), just above a river square (1,3).
    gs.setup_position({(1, 2): (BLUE, Animal.RAT)}, to_move=BLUE)
    assert S(1, 3) in targets_from(gs, BLUE, S(1, 2))     # Rat may swim in

    gs.setup_position({(1, 2): (BLUE, Animal.DOG)}, to_move=BLUE)
    assert S(1, 3) not in targets_from(gs, BLUE, S(1, 2))  # Dog may not


def test_lion_four_row_jump_along_column():
    gs = GameState()
    gs.setup_position({(1, 2): (BLUE, Animal.LION)}, to_move=BLUE)
    # Lion leaps the 3 river rows (rows 3,4,5) landing 4 rows away at (1,6).
    assert S(1, 6) in targets_from(gs, BLUE, S(1, 2))


def test_lion_three_col_jump_along_row():
    gs = GameState()
    gs.setup_position({(0, 4): (BLUE, Animal.LION)}, to_move=BLUE)
    # Lion leaps the 2 river cols (cols 1,2) landing 3 cols away at (3,4).
    assert S(3, 4) in targets_from(gs, BLUE, S(0, 4))


def test_tiger_can_make_three_col_jump():
    gs = GameState()
    gs.setup_position({(0, 4): (BLUE, Animal.TIGER)}, to_move=BLUE)
    assert S(3, 4) in targets_from(gs, BLUE, S(0, 4))


def test_tiger_cannot_make_four_row_jump():
    gs = GameState()
    gs.setup_position({(1, 2): (BLUE, Animal.TIGER)}, to_move=BLUE)
    # The Tiger is restricted to the "3 cols" jump; it may NOT leap 4 rows.
    assert S(1, 6) not in targets_from(gs, BLUE, S(1, 2))


def test_rat_blocks_four_row_jump():
    gs = GameState()
    gs.setup_position(
        {(1, 2): (BLUE, Animal.LION), (1, 4): (BLACK, Animal.RAT)},
        to_move=BLUE,
    )
    # A Rat anywhere on the water path blocks the leap.
    assert S(1, 6) not in targets_from(gs, BLUE, S(1, 2))


def test_rat_blocks_three_col_jump():
    gs = GameState()
    gs.setup_position(
        {(0, 4): (BLUE, Animal.LION), (2, 4): (BLUE, Animal.RAT)},
        to_move=BLUE,
    )
    assert S(3, 4) not in targets_from(gs, BLUE, S(0, 4))


def test_jump_can_capture_on_landing():
    gs = GameState()
    gs.setup_position(
        {(1, 2): (BLUE, Animal.LION), (1, 6): (BLACK, Animal.WOLF)},
        to_move=BLUE,
    )
    # Landing square holds a weaker enemy -> capturing jump is legal.
    assert S(1, 6) in targets_from(gs, BLUE, S(1, 2))


def test_jump_cannot_capture_stronger_on_landing():
    gs = GameState()
    gs.setup_position(
        {(1, 2): (BLUE, Animal.TIGER), (0, 4): (BLUE, Animal.LION),
         (1, 6): (BLACK, Animal.ELEPHANT)},
        to_move=BLUE,
    )
    # Lion jump onto a stronger Elephant is illegal.
    assert S(1, 6) not in targets_from(gs, BLUE, S(0, 4)) | targets_from(gs, BLUE, S(1, 2))


def test_cannot_enter_own_den():
    gs = GameState()
    gs.setup_position({(3, 7): (BLUE, Animal.DOG)}, to_move=BLUE)
    # (3,8) is Blue's own den -> illegal target.
    assert S(3, 8) not in targets_from(gs, BLUE, S(3, 7))


def test_may_step_into_enemy_den():
    gs = GameState()
    gs.setup_position({(3, 1): (BLUE, Animal.RAT)}, to_move=BLUE)
    # (3,0) is Black's den -> a legal (winning) move for Blue.
    assert S(3, 0) in targets_from(gs, BLUE, S(3, 1))
