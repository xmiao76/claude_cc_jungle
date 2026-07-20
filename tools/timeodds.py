"""Time-odds self-play: config A at ``--nodes-a`` vs config B at ``--nodes-b``.

Used to price a speedup. If an optimization makes the engine R times faster, in
a fixed time budget it searches R times more nodes, so its real-play strength
gain equals config-vs-itself at a node ratio of R. Example (R = 1.58):

    python -m tools.timeodds --a tuned --b tuned --nodes-a 63000 --nodes-b 40000 --games 120

A's score/Elo is the strength the extra search buys.
"""

from __future__ import annotations

import argparse
import multiprocessing as mp

from tools.strength_harness import elo, parse_config, run_match


def _shard(task):
    a, b, na, nb, shard, games, seed = task
    res = run_match(parse_config(a), parse_config(b), games=games, nodes=na,
                    nodes_b=nb, seed=seed + shard * 997)
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", default="tuned")
    ap.add_argument("--b", default="tuned")
    ap.add_argument("--nodes-a", type=int, required=True)
    ap.add_argument("--nodes-b", type=int, required=True)
    ap.add_argument("--games", type=int, default=120)
    ap.add_argument("--shards", type=int, default=12)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    per = max(2, args.games // args.shards)
    tasks = [(args.a, args.b, args.nodes_a, args.nodes_b, s, per, args.seed)
             for s in range(args.shards)]
    print(f"A={args.a}@{args.nodes_a}  vs  B={args.b}@{args.nodes_b}  "
          f"({args.shards} shards x {per} games)")

    with mp.Pool(args.workers) as pool:
        results = pool.map(_shard, tasks)

    w = sum(r["a_wins"] for r in results)
    loss = sum(r["a_losses"] for r in results)
    d = sum(r["draws"] for r in results)
    n = w + loss + d
    s = (w + 0.5 * d) / n
    print(f"A: +{w} -{loss} ={d}  score={s * 100:.1f}%  Elo={elo(s):+.0f}  games={n}")


if __name__ == "__main__":
    main()
