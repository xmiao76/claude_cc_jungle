"""Tests for capture legality and terrain effects."""

from config import TRAPS_BLACK, TRAPS_BLUE
from engine.board import Board
from engine.move_generator import generate_legal_moves
from engine.pieces import Animal, Color, make_piece_id
from engine.rules import can_capture, effective_rank
from tests.helpers import place

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# Test: Higher rank captures lower rank
# ---------------------------------------------------------------------------

def test_higher_rank_captures_lower():
    b = Board()
    atk = make_piece_id(Color.BLUE, Animal.LION)    # rank 7
    def_ = make_piece_id(Color.BLACK, Animal.LEOPARD)  # rank 5
    assert can_capture(atk, def_, 3, 4, 3, 3, b)


def test_equal_rank_captures():
    b = Board()
    atk = make_piece_id(Color.BLUE, Animal.WOLF)   # rank 4
    def_ = make_piece_id(Color.BLACK, Animal.WOLF)  # rank 4
    assert can_capture(atk, def_, 3, 4, 3, 3, b)


def test_lower_rank_cannot_capture():
    b = Board()
    atk = make_piece_id(Color.BLUE, Animal.CAT)       # rank 2
    def_ = make_piece_id(Color.BLACK, Animal.LEOPARD)  # rank 5
    assert not can_capture(atk, def_, 3, 4, 3, 3, b)


# ---------------------------------------------------------------------------
# Test: Rat (land) captures Elephant (land)
# ---------------------------------------------------------------------------

def test_rat_land_captures_elephant_land():
    b = Board()
    rat = make_piece_id(Color.BLUE, Animal.RAT)       # rank 1
    ele = make_piece_id(Color.BLACK, Animal.ELEPHANT)  # rank 8
    # Both on land squares
    assert can_capture(rat, ele, 0, 0, 0, 1, b), "Rat on land should capture Elephant on land"


# ---------------------------------------------------------------------------
# Test: Elephant (land) cannot capture Rat (land)
# ---------------------------------------------------------------------------

def test_elephant_cannot_capture_rat():
    b = Board()
    ele = make_piece_id(Color.BLUE, Animal.ELEPHANT)
    rat = make_piece_id(Color.BLACK, Animal.RAT)
    assert not can_capture(ele, rat, 0, 0, 0, 1, b), "Elephant should NOT capture Rat"


# ---------------------------------------------------------------------------
# Test: Rat in water cannot capture Elephant on land
# ---------------------------------------------------------------------------

def test_rat_water_cannot_capture_elephant_land():
    b = Board()
    rat = make_piece_id(Color.BLUE, Animal.RAT)
    ele = make_piece_id(Color.BLACK, Animal.ELEPHANT)
    # Rat at (1,4) = river, Elephant at (0,4) = land
    assert not can_capture(rat, ele, 1, 4, 0, 4, b), "Rat in water should NOT capture Elephant on land"


# ---------------------------------------------------------------------------
# Test: Rat on land cannot capture Rat in water
# ---------------------------------------------------------------------------

def test_rat_land_cannot_capture_rat_water():
    b = Board()
    rat_blue = make_piece_id(Color.BLUE, Animal.RAT)
    rat_black = make_piece_id(Color.BLACK, Animal.RAT)
    # Blue rat at (0,4) = land, Black rat at (1,4) = river
    assert not can_capture(rat_blue, rat_black, 0, 4, 1, 4, b), "Land rat should NOT capture water rat"


# ---------------------------------------------------------------------------
# Test: Rat in water can capture Rat in water
# ---------------------------------------------------------------------------

def test_rat_water_captures_rat_water():
    b = Board()
    rat_blue = make_piece_id(Color.BLUE, Animal.RAT)
    rat_black = make_piece_id(Color.BLACK, Animal.RAT)
    # Both in river: (1,3) and (1,4) are both river squares
    assert can_capture(rat_blue, rat_black, 1, 3, 1, 4, b), "Water rat should capture water rat"


# ---------------------------------------------------------------------------
# Test: Piece in opponent trap has effective rank 0
# ---------------------------------------------------------------------------

def test_piece_in_opponent_trap_rank_zero():
    # Blue trap squares: (2,8),(4,8),(3,7)
    # A Black piece in a Blue trap has effective rank 0
    black_elephant = make_piece_id(Color.BLACK, Animal.ELEPHANT)
    trap_col, trap_row = 2, 8  # Blue trap
    rank = effective_rank(black_elephant, trap_col, trap_row)
    assert rank == 0, "Piece in opponent trap should have effective rank 0"


def test_any_piece_captures_trapped_piece():
    """*Every* animal must be able to take a rank-0 piece — including the pairs
    that the Rat/Elephant exception would otherwise forbid.

    Previously this only checked Rat-takes-trapped-Elephant, which passes via
    the Rat-beats-Elephant exception rather than via the trap rule, so it could
    not detect the Elephant-vs-trapped-Rat defect.
    """
    b = Board()
    trap_col, trap_row = 2, 8            # a Blue trap
    atk_col, atk_row = 2, 7              # adjacent land square
    for victim in Animal:
        victim_pid = make_piece_id(Color.BLACK, victim)
        for attacker in Animal:
            atk_pid = make_piece_id(Color.BLUE, attacker)
            assert can_capture(atk_pid, victim_pid,
                               atk_col, atk_row, trap_col, trap_row, b), \
                f"{attacker.name} should capture trapped {victim.name} (rank 0)"


# ---------------------------------------------------------------------------
# Test: Piece in OWN trap has normal rank (no reduction)
# ---------------------------------------------------------------------------

def test_piece_in_own_trap_normal_rank():
    # Blue piece in Blue trap — own trap, no rank reduction
    blue_cat = make_piece_id(Color.BLUE, Animal.CAT)
    own_trap_col, own_trap_row = 2, 8  # Blue trap
    rank = effective_rank(blue_cat, own_trap_col, own_trap_row)
    assert rank == Animal.CAT, "Piece in own trap should retain normal rank"


# ---------------------------------------------------------------------------
# Test: Same-color pieces cannot capture each other
# ---------------------------------------------------------------------------

def test_cannot_capture_own_piece():
    b = Board()
    blue_lion = make_piece_id(Color.BLUE, Animal.LION)
    blue_rat = make_piece_id(Color.BLUE, Animal.RAT)
    assert not can_capture(blue_lion, blue_rat, 3, 4, 3, 3, b)


# ---------------------------------------------------------------------------
# Test: Rat in water is invulnerable to land piece attacks
# ---------------------------------------------------------------------------

def test_rat_in_water_invulnerable_to_land_attacks():
    """A land piece adjacent to the river cannot capture a rat in the river."""
    b = Board()
    rat_pid = make_piece_id(Color.BLACK, Animal.RAT)
    b._grid[1][4] = rat_pid
    b._piece_positions[int(Color.BLACK)][rat_pid] = (1, 4)

    # All Blue pieces on land adjacent to river — none should be able to capture the rat
    for animal in [Animal.CAT, Animal.DOG, Animal.WOLF, Animal.LEOPARD,
                   Animal.LION, Animal.ELEPHANT]:
        b2 = Board()
        b2._grid[1][4] = rat_pid
        b2._piece_positions[int(Color.BLACK)][rat_pid] = (1, 4)
        atk_pid = make_piece_id(Color.BLUE, animal)
        b2._grid[0][4] = atk_pid
        b2._piece_positions[int(Color.BLUE)][atk_pid] = (0, 4)
        moves = generate_legal_moves(b2, Color.BLUE)
        # No move should capture the rat at (1,4)
        captures = [m for m in moves if m.tc == 1 and m.tr == 4 and m.captured != 0]
        assert not captures, f"{animal.name} on land should not capture Rat in water"


# ---------------------------------------------------------------------------
# Test: the trap rule overrides the Rat/Elephant exception (knowIssue.txt)
#
# Regression tests for the reported defect: an enemy Rat sitting in your trap
# has rank 0, so *every* adjacent piece of yours may take it — the Elephant
# included, even though an Elephant may never take a Rat on open ground.
# ---------------------------------------------------------------------------

def _adjacent_land_square(col: int, row: int) -> tuple[int, int]:
    """Return the orthogonally adjacent square one step toward the mid-board."""
    return (col, row - 1) if row > 4 else (col, row + 1)


def test_elephant_takes_trapped_rat_all_traps():
    """Elephant takes a trapped Rat on every trap square, for both colors."""
    b = Board()
    for traps, atk_color, def_color in (
        (TRAPS_BLUE, Color.BLUE, Color.BLACK),
        (TRAPS_BLACK, Color.BLACK, Color.BLUE),
    ):
        ele = make_piece_id(atk_color, Animal.ELEPHANT)
        rat = make_piece_id(def_color, Animal.RAT)
        for (tc, tr) in sorted(traps):
            ac, ar = _adjacent_land_square(tc, tr)
            assert can_capture(ele, rat, ac, ar, tc, tr, b), (
                f"{atk_color.name} Elephant at {(ac, ar)} should capture "
                f"{def_color.name} Rat trapped at {(tc, tr)}"
            )


def test_elephant_still_cannot_take_untrapped_rat():
    """The exception survives everywhere except on a trap square."""
    b = Board()
    ele = make_piece_id(Color.BLUE, Animal.ELEPHANT)
    rat = make_piece_id(Color.BLACK, Animal.RAT)
    # Column 0 is never river and holds no traps except the back-row corners.
    assert not can_capture(ele, rat, 0, 6, 0, 5, b)
    assert not can_capture(ele, rat, 0, 3, 0, 2, b)


def test_trapped_rat_capture_is_a_legal_move():
    """The reported position end to end: the capture must reach move generation.

    This is what makes the green target marker appear in the GUI — the input
    handler only offers squares that `generate_legal_moves` produced.
    """
    b = Board()
    place(b, 3, 6, Color.BLUE, Animal.ELEPHANT)
    place(b, 3, 7, Color.BLACK, Animal.RAT)     # Black Rat inside Blue's trap
    rat_pid = make_piece_id(Color.BLACK, Animal.RAT)

    captures = [m for m in generate_legal_moves(b, Color.BLUE)
                if (m.tc, m.tr) == (3, 7)]
    assert len(captures) == 1, "Elephant should have exactly one capture of the trapped Rat"
    assert captures[0].captured == rat_pid


def test_trap_weakens_defence_only():
    """A piece standing in an enemy trap is vulnerable but not disarmed."""
    b = Board()
    trap = (3, 1)                                # a Black trap
    ele = make_piece_id(Color.BLUE, Animal.ELEPHANT)
    # It still strikes at full rank out of the trap...
    assert can_capture(ele, make_piece_id(Color.BLACK, Animal.CAT),
                       trap[0], trap[1], 3, 2, b)
    # ...but only where its real rank suffices, and never against a free Rat.
    assert not can_capture(make_piece_id(Color.BLUE, Animal.CAT),
                           make_piece_id(Color.BLACK, Animal.DOG),
                           trap[0], trap[1], 3, 2, b)
    assert not can_capture(ele, make_piece_id(Color.BLACK, Animal.RAT),
                           trap[0], trap[1], 3, 2, b)
    # ...and it is itself capturable by anything adjacent.
    for animal in Animal:
        assert can_capture(make_piece_id(Color.BLACK, animal), ele,
                           3, 2, trap[0], trap[1], b), \
            f"Black {animal.name} should capture the trapped Blue Elephant"
