"""Static exchange evaluation (ai/see.py)."""

import config
from ai.see import see
from engine.game_state import GameState
from engine.pieces import Animal, Color

BLUE = int(Color.BLUE)
BLACK = int(Color.BLACK)
V = config.PIECE_VALUES


def S(c, r):
    return c * config.ROWS + r


def test_free_capture_wins_the_victim():
    gs = GameState()
    gs.setup_position({(0, 1): (BLUE, Animal.LION), (0, 0): (BLACK, Animal.CAT)}, to_move=BLUE)
    assert see(gs.board, S(0, 1), S(0, 0)) == V[int(Animal.CAT)]


def test_capture_defended_by_stronger_piece_loses():
    # Lion takes Cat, but an adjacent Elephant recaptures the Lion.
    gs = GameState()
    gs.setup_position(
        {(0, 1): (BLUE, Animal.LION), (0, 0): (BLACK, Animal.CAT), (1, 0): (BLACK, Animal.ELEPHANT)},
        to_move=BLUE,
    )
    assert see(gs.board, S(0, 1), S(0, 0)) == V[int(Animal.CAT)] - V[int(Animal.LION)]


def test_equal_trade_is_zero():
    gs = GameState()
    gs.setup_position(
        {(0, 1): (BLUE, Animal.WOLF), (0, 0): (BLACK, Animal.WOLF), (1, 0): (BLACK, Animal.WOLF)},
        to_move=BLUE,
    )
    assert see(gs.board, S(0, 1), S(0, 0)) == 0


def test_defended_but_defender_too_weak_still_wins():
    # Lion takes Wolf; the only defender is a Cat that cannot capture the Lion.
    gs = GameState()
    gs.setup_position(
        {(0, 1): (BLUE, Animal.LION), (0, 0): (BLACK, Animal.WOLF), (1, 0): (BLACK, Animal.CAT)},
        to_move=BLUE,
    )
    assert see(gs.board, S(0, 1), S(0, 0)) == V[int(Animal.WOLF)]
