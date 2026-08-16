"""Native-engine adapter presenting the `AIPlayer` interface.

`controller.py` touches the AI through exactly three things: the constructor,
`get_best_move(state, time_budget_ms=...)`, and `request_stop()`. This provides
those on top of the Rust engine in `rust/crates/jungle-py`, so the GUI needs no
changes beyond choosing which class to build.

The Python engine is left in place rather than replaced. Two reasons, both
practical: it is the oracle the Rust rules and evaluation are checked against
(`tests/golden/`), and it is the fallback when the compiled extension is missing,
so a checkout without a Rust toolchain still plays.

Keeping two rule implementations alive is normally how they quietly diverge. Here
it is safe because the divergence is *continuously measured*: the golden corpus
tests compare them on ten thousand positions and the perft contract compares
them exhaustively, and `build.bat` runs both before packaging.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import config
from engine.board import Move
from engine.game_state import GameState
from engine.pieces import Color


@runtime_checkable
class AIEngine(Protocol):
    """What `controller.py` requires of an engine.

    Written down because there are now two implementations of it. Note that the
    players are *stateful and long-lived* — one per colour, created once per game
    and reused for every move — which is how the transposition table and the
    history heuristics survive between moves. An adapter that rebuilt the engine
    per move would silently throw all of that away.
    """

    color: Color
    difficulty: int

    def get_best_move(
        self, state: GameState, time_budget_ms: int | None = ...
    ) -> Move | None:
        """Return a move from `state.legal_moves()`, or None if there are none.

        Must return a *legal* move even when interrupted: `controller.py`
        validates the result and discards anything else, so returning None after
        a stop would leave the game stuck.
        """
        ...

    def request_stop(self) -> None:
        """Abort a running search. Called from the UI thread, not the search one."""
        ...

try:  # pragma: no cover - exercised by whether the extension is built
    import jungle_native

    AVAILABLE = True
    UNAVAILABLE_REASON = ""
except ImportError as exc:  # pragma: no cover
    jungle_native = None
    AVAILABLE = False
    UNAVAILABLE_REASON = str(exc)


# Search budgets per difficulty. Node counts rather than depths: a node budget is
# hardware-independent and scales smoothly, where a fixed depth gets whatever
# strength that depth happens to be worth in a given position. These are starting
# values; the calibration step measures them against the previous engine's levels
# so "Easy" keeps meaning what it used to.
NODE_BUDGET = {
    0: 2_000,     # Easy
    1: 60_000,    # Medium
}
TT_MEGABYTES = 64


class NativeAIPlayer:
    """The Rust engine, wearing the `AIPlayer` interface."""

    def __init__(self, color: Color, difficulty: int = 1, cfg=None) -> None:
        if not AVAILABLE:
            raise RuntimeError(f"jungle_native is not importable: {UNAVAILABLE_REASON}")
        self.color = color
        self.difficulty = difficulty
        self.cfg = cfg
        self._engine = jungle_native.Engine(TT_MEGABYTES)
        # Read by the bench command, matching the Python engine's attributes.
        self._nodes = 0
        self._last_depth = 0
        self._seldepth = 0

    # -- the controller's three-method contract -------------------------

    def get_best_move(self, state: GameState, time_budget_ms: int | None = None) -> Move | None:
        moves = state.legal_moves()
        if not moves:
            return None
        if len(moves) == 1:
            return moves[0]

        position = _to_native(state)
        budget = NODE_BUDGET.get(self.difficulty)
        if budget is not None:
            info = self._engine.think(position, nodes=budget)
        else:
            ms = time_budget_ms if time_budget_ms is not None else config.AI_TIME_HARD_MS
            info = self._engine.think(position, movetime_ms=ms)

        self._nodes = info.nodes
        self._last_depth = info.depth
        self._seldepth = info.seldepth

        if info.best_move is None:
            return None
        fc, fr, tc, tr, _captured = info.best_move
        # Return the caller's own Move object rather than a freshly built one, so
        # the identity and the `captured` field come from the position the caller
        # is actually holding.
        for m in moves:
            if (m.fc, m.fr, m.tc, m.tr) == (fc, fr, tc, tr):
                return m
        return None

    def request_stop(self) -> None:
        """Abort a running search. Called from the UI thread."""
        self._engine.stop()

    def new_game(self) -> None:
        """Drop the transposition table and history between games."""
        self._engine.reset()


def make_ai_player(color: Color, difficulty: int = 1):
    """Build the strongest available engine for this colour.

    Prefers the native engine and falls back to the Python one, so a checkout
    without a built extension still plays -- just several hundred Elo weaker and
    ten plies shallower.
    """
    if AVAILABLE:
        return NativeAIPlayer(color, difficulty)
    from ai.minimax import AIPlayer

    return AIPlayer(color, difficulty)


def _to_native(state: GameState):
    """Build a native position from a `GameState`.

    Replays the move history when the game began at the starting position, which
    is the case in real play. That is worth the effort: the position alone cannot
    express repetition, and a search that cannot see a repetition will happily
    walk into one when it is losing, or miss that it is being forced into one.

    The replay is verified against the actual board rather than assumed, so a
    state built directly by a test or the harness falls back cleanly to the
    board-only form.
    """
    history = [m for m in state.history if m is not None]
    if history:
        position = jungle_native.Position()
        try:
            for m in history:
                position.make(m.fc, m.fr, m.tc, m.tr)
        except ValueError:
            position = None
        if position is not None and position.board_string() == _board_string(state):
            position.halfmove_clock = state._halfmove_clock
            return position

    position = jungle_native.Position.from_board(
        _board_string(state),
        0 if state.turn == Color.BLUE else 1,
        state._halfmove_clock,
    )
    return position


def _board_string(state: GameState) -> str:
    """The 63-character row-major encoding the native side reads."""
    board = state.board
    out = []
    for r in range(config.ROWS):
        for c in range(config.COLS):
            pid = board.get(c, r)
            if pid == 0:
                out.append(".")
            else:
                base = "A" if pid > 0 else "a"
                out.append(chr(ord(base) + abs(pid) - 1))
    return "".join(out)
