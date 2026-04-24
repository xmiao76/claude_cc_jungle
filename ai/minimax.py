"""Negamax alpha-beta with iterative deepening, quiescence search,
killer-move heuristic, and history heuristic."""

from __future__ import annotations

import time

from engine.board import Move
from engine.game_state import GameState
from engine.move_generator import generate_capture_moves
from engine.pieces import Color
from ai.evaluator import evaluate, _INF
from ai.transposition import TranspositionTable, TT_EXACT, TT_LOWER, TT_UPPER
from config import (
    AI_DEPTH_EASY, AI_DEPTH_MEDIUM, AI_TIME_HARD_MS,
    QUIESCENCE_MAX_PLY,
)

_MATE_SCORE = _INF - 1000
_MAX_PLY = 64


class AIPlayer:
    """AI player using negamax alpha-beta with iterative deepening."""

    def __init__(self, color: Color, difficulty: int = 1) -> None:
        self.color = color
        self.difficulty = difficulty
        self._tt = TranspositionTable()
        self._nodes = 0
        self._start_time = 0.0
        self._time_limit = 0.0
        self._stopped = False
        self._best_move_root: Move | None = None
        # Killer moves: two non-capture beta-cutoff moves per ply.
        self._killers: list[list[Move | None]] = [[None, None] for _ in range(_MAX_PLY)]
        # History heuristic: keyed by (fc, fr, tc, tr).
        self._history: dict[tuple[int, int, int, int], int] = {}

    # ------------------------------------------------------------------
    # Public entry
    # ------------------------------------------------------------------

    def get_best_move(self, state: GameState, time_budget_ms: int = AI_TIME_HARD_MS) -> Move | None:
        moves = state.legal_moves()
        if not moves:
            return None
        if len(moves) == 1:
            return moves[0]

        self._nodes = 0
        self._stopped = False
        self._start_time = time.perf_counter()
        self._reset_search_heuristics()

        if self.difficulty == 0:
            self._time_limit = 999_999.0
            return self._search_fixed_depth(state, AI_DEPTH_EASY)
        if self.difficulty == 1:
            self._time_limit = 999_999.0
            return self._search_fixed_depth(state, AI_DEPTH_MEDIUM)
        self._time_limit = time_budget_ms / 1000.0
        return self._search_iterative_deepening(state)

    # ------------------------------------------------------------------
    # Search drivers
    # ------------------------------------------------------------------

    def _search_fixed_depth(self, state: GameState, depth: int) -> Move | None:
        self._best_move_root = None
        self._negamax_root(state, depth)
        return self._best_move_root

    def _search_iterative_deepening(self, state: GameState) -> Move | None:
        best_move = state.legal_moves()[0]
        self._best_move_root = best_move
        for depth in range(1, 20):
            if self._time_expired():
                break
            self._stopped = False
            self._negamax_root(state, depth)
            if not self._stopped and self._best_move_root is not None:
                best_move = self._best_move_root
            if self._time_expired():
                break
        return best_move

    def _time_expired(self) -> bool:
        return (time.perf_counter() - self._start_time) >= self._time_limit

    def _reset_search_heuristics(self) -> None:
        for slots in self._killers:
            slots[0] = None
            slots[1] = None
        self._history.clear()

    # ------------------------------------------------------------------
    # Move ordering
    # ------------------------------------------------------------------

    def _order_moves(self, moves: list[Move], tt_best: Move | None, ply: int) -> list[Move]:
        if not moves:
            return moves
        killers = self._killers[ply] if 0 <= ply < _MAX_PLY else (None, None)

        def key(m: Move) -> int:
            if tt_best is not None and m == tt_best:
                return -1_000_000
            if m.captured:
                # MVV: more valuable victim sorts earlier
                return -100_000 - abs(m.captured)
            if m == killers[0]:
                return -50_000
            if m == killers[1]:
                return -49_000
            return -self._history.get((m.fc, m.fr, m.tc, m.tr), 0)

        return sorted(moves, key=key)

    # ------------------------------------------------------------------
    # Negamax
    # ------------------------------------------------------------------

    def _negamax_root(self, state: GameState, depth: int) -> None:
        alpha = -_INF
        beta = _INF
        best_score = -_INF - 1

        moves = state.legal_moves()
        if not moves:
            return
        tt_entry = self._tt.get(state.board.turn_hash(state.turn))
        tt_best = tt_entry.best_move if tt_entry else None
        moves = self._order_moves(moves, tt_best, ply=0)
        best_move = moves[0]

        for move in moves:
            if self._stopped:
                break
            state.apply_move(move)
            score = -self._negamax(state, depth - 1, -beta, -alpha, ply=1)
            state.undo_move()
            if self._stopped:
                break
            if score > best_score:
                best_score = score
                best_move = move
            if score > alpha:
                alpha = score

        if not self._stopped and best_move is not None:
            self._best_move_root = best_move

    def _negamax(self, state: GameState, depth: int, alpha: int, beta: int, ply: int) -> int:
        self._nodes += 1
        if self._nodes & 2047 == 0 and self._time_expired():
            self._stopped = True
            return 0
        if self._stopped:
            return 0

        tt_key = state.board.turn_hash(state.turn)
        tt_entry = self._tt.get(tt_key)
        tt_best = None
        if tt_entry is not None and tt_entry.depth >= depth:
            tt_best = tt_entry.best_move
            if tt_entry.flag == TT_EXACT:
                return tt_entry.score
            if tt_entry.flag == TT_LOWER:
                alpha = max(alpha, tt_entry.score)
            elif tt_entry.flag == TT_UPPER:
                beta = min(beta, tt_entry.score)
            if alpha >= beta:
                return tt_entry.score

        if state.is_terminal():
            return evaluate(state, state.turn)

        if depth <= 0:
            return self._quiesce(state, alpha, beta, qply=0)

        moves = state.legal_moves()
        moves = self._order_moves(moves, tt_best, ply)

        best_score = -_INF
        best_move: Move | None = None
        original_alpha = alpha

        for move in moves:
            state.apply_move(move)
            score = -self._negamax(state, depth - 1, -beta, -alpha, ply + 1)
            state.undo_move()
            if self._stopped:
                return 0
            if score > best_score:
                best_score = score
                best_move = move
            if score > alpha:
                alpha = score
            if alpha >= beta:
                # Beta cutoff: record killer + history for non-captures
                if not move.captured and 0 <= ply < _MAX_PLY:
                    slots = self._killers[ply]
                    if slots[0] != move:
                        slots[1] = slots[0]
                        slots[0] = move
                    self._history[(move.fc, move.fr, move.tc, move.tr)] = (
                        self._history.get((move.fc, move.fr, move.tc, move.tr), 0)
                        + depth * depth
                    )
                break

        if best_move is not None:
            flag = TT_EXACT
            if best_score <= original_alpha:
                flag = TT_UPPER
            elif best_score >= beta:
                flag = TT_LOWER
            self._tt.put(tt_key, depth, best_score, flag, best_move)

        return best_score

    # ------------------------------------------------------------------
    # Quiescence search
    # ------------------------------------------------------------------

    def _quiesce(self, state: GameState, alpha: int, beta: int, qply: int) -> int:
        self._nodes += 1
        if self._nodes & 2047 == 0 and self._time_expired():
            self._stopped = True
            return 0

        stand_pat = evaluate(state, state.turn)
        if qply >= QUIESCENCE_MAX_PLY:
            return stand_pat
        if stand_pat >= beta:
            return beta
        if alpha < stand_pat:
            alpha = stand_pat

        captures = generate_capture_moves(state.board, state.turn)
        # MVV ordering
        captures.sort(key=lambda m: -abs(m.captured))

        for move in captures:
            state.apply_move(move)
            score = -self._quiesce(state, -beta, -alpha, qply + 1)
            state.undo_move()
            if self._stopped:
                return 0
            if score >= beta:
                return beta
            if score > alpha:
                alpha = score

        return alpha
