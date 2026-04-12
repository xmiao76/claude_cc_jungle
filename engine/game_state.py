"""GameState: wraps Board with turn tracking, history, and win detection."""

from __future__ import annotations

from engine.board import Board, Move
from engine.pieces import Color
from engine.rules import check_win, WinResult
from engine.move_generator import generate_legal_moves


class GameState:
    """Complete game state: board + whose turn + move history + result."""

    __slots__ = ("board", "turn", "history", "result", "_legal_cache")

    def __init__(self) -> None:
        self.board = Board()
        self.turn: Color = Color.BLUE   # Blue moves first
        self.history: list[Move] = []
        self.result: WinResult | None = None
        self._legal_cache: list[Move] | None = None

    def new_game(self) -> None:
        """Reset to starting position."""
        self.board.setup_starting_position()
        self.turn = Color.BLUE
        self.history.clear()
        self.result = None
        self._legal_cache = None

    # ------------------------------------------------------------------
    # Move application / undo
    # ------------------------------------------------------------------

    def apply_move(self, move: Move) -> None:
        """Apply move, update turn, check for win."""
        self.board.make_move(move)
        self.history.append(move)
        self._legal_cache = None

        # Check win *after* the move
        next_turn = Color.BLACK if self.turn == Color.BLUE else Color.BLUE
        self.result = check_win(self.board, move, next_turn)
        self.turn = next_turn

    def undo_move(self) -> None:
        """Undo the last move (used by AI search)."""
        if not self.history:
            return
        move = self.history.pop()
        self.board.unmake_move(move)
        self.turn = Color.BLUE if self.turn == Color.BLACK else Color.BLACK
        self.result = None
        self._legal_cache = None

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def legal_moves(self) -> list[Move]:
        if self._legal_cache is None:
            self._legal_cache = generate_legal_moves(self.board, self.turn)
        return self._legal_cache

    def is_terminal(self) -> bool:
        if self.result is not None:
            return True
        if not self.legal_moves():
            # No legal moves = current player loses (stalemate rule)
            return True
        return False

    def get_winner(self) -> Color | None:
        if self.result is not None:
            return self.result.winner
        if self.is_terminal() and not self.legal_moves():
            # Current player has no moves → they lose
            return Color.BLACK if self.turn == Color.BLUE else Color.BLUE
        return None

    def copy(self) -> "GameState":
        gs = GameState()
        gs.board = self.board.copy()
        gs.turn = self.turn
        gs.history = self.history[:]
        gs.result = self.result
        return gs
