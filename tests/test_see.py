"""Tests for ai/see.py — Static Exchange Evaluation."""

from ai.see import see_capture
from config import PIECE_VALUES_TUNED as VALUES
from engine.board import Move
from engine.game_state import GameState
from engine.pieces import Animal, Color
from tests.helpers import make_gs


def _find(gs: GameState, fc, fr, tc, tr) -> Move:
    for m in gs.legal_moves():
        if (m.fc, m.fr, m.tc, m.tr) == (fc, fr, tc, tr):
            return m
    raise AssertionError(f"move {(fc,fr,tc,tr)} not legal")


def test_see_positive_for_undefended_capture():
    gs = make_gs(
        (3, 4, Color.BLUE, Animal.TIGER),
        (3, 5, Color.BLACK, Animal.WOLF),
    )
    gs.turn = Color.BLUE
    move = _find(gs, 3, 4, 3, 5)
    assert see_capture(gs.board, move) == VALUES[int(Animal.WOLF)]


def test_see_negative_for_defended_capture():
    """Tiger captures Wolf, but defending Lion can recapture — net loss."""
    gs = make_gs(
        (3, 4, Color.BLUE, Animal.TIGER),     # attacker
        (3, 5, Color.BLACK, Animal.WOLF),     # victim
        (3, 6, Color.BLACK, Animal.LION),     # recapturer, outranks the Tiger
    )
    gs.turn = Color.BLUE
    move = _find(gs, 3, 4, 3, 5)
    # Net: +Wolf -Tiger, and the Tiger costs more than the Wolf.
    assert see_capture(gs.board, move) < 0


def test_see_zero_for_equal_trade():
    """Take a Wolf, lose our Wolf to the recapture: net zero.

    The recapturer only has to outrank our Wolf; its own value never enters the
    swap-off because it is not captured. (This used to use a second Black Wolf as
    the defender, which is not a position Jungle can reach — each side has
    exactly one of each animal.)
    """
    gs = make_gs(
        (3, 4, Color.BLUE, Animal.WOLF),        # attacker
        (3, 5, Color.BLACK, Animal.WOLF),       # victim, same animal
        (3, 6, Color.BLACK, Animal.LEOPARD),    # rank 5 - recaptures
    )
    gs.turn = Color.BLUE
    move = _find(gs, 3, 4, 3, 5)
    # +Wolf -our Wolf = 0, whatever the table prices a Wolf at
    assert see_capture(gs.board, move) == 0


def test_see_no_capture_returns_zero():
    gs = make_gs((3, 4, Color.BLUE, Animal.RAT))
    gs.turn = Color.BLUE
    move = Move(3, 4, 3, 3, 0)  # rat into water, no capture
    assert see_capture(gs.board, move) == 0
