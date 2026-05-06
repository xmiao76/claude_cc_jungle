"""Negamax alpha-beta search with:
- Principal Variation Search (PVS)
- Null Move Pruning (NMP)
- Late Move Reductions (LMR)
- Mate-distance scoring
- Aspiration windows
- Repetition / 50-move draw recognition
- TT in main search and quiescence
- Killer / counter-move / history heuristics with aging
- SEE-pruned quiescence with delta pruning
- Optional opening book
"""

from __future__ import annotations

import time

from engine.board import Move
from engine.game_state import GameState
from engine.move_generator import generate_capture_moves
from engine.pieces import Color
from ai.evaluator import evaluate, _INF
from ai.transposition import TranspositionTable, TT_EXACT, TT_LOWER, TT_UPPER
from ai.see import see_capture
from ai import opening_book
from config import (
    AI_DEPTH_EASY, AI_DEPTH_MEDIUM, AI_TIME_HARD_MS,
    QUIESCENCE_MAX_PLY, EVAL_WEIGHTS,
    NMP_REDUCTION, NMP_MIN_DEPTH, NMP_MIN_PIECES,
    LMR_MIN_DEPTH, LMR_MOVES_BEFORE,
    ASPIRATION_DELTA, ASPIRATION_MIN_DEPTH,
    USE_OPENING_BOOK,
)

_MATE = _INF - 1000
_MAX_PLY = 64
_MATE_BOUND = _MATE - _MAX_PLY  # any |score| >= bound is treated as mate-distance


def _mate_in(ply: int) -> int:
    return _MATE - ply


def _mated_in(ply: int) -> int:
    return -_MATE + ply


def _tt_score_to_store(score: int, ply: int) -> int:
    """Adjust mate scores to be ply-independent for TT storage."""
    if score >= _MATE_BOUND:
        return score + ply
    if score <= -_MATE_BOUND:
        return score - ply
    return score


def _tt_score_from_probe(score: int, ply: int) -> int:
    """Reverse adjustment when reading from TT."""
    if score >= _MATE_BOUND:
        return score - ply
    if score <= -_MATE_BOUND:
        return score + ply
    return score


class AIPlayer:
    """AI player using negamax PVS with iterative deepening."""

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
        # Counter-move heuristic: prev_move_tuple -> reply move.
        self._counter: dict[tuple[int, int, int, int], Move] = {}

    # ------------------------------------------------------------------
    # Public entry
    # ------------------------------------------------------------------

    def get_best_move(self, state: GameState, time_budget_ms: int = AI_TIME_HARD_MS) -> Move | None:
        moves = state.legal_moves()
        if not moves:
            return None
        if len(moves) == 1:
            return moves[0]

        # Opening book (only on Hard, for the first dozen plies)
        if USE_OPENING_BOOK and self.difficulty >= 2 and len(state.history) < 12:
            book_move = opening_book.lookup(state)
            if book_move is not None:
                return book_move

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
        self._negamax_root(state, depth, -_INF, _INF)
        return self._best_move_root

    def _search_iterative_deepening(self, state: GameState) -> Move | None:
        best_move = state.legal_moves()[0]
        self._best_move_root = best_move
        prev_score: int | None = None
        for depth in range(1, 32):
            if self._time_expired():
                break
            self._stopped = False

            # Aspiration windows after a few completed iterations.
            if prev_score is not None and depth >= ASPIRATION_MIN_DEPTH:
                delta = ASPIRATION_DELTA
                while True:
                    alpha = prev_score - delta
                    beta = prev_score + delta
                    score = self._negamax_root(state, depth, alpha, beta)
                    if self._stopped:
                        break
                    if score <= alpha or score >= beta:
                        delta *= 4
                        if delta > 1600:
                            score = self._negamax_root(state, depth, -_INF, _INF)
                            break
                        continue
                    break
            else:
                score = self._negamax_root(state, depth, -_INF, _INF)

            if not self._stopped and self._best_move_root is not None:
                best_move = self._best_move_root
                prev_score = score
            # Age history between iterations.
            self._age_history()
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
        self._counter.clear()

    def _age_history(self) -> None:
        for k in list(self._history.keys()):
            v = self._history[k] >> 1
            if v == 0:
                del self._history[k]
            else:
                self._history[k] = v

    # ------------------------------------------------------------------
    # Move ordering
    # ------------------------------------------------------------------

    def _order_moves(self, moves: list[Move], tt_best: Move | None,
                     ply: int, prev_move: Move | None) -> list[Move]:
        if not moves:
            return moves
        killers = self._killers[ply] if 0 <= ply < _MAX_PLY else (None, None)
        counter = None
        if prev_move is not None:
            counter = self._counter.get((prev_move.fc, prev_move.fr, prev_move.tc, prev_move.tr))

        def key(m: Move) -> int:
            if tt_best is not None and m == tt_best:
                return -1_000_000
            if m.captured:
                # MVV-LVA: more valuable victim first, less valuable attacker first.
                return -100_000 - abs(m.captured) * 10 + abs(m.captured) - 0
            if m == killers[0]:
                return -50_000
            if m == killers[1]:
                return -49_000
            if counter is not None and m == counter:
                return -48_000
            return -self._history.get((m.fc, m.fr, m.tc, m.tr), 0)

        return sorted(moves, key=key)

    # ------------------------------------------------------------------
    # Negamax
    # ------------------------------------------------------------------

    def _negamax_root(self, state: GameState, depth: int, alpha: int, beta: int) -> int:
        original_alpha = alpha
        best_score = -_INF - 1

        moves = state.legal_moves()
        if not moves:
            return _mated_in(0)

        tt_entry = self._tt.get(state.board.turn_hash(state.turn))
        tt_best = tt_entry.best_move if tt_entry else None
        moves = self._order_moves(moves, tt_best, ply=0, prev_move=None)
        best_move = moves[0]

        for idx, move in enumerate(moves):
            if self._stopped:
                break
            state.apply_move(move)
            if idx == 0:
                score = -self._negamax(state, depth - 1, -beta, -alpha,
                                        ply=1, prev_move=move, allow_null=True)
            else:
                # PVS null-window probe
                score = -self._negamax(state, depth - 1, -alpha - 1, -alpha,
                                        ply=1, prev_move=move, allow_null=True)
                if not self._stopped and alpha < score < beta:
                    score = -self._negamax(state, depth - 1, -beta, -alpha,
                                            ply=1, prev_move=move, allow_null=True)
            state.undo_move()
            if self._stopped:
                break
            if score > best_score:
                best_score = score
                best_move = move
            if score > alpha:
                alpha = score
            if alpha >= beta:
                break

        if not self._stopped and best_move is not None:
            self._best_move_root = best_move
            flag = TT_EXACT
            if best_score <= original_alpha:
                flag = TT_UPPER
            elif best_score >= beta:
                flag = TT_LOWER
            self._tt.put(state.board.turn_hash(state.turn), depth,
                         _tt_score_to_store(best_score, 0), flag, best_move)
        return best_score

    def _negamax(self, state: GameState, depth: int, alpha: int, beta: int,
                 ply: int, prev_move: Move | None, allow_null: bool) -> int:
        self._nodes += 1
        if self._nodes & 2047 == 0 and self._time_expired():
            self._stopped = True
            return 0
        if self._stopped:
            return 0

        # Repetition / 50-move draw.
        if ply > 0 and (state.is_repetition() or state.is_50_move_draw()):
            return 0

        # Mate distance pruning
        alpha = max(alpha, _mated_in(ply))
        beta = min(beta, _mate_in(ply + 1))
        if alpha >= beta:
            return alpha

        is_pv = (beta - alpha) > 1

        tt_key = state.board.turn_hash(state.turn)
        tt_entry = self._tt.get(tt_key)
        tt_best = None
        if tt_entry is not None:
            tt_best = tt_entry.best_move
            if tt_entry.depth >= depth and not is_pv:
                tt_score = _tt_score_from_probe(tt_entry.score, ply)
                if tt_entry.flag == TT_EXACT:
                    return tt_score
                if tt_entry.flag == TT_LOWER and tt_score >= beta:
                    return tt_score
                if tt_entry.flag == TT_UPPER and tt_score <= alpha:
                    return tt_score

        # Terminal: explicit winner via game rules.
        if state.result is not None:
            winner = state.result.winner
            if winner == state.turn:
                return _mate_in(ply)
            return _mated_in(ply)

        if depth <= 0:
            return self._quiesce(state, alpha, beta, qply=0, ply=ply)

        moves = state.legal_moves()
        if not moves:
            return _mated_in(ply)

        # ---- Null move pruning ----
        if (allow_null and not is_pv and depth >= NMP_MIN_DEPTH
                and state.board.alive_count(state.turn) >= NMP_MIN_PIECES):
            static_eval = evaluate(state, state.turn)
            if static_eval >= beta:
                state.apply_null()
                null_score = -self._negamax(state, depth - 1 - NMP_REDUCTION,
                                            -beta, -beta + 1, ply + 1,
                                            prev_move=None, allow_null=False)
                state.undo_null()
                if self._stopped:
                    return 0
                if null_score >= beta:
                    # Don't return mate scores from null search.
                    if null_score >= _MATE_BOUND:
                        null_score = beta
                    return null_score

        moves = self._order_moves(moves, tt_best, ply, prev_move)

        best_score = -_INF
        best_move: Move | None = None
        original_alpha = alpha

        for idx, move in enumerate(moves):
            state.apply_move(move)

            # ---- Late Move Reductions ----
            do_full_search = True
            score = 0
            if (idx >= LMR_MOVES_BEFORE and depth >= LMR_MIN_DEPTH
                    and not move.captured
                    and (ply >= _MAX_PLY or move != self._killers[ply][0])
                    and (ply >= _MAX_PLY or move != self._killers[ply][1])):
                r = 1 + (depth // 6) + (idx // 6)
                r = min(r, depth - 2)
                if r > 0:
                    score = -self._negamax(state, depth - 1 - r, -alpha - 1, -alpha,
                                            ply + 1, prev_move=move, allow_null=True)
                    if self._stopped:
                        state.undo_move()
                        return 0
                    do_full_search = score > alpha

            if do_full_search:
                if idx == 0:
                    score = -self._negamax(state, depth - 1, -beta, -alpha,
                                            ply + 1, prev_move=move, allow_null=True)
                else:
                    score = -self._negamax(state, depth - 1, -alpha - 1, -alpha,
                                            ply + 1, prev_move=move, allow_null=True)
                    if not self._stopped and alpha < score < beta:
                        score = -self._negamax(state, depth - 1, -beta, -alpha,
                                                ply + 1, prev_move=move, allow_null=True)

            state.undo_move()
            if self._stopped:
                return 0
            if score > best_score:
                best_score = score
                best_move = move
            if score > alpha:
                alpha = score
            if alpha >= beta:
                # Beta cutoff: record killer + counter + history for non-captures
                if not move.captured and 0 <= ply < _MAX_PLY:
                    slots = self._killers[ply]
                    if slots[0] != move:
                        slots[1] = slots[0]
                        slots[0] = move
                    self._history[(move.fc, move.fr, move.tc, move.tr)] = (
                        self._history.get((move.fc, move.fr, move.tc, move.tr), 0)
                        + depth * depth
                    )
                    if prev_move is not None:
                        self._counter[(prev_move.fc, prev_move.fr,
                                       prev_move.tc, prev_move.tr)] = move
                break

        if best_move is not None:
            flag = TT_EXACT
            if best_score <= original_alpha:
                flag = TT_UPPER
            elif best_score >= beta:
                flag = TT_LOWER
            self._tt.put(tt_key, depth, _tt_score_to_store(best_score, ply),
                         flag, best_move)

        return best_score

    # ------------------------------------------------------------------
    # Quiescence search
    # ------------------------------------------------------------------

    def _quiesce(self, state: GameState, alpha: int, beta: int,
                 qply: int, ply: int) -> int:
        self._nodes += 1
        if self._nodes & 2047 == 0 and self._time_expired():
            self._stopped = True
            return 0

        # Terminal check (winner already declared).
        if state.result is not None:
            winner = state.result.winner
            if winner == state.turn:
                return _mate_in(ply + qply)
            return _mated_in(ply + qply)

        # TT probe (depth-0 entries usable as bounds).
        tt_key = state.board.turn_hash(state.turn)
        tt_entry = self._tt.get(tt_key)
        if tt_entry is not None and tt_entry.depth >= 0:
            tt_score = _tt_score_from_probe(tt_entry.score, ply + qply)
            if tt_entry.flag == TT_EXACT:
                return tt_score
            if tt_entry.flag == TT_LOWER and tt_score >= beta:
                return tt_score
            if tt_entry.flag == TT_UPPER and tt_score <= alpha:
                return tt_score

        stand_pat = evaluate(state, state.turn)
        if qply >= QUIESCENCE_MAX_PLY:
            return stand_pat
        if stand_pat >= beta:
            return beta
        if alpha < stand_pat:
            alpha = stand_pat

        delta_margin = EVAL_WEIGHTS["delta_margin"]
        captures = generate_capture_moves(state.board, state.turn)
        # MVV ordering then SEE filter
        captures.sort(key=lambda m: -abs(m.captured))

        for move in captures:
            # Delta pruning: even capturing this victim won't reach alpha.
            if stand_pat + abs(move.captured) + delta_margin < alpha:
                continue
            # SEE prune: skip clearly losing captures.
            if see_capture(state.board, move) < 0:
                continue

            state.apply_move(move)
            score = -self._quiesce(state, -beta, -alpha, qply + 1, ply)
            state.undo_move()
            if self._stopped:
                return 0
            if score >= beta:
                return beta
            if score > alpha:
                alpha = score

        return alpha
