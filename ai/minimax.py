"""Negamax alpha-beta search with iterative deepening.

The search is feature-flagged via :class:`SearchConfig` so a strengthened
engine and a stripped "baseline" engine can be compared head-to-head in the
same process (see tools/strength_harness.py). With ``SearchConfig.baseline()``
the algorithm reduces to plain negamax + quiescence + a transposition table +
killer/MVV-LVA ordering (the original engine); ``SearchConfig.enhanced()`` adds:

  * principal variation search (PVS / null-window scouting)
  * null-move pruning (guarded against zugzwang / den-threats)
  * late-move reductions
  * the history heuristic for quiet-move ordering
  * root aspiration windows
  * a den-threat search extension
  * static-exchange-evaluation ordering + losing-capture pruning in quiescence
  * a piece-square-table evaluation term

Difficulty (real game): Easy = fixed 3-ply, Medium = fixed 5-ply, Hard =
iterative deepening under a ~2s time budget. The strength harness instead uses
a deterministic per-move *node* budget so results are reproducible.

The search mutates the GameState via make/undo and always unwinds fully, so
callers run it on a clone when the live game must stay readable.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from ai.evaluator import evaluate
from ai.see import see
from ai.transposition import EXACT, LOWER, UPPER, TranspositionTable
from config import (
    AI_DEPTH_EASY,
    AI_DEPTH_MEDIUM,
    AI_MAX_DEPTH,
    AI_TIME_HARD_MS,
    ASPIRATION_DELTA,
    DEN_BLACK_SQ,
    DEN_BLUE_SQ,
    LMR_MIN_DEPTH,
    LMR_MIN_MOVE_INDEX,
    NEIGHBORS,
    NMP_MIN_DEPTH,
    NMP_MIN_PIECES,
    NMP_REDUCTION,
    NUM_SQUARES,
    PIECE_VALUES,
    SEARCH_MAX_PLY,
)
from engine.board import Move
from engine.game_state import DRAW
from engine.move_generator import generate_captures, generate_moves

INF = 1 << 30
MATE = 1_000_000
MATE_THRESHOLD = MATE - 1000
_QCAP = 60                    # quiescence ply cap (captures reduce material anyway)
_FIXED_MODE_SAFETY_MS = 4000  # keep the UI responsive even for fixed-depth modes
_BLUE = 0

DIFFICULTY_EASY = 0
DIFFICULTY_MEDIUM = 1
DIFFICULTY_HARD = 2


@dataclass(frozen=True)
class SearchConfig:
    pvs: bool = True
    nmp: bool = True
    lmr: bool = True
    history: bool = True
    aspiration: bool = True
    extensions: bool = True
    see: bool = True           # SEE-based capture ordering (winning first)
    see_prune: bool = True     # skip SEE<0 captures in quiescence
    eval_pst: bool = True

    @staticmethod
    def baseline() -> SearchConfig:
        """The original engine: no enhancements."""
        return SearchConfig(False, False, False, False, False, False, False, False, False)

    @staticmethod
    def enhanced() -> SearchConfig:
        """All enhancements on (used for ablation; SEE is kept for comparison)."""
        return SearchConfig()

    @staticmethod
    def tuned() -> SearchConfig:
        """The shipped engine. Self-play (200+ games) showed that SEE and the
        piece-square-table term are net negatives for this engine (SEE's
        quiescence pruning mis-prunes tactics; the PST double-counts advancement
        the eval already rewards, so deeper search optimizes a distorted
        objective). Everything else -- PVS, null-move pruning, late-move
        reductions, the history heuristic, aspiration windows, and the den-threat
        extension -- is kept."""
        return SearchConfig(see=False, see_prune=False, eval_pst=False)


class Searcher:
    """One reusable search instance (holds its transposition table + config)."""

    def __init__(self, config: SearchConfig | None = None, max_nodes: int | None = None) -> None:
        self.cfg = config if config is not None else SearchConfig.enhanced()
        self.max_nodes = max_nodes
        self.tt = TranspositionTable()
        self.state = None
        self.nodes = 0
        self.stop = False
        self.deadline: float | None = None
        self.killers: list[list[Move | None]] = []
        self.history: list[list[int]] | None = None
        self.root_best: Move | None = None

    # -- stop conditions ----------------------------------------------------

    def _should_stop(self) -> bool:
        self.nodes += 1
        if self.stop:
            return True
        if self.max_nodes is not None and self.nodes >= self.max_nodes:
            self.stop = True
            return True
        if self.deadline is not None and (self.nodes & 2047) == 0 \
                and time.monotonic() >= self.deadline:
            self.stop = True
            return True
        return False

    # -- ordering -----------------------------------------------------------

    def _is_killer(self, m: Move, ply: int) -> bool:
        k1, k2 = self.killers[ply]
        return ((k1 is not None and k1.frm == m.frm and k1.to == m.to)
                or (k2 is not None and k2.frm == m.frm and k2.to == m.to))

    def _order(self, moves: list[Move], tt_move: Move | None, ply: int) -> None:
        board = self.state.board
        sq = board.sq
        k1, k2 = self.killers[ply]
        tf, tt_ = (tt_move.frm, tt_move.to) if tt_move else (-1, -1)
        k1f, k1t = (k1.frm, k1.to) if k1 else (-1, -1)
        k2f, k2t = (k2.frm, k2.to) if k2 else (-1, -1)
        hist = self.history
        use_see = self.cfg.see

        def key(m: Move) -> int:
            if m.frm == tf and m.to == tt_:
                return 1_000_000_000
            if m.captured:
                mvv = PIECE_VALUES[m.captured & 0x0F] * 16 - PIECE_VALUES[sq[m.frm] & 0x0F]
                if use_see and see(board, m.frm, m.to) < 0:
                    return -500_000_000 + mvv          # losing capture: try last
                return 500_000_000 + mvv               # winning/equal capture
            if (m.frm == k1f and m.to == k1t) or (m.frm == k2f and m.to == k2t):
                return 400_000_000
            if hist is not None:
                return hist[m.frm][m.to]
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

    # -- den-threat detection (extension trigger) ---------------------------

    def _own_den_threatened(self) -> bool:
        """True if an enemy piece is adjacent to the side-to-move's own den and
        could step in next move (analogous to being in check)."""
        st = self.state
        sq = st.board.sq
        stm = st.to_move
        own_den = DEN_BLUE_SQ if stm == _BLUE else DEN_BLACK_SQ
        for nsq in NEIGHBORS[own_den]:
            code = sq[nsq]
            if code and (code >> 4) != stm:
                return True
        return False

    # -- quiescence ---------------------------------------------------------

    def _quiescence(self, alpha: int, beta: int, ply: int) -> int:
        if self._should_stop():
            return alpha
        st = self.state
        stand = evaluate(st, self.cfg.eval_pst)
        if stand >= beta:
            return stand
        if stand > alpha:
            alpha = stand
        if ply >= _QCAP:
            return alpha

        board = st.board
        caps = generate_captures(board, st.to_move)
        self._order_caps(caps)
        use_prune = self.cfg.see_prune
        for m in caps:
            if use_prune and see(board, m.frm, m.to) < 0:
                continue                              # skip clearly losing captures
            st.make_move(m, detect_no_moves=False)
            res = st.result
            if res is not None:
                score = 0 if res == DRAW else MATE - (ply + 1)
            else:
                score = -self._quiescence(-beta, -alpha, ply + 1)
            st.undo_move()
            if self.stop:
                return alpha
            if score > alpha:
                alpha = score
                if alpha >= beta:
                    break
        return alpha

    # -- main search --------------------------------------------------------

    def _negamax(self, depth: int, alpha: int, beta: int, ply: int) -> int:
        if self._should_stop():
            return 0
        st = self.state
        if ply >= SEARCH_MAX_PLY:
            return evaluate(st, self.cfg.eval_pst)
        alpha_orig = alpha
        key = st.hash

        tt_move: Move | None = None
        entry = self.tt.probe(key)
        if entry is not None:
            tt_move = entry.move
            if entry.depth >= depth and abs(entry.score) < MATE_THRESHOLD:
                f = entry.flag
                if f == EXACT:
                    return entry.score
                if f == LOWER:
                    if entry.score > alpha:
                        alpha = entry.score
                elif f == UPPER:
                    if entry.score < beta:
                        beta = entry.score
                if alpha >= beta:
                    return entry.score

        critical = self.cfg.extensions and self._own_den_threatened()
        if critical:
            depth += 1                                # den-threat extension

        if depth <= 0:
            return self._quiescence(alpha, beta, ply)

        # Null-move pruning (disabled when in a den-threat or low on material).
        if (self.cfg.nmp and depth >= NMP_MIN_DEPTH and not critical
                and beta < MATE_THRESHOLD
                and st.counts[st.to_move] >= NMP_MIN_PIECES):
            st.make_null()
            r = NMP_REDUCTION + (1 if depth >= 6 else 0)
            null_score = -self._negamax(depth - 1 - r, -beta, -beta + 1, ply + 1)
            st.undo_null()
            if self.stop:
                return 0
            if null_score >= beta:
                return beta                           # fail-high (never a mate score)

        moves = generate_moves(st.board, st.to_move)
        if not moves:
            return -MATE + ply                        # no legal move: side to move loses

        self._order(moves, tt_move, ply)
        best = -INF
        best_move = moves[0]
        pvs = self.cfg.pvs
        lmr = self.cfg.lmr
        move_index = 0
        for m in moves:
            is_capture = m.captured != 0
            st.make_move(m, detect_no_moves=False)
            res = st.result
            if res is not None:
                score = 0 if res == DRAW else MATE - (ply + 1)
                st.undo_move()
            else:
                if pvs and move_index > 0:
                    reduction = 0
                    if (lmr and depth >= LMR_MIN_DEPTH and move_index >= LMR_MIN_MOVE_INDEX
                            and not is_capture and not critical and not self._is_killer(m, ply)):
                        reduction = 1 + (1 if (move_index >= 6 and depth >= 6) else 0)
                    score = -self._negamax(depth - 1 - reduction, -alpha - 1, -alpha, ply + 1)
                    if not self.stop and score > alpha:
                        score = -self._negamax(depth - 1, -beta, -alpha, ply + 1)
                else:
                    score = -self._negamax(depth - 1, -beta, -alpha, ply + 1)
                st.undo_move()
            if self.stop:
                return best if best > -INF else 0
            if score > best:
                best = score
                best_move = m
                if score > alpha:
                    alpha = score
                    if alpha >= beta:
                        if not is_capture:
                            self._add_killer(m, ply)
                            if self.history is not None:
                                self.history[m.frm][m.to] += depth * depth
                        break
            move_index += 1

        flag = EXACT
        if best <= alpha_orig:
            flag = UPPER
        elif best >= beta:
            flag = LOWER
        self.tt.store(key, depth, flag, best, best_move)
        return best

    def _search_root(self, depth: int, alpha: int, beta: int) -> tuple[Move | None, int]:
        st = self.state
        moves = generate_moves(st.board, st.to_move)
        if not moves:
            return None, -MATE
        self._order(moves, self.root_best, 0)
        best = -INF
        best_move = moves[0]
        pvs = self.cfg.pvs
        move_index = 0
        for m in moves:
            st.make_move(m, detect_no_moves=False)
            res = st.result
            if res is not None:
                score = 0 if res == DRAW else MATE - 1
                st.undo_move()
            else:
                if pvs and move_index > 0:
                    score = -self._negamax(depth - 1, -alpha - 1, -alpha, 1)
                    if not self.stop and alpha < score < beta:
                        score = -self._negamax(depth - 1, -beta, -alpha, 1)
                else:
                    score = -self._negamax(depth - 1, -beta, -alpha, 1)
                st.undo_move()
            if self.stop:
                break
            if score > best:
                best = score
                best_move = m
                if score > alpha:
                    alpha = score
                    if alpha >= beta:
                        break                          # fail-high (aspiration widens)
            move_index += 1
        return best_move, best

    def _aspiration(self, depth: int, prev: int) -> tuple[Move | None, int]:
        delta = ASPIRATION_DELTA
        alpha = prev - delta
        beta = prev + delta
        while True:
            bm, score = self._search_root(depth, alpha, beta)
            if self.stop:
                return bm, score
            if score <= alpha:
                alpha = max(-INF, alpha - delta)
                delta *= 2
            elif score >= beta:
                beta = min(INF, beta + delta)
                delta *= 2
            else:
                return bm, score

    def search(self, state, *, depth: int | None = None, time_ms: int | None = None,
               max_nodes: int | None = None) -> Move | None:
        """Return the best move for ``state.to_move``.

        Modes: fixed ``depth`` (single search), ``time_ms`` (iterative under a
        wall-clock budget), or a ``max_nodes`` budget (iterative, deterministic).
        """
        self.state = state
        self.nodes = 0
        self.stop = False
        self.root_best = None
        self.completed_depth = 0
        if max_nodes is not None:
            self.max_nodes = max_nodes
        self.killers = [[None, None] for _ in range(SEARCH_MAX_PLY + _QCAP + 4)]
        self.history = ([[0] * NUM_SQUARES for _ in range(NUM_SQUARES)]
                        if self.cfg.history else None)
        # Cleared between real moves to avoid graph-history-interaction on
        # repetition/50-move draw scores; iterative deepening within this call
        # still shares the freshly built table.
        self.tt.clear()

        moves = state.legal_moves()
        if not moves:
            return None
        best_move = moves[0]

        fixed = depth is not None and time_ms is None and self.max_nodes is None
        if fixed:
            self.deadline = time.monotonic() + _FIXED_MODE_SAFETY_MS / 1000.0
            bm, _ = self._search_root(depth, -INF, INF)
            self.completed_depth = depth
            return bm if bm is not None else best_move

        # Iterative deepening (time- and/or node-limited, optionally depth-capped).
        self.deadline = (time.monotonic() + time_ms / 1000.0) if time_ms is not None else None
        max_d = depth if depth is not None else AI_MAX_DEPTH
        prev = 0
        d = 1
        while d <= max_d:
            if self.cfg.aspiration and d >= 3 and abs(prev) < MATE_THRESHOLD:
                bm, score = self._aspiration(d, prev)
            else:
                bm, score = self._search_root(d, -INF, INF)
            if self.stop:
                break                                  # discard the incomplete depth
            if bm is not None:
                best_move = bm
                self.root_best = bm
                prev = score
                self.completed_depth = d
            if abs(score) >= MATE_THRESHOLD:
                break
            d += 1
        return best_move


class AIPlayer:
    """Difficulty-configured front end over :class:`Searcher` (uses the enhanced
    engine by default)."""

    def __init__(self, color: int, difficulty: int, config: SearchConfig | None = None) -> None:
        self.color = color
        self.difficulty = difficulty
        self._searcher = Searcher(config if config is not None else SearchConfig.tuned())

    def choose_move(self, state) -> Move | None:
        if self.difficulty == DIFFICULTY_EASY:
            return self._searcher.search(state, depth=AI_DEPTH_EASY)
        if self.difficulty == DIFFICULTY_MEDIUM:
            return self._searcher.search(state, depth=AI_DEPTH_MEDIUM)
        return self._searcher.search(state, time_ms=AI_TIME_HARD_MS)
