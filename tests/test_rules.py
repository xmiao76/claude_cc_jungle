"""Capture-legality rules: ranks, the Rat/Elephant exception, water, traps."""

import config
from engine.pieces import Animal, Color
from engine.rules import can_capture, is_trapped

BLUE = int(Color.BLUE)
BLACK = int(Color.BLACK)


def S(c, r):
    return c * config.ROWS + r


# Land square helpers (rows 0-2 and 6-8 are all land).
A = S(3, 1)   # attacker square (land)
D = S(3, 2)   # defender square (land, adjacent)


def cap(atk_animal, def_animal, atk_sq=A, def_sq=D, atk_color=BLUE, def_color=BLACK):
    return can_capture(atk_color, int(atk_animal), atk_sq,
                       def_color, int(def_animal), def_sq)


def test_higher_rank_captures_lower():
    assert cap(Animal.LION, Animal.WOLF)
    assert cap(Animal.ELEPHANT, Animal.LION)


def test_equal_rank_captures():
    assert cap(Animal.WOLF, Animal.WOLF)


def test_lower_rank_cannot_capture_higher():
    assert not cap(Animal.WOLF, Animal.LION)
    assert not cap(Animal.CAT, Animal.DOG)


def test_rat_captures_elephant():
    assert cap(Animal.RAT, Animal.ELEPHANT)


def test_elephant_cannot_capture_rat():
    assert not cap(Animal.ELEPHANT, Animal.RAT)


def test_no_capture_across_water_boundary():
    # Attacker on land, defender (rat) in the river -> blocked.
    land = S(0, 3)     # col 0, row 3 is a land bridge beside the river
    water = S(1, 3)    # river square
    assert config.IS_RIVER[water] and not config.IS_RIVER[land]
    assert not can_capture(BLUE, int(Animal.LION), land,
                           BLACK, int(Animal.RAT), water)
    # And the reverse: rat in water cannot capture a land piece.
    assert not can_capture(BLUE, int(Animal.RAT), water,
                           BLACK, int(Animal.ELEPHANT), land)


def test_rat_versus_rat_in_same_water():
    w1 = S(1, 3)
    w2 = S(1, 4)
    assert config.IS_RIVER[w1] and config.IS_RIVER[w2]
    assert can_capture(BLUE, int(Animal.RAT), w1, BLACK, int(Animal.RAT), w2)


def test_trapped_piece_is_capturable_by_anyone():
    # A Black piece standing on one of Blue's traps has rank 0.
    trap = S(3, 7)     # a Blue trap (around Blue's den)
    assert is_trapped(BLACK, trap)          # Black piece here is trapped
    assert not is_trapped(BLUE, trap)       # a Blue piece on its own trap is not
    attacker_sq = S(3, 6)                   # adjacent land
    # Even a Cat can take a trapped Elephant.
    assert can_capture(BLUE, int(Animal.CAT), attacker_sq,
                       BLACK, int(Animal.ELEPHANT), trap)


def test_elephant_takes_trapped_rat():
    """Trap rule overrides the Rat/Elephant exception."""
    trap = S(2, 8)     # a Blue trap
    attacker_sq = S(2, 7)
    assert can_capture(BLUE, int(Animal.ELEPHANT), attacker_sq,
                       BLACK, int(Animal.RAT), trap)
