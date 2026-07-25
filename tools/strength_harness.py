"""Strength-measurement harness for the Jungle AI.

Pits two engine configurations head-to-head in self-play and reports the score,
so any change to the search/evaluation can be proven stronger (or not) against a
control. Also provides a node/depth benchmark on fixed positions.

The engine is deterministic, so variety comes from a handful of *seeded* random
opening plies. Each opening is played twice with the colors swapped, cancelling
first-move advantage.

Results come with a confidence interval and an LOS, because a bare win
percentage is not decidable at small sample sizes: over 20 games one standard
error is roughly 11 points, so "51%" and "no difference" are the same
measurement. Trust the verdict line, not the percentage.

Usage (run from the repo root, headless — no pygame needed):

    # All enhancements vs the original engine, equal time budget, 8 games at once:
    python -m tools.strength_harness selfplay --a strong --b baseline \
        --games 200 --budget 300 --jobs 8

    # A/A sanity check (should be inconclusive around 50%):
    python -m tools.strength_harness selfplay --a strong --b strong --games 20 --budget 200

    # Node / effective-depth benchmark (search: eval + heuristics + clock):
    python -m tools.strength_harness bench --config strong --budget 2000

    # Move-generation benchmark and fingerprint (no eval, no search, no clock):
    python -m tools.strength_harness perft --depth 5
"""

from __future__ import annotations

import argparse
import json
import math
import multiprocessing
import random
import time

from ai.minimax import AIPlayer
from ai.search_config import SearchConfig, baseline_config, strong_config, v1_config
from engine.game_state import GameState
from engine.pieces import Color
from tools.positions import fixed_midgame

_CONFIGS = {
    "strong": strong_config,      # the shipped engine: every enhancement on
    "v1": v1_config,              # strong minus the evaluation rebuild (the control)
    "baseline": baseline_config,  # every enhancement off: the original engine
}


def register_config(name: str, factory) -> None:
    """Make a named configuration available to ``--a`` / ``--b`` / ``--config``."""
    _CONFIGS[name] = factory

_HARD_DIFFICULTY = 2   # iterative deepening (time-controlled) for a fair comparison


def resolve_config(name: str) -> SearchConfig:
    """Map a CLI name to a SearchConfig (raises on unknown name)."""
    if name not in _CONFIGS:
        raise ValueError(f"unknown config {name!r}; choose from {sorted(_CONFIGS)}")
    return _CONFIGS[name]()


def _apply_random_opening(gs: GameState, rng: random.Random, plies: int) -> None:
    """Play *plies* random legal moves to diversify the opening."""
    for _ in range(plies):
        if gs.is_terminal():
            return
        moves = gs.legal_moves()
        if not moves:
            return
        gs.apply_move(rng.choice(moves))


def play_one(cfg_blue: SearchConfig, cfg_black: SearchConfig, *,
             budget_ms: int, max_moves: int,
             opening_seed: int, opening_plies: int) -> Color | None:
    """Play a single game. Returns the winning Color, or None for a draw/timeout."""
    gs = GameState()
    gs.new_game()
    _apply_random_opening(gs, random.Random(opening_seed), opening_plies)

    ai_blue = AIPlayer(Color.BLUE, _HARD_DIFFICULTY, cfg_blue)
    ai_black = AIPlayer(Color.BLACK, _HARD_DIFFICULTY, cfg_black)

    for _ in range(max_moves):
        if gs.is_terminal():
            break
        ai = ai_blue if gs.turn == Color.BLUE else ai_black
        move = ai.get_best_move(gs, time_budget_ms=budget_ms)
        if move is None:
            break
        gs.apply_move(move)

    return gs.get_winner()


def _normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def score_to_elo(score: float) -> float:
    """Convert a score in (0, 1) to an Elo difference.

    Saturates at ±800 for a clean sweep, where the true difference is unbounded.
    """
    if score <= 0.0:
        return -800.0
    if score >= 1.0:
        return 800.0
    return -400.0 * math.log10(1.0 / score - 1.0)


def match_statistics(a_wins: int, b_wins: int, draws: int) -> dict:
    """Turn raw counts into a score, an Elo estimate with a CI, and an LOS.

    The bare win percentage the harness used to print is not decidable at small
    sample sizes: at 20 games one standard error is about 11 points, so a "51%,
    A stronger" verdict is indistinguishable from noise. These are the numbers
    needed to tell a real gain from sampling error.

    * ``a_score``   — (wins + draws/2) / games
    * ``elo``       — Elo difference implied by the score
    * ``elo_lo/hi`` — 95% confidence interval, from the standard error of the
      score (a normal approximation; adequate well before 100 games)
    * ``los``       — likelihood of superiority: P(A is genuinely stronger),
      the standard decisive-games normal approximation
    """
    games = a_wins + b_wins + draws
    if games == 0:
        return {"a_wins": 0, "b_wins": 0, "draws": 0, "games": 0, "a_score": 0.0,
                "elo": 0.0, "elo_lo": 0.0, "elo_hi": 0.0, "los": 0.5,
                "score_stderr": 0.0}

    score = (a_wins + 0.5 * draws) / games

    # Sample variance of the per-game result (1 / 0.5 / 0), then the standard
    # error of their mean.
    variance = (
        a_wins * (1.0 - score) ** 2
        + draws * (0.5 - score) ** 2
        + b_wins * (0.0 - score) ** 2
    ) / games
    stderr = math.sqrt(variance / games) if games > 1 else 0.0

    lo = min(max(score - 1.96 * stderr, 0.0), 1.0)
    hi = min(max(score + 1.96 * stderr, 0.0), 1.0)

    decisive = a_wins + b_wins
    los = 0.5 if decisive == 0 else _normal_cdf((a_wins - b_wins) / math.sqrt(decisive))

    return {
        "a_wins": a_wins,
        "b_wins": b_wins,
        "draws": draws,
        "games": games,
        "a_score": score,
        "score_stderr": stderr,
        "elo": score_to_elo(score),
        "elo_lo": score_to_elo(lo),
        "elo_hi": score_to_elo(hi),
        "los": los,
    }


def _play_task(task: tuple) -> tuple[int, bool, Color | None]:
    """Play one game for a worker. Must be top-level so it can be pickled."""
    (pair, swapped, cfg_first, cfg_second,
     budget_ms, max_moves, opening_seed, opening_plies) = task
    winner = play_one(cfg_first, cfg_second, budget_ms=budget_ms,
                      max_moves=max_moves, opening_seed=opening_seed,
                      opening_plies=opening_plies)
    return pair, swapped, winner


def _tally(results, verbose: bool = False) -> tuple[int, int, int]:
    """Fold game outcomes into (a_wins, b_wins, draws).

    ``swapped`` says whether A played Black in that game, so Blue/Black winners
    map onto A/B accordingly.
    """
    a_wins = b_wins = draws = 0
    for i, (_pair, swapped, winner) in enumerate(results, start=1):
        if winner is None:
            draws += 1
        else:
            a_won = (winner == Color.BLACK) if swapped else (winner == Color.BLUE)
            if a_won:
                a_wins += 1
            else:
                b_wins += 1
        if verbose:
            print(f"  game {i}: A={a_wins} B={b_wins} D={draws}")
    return a_wins, b_wins, draws


def play_match(cfg_a: SearchConfig, cfg_b: SearchConfig, *,
               games: int = 20, budget_ms: int = 300, max_moves: int = 200,
               opening_plies: int = 6, seed: int = 12345,
               jobs: int = 1, verbose: bool = False) -> dict:
    """Play *games* games (rounded down to color-swapped pairs) of A vs B.

    Each opening is played twice with the colors swapped, cancelling first-move
    advantage. Set *jobs* > 1 to run games in parallel — they are independent, and
    a serious match is otherwise an hour-plus of wall clock.

    Returns the dict from :func:`match_statistics`.
    """
    n_pairs = max(1, games // 2)

    tasks = []
    for p in range(n_pairs):
        opening_seed = seed + p
        # A as Blue, then the same opening with the colors swapped.
        tasks.append((p, False, cfg_a, cfg_b, budget_ms, max_moves,
                      opening_seed, opening_plies))
        tasks.append((p, True, cfg_b, cfg_a, budget_ms, max_moves,
                      opening_seed, opening_plies))

    if jobs > 1:
        with multiprocessing.Pool(processes=jobs) as pool:
            results = pool.map(_play_task, tasks)
    else:
        results = [_play_task(t) for t in tasks]

    a_wins, b_wins, draws = _tally(results, verbose=verbose)
    return match_statistics(a_wins, b_wins, draws)


def _fixed_midgame() -> GameState:
    """A reproducible, out-of-book midgame (12 pieces, Blue to move).

    Shared with the test suite via :mod:`tools.positions` so both measure the
    same position, and built through ``Board.place`` so the Zobrist hash is
    correct — the previous inline version wrote the grid directly and left
    ``hash == 0``, which aliased every bench position to the same
    transposition-table key.
    """
    return fixed_midgame()


def _bench_positions() -> list[tuple[str, GameState]]:
    """Return a fixed list of (name, GameState) benchmark positions.

    All positions are out-of-book so the search (not the book) is measured.
    """
    out: list[tuple[str, GameState]] = [("fixed-mid", _fixed_midgame())]
    for s in (1, 2):
        gs = GameState()
        gs.new_game()
        _apply_random_opening(gs, random.Random(100 + s), 12)
        if not gs.is_terminal():
            out.append((f"midgame-{s}", gs))
    return out


def run_bench(cfg: SearchConfig, budget_ms: int) -> None:
    """Run get_best_move on each bench position and print depth/nodes/nps."""
    print(f"{'position':<12} {'depth':>5} {'seldep':>7} {'nodes':>10} {'nps':>9} {'time_s':>7}")
    for name, gs in _bench_positions():
        ai = AIPlayer(gs.turn, _HARD_DIFFICULTY, cfg)
        t0 = time.perf_counter()
        ai.get_best_move(gs.copy(), time_budget_ms=budget_ms)
        dt = time.perf_counter() - t0
        nps = ai._nodes / dt if dt > 0 else 0.0
        print(f"{name:<12} {ai._last_depth:>5} {ai._seldepth:>7} "
              f"{ai._nodes:>10} {nps:>9.0f} {dt:>7.2f}")


def _verdict(res: dict) -> str:
    """Describe the result honestly, including when it is not decidable."""
    if res["elo_lo"] > 0.0:
        return "A is stronger (95% CI excludes parity)"
    if res["elo_hi"] < 0.0:
        return "A is WEAKER (95% CI excludes parity)"
    # ASCII only: this prints to cp1252 consoles on Windows.
    return (f"inconclusive - CI spans parity; "
            f"LOS {res['los'] * 100:.0f}%, need more games")


def _cmd_selfplay(args: argparse.Namespace) -> None:
    cfg_a = resolve_config(args.a)
    cfg_b = resolve_config(args.b)
    print(f"Self-play: A={args.a} vs B={args.b} | "
          f"games={args.games} budget={args.budget}ms "
          f"opening_plies={args.opening_plies} seed={args.seed} jobs={args.jobs}")
    t0 = time.perf_counter()
    res = play_match(cfg_a, cfg_b, games=args.games, budget_ms=args.budget,
                     max_moves=args.max_moves, opening_plies=args.opening_plies,
                     seed=args.seed, jobs=args.jobs, verbose=args.verbose)
    dt = time.perf_counter() - t0

    if args.json:
        print(json.dumps({**res, "a": args.a, "b": args.b,
                          "budget_ms": args.budget, "elapsed_s": round(dt, 1)},
                         indent=2))
        return

    print("-" * 62)
    print(f"A ({args.a}) wins : {res['a_wins']}")
    print(f"B ({args.b}) wins : {res['b_wins']}")
    print(f"draws          : {res['draws']}")
    print(f"games          : {res['games']}")
    print(f"A score        : {res['a_score'] * 100:.1f}% "
          f"+/- {res['score_stderr'] * 100 * 1.96:.1f} (95%)")
    print(f"Elo            : {res['elo']:+.0f} "
          f"[{res['elo_lo']:+.0f}, {res['elo_hi']:+.0f}]")
    print(f"LOS            : {res['los'] * 100:.1f}%")
    print(f"verdict        : {_verdict(res)}")
    print(f"elapsed        : {dt:.1f}s")


def _cmd_bench(args: argparse.Namespace) -> None:
    cfg = resolve_config(args.config)
    print(f"Bench: config={args.config} budget={args.budget}ms")
    run_bench(cfg, args.budget)


def _cmd_perft(args: argparse.Namespace) -> None:
    """Move-generation benchmark and correctness fingerprint.

    Unlike `bench`, this touches no evaluation, no search heuristics and no
    clock, so it isolates move generation and make/unmake.
    """
    from engine.game_state import GameState
    from tools.perft import perft_divide, timed_perft

    gs = GameState()
    gs.new_game()
    print(f"{'depth':>5} {'leaves':>14} {'time_s':>8} {'leaves/s':>12}")
    for depth in range(1, args.depth + 1):
        gs_run = GameState()
        gs_run.new_game()
        leaves, dt = timed_perft(gs_run, depth)
        rate = leaves / dt if dt > 0 else 0.0
        print(f"{depth:>5} {leaves:>14,} {dt:>8.2f} {rate:>12,.0f}")

    if args.divide:
        print(f"\ndivide at depth {args.depth}:")
        for label, count in perft_divide(gs, args.depth):
            print(f"  {label:<14} {count:>12,}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Jungle AI strength harness")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("selfplay", help="A vs B self-play match")
    sp.add_argument("--a", default="strong", help="config for side A")
    sp.add_argument("--b", default="baseline", help="config for side B")
    sp.add_argument("--games", type=int, default=20)
    sp.add_argument("--budget", type=int, default=300, help="per-move ms")
    sp.add_argument("--max-moves", type=int, default=200)
    sp.add_argument("--opening-plies", type=int, default=6)
    sp.add_argument("--seed", type=int, default=12345)
    sp.add_argument("--jobs", type=int, default=1,
                    help="parallel games (they are independent; 1 = serial)")
    sp.add_argument("--json", action="store_true", help="emit machine-readable results")
    sp.add_argument("--verbose", action="store_true")
    sp.set_defaults(func=_cmd_selfplay)

    bp = sub.add_parser("bench", help="node/depth benchmark")
    bp.add_argument("--config", default="strong")
    bp.add_argument("--budget", type=int, default=2000, help="per-position ms")
    bp.set_defaults(func=_cmd_bench)

    pp = sub.add_parser("perft", help="move-generation benchmark and fingerprint")
    pp.add_argument("--depth", type=int, default=4)
    pp.add_argument("--divide", action="store_true",
                    help="also print per-root-move counts, to localise a mismatch")
    pp.set_defaults(func=_cmd_perft)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
