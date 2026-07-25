"""Tests for AI-result delivery in the controller.

The controller runs the search on a daemon thread and delivers the result through
a pygame event. Nothing guaranteed that the result still belonged to the position
on screen, so a search left in flight by Escape / Play Again / Undo could have its
move applied to a different board. That does not raise — it corrupts silently:

* `Board.make_move` reads `pid = 0` from the now-empty source square,
* `_pid_index(0)` returns -1, so the Zobrist update XORs index 15 (wrong key,
  which then poisons the TT, repetition detection and the opening book),
* `_grid[tc][tr] = 0` erases whatever piece stood on the destination,
* `piece_id_color(0)` is BLACK, so a phantom `piece_id 0` is filed into Black's
  position index and inflates `alive_count` permanently.

These tests drive `_on_ai_move` directly, so they need no display or event loop.
"""

from __future__ import annotations

import pytest

import controller as controller_module
from controller import AppState
from engine.board import Move
from engine.game_state import GameState
from engine.pieces import Animal, Color
from tests.helpers import assert_board_consistent, make_gs


class _StubRenderer:
    """Records the calls `_on_ai_move` makes, without touching pygame."""

    def __init__(self) -> None:
        self.flashes: list[tuple[int, int]] = []
        self.animations: list[tuple[int, int, int, int]] = []
        self.cleared = 0

    def trigger_capture_flash(self, col, row, tick_ms):
        self.flashes.append((col, row))

    def start_move_animation(self, animal, color, fc, fr, tc, tr, tick_ms):
        self.animations.append((fc, fr, tc, tr))

    def clear_transient_effects(self):
        self.cleared += 1

    def has_active_animation(self, tick_ms):
        return False


class _StubAudio:
    def __init__(self) -> None:
        self.played: list[str] = []

    def play(self, name):
        self.played.append(name)


class _StubInput:
    def reset(self):
        pass


def _controller(gs: GameState) -> controller_module.Controller:
    """Build a Controller without running __init__ (which needs a display)."""
    c = controller_module.Controller.__new__(controller_module.Controller)
    c.gs = gs
    c.renderer = _StubRenderer()
    c.audio = _StubAudio()
    c.input_handler = _StubInput()
    c.state = AppState.AI_THINKING
    c.mode_ava = False
    c.difficulty = 1
    c._human_color = Color.BLUE
    c._ai_blue = None
    c._ai_black = None
    c._ai_generation = 7
    c._pending_ai_after_anim = False
    c._quit_requested = False
    # Record follow-up search starts instead of spawning real threads: these
    # tests are about the delivery logic in `_on_ai_move`, not about threading.
    c.started_searches = []
    c._start_ai_thread = c.started_searches.append
    return c


def test_stale_generation_result_is_discarded():
    """A move from a superseded search must not be applied."""
    gs = make_gs(
        (3, 4, Color.BLUE, Animal.WOLF),
        (0, 0, Color.BLACK, Animal.LION),
        turn=Color.BLUE,
    )
    c = _controller(gs)
    before_hash = gs.board.hash

    stale = Move(3, 4, 3, 3, 0)
    c._on_ai_move(stale, tick_ms=0, generation=c._ai_generation - 1)

    assert gs.history == [], "stale result must not be applied"
    assert gs.board.hash == before_hash
    assert_board_consistent(gs.board)


def test_current_generation_result_is_applied():
    gs = make_gs(
        (3, 4, Color.BLUE, Animal.WOLF),
        (0, 0, Color.BLACK, Animal.LION),
        turn=Color.BLUE,
    )
    c = _controller(gs)

    c._on_ai_move(Move(3, 4, 3, 3, 0), tick_ms=0, generation=c._ai_generation)

    assert len(gs.history) == 1
    assert gs.board.get(3, 3) != 0
    assert_board_consistent(gs.board)


def test_move_for_a_different_position_is_not_applied(capsys):
    """The exact corruption path: a move whose source square is now empty.

    Even with a matching generation, a move must be checked against the current
    legal moves. Applying this one would write piece id 0 into the grid.
    """
    gs = make_gs(
        (3, 4, Color.BLUE, Animal.WOLF),
        (0, 0, Color.BLACK, Animal.LION),
        turn=Color.BLUE,
    )
    c = _controller(gs)

    # (5,5) holds nothing — this move belongs to some other position entirely.
    bogus = Move(5, 5, 5, 4, 0)
    c._on_ai_move(bogus, tick_ms=0, generation=c._ai_generation)

    assert_board_consistent(gs.board)
    assert 0 not in gs.board.pieces_of(Color.BLACK), "phantom piece id 0 was filed"
    assert gs.board.alive_count(Color.BLACK) == 1
    # A legal fallback was played instead of freezing, and it was reported.
    assert "discarding unusable AI move" in capsys.readouterr().out
    assert len(gs.history) == 1
    assert gs.history[0].fc == 3 and gs.history[0].fr == 4, (
        "the fallback must move the piece that actually exists"
    )


def test_none_result_does_not_freeze_the_game(capsys):
    """A crashed search returns None; the game must keep going, loudly."""
    gs = make_gs(
        (3, 4, Color.BLUE, Animal.WOLF),
        (0, 0, Color.BLACK, Animal.LION),
        turn=Color.BLUE,
    )
    c = _controller(gs)

    c._on_ai_move(None, tick_ms=0, generation=c._ai_generation)

    assert len(gs.history) == 1, "should fall back to a legal move, not stall"
    assert "discarding unusable AI move" in capsys.readouterr().out
    # The turn advanced and play continues, rather than the game sitting in
    # AI_THINKING with a spinner and no pending result.
    assert gs.turn == Color.BLACK
    assert c.started_searches == [Color.BLACK], "the next search should be queued"
    assert_board_consistent(gs.board)


def test_result_ignored_once_the_game_is_over():
    gs = make_gs(
        (6, 8, Color.BLACK, Animal.RAT),
        (5, 8, Color.BLUE, Animal.CAT),
        (6, 7, Color.BLUE, Animal.DOG),
        turn=Color.BLACK,
    )
    assert gs.is_terminal()
    c = _controller(gs)

    c._on_ai_move(Move(6, 8, 5, 8, 2), tick_ms=0, generation=c._ai_generation)
    assert gs.history == []


# ---------------------------------------------------------------------------
# Search cancellation
# ---------------------------------------------------------------------------

def test_request_stop_aborts_the_search():
    """`request_stop` must end a search that has no time limit of its own."""
    from ai.minimax import AIPlayer

    gs = make_gs(*[
        (0, 6, Color.BLUE, Animal.ELEPHANT), (2, 6, Color.BLUE, Animal.WOLF),
        (4, 6, Color.BLUE, Animal.LEOPARD), (0, 2, Color.BLACK, Animal.RAT),
        (2, 2, Color.BLACK, Animal.LEOPARD), (4, 2, Color.BLACK, Animal.WOLF),
    ], turn=Color.BLUE)

    ai = AIPlayer(Color.BLUE, 1)          # fixed depth, watchdog only
    ai.request_stop()                      # stop before it even starts
    move = ai.get_best_move(gs)

    # A stop request must not lose the ability to return a playable move.
    assert move is not None
    assert move in gs.legal_moves()


def test_get_best_move_clears_a_previous_stop_request():
    """A stop applies to one search, not to the player for the rest of the game."""
    from ai.minimax import AIPlayer

    gs = make_gs(
        (3, 4, Color.BLUE, Animal.WOLF),
        (0, 0, Color.BLACK, Animal.LION),
        turn=Color.BLUE,
    )
    ai = AIPlayer(Color.BLUE, 1)
    ai.request_stop()
    ai.get_best_move(gs)
    assert ai._stop_requested is False, "stop flag must reset per search"

    ai.get_best_move(gs)
    assert ai._last_depth > 0, "the next search must run normally"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
