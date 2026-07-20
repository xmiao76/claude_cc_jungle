"""AI search: tactics, mate-finding, robustness, and responsiveness."""

import time

import config
from ai.minimax import DIFFICULTY_EASY, DIFFICULTY_HARD, DIFFICULTY_MEDIUM, AIPlayer
from engine.game_state import GameState
from engine.move_generator import generate_moves
from engine.pieces import Animal, Color

BLUE = int(Color.BLUE)
BLACK = int(Color.BLACK)


def S(c, r):
    return c * config.ROWS + r


def test_ai_takes_a_free_capture():
    gs = GameState()
    gs.setup_position(
        {(3, 4): (BLUE, Animal.LION), (3, 5): (BLACK, Animal.CAT)},
        to_move=BLUE,
    )
    ai = AIPlayer(BLUE, DIFFICULTY_EASY)
    move = ai.choose_move(gs)
    assert move is not None
    assert move.to == S(3, 5) and move.captured != 0


def test_ai_finds_mate_in_one_den_dash():
    gs = GameState()
    gs.setup_position(
        {(3, 1): (BLUE, Animal.RAT), (0, 0): (BLACK, Animal.ELEPHANT),
         (6, 8): (BLACK, Animal.LION)},
        to_move=BLUE,
    )
    for diff in (DIFFICULTY_EASY, DIFFICULTY_MEDIUM):
        ai = AIPlayer(BLUE, diff)
        move = ai.choose_move(gs)
        assert move.to == S(3, 0), f"difficulty {diff} missed the den dash"


def test_ai_avoids_losing_its_piece_for_nothing():
    """Blue Lion can grab a Wolf, but the Wolf is defended on land by an
    Elephant that would recapture the Lion - a bad trade. Avoid it."""
    gs = GameState()
    gs.setup_position(
        {(0, 4): (BLUE, Animal.LION),
         (0, 5): (BLACK, Animal.WOLF), (0, 6): (BLACK, Animal.ELEPHANT),
         (6, 8): (BLUE, Animal.RAT)},
        to_move=BLUE,
    )
    ai = AIPlayer(BLUE, DIFFICULTY_MEDIUM)
    move = ai.choose_move(gs)
    # Taking the defended Wolf (Lion for Wolf, then losing the Lion) is bad.
    assert not (move.frm == S(0, 4) and move.to == S(0, 5))


def test_ai_returns_legal_move_from_initial_position():
    gs = GameState()
    ai = AIPlayer(BLUE, DIFFICULTY_MEDIUM)
    move = ai.choose_move(gs)
    legal = generate_moves(gs.board, BLUE)
    assert any(m.frm == move.frm and m.to == move.to for m in legal)


def test_hard_ai_is_responsive():
    gs = GameState()
    ai = AIPlayer(BLUE, DIFFICULTY_HARD)
    start = time.monotonic()
    move = ai.choose_move(gs)
    elapsed = time.monotonic() - start
    assert move is not None
    # Budget is ~2s; allow generous slack for a loaded CI machine.
    assert elapsed < config.AI_TIME_HARD_MS / 1000.0 + 2.0
