//! Negamax with principal variation search.
//!
//! Feature-for-feature the Python engine's search — aspiration windows, PVS,
//! null-move pruning, reverse futility, razoring, futility, late-move pruning and
//! reductions, killers / counter-moves / history, a transposition table, and a
//! quiescence search with SEE and delta pruning — with its known defects fixed
//! rather than carried across. Those are called out at the point where each
//! decision is made.
//!
//! Jungle has no check, so the tactical analogue of a mate threat is **den
//! entry**: a move onto the enemy den wins immediately and unconditionally. That
//! shapes the search in three places — such a move is ordered first, it is never
//! reduced or pruned, and reaching one ends the node at once.

use std::sync::atomic::{AtomicBool, Ordering as AtomicOrdering};
use std::sync::Arc;
use std::time::{Duration, Instant};

use jungle_core::bitboard::enemy_den;
use jungle_core::position::Position;
use jungle_core::types::{Move, MoveList};
use jungle_core::generate_into;
use jungle_eval::evaluate;
use jungle_eval::params::PIECE_VALUES;

use crate::ordering::{Heuristics, OrderedMoves};
use crate::params::SearchParams;
use crate::score::*;
use crate::tt::{TranspositionTable, BOUND_EXACT, BOUND_LOWER, BOUND_UPPER};

/// How often to look at the clock. Checking every node costs more than it saves.
const CLOCK_INTERVAL: u64 = 2047;

#[derive(Clone, Debug, Default)]
pub struct Limits {
    pub depth: Option<i32>,
    pub nodes: Option<u64>,
    pub movetime: Option<Duration>,
}

impl Limits {
    pub fn depth(d: i32) -> Limits {
        Limits {
            depth: Some(d),
            ..Default::default()
        }
    }
    /// A fixed node budget: deterministic, so an A/B match is reproducible and
    /// free of timing noise. This is the limit tuning matches should use.
    pub fn nodes(n: u64) -> Limits {
        Limits {
            nodes: Some(n),
            ..Default::default()
        }
    }
    pub fn movetime(ms: u64) -> Limits {
        Limits {
            movetime: Some(Duration::from_millis(ms)),
            ..Default::default()
        }
    }
}

#[derive(Clone, Debug, Default)]
pub struct SearchResult {
    pub best_move: Option<Move>,
    pub score: i32,
    pub depth: i32,
    pub seldepth: usize,
    pub nodes: u64,
    pub elapsed: Duration,
}

pub struct Searcher {
    tt: TranspositionTable,
    heur: Heuristics,
    params: SearchParams,
    nodes: u64,
    seldepth: usize,
    stopped: bool,
    stop_flag: Arc<AtomicBool>,
    start: Instant,
    deadline: Option<Instant>,
    node_limit: Option<u64>,
    root_best: Option<Move>,
    root_moves_done: usize,
}

impl Searcher {
    pub fn new(tt_megabytes: usize) -> Searcher {
        Searcher::with_params(tt_megabytes, SearchParams::default())
    }

    /// A searcher with non-default tuning. Used by the A/B harness so two
    /// configurations can play each other in one process.
    pub fn with_params(tt_megabytes: usize, params: SearchParams) -> Searcher {
        Searcher {
            tt: TranspositionTable::new(tt_megabytes),
            heur: Heuristics::new(),
            params,
            nodes: 0,
            seldepth: 0,
            stopped: false,
            stop_flag: Arc::new(AtomicBool::new(false)),
            start: Instant::now(),
            deadline: None,
            node_limit: None,
            root_best: None,
            root_moves_done: 0,
        }
    }

    /// A handle another thread can set to abort the search promptly.
    pub fn stop_handle(&self) -> Arc<AtomicBool> {
        Arc::clone(&self.stop_flag)
    }

    /// Forget everything learned. Between unrelated positions only: the table and
    /// the history are worth carrying across the moves of one game.
    pub fn reset(&mut self) {
        self.tt.clear();
        self.heur.clear();
    }

    pub fn nodes(&self) -> u64 {
        self.nodes
    }

    pub fn hashfull(&self) -> usize {
        self.tt.hashfull()
    }

    #[inline(always)]
    fn out_of_time(&self) -> bool {
        if self.stop_flag.load(AtomicOrdering::Relaxed) {
            return true;
        }
        if let Some(limit) = self.node_limit {
            if self.nodes >= limit {
                return true;
            }
        }
        match self.deadline {
            Some(d) => Instant::now() >= d,
            None => false,
        }
    }

    #[inline(always)]
    fn check_clock(&mut self) -> bool {
        if self.nodes & CLOCK_INTERVAL == 0 && self.out_of_time() {
            self.stopped = true;
        }
        self.stopped
    }

    // -----------------------------------------------------------------
    // Iterative deepening
    // -----------------------------------------------------------------

    pub fn think(&mut self, pos: &mut Position, limits: &Limits) -> SearchResult {
        self.nodes = 0;
        self.seldepth = 0;
        self.stopped = false;
        self.root_best = None;
        self.stop_flag.store(false, AtomicOrdering::Relaxed);
        self.start = Instant::now();
        self.deadline = limits.movetime.map(|d| self.start + d);
        self.node_limit = limits.nodes;
        self.tt.new_generation();

        let max_depth = limits.depth.unwrap_or(MAX_PLY as i32 - 2);

        let mut root = MoveList::new();
        generate_into(pos, &mut root);
        if root.is_empty() {
            return SearchResult {
                best_move: None,
                score: mated_in(0),
                elapsed: self.start.elapsed(),
                ..Default::default()
            };
        }
        // One legal move: play it. Searching would only tell us what we already
        // have to do, and the clock is better spent on the next position.
        if root.len() == 1 {
            return SearchResult {
                best_move: Some(root[0]),
                score: 0,
                depth: 1,
                seldepth: 1,
                nodes: 1,
                elapsed: self.start.elapsed(),
            };
        }

        let mut best = root[0];
        let mut score = 0;
        let mut completed = 0;
        let mut previous: Option<i32> = None;
        let mut last_iteration = Duration::ZERO;

        for depth in 1..=max_depth {
            // Don't start an iteration we can predict will not finish; the
            // partial result is usually worth less than the time it costs.
            if depth > 1 {
                if let Some(d) = self.deadline {
                    let now = Instant::now();
                    if now + last_iteration.mul_f32(1.5) > d {
                        break;
                    }
                }
            }

            let iteration_start = Instant::now();
            let iteration_score = self.aspiration(pos, depth, previous);

            if self.stopped {
                // Keep a better move found before the interruption: the moves are
                // ordered best-first, so a partial iteration has still searched
                // the most promising ones.
                if self.root_moves_done >= 1 {
                    if let Some(m) = self.root_best {
                        best = m;
                        score = iteration_score;
                        completed = depth;
                    }
                }
                break;
            }

            if let Some(m) = self.root_best {
                best = m;
            }
            score = iteration_score;
            previous = Some(iteration_score);
            completed = depth;
            last_iteration = iteration_start.elapsed();
            self.heur.age();

            // A forced mate is found; searching deeper cannot improve on it.
            if is_mate_score(iteration_score) {
                break;
            }
        }

        SearchResult {
            best_move: Some(best),
            score,
            depth: completed,
            seldepth: self.seldepth,
            nodes: self.nodes,
            elapsed: self.start.elapsed(),
        }
    }

    /// Search one depth, narrowing the window around the previous score and
    /// widening on a fail.
    fn aspiration(&mut self, pos: &mut Position, depth: i32, previous: Option<i32>) -> i32 {
        let Some(prev) = previous.filter(|_| depth >= self.params.aspiration_min_depth) else {
            return self.search_root(pos, depth, -INF, INF);
        };

        let mut delta = self.params.aspiration_delta;
        let mut alpha = (prev - delta).max(-INF);
        let mut beta = (prev + delta).min(INF);

        loop {
            let score = self.search_root(pos, depth, alpha, beta);
            if self.stopped {
                return score;
            }
            if score <= alpha {
                // Fail low: widen downward but keep beta, so the re-search stays
                // narrow on the side that is not in doubt.
                beta = (alpha + beta) / 2;
                alpha = (score - delta).max(-INF);
            } else if score >= beta {
                beta = (score + delta).min(INF);
            } else {
                return score;
            }
            delta += delta / 2;
            if delta > 32 * self.params.aspiration_delta {
                return self.search_root(pos, depth, -INF, INF);
            }
        }
    }

    fn search_root(&mut self, pos: &mut Position, depth: i32, mut alpha: i32, beta: i32) -> i32 {
        let key = pos.key();
        let tt_move = self.tt.probe(key, 0).and_then(|h| h.mv);

        let mut moves = MoveList::new();
        generate_into(pos, &mut moves);
        let mut ordered = OrderedMoves::new(pos, moves, tt_move, &self.heur, 0, None);

        let original_alpha = alpha;
        let mut best_score = -INF;
        let mut best_move = None;
        let mut idx = 0usize;
        self.root_moves_done = 0;

        while let Some(m) = ordered.next_move() {
            pos.make(m);
            let score = if idx == 0 {
                -self.negamax(pos, depth - 1, -beta, -alpha, 1, Some(m), true)
            } else {
                let s = -self.negamax(pos, depth - 1, -alpha - 1, -alpha, 1, Some(m), true);
                if !self.stopped && s > alpha && s < beta {
                    -self.negamax(pos, depth - 1, -beta, -alpha, 1, Some(m), true)
                } else {
                    s
                }
            };
            pos.unmake();

            if self.stopped {
                break;
            }
            self.root_moves_done += 1;

            if score > best_score {
                best_score = score;
                best_move = Some(m);
                // Commit mid-iteration so an interrupted search still improves on
                // the previous depth rather than discarding its work.
                if score > original_alpha {
                    self.root_best = Some(m);
                }
            }
            if score > alpha {
                alpha = score;
            }
            if alpha >= beta {
                break;
            }
            idx += 1;
        }

        if let Some(m) = best_move {
            let bound = if best_score <= original_alpha {
                BOUND_UPPER
            } else if best_score >= beta {
                BOUND_LOWER
            } else {
                BOUND_EXACT
            };
            self.tt
                .store(key, Some(m), best_score, 0, depth as i8, bound, 0);
        }
        best_score
    }

    // -----------------------------------------------------------------
    // Main search
    // -----------------------------------------------------------------

    #[allow(clippy::too_many_arguments)]
    fn negamax(
        &mut self,
        pos: &mut Position,
        depth: i32,
        mut alpha: i32,
        mut beta: i32,
        ply: i32,
        prev: Option<Move>,
        allow_null: bool,
    ) -> i32 {
        self.nodes += 1;
        self.seldepth = self.seldepth.max(ply as usize);
        if self.check_clock() {
            return 0;
        }

        // Draws. Repetition is a search-side draw score, not a game rule.
        if ply > 0 && (pos.is_repetition() || pos.is_fifty_move_draw()) {
            return 0;
        }

        // Mate-distance pruning: if we already have a mate at least this fast,
        // nothing deeper here can matter.
        alpha = alpha.max(mated_in(ply));
        beta = beta.min(mate_in(ply + 1));
        if alpha >= beta {
            return alpha;
        }

        let is_pv = beta - alpha > 1;
        let key = pos.key();

        let hit = self.tt.probe(key, ply);
        let mut tt_move = None;
        if let Some(ref h) = hit {
            tt_move = h.mv;
            if h.depth as i32 >= depth && !is_pv {
                let usable = match h.bound {
                    BOUND_EXACT => true,
                    BOUND_LOWER => h.score >= beta,
                    BOUND_UPPER => h.score <= alpha,
                    _ => false,
                };
                if usable {
                    return h.score;
                }
            }
        }

        // Already decided by the rules.
        if let Some(winner) = pos.result() {
            return if winner == pos.side_to_move() {
                mate_in(ply)
            } else {
                mated_in(ply)
            };
        }

        if depth <= 0 {
            return self.quiesce(pos, alpha, beta, ply, 0);
        }

        let mut moves = MoveList::new();
        generate_into(pos, &mut moves);
        if moves.is_empty() {
            // No legal move is a loss for the side to move, not a draw.
            return mated_in(ply);
        }

        let side = pos.side_to_move();
        let den = enemy_den(side.index());

        let outside_mate_window = alpha.abs() < MATE_BOUND && beta.abs() < MATE_BOUND;
        let mut static_eval = None;

        if !is_pv && outside_mate_window {
            let eval = evaluate(pos, side);
            static_eval = Some(eval);
            let p = self.params;

            // Reverse futility: so far ahead that giving up a few plies still
            // beats beta.
            if p.use_rfp && depth <= p.rfp_max_depth && eval - p.rfp_margin * depth >= beta {
                return eval;
            }

            // Razoring: so far behind that only a tactic saves us; let quiescence
            // decide whether one exists.
            if p.use_razoring && depth <= p.razor_max_depth && eval + p.razor_margin < alpha {
                let q = self.quiesce(pos, alpha, beta, ply, 0);
                if self.stopped {
                    return 0;
                }
                if q < alpha {
                    return q;
                }
            }

            // Null-move pruning. Withheld when the side to move is down to a
            // couple of pieces, where zugzwang-like positions make passing a
            // materially different proposition.
            if p.use_nmp
                && allow_null
                && depth >= p.nmp_min_depth
                && pos.alive_count(side) >= p.nmp_min_pieces
                && eval >= beta
            {
                pos.make_null();
                let null_score =
                    -self.negamax(pos, depth - 1 - p.nmp_reduction, -beta, -beta + 1, ply + 1, None, false);
                pos.unmake_null();
                if self.stopped {
                    return 0;
                }
                if null_score >= beta {
                    // A mate score proved by *not moving* is not a real mate.
                    return if null_score >= MATE_BOUND { beta } else { null_score };
                }
            }
        }

        let mut ordered = OrderedMoves::new(pos, moves, tt_move, &self.heur, ply as usize, prev);
        let original_alpha = alpha;
        let mut best_score = -INF;
        let mut best_move = None;
        let mut idx = 0usize;
        let mut quiets_tried = 0usize;
        let mut tried: [Move; 32] = [Move(0); 32];

        while let Some(m) = ordered.next_move() {
            let is_capture = pos.piece_at(m.to()).is_some();
            let enters_den = m.to() == den;

            // Entering the enemy den wins on the spot. Ordering puts it first, so
            // this ends the node immediately -- with the score the search would
            // have produced had it played the move and looked.
            if enters_den {
                best_score = mate_in(ply + 1);
                best_move = Some(m);
                break;
            }

            let is_quiet = !is_capture;

            // Forward pruning of late or hopeless quiet moves, once we already
            // have something to fall back on.
            if is_quiet && best_move.is_some() && !is_pv && outside_mate_window {
                let p = self.params;
                if p.use_lmp && quiets_tried >= p.lmp_base + (depth * depth) as usize {
                    idx += 1;
                    continue;
                }
                if let Some(eval) = static_eval {
                    if p.use_futility
                        && depth <= p.futility_max_depth
                        && eval + p.futility_margin <= alpha
                    {
                        idx += 1;
                        continue;
                    }
                }
            }

            pos.make(m);

            // Late-move reductions. Never inside the principal variation, and
            // never for a capture -- reducing the moves that change material is
            // how a search talks itself out of a tactic.
            // A killer is a quiet move already known to refute something at this
            // ply, so reducing it would search the one quiet move with evidence
            // behind it *less* deeply than the ones without. Measured: leaving
            // this out cost about 56 Elo at fixed depth 5 against the engine this
            // one replaces, while looking like a harmless simplification.
            let reducible = is_quiet
                && (self.params.lmr_reduce_killers || !self.heur.is_killer(ply as usize, m));
            if self.params.use_lmr
                && !is_pv
                && idx >= self.params.lmr_moves_before
                && depth >= self.params.lmr_min_depth
                && reducible
            {
                let r = (1 + (depth / 6) + (idx as i32 / 6)).min(depth - 2);
                if r > 0 {
                    let reduced =
                        -self.negamax(pos, depth - 1 - r, -alpha - 1, -alpha, ply + 1, Some(m), true);
                    if self.stopped {
                        pos.unmake();
                        return 0;
                    }
                    if reduced <= alpha {
                        // The reduced search agrees this move is not worth more;
                        // take its word rather than paying for a full one.
                        pos.unmake();
                        if reduced > best_score {
                            best_score = reduced;
                            best_move = Some(m);
                        }
                        if quiets_tried < tried.len() {
                            tried[quiets_tried] = m;
                        }
                        quiets_tried += 1;
                        idx += 1;
                        continue;
                    }
                }
            }

            let score = if idx == 0 {
                -self.negamax(pos, depth - 1, -beta, -alpha, ply + 1, Some(m), true)
            } else {
                let s = -self.negamax(pos, depth - 1, -alpha - 1, -alpha, ply + 1, Some(m), true);
                if !self.stopped && s > alpha && s < beta {
                    -self.negamax(pos, depth - 1, -beta, -alpha, ply + 1, Some(m), true)
                } else {
                    s
                }
            };

            pos.unmake();
            if self.stopped {
                return 0;
            }

            if score > best_score {
                best_score = score;
                best_move = Some(m);
            }
            if score > alpha {
                alpha = score;
            }
            if alpha >= beta {
                if is_quiet {
                    let n = quiets_tried.min(tried.len());
                    self.heur
                        .record_cutoff(side, m, depth, ply as usize, prev, &tried[..n]);
                }
                break;
            }
            if is_quiet {
                if quiets_tried < tried.len() {
                    tried[quiets_tried] = m;
                }
                quiets_tried += 1;
            }
            idx += 1;
        }

        if let Some(m) = best_move {
            let bound = if best_score <= original_alpha {
                BOUND_UPPER
            } else if best_score >= beta {
                BOUND_LOWER
            } else {
                BOUND_EXACT
            };
            self.tt.store(
                key,
                Some(m),
                best_score,
                static_eval.unwrap_or(0),
                depth as i8,
                bound,
                ply,
            );
        }

        best_score
    }

    // -----------------------------------------------------------------
    // Quiescence
    // -----------------------------------------------------------------

    /// Search the tactical continuations only, so evaluation is never applied in
    /// the middle of an exchange.
    ///
    /// Fail-soft, unlike the Python version, which returned `beta` on a cutoff
    /// while the main search returned a real score. That mismatch was contained
    /// only because quiescence never wrote to the transposition table; making the
    /// two agree removes the trap rather than the containment.
    fn quiesce(&mut self, pos: &mut Position, mut alpha: i32, beta: i32, ply: i32, qply: i32) -> i32 {
        self.nodes += 1;
        self.seldepth = self.seldepth.max((ply + qply) as usize);
        if self.check_clock() {
            return 0;
        }

        let distance = ply + qply;

        if let Some(winner) = pos.result() {
            return if winner == pos.side_to_move() {
                mate_in(distance)
            } else {
                mated_in(distance)
            };
        }

        let mut moves = MoveList::new();
        generate_into(pos, &mut moves);
        if moves.is_empty() {
            return mated_in(distance);
        }
        if pos.is_fifty_move_draw() {
            return 0;
        }

        let side = pos.side_to_move();
        let den = enemy_den(side.index());

        // A den entry available here wins outright; no need to evaluate anything.
        for &m in moves.as_slice() {
            if m.to() == den {
                return mate_in(distance + 1);
            }
        }

        let stand_pat = evaluate(pos, side);
        if qply >= self.params.quiescence_max_ply {
            return stand_pat;
        }
        let mut best = stand_pat;
        if stand_pat >= beta {
            return stand_pat;
        }
        if stand_pat > alpha {
            alpha = stand_pat;
        }

        // Captures only from here.
        let mut noisy = MoveList::new();
        for &m in moves.as_slice() {
            if pos.piece_at(m.to()).is_some() {
                noisy.push(m);
            }
        }
        let mut ordered = OrderedMoves::new(pos, noisy, None, &self.heur, ply as usize, None);

        while let Some((m, order_score)) = ordered.next_scored() {
            // Ordering has already run static exchange evaluation and sorted the
            // losing captures into their own band below everything else, so the
            // first one it yields means the rest are losing too.
            if OrderedMoves::is_losing_capture(order_score) {
                break;
            }

            let victim = pos.piece_at(m.to()).expect("noisy move without a victim");
            let victim_value = PIECE_VALUES[victim.rank() as usize];

            // Delta pruning: even winning this piece for free does not reach
            // alpha. Note this must use the victim's *value*, not its rank -- the
            // Python engine once compared a rank (1..8) against a centipawn
            // margin, which collapsed the test into "am I 200 behind?" and then
            // pruned every capture, free material included.
            if stand_pat + victim_value + self.params.delta_margin < alpha {
                continue;
            }

            pos.make(m);
            let score = -self.quiesce(pos, -beta, -alpha, ply, qply + 1);
            pos.unmake();
            if self.stopped {
                return 0;
            }

            if score > best {
                best = score;
            }
            if score >= beta {
                return score;
            }
            if score > alpha {
                alpha = score;
            }
        }

        best
    }
}

