"""Tests for win condition detection."""

from engine.board import Move
from engine.game_state import GameState
from engine.pieces import Animal, Color, make_piece_id
from tests.helpers import make_gs

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

make_gs_with_pieces = make_gs


# ---------------------------------------------------------------------------
# Test: Den entry wins immediately
# ---------------------------------------------------------------------------

def test_blue_enters_black_den():
    """Blue piece moving into Black's den (3,0) should win for Blue."""
    # Blue Wolf at (3,1), Black has a piece elsewhere
    gs = make_gs_with_pieces(
        (3, 1, Color.BLUE, Animal.WOLF),
        (0, 8, Color.BLACK, Animal.ELEPHANT),
    )
    gs.turn = Color.BLUE

    # Move Wolf into Black's den
    move = Move(3, 1, 3, 0, 0)
    gs.apply_move(move)

    assert gs.result is not None, "Game should be over after den entry"
    assert gs.result.winner == Color.BLUE, "Blue should win by entering Black's den"


def test_black_enters_blue_den():
    """Black piece moving into Blue's den (3,8) should win for Black."""
    gs = make_gs_with_pieces(
        (0, 0, Color.BLUE, Animal.ELEPHANT),
        (3, 7, Color.BLACK, Animal.WOLF),
    )
    gs.turn = Color.BLACK

    move = Move(3, 7, 3, 8, 0)
    gs.apply_move(move)

    assert gs.result is not None
    assert gs.result.winner == Color.BLACK, "Black should win by entering Blue's den"


# ---------------------------------------------------------------------------
# Test: Capture-all wins
# ---------------------------------------------------------------------------

def test_capture_last_piece_wins():
    """Capturing the opponent's last remaining piece should win."""
    gs = make_gs_with_pieces(
        (0, 0, Color.BLUE, Animal.LION),
        (0, 1, Color.BLACK, Animal.CAT),   # Black's only piece
    )
    gs.turn = Color.BLUE

    move = Move(0, 0, 0, 1, make_piece_id(Color.BLACK, Animal.CAT))
    gs.apply_move(move)

    assert gs.result is not None
    assert gs.result.winner == Color.BLUE


# ---------------------------------------------------------------------------
# Test: No win in mid-game
# ---------------------------------------------------------------------------

def test_no_win_midgame():
    """Mid-game state with many pieces should return no winner."""
    gs = GameState()
    gs.new_game()
    gs.apply_move(gs.legal_moves()[0])

    assert gs.result is None
    assert gs.get_winner() is None


# ---------------------------------------------------------------------------
# Test: check_win returns None for normal capture
# ---------------------------------------------------------------------------

def test_normal_capture_no_win():
    """A capture that doesn't end the game should not trigger win."""
    gs = make_gs_with_pieces(
        (0, 0, Color.BLUE, Animal.LION),
        (0, 1, Color.BLACK, Animal.CAT),
        (0, 8, Color.BLACK, Animal.ELEPHANT),  # Black still has another piece
    )
    gs.turn = Color.BLUE

    move = Move(0, 0, 0, 1, make_piece_id(Color.BLACK, Animal.CAT))
    gs.apply_move(move)

    assert gs.result is None, "Should not be over; Black still has Elephant"


# ---------------------------------------------------------------------------
# Test: Stalemate (no legal moves) — player with no moves loses
# ---------------------------------------------------------------------------

def test_stalemate_loses():
    """A player with no legal moves loses.

    The Black Rat sits in the (6,8) corner, so it has only two neighbours:
    (5,8) and (6,7). Blocking both with pieces the Rat cannot capture leaves it
    with zero moves. The blockers must be ranks 2-7: a Rat may capture another
    Rat, and — crucially — a Rat *can* capture an Elephant, so an Elephant is
    not a blocker. (An earlier version of this test used an Elephant and a Lion,
    which left the Rat a legal capture; the assertions then sat behind an
    `if not moves:` guard that never ran.)
    """
    gs = make_gs_with_pieces(
        (6, 8, Color.BLACK, Animal.RAT),   # boxed into the corner
        (5, 8, Color.BLUE, Animal.CAT),    # rank 2 — Rat cannot take it
        (6, 7, Color.BLUE, Animal.DOG),    # rank 3 — Rat cannot take it
    )
    gs.turn = Color.BLACK

    assert gs.legal_moves() == [], "Black Rat should be completely boxed in"
    assert gs.is_terminal()
    assert gs.get_winner() == Color.BLUE, "Side with no legal moves loses"
