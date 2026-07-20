"""Negamax alpha-beta search with iterative deepening.

Difficulty:
  * Easy   - fixed 3-ply search (instant)
  * Medium - fixed 5-ply search (fast)
  * Hard   - iterative deepening under a time budget (~2s)

The search mutates the ``GameState`` it is given via make/undo and always
unwinds fully, so callers run it on a *clone* when the live game must stay
readable (e.g. from a background thread).
"""

from __future__ import annotations

import time

from ai.evaluator import evaluate
from ai.transposition import EXACT, LOWER, UPPER, TranspositionTable
from config import AI_DEPTH_EASY, AI_DEPTH_MEDIUM, AI_MAX_DEPTH, AI_TIME_HARD_MS, PIECE_VALUES
from engine.board import Move
from engine.game_state import DRAW
from engine.move_generator import generate_captures, generate_moves

INF = 1 << 30
MATE = 1_000_000
MATE_THRESHOLD = MATE - 1000
_QUIESCENCE_PLY_CAP = 60          # captures strictly reduce material, so this is a safety net
_FIXED_MODE_SAFETY_MS = 4000      # guarantee UI responsiveness even for fixed depth

DIFFICULTY_EASY = 0
DIFFICULTY_MEDIUM = 1
DIFFICULTY_HARD = 2


class Searcher:
    """One reusable search instance (keeps its transposition table warm)."""

    def __init__(self) -> None:
        self.tt = TranspositionTable()
        self.state = None
        self.nodes = 0
        self.stop = False
        self.deadline: float | None = None
        self.killers: list[list[Move | None]] = []
        self.root_best: Move | None = None

    # -- ordering -----------------------------------------------------------

    def _order(self, moves: list[Move], tt_move: Move | None, ply: int) -> None:
        sq = self.state.board.sq
        k1, k2 = self.killers[ply]
        tf, tt_ = (tt_move.frm, tt_move.to) if tt_move else (-1, -1)
        k1f, k1t = (k1.frm, k1.to) if k1 else (-1, -1)
        k2f, k2t = (k2.frm, k2.to) if k2 else (-1, -1)

        def key(m: Move) -> int:
            if m.frm == tf and m.to == tt_:
                return 3_000_000
            if m.captured:
                atk = PIECE_VALUES[sq[m.frm] & 0x0F]
                vic = PIECE_VALUES[m.captured & 0x0F]
                return 1_000_000 + vic * 16 - atk
            if (m.frm == k1f and m.to == k1t) or (m.frm == k2f and m.to == k2t):
                return 500_000
            return 0

        moves.sort(key=key, reverse=True)

    def _order_caps(self, caps: list[Move]) -> None:
        sq = self.state.board.sq

        def key(m: Move) -> int:
            return PIECE_VALUES[m.captured & 0x0F] * 16 - PIECE_VALUES[sq[m.frm] & 0x0F]

        caps.sort(key=key, reverse=True)

    def _add_killer(self, move: Move, ply: int) -> None:
        slot = self.killers[ply]
        if slot[0] is None or (slot[0].frm, slot[0].to) != (move.frm, move.to):
            slot[1] = slot[0]
            slot[0] = move

    # -- timing -------------------------------------------------------------

    def _timed_out(self) -> bool:
        self.nodes += 1
        if self.nodes & 2047 == 0 and self.deadline is not None:
            if time.monotonic() >= self.deadline:
                self.stop = True
        return self.stop

    # -- search -------------------------------------------------------------

    def _quiescence(self, alpha: int, beta: int, ply: int) -> int:
        if self._timed_out():
            return alpha
        state = self.state
        stand = evaluate(state)
        if stand >= beta:
            return stand
        if stand > alpha:
            alpha = stand
        if ply >= _QUIESCENCE_PLY_CAP:
            return alpha

        caps = generate_captures(state.board, state.to_move)
        self._order_caps(caps)
        for m in caps:
            state.make_move(m, detect_no_moves=False)
            res = state.result
            if res is not None:
                score = 0 if res == DRAW else MATE - (ply + 1)
            else:
                score = -self._quiescence(-beta, -alpha, ply + 1)
            state.undo_move()
            if self.stop:
                return alpha
            if score > alpha:
                alpha = score
                if alpha >= beta:
                    break
        return alpha

    def _negamax(self, depth: int, alpha: int, beta: int, ply: int) -> int:
        if self._timed_out():
            return 0
        state = self.state
        key = state.hash
        alpha_orig = alpha

        tt_move: Move | None = None
        entry = self.tt.probe(key)
        if entry is not None:
            tt_move = entry.move
            if entry.depth >= depth and abs(entry.score) < MATE_THRESHOLD:
                if entry.flag == EXACT:
                    return entry.score
                if entry.flag == LOWER and entry.score > alpha:
                    alpha = entry.score
                elif entry.flag == UPPER and entry.score < beta:
                    beta = entry.score
                if alpha >= beta:
                    return entry.score

        if depth <= 0:
            return self._quiescence(alpha, beta, ply)

        moves = generate_moves(state.board, state.to_move)
        if not moves:
            return -MATE + ply          # no legal move: the side to move loses

        self._order(moves, tt_move, ply)
        best = -INF
        best_move = moves[0]
        for m in moves:
            state.make_move(m, detect_no_moves=False)
            res = state.result
            if res is not None:
                score = 0 if res == DRAW else MATE - (ply + 1)
            else:
                score = -self._negamax(depth - 1, -beta, -alpha, ply + 1)
            state.undo_move()
            if self.stop:
                return best if best > -INF else 0
            if score > best:
                best = score
                best_move = m
                if score > alpha:
                    alpha = score
                    if alpha >= beta:
                        if m.captured == 0:
                            self._add_killer(m, ply)
                        break

        flag = EXACT
        if best <= alpha_orig:
            flag = UPPER
        elif best >= beta:
            flag = LOWER
        self.tt.store(key, depth, flag, best, best_move)
        return best

    def _search_root(self, depth: int) -> tuple[Move | None, int]:
        state = self.state
        moves = generate_moves(state.board, state.to_move)
        if not moves:
            return None, -MATE
        self._order(moves, self.root_best, 0)
        best = -INF
        best_move = moves[0]
        alpha = -INF
        for m in moves:
            state.make_move(m, detect_no_moves=False)
            res = state.result
            if res is not None:
                score = 0 if res == DRAW else MATE - 1
            else:
                score = -self._negamax(depth - 1, -INF, -alpha, 1)
            state.undo_move()
            if self.stop:
                break
            if score > best:
                best = score
                best_move = m
                if score > alpha:
                    alpha = score
        return best_move, best

    def search(self, state, *, depth: int | None, time_ms: int | None) -> Move | None:
        """Return the best move for ``state.to_move``.

        Exactly one of ``depth`` (fixed) or ``time_ms`` (iterative) is used.
        """
        self.state = state
        self.nodes = 0
        self.stop = False
        self.root_best = None
        self.killers = [[None, None] for _ in range(AI_MAX_DEPTH + _QUIESCENCE_PLY_CAP + 4)]
        # Clear the table between real moves. Repetition / 50-move draw scores are
        # history-dependent, so a value stored under a bare board+side key on one
        # turn must not be reused on a later turn reached via a different history
        # (the graph-history-interaction problem). Clearing per move removes that
        # cross-turn contamination; iterative deepening within this call still
        # shares the freshly built table. (Residual within-search GHI is a known,
        # low-impact limitation accepted for a casual-play engine.)
        self.tt.clear()

        moves = state.legal_moves()
        if not moves:
            return None
        best_move = moves[0]

        if time_ms is None:                      # fixed-depth (Easy / Medium)
            self.deadline = time.monotonic() + _FIXED_MODE_SAFETY_MS / 1000.0
            bm, _ = self._search_root(depth)
            if bm is not None:
                best_move = bm
        else:                                    # iterative deepening (Hard)
            self.deadline = time.monotonic() + time_ms / 1000.0
            d = 1
            while d <= AI_MAX_DEPTH:
                bm, score = self._search_root(d)
                if self.stop:
                    break                        # discard the incomplete depth
                if bm is not None:
                    best_move = bm
                    self.root_best = bm
                if abs(score) >= MATE_THRESHOLD:
                    break                        # forced result found
                d += 1
        return best_move


class AIPlayer:
    """Difficulty-configured front end over :class:`Searcher`."""

    def __init__(self, color: int, difficulty: int) -> None:
        self.color = color
        self.difficulty = difficulty
        self._searcher = Searcher()

    def choose_move(self, state) -> Move | None:
        if self.difficulty == DIFFICULTY_EASY:
            return self._searcher.search(state, depth=AI_DEPTH_EASY, time_ms=None)
        if self.difficulty == DIFFICULTY_MEDIUM:
            return self._searcher.search(state, depth=AI_DEPTH_MEDIUM, time_ms=None)
        return self._searcher.search(state, depth=None, time_ms=AI_TIME_HARD_MS)
