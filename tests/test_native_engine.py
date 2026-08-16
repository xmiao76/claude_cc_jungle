"""Tests for the native engine and the adapter that presents it to the GUI.

Everything here is skipped when the compiled extension is absent, so a checkout
without a Rust toolchain still has a green suite — the game falls back to the
Python engine in exactly the same way.

Two kinds of test. The first kind re-checks, from Python, that the native engine
agrees with the Python one: the same perft numbers, the same legal moves, the
same evaluation. Those comparisons also exist on the Rust side, but running them
from here is what catches a *binding* bug — a coordinate transposed at the
boundary, a colour code inverted — which the Rust tests cannot see because they
never cross it.

The second kind covers the contract `controller.py` depends on: a legal move
always, a prompt stop, and state that survives across moves.
"""

from __future__ import annotations

import threading
import time

import pytest

from ai.native import AVAILABLE, UNAVAILABLE_REASON, NativeAIPlayer, _to_native, make_ai_player
from engine.game_state import GameState
from engine.move_generator import generate_legal_moves
from engine.pieces import Color
from tests.helpers import make_gs
from tools.golden import decode_position, encode_board, read

pytestmark = pytest.mark.skipif(
    not AVAILABLE, reason=f"jungle_native not built: {UNAVAILABLE_REASON}"
)


@pytest.fixture(scope="module")
def jn():
    import jungle_native

    return jungle_native


# ---------------------------------------------------------------------------
# The native engine agrees with the Python one, across the binding
# ---------------------------------------------------------------------------

def test_perft_matches_the_frozen_contract(jn):
    from tests.test_perft import EXPECTED, POSITIONS

    for name, factory in POSITIONS.items():
        gs = factory()
        pos = jn.Position.from_board(
            encode_board(gs.board), 0 if gs.turn == Color.BLUE else 1, 0
        )
        for depth, want in enumerate(EXPECTED[name], start=1):
            got = jn.perft(pos, depth)
            assert got == want, f"{name} perft({depth}): expected {want}, got {got}"


def test_legal_moves_match_python_across_the_corpus(jn):
    """A transposed coordinate at the boundary would show up here and nowhere else."""
    for i, line in enumerate(read()[:2000]):
        gs, _, _, _ = decode_position(line)
        pos = jn.Position.from_board(
            encode_board(gs.board),
            0 if gs.turn == Color.BLUE else 1,
            gs._halfmove_clock,
        )
        native = sorted(pos.legal_moves())
        python = sorted(
            (m.fc, m.fr, m.tc, m.tr, m.captured)
            for m in generate_legal_moves(gs.board, gs.turn)
        )
        assert native == python, f"line {i}: legal moves diverged"


def test_evaluation_matches_python_across_the_corpus(jn):
    from ai.evaluator import evaluate
    from ai.search_config import strong_config

    cfg = strong_config()
    for i, line in enumerate(read()[:2000]):
        gs, _, _, _ = decode_position(line)
        pos = jn.Position.from_board(
            encode_board(gs.board), 0 if gs.turn == Color.BLUE else 1, 0
        )
        assert jn.evaluate(pos, 0) == evaluate(gs, Color.BLUE, cfg), f"line {i}"
        assert jn.evaluate(pos, 1) == evaluate(gs, Color.BLACK, cfg), f"line {i}"


def test_terminal_and_winner_match_python(jn):
    for i, line in enumerate(read()[:2000]):
        gs, terminal, winner, _ = decode_position(line)
        pos = jn.Position.from_board(
            encode_board(gs.board),
            0 if gs.turn == Color.BLUE else 1,
            gs._halfmove_clock,
        )
        assert pos.is_terminal() == terminal, f"line {i}"
        want = None if winner == "-" else (0 if winner == "B" else 1)
        assert pos.winner() == want, f"line {i}"


def test_an_illegal_move_is_refused_rather_than_corrupting_the_board(jn):
    pos = jn.Position()
    with pytest.raises(ValueError):
        pos.make(3, 6, 3, 5)  # no Blue piece on (3,6)
    pos.assert_consistent()
    assert pos.board_string() == jn.Position().board_string()


def test_off_board_coordinates_are_refused(jn):
    pos = jn.Position()
    for bad in [(7, 0), (0, 9), (99, 99)]:
        with pytest.raises(ValueError):
            pos.get(*bad)


# ---------------------------------------------------------------------------
# The adapter's contract with the controller
# ---------------------------------------------------------------------------

def test_make_ai_player_prefers_the_native_engine():
    assert isinstance(make_ai_player(Color.BLUE, 2), NativeAIPlayer)


def test_history_replay_reproduces_the_position():
    """The adapter replays the game so the search can see repetitions.

    Verified against the board rather than trusted, which is also what makes the
    fallback safe: a state the replay cannot reproduce falls back to the
    board-only form instead of searching the wrong position.
    """
    gs = GameState()
    gs.new_game()
    for _ in range(12):
        gs.apply_move(gs.legal_moves()[0])
    native = _to_native(gs)
    assert native.board_string() == encode_board(gs.board)
    assert native.side_to_move == int(gs.turn)
    assert native.halfmove_clock == gs._halfmove_clock


def test_a_position_without_history_still_works():
    from engine.pieces import Animal

    gs = make_gs(
        (3, 4, Color.BLUE, Animal.ELEPHANT),
        (3, 5, Color.BLACK, Animal.RAT),
    )
    native = _to_native(gs)
    assert native.board_string() == encode_board(gs.board)


@pytest.mark.parametrize("difficulty", [0, 1, 2])
def test_every_difficulty_returns_a_legal_move(difficulty):
    gs = GameState()
    gs.new_game()
    ai = make_ai_player(Color.BLUE, difficulty)
    for _ in range(6):
        if gs.is_terminal():
            break
        move = ai.get_best_move(gs, time_budget_ms=200)
        assert move is not None
        assert move in gs.legal_moves()
        gs.apply_move(move)


def test_the_returned_move_is_the_callers_own_object():
    """`controller.py` validates with `move not in gs.legal_moves()`.

    A freshly built Move with a stale `captured` field would compare unequal and
    be discarded as unusable, so the adapter returns the caller's object.
    """
    gs = GameState()
    gs.new_game()
    ai = make_ai_player(Color.BLUE, 0)
    move = ai.get_best_move(gs)
    assert any(move is m for m in gs.legal_moves())


def test_a_single_legal_move_is_played_without_searching():
    from engine.pieces import Animal

    gs = make_gs(
        (3, 4, Color.BLUE, Animal.ELEPHANT),
        (3, 5, Color.BLACK, Animal.RAT),
    )
    ai = make_ai_player(Color.BLUE, 2)
    move = ai.get_best_move(gs, time_budget_ms=5000)
    assert move in gs.legal_moves()


def test_request_stop_returns_a_legal_move_promptly():
    gs = GameState()
    gs.new_game()
    ai = make_ai_player(Color.BLUE, 2)

    def stop_soon():
        time.sleep(0.1)
        ai.request_stop()

    t = threading.Thread(target=stop_soon)
    t.start()
    started = time.perf_counter()
    move = ai.get_best_move(gs, time_budget_ms=30_000)
    elapsed = time.perf_counter() - started
    t.join()

    assert elapsed < 3.0, f"stop took {elapsed:.1f}s"
    assert move is not None and move in gs.legal_moves()


def test_a_full_ai_vs_ai_game_completes_cleanly():
    """The end-to-end path the game actually runs.

    Every move must be legal, the board must stay self-consistent after each one,
    and the game must reach a real conclusion rather than grinding to the move
    cap -- which is what would happen if the engine could not see a win.
    """
    from tests.helpers import assert_board_consistent

    gs = GameState()
    gs.new_game()
    players = {
        Color.BLUE: make_ai_player(Color.BLUE, 1),
        Color.BLACK: make_ai_player(Color.BLACK, 1),
    }

    plies = 0
    for _ in range(300):
        if gs.is_terminal():
            break
        move = players[gs.turn].get_best_move(gs, time_budget_ms=100)
        assert move is not None, "engine gave up in a live position"
        assert move in gs.legal_moves(), f"illegal move {move}"
        gs.apply_move(move)
        assert_board_consistent(gs.board)
        plies += 1

    assert gs.is_terminal(), f"game did not finish in {plies} plies"
    assert plies > 4, "game ended suspiciously early"


def test_the_controller_applies_a_native_move():
    """`_on_ai_move` validates against `legal_moves()` before applying.

    A move object that failed that check would be silently discarded and the game
    would stall, so this drives the real delivery path with a real native result.
    """
    import controller as controller_module
    from tests.test_controller_ai_thread import _controller

    gs = GameState()
    gs.new_game()
    c = _controller(gs)
    c.state = controller_module.AppState.AI_THINKING

    ai = make_ai_player(Color.BLUE, 0)
    move = ai.get_best_move(gs)
    c._on_ai_move(move, tick_ms=0, generation=c._ai_generation)

    assert gs.history == [move], "the controller discarded a native move"


def test_search_telemetry_is_exposed_for_the_bench():
    gs = GameState()
    gs.new_game()
    ai = make_ai_player(Color.BLUE, 2)
    ai.get_best_move(gs, time_budget_ms=300)
    assert ai._nodes > 0
    assert ai._last_depth > 0
    assert ai._seldepth >= ai._last_depth - 1
