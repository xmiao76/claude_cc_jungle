"""Reproducible self-play strength harness for the Jungle engine.

Two engine configurations play a match under an equal, deterministic per-move
*node* budget (not wall-clock, so results are machine-independent and exactly
reproducible). Each seeded opening is played twice with colors swapped to cancel
first-move bias. Reports score, Elo difference, and a 95% confidence interval.

Because node-limited search is deterministic, `--a X --b X` should score ~50%
(a self-consistency check that the harness is unbiased).

CLI:
    python -m tools.strength_harness --a enhanced --b baseline --games 60 --nodes 5000 --seed 1

Config specs:
    baseline            all enhancements off (the original engine)
    enhanced            all enhancements on
    no:nmp,lmr          enhanced with the listed features OFF (ablation)
    only:pvs,history    baseline with the listed features ON
"""

from __future__ import annotations

import argparse
import math
import random

from ai.minimax import SearchConfig, Searcher
from engine.game_state import DRAW, GameState
from engine.move_generator import generate_moves
from engine.pieces import Color

BLUE = int(Color.BLUE)
BLACK = int(Color.BLACK)

_FEATURES = ("pvs", "nmp", "lmr", "history", "aspiration", "extensions",
             "see", "see_prune", "eval_pst")


def parse_config(spec: str) -> SearchConfig:
    spec = spec.strip()
    if spec == "baseline":
        return SearchConfig.baseline()
    if spec == "enhanced":
        return SearchConfig.enhanced()
    if spec == "tuned":
        return SearchConfig.tuned()
    if spec.startswith("no:"):
        off = {f.strip() for f in spec[3:].split(",") if f.strip()}
        _validate(off)
        return SearchConfig(**{f: (f not in off) for f in _FEATURES})
    if spec.startswith("only:"):
        on = {f.strip() for f in spec[5:].split(",") if f.strip()}
        _validate(on)
        return SearchConfig(**{f: (f in on) for f in _FEATURES})
    raise ValueError(f"unknown config spec: {spec!r}")


def _validate(feats: set[str]) -> None:
    bad = feats - set(_FEATURES)
    if bad:
        raise ValueError(f"unknown feature(s): {sorted(bad)}; valid: {_FEATURES}")


def random_opening(rng: random.Random, plies: int) -> list:
    """A short sequence of random legal moves from the start (diversifies games)."""
    gs = GameState()
    moves = []
    for _ in range(plies):
        legal = generate_moves(gs.board, gs.to_move)
        if not legal or gs.game_over:
            break
        mv = legal[rng.randrange(len(legal))]
        gs.make_move(mv)
        moves.append(mv)
        if gs.game_over:
            moves.pop()          # don't start a game that's already decided
            break
    return moves


def play_game(opening: list, a_is_blue: bool, cfg_a: SearchConfig, cfg_b: SearchConfig,
              nodes_a: int, nodes_b: int, move_cap: int) -> float:
    """Play one game; return A's result: 1.0 win, 0.5 draw, 0.0 loss."""
    gs = GameState()
    for mv in opening:
        gs.make_move(mv)
    searcher_a = Searcher(cfg_a, max_nodes=nodes_a)
    searcher_b = Searcher(cfg_b, max_nodes=nodes_b)
    a_color = BLUE if a_is_blue else BLACK

    plies = 0
    while not gs.game_over and plies < move_cap:
        a_to_move = (gs.to_move == a_color)
        searcher = searcher_a if a_to_move else searcher_b
        mv = searcher.search(gs)
        if mv is None:
            break
        gs.make_move(mv)
        plies += 1

    if gs.result == DRAW or not gs.game_over:
        return 0.5
    return 1.0 if gs.winner() == Color(a_color) else 0.0


def run_match(cfg_a: SearchConfig, cfg_b: SearchConfig, *, games: int, nodes: int,
              seed: int, opening_plies: int = 4, move_cap: int = 250,
              progress=None, nodes_b: int | None = None) -> dict:
    """Run a match and return aggregate counts (from A's perspective).

    ``nodes`` is A's per-move node budget; ``nodes_b`` (default = ``nodes``) is
    B's. Asymmetric budgets simulate a time handicap (time-odds), e.g. to price
    a speedup: give the faster engine proportionally more nodes."""
    nb = nodes if nodes_b is None else nodes_b
    pairs = (games + 1) // 2
    a_wins = a_losses = draws = 0
    played = 0
    for i in range(pairs):
        opening = random_opening(random.Random(seed * 100003 + i), opening_plies)
        for a_is_blue in (True, False):
            if played >= games:
                break
            r = play_game(opening, a_is_blue, cfg_a, cfg_b, nodes, nb, move_cap)
            if r == 1.0:
                a_wins += 1
            elif r == 0.0:
                a_losses += 1
            else:
                draws += 1
            played += 1
            if progress:
                progress(played, games, a_wins, a_losses, draws)
    return {"games": played, "a_wins": a_wins, "a_losses": a_losses, "draws": draws}


def elo(score: float) -> float:
    score = min(max(score, 1e-6), 1 - 1e-6)
    return -400.0 * math.log10((1 - score) / score)


def summarize(res: dict) -> str:
    n = res["games"]
    w, loss, d = res["a_wins"], res["a_losses"], res["draws"]
    score = (w + 0.5 * d) / n if n else 0.0
    se = math.sqrt(max(score * (1 - score) / n, 1e-12)) if n else 0.0
    lo, hi = max(0.0, score - 1.96 * se), min(1.0, score + 1.96 * se)
    return (f"games={n}  A: +{w} -{loss} ={d}  "
            f"score={score * 100:.1f}%  Elo={elo(score):+.0f} "
            f"[{elo(lo):+.0f}, {elo(hi):+.0f}]")


def main() -> None:
    ap = argparse.ArgumentParser(description="Jungle engine self-play strength harness")
    ap.add_argument("--a", default="enhanced", help="config A spec (default: enhanced)")
    ap.add_argument("--b", default="baseline", help="config B spec (default: baseline)")
    ap.add_argument("--games", type=int, default=40)
    ap.add_argument("--nodes", type=int, default=5000, help="per-move node budget")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--opening-plies", type=int, default=4)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    cfg_a, cfg_b = parse_config(args.a), parse_config(args.b)

    def progress(done, total, w, loss, d):
        if not args.quiet:
            print(f"\r  {done}/{total}  +{w} -{loss} ={d}", end="", flush=True)

    res = run_match(cfg_a, cfg_b, games=args.games, nodes=args.nodes, seed=args.seed,
                    opening_plies=args.opening_plies, progress=progress)
    if not args.quiet:
        print()
    print(f"A={args.a}  vs  B={args.b}  @ {args.nodes} nodes/move")
    print(summarize(res))


if __name__ == "__main__":
    main()
