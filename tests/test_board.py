"""Board encoding, Zobrist hashing, and apply/revert reversibility."""

import config
from engine.board import Board, Move
from engine.pieces import Animal, Color, code_animal, code_color, make_code


def S(c, r):
    return c * config.ROWS + r


def test_piece_encoding_roundtrip():
    for color in (Color.BLUE, Color.BLACK):
        for animal in Animal:
            code = make_code(int(color), int(animal))
            assert code_color(code) == int(color)
            assert code_animal(code) == int(animal)


def test_place_remove_hash_symmetry():
    b = Board()
    assert b.zobrist == 0
    b.set_piece(S(3, 4), int(Color.BLUE), int(Animal.LION))
    assert b.zobrist != 0
    b.remove(S(3, 4))
    assert b.zobrist == 0  # placing then removing cancels out


def test_distinct_tokens_per_color():
    """A Blue and a Black piece of the same animal on the same square must
    hash differently (guards against a classic Zobrist bug)."""
    b1 = Board()
    b1.set_piece(S(2, 2), int(Color.BLUE), int(Animal.RAT))
    b2 = Board()
    b2.set_piece(S(2, 2), int(Color.BLACK), int(Animal.RAT))
    assert b1.zobrist != b2.zobrist


def test_apply_revert_restores_board_and_hash():
    b = Board()
    b.set_piece(S(0, 0), int(Color.BLUE), int(Animal.LION))
    b.set_piece(S(0, 1), int(Color.BLACK), int(Animal.WOLF))
    before_sq = b.sq[:]
    before_hash = b.zobrist

    capture = b.sq[S(0, 1)]
    mv = Move(S(0, 0), S(0, 1), capture)   # Lion captures Wolf
    b.apply(mv)
    assert b.sq[S(0, 0)] == 0
    assert code_animal(b.sq[S(0, 1)]) == int(Animal.LION)
    assert b.zobrist != before_hash

    b.revert(mv)
    assert b.sq == before_sq
    assert b.zobrist == before_hash
