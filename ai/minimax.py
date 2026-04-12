"""Negamax alpha-beta with iterative deepening and transposition table."""

from __future__ import annotations

import time
from typing import Optional

from engine.board import Move
from engine.game_state import GameState
from engine.pieces import Animal, Color, piece_id_animal
from ai.evaluator import evaluate, _INF
from ai.transposition import TranspositionTable, TT_EXACT, TT_LOWER, TT_UPPER
from config import AI_DEPTH_EASY, AI_DEPTH_MEDIUM, AI_TIME_HARD_MS

_MATE_SCORE = _INF - 1000


def _order_moves(moves: list[Move], tt_best: Move | None) -> list[Move]:
    """Order moves for better alpha-beta cutoffs.

    Priority:
    1. Transposition table best move
    2. Captures (sorted by victim rank descending — MVV)
    3. All other moves
    """
    if not moves:
        return moves

    def key(m: Move) -> int:
        if tt_best and m == tt_best:
            return -1000
        if m.captured:
            victim_rank = abs(m.captured)
            return -victim_rank  # higher rank victim = more negative = sorted first
        return 0

    return sorted(moves, key=key)


class AIPlayer:
    """AI player using negamax alpha-beta with iterative deepening."""

    def __init__(self, color: Color, difficulty: int = 1) -> None:
        """
        difficulty: 0=Easy (depth 2), 1=Medium (depth 4), 2=Hard (iterative deepening)
        """
        self.color = color
        self.difficulty = difficulty
        self._tt = TranspositionTable()
        self._nodes = 0
        self._start_time = 0.0
        self._time_limit = 0.0
        self._stopped = False
        self._best_move_root: Move | None = None

    def get_best_move(self, state: GameState, time_budget_ms: int = AI_TIME_HARD_MS) -> Move | None:
        """Return the best move for the current position, respecting the time budget."""
        moves = state.legal_moves()
        if not moves:
            return None
        if len(moves) == 1:
            return moves[0]

        self._nodes = 0
        self._stopped = False
        self._start_time = time.perf_counter()

        if self.difficulty == 0:
            # Easy: fixed depth — no time limit
            self._time_limit = 999999.0
            return self._search_fixed_depth(state, AI_DEPTH_EASY)
        elif self.difficulty == 1:
            # Medium: fixed depth — no time limit
            self._time_limit = 999999.0
            return self._search_fixed_depth(state, AI_DEPTH_MEDIUM)
        else:
            # Hard: iterative deepening with time budget
            self._time_limit = time_budget_ms / 1000.0
            return self._search_iterative_deepening(state, time_budget_ms)

    def _search_fixed_depth(self, state: GameState, depth: int) -> Move | None:
        self._best_move_root = None
        self._negamax_root(state, depth)
        return self._best_move_root

    def _search_iterative_deepening(self, state: GameState, time_budget_ms: int) -> Move | None:
        best_move = state.legal_moves()[0]  # fallback
        self._best_move_root = best_move

        for depth in range(1, 20):
            if self._time_expired():
                break
            self._stopped = False
            self._negamax_root(state, depth)
            if not self._stopped:
                best_move = self._best_move_root
            if self._time_expired():
                break

        return best_move

    def _time_expired(self) -> bool:
        return (time.perf_counter() - self._start_time) >= self._time_limit

    def _negamax_root(self, state: GameState, depth: int) -> None:
        """Run negamax at root and store best move in self._best_move_root."""
        alpha = -_INF
        beta = _INF
        best_score = -_INF - 1
        best_move = None

        moves = state.legal_moves()
        if not moves:
            return
        tt_entry = self._tt.get(state.board.turn_hash(state.turn))
        tt_best = tt_entry.best_move if tt_entry else None
        moves = _order_moves(moves, tt_best)
        best_move = moves[0]  # fallback: always have a move to return

        for move in moves:
            if self._stopped:
                break
            state.apply_move(move)
            score = -self._negamax(state, depth - 1, -beta, -alpha)
            state.undo_move()

            if self._stopped:
                break

            if score > best_score:
                best_score = score
                best_move = move
            alpha = max(alpha, score)

        if not self._stopped and best_move is not None:
            self._best_move_root = best_move

    def _negamax(self, state: GameState, depth: int, alpha: int, beta: int) -> int:
        """Negamax with alpha-beta pruning and transposition table."""
        self._nodes += 1

        # Time check every 2048 nodes
        if self._nodes & 2047 == 0:
            if self._time_expired():
                self._stopped = True
                return 0

        if self._stopped:
            return 0

        # Transposition table lookup
        tt_key = state.board.turn_hash(state.turn)
        tt_entry = self._tt.get(tt_key)
        tt_best = None
        if tt_entry is not None and tt_entry.depth >= depth:
            tt_best = tt_entry.best_move
            if tt_entry.flag == TT_EXACT:
                return tt_entry.score
            elif tt_entry.flag == TT_LOWER:
                alpha = max(alpha, tt_entry.score)
            elif tt_entry.flag == TT_UPPER:
                beta = min(beta, tt_entry.score)
            if alpha >= beta:
                return tt_entry.score

        # Terminal / leaf
        if state.is_terminal():
            return evaluate(state, state.turn)

        if depth == 0:
            return evaluate(state, state.turn)

        moves = state.legal_moves()
        moves = _order_moves(moves, tt_best)

        best_score = -_INF
        best_move = None
        original_alpha = alpha

        for move in moves:
            state.apply_move(move)
            score = -self._negamax(state, depth - 1, -beta, -alpha)
            state.undo_move()

            if self._stopped:
                return 0

            if score > best_score:
                best_score = score
                best_move = move
            alpha = max(alpha, score)
            if alpha >= beta:
                break  # beta cutoff

        # Store in transposition table
        if best_move is not None:
            flag = TT_EXACT
            if best_score <= original_alpha:
                flag = TT_UPPER
            elif best_score >= beta:
                flag = TT_LOWER
            self._tt.put(tt_key, depth, best_score, flag, best_move)

        return best_score
